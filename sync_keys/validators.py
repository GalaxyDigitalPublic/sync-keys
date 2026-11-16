import os
import re

import click
from eth_utils import is_address, to_checksum_address


# click callbacks
def validate_eth_address(ctx, param, value):
    return validate_eth_address_prompt(value)


def validate_db_uri(ctx, param, value):
    # user:password@ by default; with SYNC_KEYS_DB_AUTH=aws-iam|azure-ad the URL has no password (token auth)
    token_auth = os.getenv("SYNC_KEYS_DB_AUTH", "password").strip().lower() != "password"
    pattern = re.compile(r".+:\/\/[^@]+@.+\/.+" if token_auth else r".+:\/\/.+:.*@.+\/.+")
    if not pattern.match(value):
        raise click.BadParameter("Invalid database connection string")
    return value


def validate_env_name(ctx, param, value):
    if not os.getenv(value):
        raise click.BadParameter(f"Empty environment variable {value}")
    return value


# click prompts
def validate_eth_address_prompt(value):
    try:
        if is_address(value):
            return to_checksum_address(value)
    except ValueError:
        pass

    raise click.BadParameter("Invalid Ethereum address")
