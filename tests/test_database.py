import pytest
from unittest.mock import MagicMock, patch


from database import Database


class TestDatabaseInit:
    def test_default_table_name(self):
        """Database should use 'keys' as default table name."""
        db = Database(db_url="postgresql://user:pass@localhost/dbname")
        assert db.table_name == "keys"

    def test_custom_table_name(self):
        """Database should accept custom table name."""
        db = Database(
            db_url="postgresql://user:pass@localhost/dbname",
            table_name="custom_keys",
        )
        assert db.table_name == "custom_keys"


class TestUpdateKeys:
    @patch("database.execute_values")
    @patch("database._get_db_connection")
    def test_creates_table_with_default_name(
        self, mock_get_conn, mock_execute_values, mock_cursor
    ):
        """update_keys should CREATE TABLE with default 'keys' name."""
        mock_get_conn.return_value.__enter__ = MagicMock(
            return_value=mock_get_conn.return_value
        )
        mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_conn.return_value.cursor.return_value.__enter__ = MagicMock(
            return_value=mock_cursor
        )
        mock_get_conn.return_value.cursor.return_value.__exit__ = MagicMock(
            return_value=False
        )

        db = Database(db_url="postgresql://user:pass@localhost/dbname")
        db.update_keys(keys=[])

        # Check that the executed SQL contains the default table name
        executed_sql = str(mock_cursor.execute.call_args[0][0]).lower()
        assert "identifier('keys')" in executed_sql
        assert "drop table if exists" in executed_sql
        assert "create table" in executed_sql

    @patch("database.execute_values")
    @patch("database._get_db_connection")
    def test_creates_table_with_custom_name(
        self, mock_get_conn, mock_execute_values, mock_cursor
    ):
        """update_keys should CREATE TABLE with custom table name."""
        mock_get_conn.return_value.__enter__ = MagicMock(
            return_value=mock_get_conn.return_value
        )
        mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_conn.return_value.cursor.return_value.__enter__ = MagicMock(
            return_value=mock_cursor
        )
        mock_get_conn.return_value.cursor.return_value.__exit__ = MagicMock(
            return_value=False
        )

        db = Database(
            db_url="postgresql://user:pass@localhost/dbname",
            table_name="validator_keys",
        )
        db.update_keys(keys=[])

        executed_sql = str(mock_cursor.execute.call_args[0][0]).lower()
        assert "identifier('validator_keys')" in executed_sql
        assert "drop table if exists" in executed_sql
        assert "create table" in executed_sql
        # Should NOT contain default "keys" table
        assert "identifier('keys')" not in executed_sql

    @patch("database.execute_values")
    @patch("database._get_db_connection")
    def test_inserts_to_custom_table(
        self, mock_get_conn, mock_execute_values, mock_cursor, sample_key_records
    ):
        """update_keys should INSERT INTO custom table name."""
        mock_get_conn.return_value.__enter__ = MagicMock(
            return_value=mock_get_conn.return_value
        )
        mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_conn.return_value.cursor.return_value.__enter__ = MagicMock(
            return_value=mock_cursor
        )
        mock_get_conn.return_value.cursor.return_value.__exit__ = MagicMock(
            return_value=False
        )

        db = Database(
            db_url="postgresql://user:pass@localhost/dbname",
            table_name="my_keys",
        )
        db.update_keys(keys=sample_key_records)

        # Check execute_values was called with correct table name
        insert_sql = str(mock_execute_values.call_args[0][1]).lower()
        assert "insert into" in insert_sql
        assert "identifier('my_keys')" in insert_sql


