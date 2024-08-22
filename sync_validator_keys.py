import os
import platform
from os import mkdir
from os.path import exists, join
from typing import List, Tuple, Optional

import click
import yaml

from database import Database, check_db_connection
from utils import is_lists_equal
from validators import validate_db_uri, validate_env_name, validate_eth_address

PUBLIC_KEYS_CSV_FILENAME = "validator_keys.csv"
LIGHTHOUSE_CONFIG_FILENAME = "validator_definitions.yml"
SIGNER_CONFIG_FILENAME = "signer_keys.yml"
SIGNER_PROPOSER_CONFIG_FILENAME = "proposerConfig.json"
WEB3SIGNER_URL_ENV = "WEB3SIGNER_URL"


@click.command(help="Synchronizes validator public keys from the database")
@click.option(
    "--db-url",
    help="The database connection address.",
    required=True,
    callback=validate_db_uri,
)
@click.option(
    "--output-dir",
    help="The folder where validator keys will be saved.",
    required=True,
    type=click.Path(exists=False, file_okay=False, dir_okay=True),
)
@click.option(
    "--web3signer-url-env",
    help="The environment variable with web3signer url.",
    default=WEB3SIGNER_URL_ENV,
    callback=validate_env_name,
)
@click.option(
    "--default-recipient",
    help="The default fee recipient starting with 0x.",
    required=True,
    callback=validate_eth_address,
)
@click.option(
    "--total-validators",
    help="The total number of validators connected to the web3signer.",
    required=True,
    type=click.IntRange(min=1),
)
def sync_validator_keys(
    db_url: str,
    output_dir: str,
    web3signer_url_env: str,
    default_recipient: str,
    total_validators: int,
) -> None:
    """
    The command is run by the init container in validator pods.
    Fetch public keys for a specific validator index and store them in the output_dir
    """
    # The statefulset will number these statefulsetname-n with n being 0 to replicas-1
    hostname = platform.node().split(".")[0]
    index = hostname.split("-")[-1]

    check_db_connection(db_url)

    database = Database(db_url=db_url)
    keys = database.fetch_public_keys()

    public_keys_count = len(keys)
    start_index, end_index = _get_key_indexes(
        public_keys_count=public_keys_count,
        validator_index=int(index),
        total_validators=total_validators,
    )
    if not 0 <= start_index < end_index <= public_keys_count:
        raise click.ClickException("Invalid validator index, this is a bug")

    # get public keys for this validator
    keys = keys[start_index:end_index]
    if not keys:
        raise click.ClickException(
            "Failed to get range of public keys for the validator, this is a bug"
        )

    if not exists(output_dir):
        mkdir(output_dir)

    # check current public keys CSV
    lighthouse_filename = join(output_dir, LIGHTHOUSE_CONFIG_FILENAME)
    if exists(lighthouse_filename):
        with open(lighthouse_filename) as f:
            current_keys = _load_lighthouse_config(f)
        if is_lists_equal(keys, current_keys):
            click.secho(
                "Keys already synced to the last version.\n",
                bold=True,
                fg="green",
            )
            return

    # save lighthouse config
    web3signer_url = os.environ[web3signer_url_env]
    lighthouse_config = _generate_lighthouse_config(
        public_keys_with_recipient=keys,
        web3signer_url=web3signer_url,
        default_recipient=default_recipient,
    )
    with open(join(output_dir, LIGHTHOUSE_CONFIG_FILENAME), "w") as f:
        f.write(lighthouse_config)

    # save teku/prysm config
    signer_keys_config = _generate_signer_keys_config(
        public_keys_with_recipient=keys, default_recipient=default_recipient
    )
    with open(join(output_dir, SIGNER_CONFIG_FILENAME), "w") as f:
        f.write(signer_keys_config)

    click.secho(
        f"The validator now uses {len(keys)} public keys.\n",
        bold=True,
        fg="green",
    )


def _generate_lighthouse_config(
    public_keys_with_recipient: List[Tuple[str, Optional[str]]],
    web3signer_url: str,
    default_recipient: str,
) -> str:
    """
    Generate config for Lighthouse clients
    """
    items = [
        {
            "enabled": True,
            "voting_public_key": public_key,
            "type": "web3signer",
            "url": web3signer_url,
            "suggested_fee_recipient": (
                fee_recipient if fee_recipient is not None else default_recipient
            ),
        }
        for public_key, fee_recipient in public_keys_with_recipient
    ]

    return yaml.dump(items, explicit_start=True)


def _load_lighthouse_config(file) -> List[str]:
    """
    Load config for Lighthouse clients
    """
    try:
        items = yaml.safe_load(file)
        return [item.get("voting_public_key") for item in items]
    except yaml.YAMLError:
        return []


def _generate_signer_keys_config(
    public_keys_with_recipient: List[Tuple[str, Optional[str]]],
    default_recipient: str,
) -> str:
    """
    Generate config for Teku and Prysm clients
    """
    keys = ",".join([f'"{public_key}"' for public_key in public_keys_with_recipient])
    return f"""validators-external-signer-public-keys: [{keys}]"""


def _get_key_indexes(
    public_keys_count: int,
    total_validators: int,
    validator_index: int,
) -> tuple[int, int]:
    keys_per_validator = (public_keys_count - 1) // total_validators + 1
    start_index = keys_per_validator * validator_index
    end_index = min(start_index + keys_per_validator, public_keys_count)
    return start_index, end_index
