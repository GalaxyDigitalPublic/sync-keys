from typing import List, Tuple, Optional
from urllib.parse import urlparse

import click
import psycopg2
from psycopg2.extras import execute_values

from typings import DatabaseKeyRecord


class Database:
    def __init__(self, db_url: str):
        self.db_url = db_url

    def update_keys(self, keys: List[DatabaseKeyRecord]) -> None:
        """Updates database records to new state."""
        with _get_db_connection(self.db_url) as conn:
            with conn.cursor() as cur:
                # recreate table
                cur.execute(
                    """
                    DROP TABLE IF EXISTS keys;
                    CREATE TABLE keys (
                        public_key TEXT UNIQUE NOT NULL,
                        private_key TEXT UNIQUE NOT NULL,
                        nonce TEXT NOT NULL,
                        validator_index TEXT NOT NULL,
                        fee_recipient TEXT)
                    ;"""
                )

                # insert keys
                execute_values(
                    cur,
                    "INSERT INTO keys (public_key, private_key, nonce, validator_index, fee_recipient) VALUES %s",
                    [
                        (
                            x["public_key"],
                            x["private_key"],
                            x["nonce"],
                            x["validator_index"],
                            x["fee_recipient"],
                        )
                        for x in keys
                    ],
                )

    def fetch_public_keys_by_validator_index(
        self, validator_index: str
    ) -> List[Tuple[str, Optional[str]]]:
        with _get_db_connection(self.db_url) as conn:
            with conn.cursor() as cur:
                # Check if the fee_recipient column exists
                cur.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name='keys' AND column_name='fee_recipient';
                """
                )
                fee_recipient_exists = cur.fetchone() is not None
                if fee_recipient_exists:
                    # If the fee_recipient column exists, include it in the query
                    cur.execute(
                        """
                        SELECT public_key, fee_recipient
                        FROM keys
                        WHERE validator_index = %s;
                    """,
                        (validator_index,),
                    )
                else:
                    # If the fee_recipient column does not exist, query only public_key
                    cur.execute(
                        """
                        SELECT public_key, NULL AS fee_recipient
                        FROM keys
                        WHERE validator_index = %s;
                    """,
                        (validator_index,),
                    )

                rows = cur.fetchall()
                return [(row[0], row[1]) for row in rows]

    def fetch_keys(self) -> List[DatabaseKeyRecord]:
        with _get_db_connection(self.db_url) as conn:
            with conn.cursor() as cur:
                cur.execute("select * from keys")
                rows = cur.fetchall()
                return [
                    DatabaseKeyRecord(
                        public_key=row[0],
                        private_key=row[1],
                        nonce=row[2],
                        validator_index=row[3],
                        fee_recipient=row[4],
                    )
                    for row in rows
                ]


def check_db_connection(db_url):
    connection = _get_db_connection(db_url=db_url)
    try:
        cur = connection.cursor()
        cur.execute("SELECT 1")
    except psycopg2.OperationalError as e:
        raise click.ClickException(
            f"Error: failed to connect to the database server with provided URL. Error details: {e}",
        )


def _get_db_connection(db_url):
    result = urlparse(db_url)
    return psycopg2.connect(
        database=result.path[1:],
        user=result.username,
        password=result.password,
        host=result.hostname,
        port=result.port,
    )