class TestFetchPublicKeysByValidatorIndex:
    @patch("database._get_db_connection")
    def test_queries_default_table(self, mock_get_conn, mock_cursor):
        """fetch_public_keys_by_validator_index should query default 'keys' table."""
        mock_cursor.fetchone.return_value = ("fee_recipient",)  # Column exists
        mock_cursor.fetchall.return_value = [("0xpubkey1", "0xfee1")]

        mock_get_conn.return_value.__enter__ = MagicMock(
            return_value=mock_get_conn.return_value
        )
        mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_conn.return_value.cursor.return_value.__enter__ = MagicMock(
            return_value=mock_cursor
        )
        mock_get_conn.return_value.cursor.return_value.__exit__ = MagicMock(
            return_value=False
        )

        db = Database(db_url="postgresql://user:pass@localhost/dbname")
        db.fetch_public_keys_by_validator_index(validator_index="0")

        # Check the information_schema query uses default table name
        calls = mock_cursor.execute.call_args_list
        # Check that the second call (SELECT query) contains the table name
        select_query = str(calls[1][0][0]).lower()
        assert "identifier('keys')" in select_query

    @patch("database._get_db_connection")
    def test_queries_custom_table(self, mock_get_conn, mock_cursor):
        """fetch_public_keys_by_validator_index should query custom table."""
        mock_cursor.fetchone.return_value = ("fee_recipient",)  # Column exists
        mock_cursor.fetchall.return_value = [("0xpubkey1", "0xfee1")]

        mock_get_conn.return_value.__enter__ = MagicMock(
            return_value=mock_get_conn.return_value
        )
        mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_conn.return_value.cursor.return_value.__enter__ = MagicMock(
            return_value=mock_cursor
        )
        mock_get_conn.return_value.cursor.return_value.__exit__ = MagicMock(
            return_value=False
        )

        db = Database(
            db_url="postgresql://user:pass@localhost/dbname",
            table_name="custom_keys",
        )
        db.fetch_public_keys_by_validator_index(validator_index="0")

        calls = mock_cursor.execute.call_args_list
        # Check information_schema query uses the table name as a parameter
        assert calls[0][0][1] == ("custom_keys",)
        # Check SELECT query contains the identifier
        select_query = str(calls[1][0][0]).lower()
        assert "identifier('custom_keys')" in select_query

    @patch("database._get_db_connection")
    def test_queries_table_without_fee_recipient_column(
        self, mock_get_conn, mock_cursor
    ):
        """Should handle legacy tables without fee_recipient column."""
        mock_cursor.fetchone.return_value = None  # Column doesn't exist
        mock_cursor.fetchall.return_value = [("0xpubkey1", None)]

        mock_get_conn.return_value.__enter__ = MagicMock(
            return_value=mock_get_conn.return_value
        )
        mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_conn.return_value.cursor.return_value.__enter__ = MagicMock(
            return_value=mock_cursor
        )
        mock_get_conn.return_value.cursor.return_value.__exit__ = MagicMock(
            return_value=False
        )

        db = Database(
            db_url="postgresql://user:pass@localhost/dbname",
            table_name="legacy_keys",
        )
        db.fetch_public_keys_by_validator_index(validator_index="0")

        calls = mock_cursor.execute.call_args_list
        select_query = str(calls[1][0][0]).lower()
        assert "identifier('legacy_keys')" in select_query
        assert "null as fee_recipient" in select_query


class TestFetchKeysEmptyClusterId:
    """An empty id previously fell through the truthiness check and returned every cluster."""

    def test_empty_string_is_rejected(self):
        db = Database(
            db_url="postgresql://user:pass@localhost/dbname",
            table_name="validator_keys",
        )
        with pytest.raises(ValueError, match="client_cluster_id was empty"):
            db.fetch_keys(client_cluster_id="")

    def test_whitespace_only_is_rejected(self):
        db = Database(
            db_url="postgresql://user:pass@localhost/dbname",
            table_name="validator_keys",
        )
        with pytest.raises(ValueError, match="client_cluster_id was empty"):
            db.fetch_keys(client_cluster_id="   ")


class TestHasColumn:
    """has_column resolves the table through search_path, then reads pg_attribute."""

    @staticmethod
    def _wire(mock_get_conn, mock_cursor):
        mock_get_conn.return_value.__enter__ = MagicMock(
            return_value=mock_get_conn.return_value
        )
        mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_conn.return_value.cursor.return_value.__enter__ = MagicMock(
            return_value=mock_cursor
        )
        mock_get_conn.return_value.cursor.return_value.__exit__ = MagicMock(
            return_value=False
        )

    @patch("database._get_db_connection")
    def test_true_when_pg_attribute_has_the_column(self, mock_get_conn, mock_cursor):
        self._wire(mock_get_conn, mock_cursor)
        mock_cursor.fetchone.side_effect = [(16384,), (1,)]

        db = Database(
            db_url="postgresql://user:pass@localhost/dbname",
            table_name="validator_keys",
        )
        assert db.has_column("client_cluster_id") is True

        first, second = mock_cursor.execute.call_args_list
        assert "to_regclass" in first[0][0]
        assert first[0][1] == ("validator_keys",)
        # the second query is scoped by the resolved oid, not by table name
        assert "pg_attribute" in second[0][0]
        assert second[0][1] == (16384, "client_cluster_id")

    @patch("database._get_db_connection")
    def test_false_when_column_absent(self, mock_get_conn, mock_cursor):
        self._wire(mock_get_conn, mock_cursor)
        mock_cursor.fetchone.side_effect = [(16384,), None]

        db = Database(db_url="postgresql://user:pass@localhost/dbname")
        assert db.has_column("client_cluster_id") is False

    @patch("database._get_db_connection")
    def test_aborts_when_table_cannot_be_resolved(self, mock_get_conn, mock_cursor):
        """Detection failure must never fall through to an unfiltered read."""
        self._wire(mock_get_conn, mock_cursor)
        mock_cursor.fetchone.side_effect = [(None,)]

        db = Database(
            db_url="postgresql://user:pass@localhost/dbname", table_name="ghost_table"
        )
        with pytest.raises(ValueError, match="could not be resolved"):
            db.has_column("client_cluster_id")


