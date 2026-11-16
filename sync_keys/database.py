from typing import List, Optional, Sequence, Tuple
import os
from urllib.parse import parse_qs, urlparse

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

    def count_all_keys(self) -> int:
        """Count every row in the table, ignoring any cluster predicate.

        This is what tells "nothing has been provisioned yet" apart from "this table holds
        keys, but none matched my cluster". The first is legitimate for a signer that serves
        no validators; the second almost always means a wrong cluster id or a keystore URL
        pointing at another namespace's database, and starting empty in that case silently
        stops a signer that is supposed to be signing.

        The keystore directory cannot answer this: it is a tmpfs emptyDir, so it is empty on
        every pod start regardless.
        """
        with _get_db_connection(self.db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql.SQL("SELECT count(*) FROM {table}").format(
                        table=sql.Identifier(self.table_name)
                    )
                )
                return int(cur.fetchone()[0])


def check_db_connection(db_url):
    connection = _get_db_connection(db_url=db_url)
    try:
        cur = connection.cursor()
        cur.execute("SELECT 1")
    except psycopg2.OperationalError as e:
        raise click.ClickException(
            f"Error: failed to connect to the database server with provided URL. Error details: {e}",
        )


DB_AUTH_ENV = "SYNC_KEYS_DB_AUTH"
DB_AUTH_MODES = ("password", "aws-iam", "azure-ad")
AZURE_POSTGRES_SCOPE = "https://ossrdbms-aad.database.windows.net/.default"
# Token modes verify the server (a stolen token is a valid login for ~15 min): verify-full only, CA per cloud.
RDS_CA_BUNDLE = "/etc/ssl/certs/rds-global-bundle.pem"  # baked into the image, see Dockerfile
CA_FILE_ENV = "SYNC_KEYS_DB_CA_FILE"


def _db_auth_mode() -> str:
    mode = os.environ.get(DB_AUTH_ENV, "password").strip().lower()
    if mode not in DB_AUTH_MODES:  # fail closed: a typo must not fall back to a password
        raise ValueError(f"{DB_AUTH_ENV} must be one of {DB_AUTH_MODES}, got {mode!r}")
    return mode


def _token_password(mode: str, host: str, port: int, user: str) -> str:
    """Short-lived database credential from the workload identity (no static password)."""
    if mode == "aws-iam":
        import boto3  # only needed in this mode

        region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
        if not region:
            raise ValueError("aws-iam database auth needs AWS_REGION (or AWS_DEFAULT_REGION)")
        return boto3.client("rds", region_name=region).generate_db_auth_token(
            DBHostname=host, Port=port, DBUsername=user
        )
    from azure.identity import DefaultAzureCredential  # only needed in this mode

    return DefaultAzureCredential().get_token(AZURE_POSTGRES_SCOPE).token


def _get_db_connection(db_url):
    """Connect with the URL's password (default), or, with SYNC_KEYS_DB_AUTH=aws-iam|azure-ad, with a token
    from the pod's cloud identity (RDS IAM / Entra ID). Token modes refuse a password in the URL and plaintext."""
    result = urlparse(db_url)
    mode = _db_auth_mode()
    params = {"database": result.path[1:], "user": result.username, "host": result.hostname, "port": result.port}
    if mode == "password":  # unchanged behaviour
        return psycopg2.connect(password=result.password, **params)
    params.update({k: v[-1] for k, v in parse_qs(result.query).items()})
    if result.password:
        raise ValueError(f"{DB_AUTH_ENV}={mode}: remove the password from the database URL")
    if params.setdefault("sslmode", "verify-full") != "verify-full":
        raise ValueError(f"{DB_AUTH_ENV}={mode} verifies the server: sslmode must be verify-full")
    if "sslrootcert" not in params:
        params["sslrootcert"] = os.environ.get(CA_FILE_ENV) or (RDS_CA_BUNDLE if mode == "aws-iam" else "system")
    if params["sslrootcert"] != "system" and not os.path.isfile(params["sslrootcert"]):
        raise ValueError(f"database CA bundle not found: {params['sslrootcert']} (set {CA_FILE_ENV})")
    params["password"] = _token_password(mode, result.hostname, result.port or 5432, result.username)
    return psycopg2.connect(**params)
