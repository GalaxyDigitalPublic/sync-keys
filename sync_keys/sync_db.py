import os
import sys
import math

from typing import Dict

import click
import glob
from eth_typing import HexStr
from eth_utils import is_address

from database import Database, check_db_connection
from validators import validate_db_uri
from web3signer import Web3SignerManager
from typings import DBKeyInfo

from ethstaker_deposit.key_handling.keystore import Keystore


@click.command(help="Synchronizes validator keystores in the database for web3signer")
@click.option(
    "--db-url",
    help="The database connection address.",
    prompt="Enter the database connection string, ex. 'postgresql://username:pass@hostname/dbname'",
    callback=validate_db_uri,
)
@click.option(
    "--validator-capacity",
    help="Keys count per validator.",
    prompt="Enter keys count per validator",
    type=int,
    default=100,
)
@click.option(
    "--private-keys-dir",
    help="The folder with private keys.",
    prompt="Enter the folder holding keystore-m files",
    type=click.Path(exists=False, file_okay=False, dir_okay=True),
)
@click.option(
    "--table-name",
    help="Database table name for storing keys.",
    default="keys",
    show_default=True,
)
def sync_db(
    db_url: str,
    validator_capacity: int,
    private_keys_dir: str,
    table_name: str,
) -> None:
    check_db_connection(db_url)

    web3signer = Web3SignerManager(
        validator_capacity=validator_capacity,
    )

    database = Database(
        db_url=db_url,
        table_name=table_name,
    )

    keypairs: Dict[HexStr, DBKeyInfo] = dict()

    click.secho("Decrypting private keys...", bold=True)

    # Top-level dir, no specific fee recipient
    fee_recipient = None
    private_keys_dir = os.path.expanduser(private_keys_dir)
    keyfiles = glob.glob(os.path.join(private_keys_dir, "keystore*.json"))
    if keyfiles:
        decrypt_key = click.prompt(
            f"Enter the password to decrypt validators private keys in {private_keys_dir}",
            type=click.STRING,
            hide_input=True,
        )

        with click.progressbar(
            length=len(keyfiles),
            label="Decrypting private keys:\t\t",
            show_percent=False,
            show_pos=True,
        ) as bar:
            for filename in keyfiles:
                keystore = Keystore.from_file(filename)

                try:
                    secret_bytes = keystore.decrypt(decrypt_key)
                except Exception:
                    click.secho(
                        f"Unable to decrypt {filename} with the provided password",
                        bold=True,
                        err=True,
                        fg="red",
                    )

                    sys.exit("Password incorrect")

                keypairs["0x" + keystore.pubkey] = DBKeyInfo(
                    int.from_bytes(secret_bytes, "big"), fee_recipient
                )
                bar.update(1)

    # Look for directories that encode a specific fee recipient
    for root, dirs, files in os.walk(private_keys_dir):
        for dir_name in dirs:
            if dir_name.startswith("0x"):
                try:
                    if is_address(dir_name):
                        fee_recipient = dir_name
                    else:
                        continue
                except ValueError:
                    continue
                dir_path = os.path.join(root, dir_name)
                keyfiles = glob.glob(os.path.join(dir_path, "keystore*.json"))
                if keyfiles:
                    decrypt_key = click.prompt(
                        f"Enter the password to decrypt validators private keys in {dir_path}",
                        type=click.STRING,
                        hide_input=True,
                    )

                    with click.progressbar(
                        length=len(keyfiles),
                        label="Decrypting private keys:\t\t",
                        show_percent=False,
                        show_pos=True,
                    ) as bar:
                        for filename in keyfiles:
                            keystore = Keystore.from_file(filename)

                            try:
                                secret_bytes = keystore.decrypt(decrypt_key)
                            except Exception:
                                click.secho(
                                    f"Unable to decrypt {filename} with the provided password",
                                    bold=True,
                                    err=True,
                                    fg="red",
                                )

                                sys.exit("Password incorrect")

                            keypairs["0x" + keystore.pubkey] = DBKeyInfo(
                                int.from_bytes(secret_bytes, "big"), fee_recipient
                            )
                            bar.update(1)

    click.confirm(
        f"Found {len(keypairs)} key pairs, apply changes to the database?",
        default=True,
        abort=True,
    )

    keys = web3signer.process_transferred_keypairs(keypairs)

    validators_count = math.ceil(len(keypairs) / validator_capacity)

    database.update_keys(keys=keys)

    click.secho(
        f"The database contains {len(keypairs)} validator keys.\n"
        f"Please upgrade the 'validators' helm chart with 'validatorsCount' set to {validators_count}\n"
        f"Set 'DECRYPTION_KEY' env to '{web3signer.encoder.cipher_key_str}'",
        bold=True,
        fg="green",
    )
