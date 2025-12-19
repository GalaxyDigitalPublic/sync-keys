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
        executed_sql = mock_cursor.execute.call_args[0][0]
        assert "DROP TABLE IF EXISTS keys" in executed_sql
        assert "CREATE TABLE keys" in executed_sql

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

        executed_sql = mock_cursor.execute.call_args[0][0]
        assert "DROP TABLE IF EXISTS validator_keys" in executed_sql
        assert "CREATE TABLE validator_keys" in executed_sql
        # Should NOT contain default "keys" table
        assert "DROP TABLE IF EXISTS keys" not in executed_sql

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
        insert_sql = mock_execute_values.call_args[0][1]
        assert "INSERT INTO my_keys" in insert_sql


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
        schema_query = calls[0][0][0]
        assert "table_name='keys'" in schema_query

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
        # Check information_schema query
        schema_query = calls[0][0][0]
        assert "table_name='custom_keys'" in schema_query
        # Check SELECT query
        select_query = calls[1][0][0]
        assert "FROM custom_keys" in select_query

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
        select_query = calls[1][0][0]
        assert "FROM legacy_keys" in select_query
        assert "NULL AS fee_recipient" in select_query


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

        executed_sql = mock_cursor.execute.call_args[0][0]
        assert "from keys" in executed_sql.lower()

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

        executed_sql = mock_cursor.execute.call_args[0][0]
        assert "from signer_keys" in executed_sql.lower()
        assert (
            "from keys" not in executed_sql.lower()
            or "signer_keys" in executed_sql.lower()
        )

    @patch("database._get_db_connection")
    def test_returns_database_key_records(self, mock_get_conn, mock_cursor):
        """fetch_keys should return list of DatabaseKeyRecord."""
        mock_cursor.fetchall.return_value = [
            ("0xpub1", "enc_priv1", "nonce1", "0", "0xfee1"),
            ("0xpub2", "enc_priv2", "nonce2", "1", None),
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
        assert result[0]["fee_recipient"] == "0xfee1"
        assert result[1]["fee_recipient"] is None
