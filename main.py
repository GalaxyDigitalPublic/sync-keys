import click

from sync_validator_keys import sync_validator_keys
from sync_web3signer_keys import sync_web3signer_keys


@click.group()
def cli() -> None:
    pass


cli.add_command(sync_validator_keys)
cli.add_command(sync_web3signer_keys)

if __name__ == "__main__":
    cli()
