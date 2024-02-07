import click

from sync_validator_keys import sync_validator_keys

@click.group()
def cli() -> None:
    pass

cli.add_command(sync_validator_keys)

if __name__ == "__main__":
    cli()
