from typing import List, Optional, Sequence, Tuple
from urllib.parse import urlparse

import click
import psycopg2
from psycopg2 import sql
from psycopg2.extras import execute_values

from typings import DatabaseKeyRecord, Web3SignerKeyRecord


class Database:
    def __init__(self, db_url: str, table_name: str = "keys"):
        self.db_url = db_url
        self.table_name = table_name

    def update_keys(self, keys: List[DatabaseKeyRecord]) -> None:
        """Updates database records to new state."""
        with _get_db_connection(self.db_url) as conn:
            with conn.cursor() as cur:
                # recreate table
                cur.execute(
                    sql.SQL("""
                    DROP TABLE IF EXISTS {table};
                    CREATE TABLE {table} (
                        public_key TEXT UNIQUE NOT NULL,
                        private_key TEXT UNIQUE NOT NULL,
                        nonce TEXT NOT NULL,
                        validator_index TEXT NOT NULL,
                        fee_recipient TEXT)
                    ;""").format(table=sql.Identifier(self.table_name))
                )

                # insert keys
                execute_values(
                    cur,
                    sql.SQL(
                        "INSERT INTO {table} (public_key, private_key, nonce, validator_index, fee_recipient) VALUES %s"
                    ).format(table=sql.Identifier(self.table_name)),
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
                    sql.SQL("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name=%s AND column_name='fee_recipient';
                """),
                    (self.table_name,),
                )
                fee_recipient_exists = cur.fetchone() is not None
                if fee_recipient_exists:
                    # If the fee_recipient column exists, include it in the query
                    cur.execute(
                        sql.SQL("""
                        SELECT public_key, fee_recipient
                        FROM {table}
                        WHERE validator_index = %s;
                    """).format(table=sql.Identifier(self.table_name)),
                        (validator_index,),
                    )
                else:
                    # If the fee_recipient column does not exist, query only public_key
                    cur.execute(
                        sql.SQL("""
                        SELECT public_key, NULL AS fee_recipient
                        FROM {table}
                        WHERE validator_index = %s;
                    """).format(table=sql.Identifier(self.table_name)),
                        (validator_index,),
                    )

                rows = cur.fetchall()
                return [(row[0], row[1]) for row in rows]

    def has_column(self, column_name: str) -> bool:
        """Whether the configured table has the named column.

        Used to fail closed: a table carrying client_cluster_id holds more than one
        cluster's keys, so reading it without a predicate must be a deliberate choice.
        """
        if "." in self.table_name:
            # to_regclass would resolve "schema.table", but the queries quote table_name as a
            # single identifier, so detection would succeed and the fetch would then fail with
            # UndefinedTable. Unqualified names only, consistent with the rest of this class.
            raise ValueError(
                f"table_name {self.table_name!r} must be unqualified; set search_path instead "
                "of qualifying the table."
            )

        with _get_db_connection(self.db_url) as conn:
            with conn.cursor() as cur:
                # to_regclass resolves the name through search_path exactly as the SELECT in
                # fetch_keys will, so this inspects the same table the query hits. Matching on
                # information_schema.table_name alone would match a same-named table in any
                # schema and could answer for the wrong one.
                cur.execute("SELECT to_regclass(%s)::oid", (self.table_name,))
                relation = cur.fetchone()[0]  # oid, resolved via search_path
                if relation is None:
                    # Never fall through to an unfiltered read because detection failed.
                    raise ValueError(
                        f"Table {self.table_name!r} could not be resolved on the current "
                        "search_path, so its columns are unknown."
                    )
                cur.execute(
                    "SELECT 1 FROM pg_attribute "
                    "WHERE attrelid = %s AND attname = %s AND attnum > 0 AND NOT attisdropped",
                    (relation, column_name),
                )
                return cur.fetchone() is not None

    def fetch_keys(
        self, client_cluster_ids: Optional[Sequence[str]] = None
    ) -> List[Web3SignerKeyRecord]:
        """Fetch the encrypted keystores web3signer needs.

        Only public_key, private_key and nonce are selected. SELECT * was previously mapped
        by ordinal, which silently mis-assigned columns when pointed at a table with a
        different shape: the key operation service's validator_keys holds
        (public_key, private_key, nonce, bulk_key_gen_id, batch_id, client_cluster_id), so
        ordinals 3 and 4 are not validator_index and fee_recipient. Naming the three columns
        this command actually uses works against both table shapes.

        client_cluster_ids restricts the read to the named clusters. Without it every
        web3signer sharing a database loads every cluster's private keys. It is optional
        because the legacy agent-managed table has no such column, and it accepts several ids
        because one signer can legitimately serve more than one cluster -- naming them
        explicitly means a cluster added to the database later is not picked up silently.
        """
        if client_cluster_ids is not None:
            ids = list(client_cluster_ids)
            if not ids or any(not str(cid).strip() for cid in ids):
                # An empty value previously fell through a truthiness check and returned every
                # cluster's keys -- the exact failure the predicate exists to prevent.
                raise ValueError(
                    "client_cluster_ids contained an empty value. Pass one or more cluster ids, "
                    "or omit the argument entirely to read a table that has no "
                    "client_cluster_id column."
                )

        with _get_db_connection(self.db_url) as conn:
            with conn.cursor() as cur:
                if client_cluster_ids is not None:
                    cur.execute(
                        sql.SQL(
                            "SELECT public_key, private_key, nonce FROM {table} "
                            "WHERE client_cluster_id = ANY(%s)"
                        ).format(table=sql.Identifier(self.table_name)),
                        (list(client_cluster_ids),),
                    )
                else:
                    cur.execute(
                        sql.SQL(
                            "SELECT public_key, private_key, nonce FROM {table}"
                        ).format(table=sql.Identifier(self.table_name))
                    )
                rows = cur.fetchall()
                return [
                    Web3SignerKeyRecord(
                        public_key=row[0],
                        private_key=row[1],
                        nonce=row[2],
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
