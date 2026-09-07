import glob
import os
import re
from os import mkdir
from os.path import exists
from typing import List

import click
import yaml
from web3 import Web3

from encoder import Decoder
from database import Database, check_db_connection
from utils import is_lists_equal
from validators import validate_db_uri, validate_env_name

DECRYPTION_KEY_ENV = "DECRYPTION_KEY"

# Only filenames this command generates are eligible for pruning.
_GENERATED_KEYSTORE_RE = re.compile(r"key_\d+\.yaml")


def _validate_cluster_ids(ctx, param, value):
    """Reject empty or whitespace cluster ids.

    With a repeatable option an empty value arrives as ("",), which is truthy, so it would
    otherwise satisfy the "a cluster was named" check and disable scoping -- the exact failure
    the option exists to prevent.
    """
    if value is None:
        return ()
    cleaned = tuple(v.strip() for v in value)
    if any(not v for v in cleaned):
        raise click.BadParameter("cluster id must not be empty", ctx=ctx, param=param)
    return cleaned


@click.command(help="Synchronizes web3signer private keys from the database")
@click.option(
    "--db-url",
    help="The database connection address.",
    required=True,
    callback=validate_db_uri,
)
@click.option(
    "--output-dir",
    help="The folder where web3signer keystores will be saved.",
    required=True,
    type=click.Path(exists=False, file_okay=False, dir_okay=True),
)
@click.option(
    "--decryption-key-env",
    help="The environment variable with the decryption key for private keys in the database.",
    default=DECRYPTION_KEY_ENV,
    callback=validate_env_name,
)
@click.option(
    "--table-name",
    help="Database table name for storing keys.",
    default="keys",
    show_default=True,
)
@click.option(
    "--client-cluster-id",
    "client_cluster_ids",
    multiple=True,
    callback=_validate_cluster_ids,
    help=(
        "Restrict keys to this cluster. Repeat the option for a signer that serves more than "
        "one cluster. Required when the table carries a client_cluster_id column, otherwise "
        "every web3signer sharing the database loads every cluster's private keys. Naming the "
        "clusters explicitly is preferable to --all-clusters, because a cluster added to the "
        "database later is then not picked up silently."
    ),
)
@click.option(
    "--all-clusters",
    is_flag=True,
    default=False,
    help=(
        "Deliberately load every cluster's keys from a cluster-scoped table. Only correct "
        "when one web3signer really does serve every cluster in that table."
    ),
)
@click.option(
    "--allow-no-keys",
    is_flag=True,
    default=False,
    help=(
        "Start with an empty keystore even when the table holds keys for other clusters. "
        "Rarely needed: an entirely empty table is already tolerated without this. Use it "
        "only for a signer that genuinely serves none of the clusters in a populated table."
    ),
)
def sync_web3signer_keys(
    db_url: str,
    output_dir: str,
    decryption_key_env: str,
    table_name: str,
    client_cluster_ids: tuple = (),
    all_clusters: bool = False,
    allow_no_keys: bool = False,
) -> None:
    """
    The command is running by the init container in web3signer pods.
    Fetch and decrypt keys for web3signer and store them as keypairs in the output_dir.
    """
    check_db_connection(db_url)

    database = Database(db_url=db_url, table_name=table_name)

    if client_cluster_ids and all_clusters:
        raise click.ClickException(
            "--client-cluster-id and --all-clusters are mutually exclusive."
        )

    if (
        not client_cluster_ids
        and not all_clusters
        and database.has_column("client_cluster_id")
    ):
        # Fail closed. This table holds more than one cluster's keys, and forgetting the
        # predicate hands this signer private keys belonging to other clusters.
        raise click.ClickException(
            f"Table '{table_name}' has a client_cluster_id column, so it may hold several "
            "clusters' keys. Pass --client-cluster-id <id>, or --all-clusters to override."
        )

    keys_records = database.fetch_keys(client_cluster_ids=client_cluster_ids or None)

    if not keys_records:
        # Distinguish the two ways a read comes back empty, rather than asking an operator to
        # declare which one it is with a flag. A flag has to be toggled in lockstep with the
        # signer's lifecycle: left on it permanently disables this guard for that namespace,
        # and removed at the wrong moment it stops the pod from starting.
        #
        #   table empty        -> nothing is provisioned anywhere yet. Starting with an empty
        #                         keystore is correct, and is what web3signer already does.
        #   table has rows,    -> this database holds keys, just none for the cluster asked
        #   none for my cluster   for. Almost always a wrong cluster id or a keystore URL
        #                         pointing at another namespace, so refuse: reconciling to
        #                         empty would silently stop a signer that should be signing.
        #
        # The keystore directory cannot make this distinction, because it is a tmpfs emptyDir
        # and so is empty on every pod start either way.
        total = database.count_all_keys()

        if total and not allow_no_keys:
            raise click.ClickException(
                f"Table '{table_name}' holds {total} row(s), but none for cluster(s) "
                f"{', '.join(client_cluster_ids) if client_cluster_ids else '<unscoped>'}. "
                "Refusing to reconcile the keystore directory to empty, which would stop "
                "this signer from signing. Check --client-cluster-id and the keystore URL. "
                "Pass --allow-no-keys only if this signer genuinely serves none of them."
            )

        click.secho(
            f"No keys found in '{table_name}'; starting with an empty keystore.\n",
            bold=True,
            fg="yellow",
        )
        return

    # decrypt private keys
    decryption_key = os.environ[decryption_key_env]
    decoder = Decoder(decryption_key)
    private_keys: List[str] = []
    for key_record in keys_records:
        key = decoder.decrypt(data=key_record["private_key"], nonce=key_record["nonce"])
        hex = Web3.to_hex(int(key))
        private_keys.append(f"0x{hex[2:].zfill(64)}")  # pad missing leading zeros

    if not exists(output_dir):
        mkdir(output_dir)

    # check current keys
    current_keys = []
    for filename in glob.glob(os.path.join(output_dir, "*.yaml")):
        with open(os.path.join(os.getcwd(), filename), "r") as f:
            content = yaml.safe_load(f.read())
            current_keys.append(content.get("privateKey"))

    if is_lists_equal(current_keys, private_keys):
        click.secho(
            "Keys already synced to the last version.\n",
            bold=True,
            fg="green",
        )
        return

    # save key files
    for index, private_key in enumerate(private_keys):
        filename = f"key_{index}.yaml"
        with open(os.path.join(output_dir, filename), "w") as f:
            f.write(_generate_key_file(private_key))

    # Remove keystores left behind by a previous, larger key set. web3signer loads every
    # *.yaml in this directory, so without this a run that returns fewer keys than the last
    # one keeps serving the surplus -- which silently defeats --client-cluster-id on an
    # already-deployed signer. Written first, then pruned, so the generated set is never
    # momentarily absent.
    #
    # Only files this command generates are considered. Anything else in the directory is
    # left alone: deleting an unrecognised file would be destructive well beyond this
    # command's remit.
    keep = {f"key_{i}.yaml" for i in range(len(private_keys))}
    for filename in glob.glob(os.path.join(output_dir, "*.yaml")):
        basename = os.path.basename(filename)
        if not _GENERATED_KEYSTORE_RE.fullmatch(basename) or basename in keep:
            continue
        os.remove(filename)
        click.secho(f"Removed stale keystore {basename}.", fg="yellow")

    click.secho(
        f"Web3Signer now uses {len(private_keys)} private keys.\n",
        bold=True,
        fg="green",
    )


def _generate_key_file(private_key: str) -> str:
    item = {
        "type": "file-raw",
        "keyType": "BLS",
        "privateKey": private_key,
    }
    return yaml.dump(item)
