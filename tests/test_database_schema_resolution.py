"""Real-PostgreSQL tests for schema-exact column detection.

has_column decides whether sync-web3signer-keys must fail closed, so it has to answer for
the same table fetch_keys will read. Matching information_schema.table_name alone would
match a same-named table in any schema. Mocks cannot catch that, so these run against a
live server.

Set SYNC_KEYS_TEST_DSN to enable, e.g.
  SYNC_KEYS_TEST_DSN=postgresql://postgres:pw@127.0.0.1:55433/t pytest tests -q
"""

import os

import psycopg2
import pytest

import database as database_module
from database import Database

DSN: str = os.getenv("SYNC_KEYS_TEST_DSN", "")
pytestmark = pytest.mark.skipif(not DSN, reason="SYNC_KEYS_TEST_DSN not set")


@pytest.fixture()
def two_schemas():
    conn = psycopg2.connect(DSN)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(
        "DROP SCHEMA IF EXISTS sk_a CASCADE; DROP SCHEMA IF EXISTS sk_b CASCADE;"
    )
    cur.execute("CREATE SCHEMA sk_a; CREATE SCHEMA sk_b;")
    # same table name in both schemas, only one carries client_cluster_id
    cur.execute(
        "CREATE TABLE sk_a.shared (public_key TEXT, private_key TEXT, nonce TEXT, "
        "client_cluster_id TEXT)"
    )
    cur.execute(
        "CREATE TABLE sk_b.shared (public_key TEXT, private_key TEXT, nonce TEXT)"
    )
    yield
    cur.execute(
        "DROP SCHEMA IF EXISTS sk_a CASCADE; DROP SCHEMA IF EXISTS sk_b CASCADE;"
    )
    cur.close()
    conn.close()


def _pin_search_path(monkeypatch, path):
    original = database_module._get_db_connection

    def connect(db_url):
        conn = original(db_url)
        cur = conn.cursor()
        cur.execute(f"SET search_path TO {path}")
        cur.close()
        return conn

    monkeypatch.setattr(database_module, "_get_db_connection", connect)


def test_answers_for_the_first_schema_on_the_path(two_schemas, monkeypatch):
    _pin_search_path(monkeypatch, "sk_a, sk_b")
    assert Database(DSN, table_name="shared").has_column("client_cluster_id") is True


def test_answer_inverts_when_schema_order_flips(two_schemas, monkeypatch):
    """The same table name, the same database, the opposite answer. This is the case
    information_schema.table_name matching would get wrong."""
    _pin_search_path(monkeypatch, "sk_b, sk_a")
    assert Database(DSN, table_name="shared").has_column("client_cluster_id") is False


def test_unresolvable_table_aborts_rather_than_reporting_false(
    two_schemas, monkeypatch
):
    """Detection failure must never fall through to an unfiltered read."""
    _pin_search_path(monkeypatch, "sk_a, sk_b")
    with pytest.raises(ValueError, match="could not be resolved"):
        Database(DSN, table_name="no_such_table").has_column("client_cluster_id")
