import glob
import os
from os import mkdir
from os.path import exists
from typing import List, Optional

import click
import yaml
from web3 import Web3

from encoder import Decoder
from database import Database, check_db_connection
from utils import is_lists_equal
from validators import validate_db_uri, validate_env_name

DECRYPTION_KEY_ENV = "DECRYPTION_KEY"


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
    help=(
        "Restrict keys to a single cluster. Required when the table carries a "
        "client_cluster_id column, otherwise every web3signer sharing the database loads "
        "every cluster's private keys."
    ),
    default=None,
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
def sync_web3signer_keys(
    db_url: str,
    output_dir: str,
    decryption_key_env: str,
    table_name: str,
    client_cluster_id: Optional[str] = None,
    all_clusters: bool = False,
) -> None:
    """
    The command is running by the init container in web3signer pods.
    Fetch and decrypt keys for web3signer and store them as keypairs in the output_dir.
    """
    check_db_connection(db_url)

    database = Database(db_url=db_url, table_name=table_name)

    if client_cluster_id and all_clusters:
        raise click.ClickException(
            "--client-cluster-id and --all-clusters are mutually exclusive."
        )

    if (
        not client_cluster_id
        and not all_clusters
        and database.has_column("client_cluster_id")
    ):
        # Fail closed. This table holds more than one cluster's keys, and forgetting the
        # predicate hands this signer private keys belonging to other clusters.
        raise click.ClickException(
            f"Table '{table_name}' has a client_cluster_id column, so it may hold several "
            "clusters' keys. Pass --client-cluster-id <id>, or --all-clusters to override."
        )

    keys_records = database.fetch_keys(client_cluster_id=client_cluster_id)

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
    # already-deployed signer. Written first, then pruned, so the directory is never empty.
    for filename in glob.glob(os.path.join(output_dir, "*.yaml")):
        if os.path.basename(filename) not in {
            f"key_{i}.yaml" for i in range(len(private_keys))
        }:
            os.remove(filename)
            click.secho(
                f"Removed stale keystore {os.path.basename(filename)}.", fg="yellow"
            )

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