class TestFetchKeysClusterFilter:
    """A shared keystore database must not hand every web3signer every cluster's keys."""

    @staticmethod
    def _wire(mock_get_conn, mock_cursor):
        mock_cursor.fetchall.return_value = []
        mock_get_conn.return_value.__enter__ = MagicMock(
            return_value=mock_get_conn.return_value
        )
        mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_conn.return_value.cursor.return_value.__enter__ = MagicMock(
            return_value=mock_cursor
        )
        mock_get_conn.return_value.cursor.return_value.__exit__ = MagicMock(
            return_value=False
        )

    @patch("database._get_db_connection")
    def test_applies_predicate_and_binds_parameter(self, mock_get_conn, mock_cursor):
        self._wire(mock_get_conn, mock_cursor)
        db = Database(
            db_url="postgresql://user:pass@localhost/dbname",
            table_name="validator_keys",
        )
        db.fetch_keys(client_cluster_id="cluster-apne2-1")

        executed_sql = str(mock_cursor.execute.call_args[0][0]).lower()
        assert "where client_cluster_id = %s" in executed_sql
        # bound as a parameter, never interpolated
        assert mock_cursor.execute.call_args[0][1] == ("cluster-apne2-1",)

    @patch("database._get_db_connection")
    def test_omits_predicate_when_no_cluster_given(self, mock_get_conn, mock_cursor):
        """The legacy agent-managed table has no client_cluster_id column."""
        self._wire(mock_get_conn, mock_cursor)
        db = Database(db_url="postgresql://user:pass@localhost/dbname")
        db.fetch_keys()

        executed_sql = str(mock_cursor.execute.call_args[0][0]).lower()
        assert "where" not in executed_sql
        assert len(mock_cursor.execute.call_args[0]) == 1


class TestFetchKeys:
    @patch("database._get_db_connection")
    def test_queries_default_table(self, mock_get_conn, mock_cursor):
        """fetch_keys should SELECT * FROM default 'keys' table."""
        mock_cursor.fetchall.return_value = []

        mock_get_conn.return_value.__enter__ = MagicMock(
            return_value=mock_get_conn.return_value
        )
        mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_conn.return_value.cursor.return_value.__enter__ = MagicMock(
            return_value=mock_cursor
        )
        mock_get_conn.return_value.cursor.return_value.__exit__ = MagicMock(
            return_value=False
        )

        db = Database(db_url="postgresql://user:pass@localhost/dbname")
        db.fetch_keys()

        executed_sql = str(mock_cursor.execute.call_args[0][0]).lower()
        assert "identifier('keys')" in executed_sql
        assert "select public_key, private_key, nonce from" in executed_sql
        assert "select * from" not in executed_sql

    @patch("database._get_db_connection")
    def test_queries_custom_table(self, mock_get_conn, mock_cursor):
        """fetch_keys should SELECT * FROM custom table."""
        mock_cursor.fetchall.return_value = []

        mock_get_conn.return_value.__enter__ = MagicMock(
            return_value=mock_get_conn.return_value
        )
        mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_conn.return_value.cursor.return_value.__enter__ = MagicMock(
            return_value=mock_cursor
        )
        mock_get_conn.return_value.cursor.return_value.__exit__ = MagicMock(
            return_value=False
        )

        db = Database(
            db_url="postgresql://user:pass@localhost/dbname",
            table_name="signer_keys",
        )
        db.fetch_keys()

        executed_sql = str(mock_cursor.execute.call_args[0][0]).lower()
        assert "identifier('signer_keys')" in executed_sql
        assert "select public_key, private_key, nonce from" in executed_sql
        assert "select * from" not in executed_sql
        # Should NOT contain default "keys" table
        assert "identifier('keys')" not in executed_sql

    @patch("database._get_db_connection")
    def test_returns_database_key_records(self, mock_get_conn, mock_cursor):
        """fetch_keys should return list of Web3SignerKeyRecord.

        Only the three columns web3signer uses are selected, so a row is a 3-tuple. The
        previous 5-column ordinal mapping mis-assigned columns against the key operation
        service's validator_keys table, which has bulk_key_gen_id and batch_id in those
        positions rather than validator_index and fee_recipient.
        """
        mock_cursor.fetchall.return_value = [
            ("0xpub1", "enc_priv1", "nonce1"),
            ("0xpub2", "enc_priv2", "nonce2"),
        ]

        mock_get_conn.return_value.__enter__ = MagicMock(
            return_value=mock_get_conn.return_value
        )
        mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_conn.return_value.cursor.return_value.__enter__ = MagicMock(
            return_value=mock_cursor
        )
        mock_get_conn.return_value.cursor.return_value.__exit__ = MagicMock(
            return_value=False
        )

        db = Database(db_url="postgresql://user:pass@localhost/dbname")
        result = db.fetch_keys()

        assert len(result) == 2
        assert result[0]["public_key"] == "0xpub1"
        assert result[0]["private_key"] == "enc_priv1"
        assert result[0]["nonce"] == "nonce1"
        assert result[1]["public_key"] == "0xpub2"
        assert "validator_index" not in result[0]
        assert "fee_recipient" not in result[0]
