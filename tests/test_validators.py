from unittest.mock import MagicMock

import click
import pytest

from validators import validate_db_uri, validate_env_name, validate_eth_address


class TestValidateEthAddress:
    def test_valid_address_lowercase(self):
        ctx = MagicMock()
        param = MagicMock()
        result = validate_eth_address(
            ctx, param, "0x1234567890123456789012345678901234567890"
        )
        # Should return checksum address
        assert result == "0x1234567890123456789012345678901234567890"

    def test_valid_address_checksum(self):
        ctx = MagicMock()
        param = MagicMock()
        # Valid checksum address
        result = validate_eth_address(
            ctx, param, "0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed"
        )
        assert result == "0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed"

    def test_invalid_address_too_short(self):
        ctx = MagicMock()
        param = MagicMock()
        with pytest.raises(click.BadParameter, match="Invalid Ethereum address"):
            validate_eth_address(ctx, param, "0x1234")

    def test_invalid_address_wrong_length(self):
        ctx = MagicMock()
        param = MagicMock()
        with pytest.raises(click.BadParameter, match="Invalid Ethereum address"):
            validate_eth_address(
                ctx, param, "0x123456789012345678901234567890123456789"
            )  # 39 chars

    def test_invalid_address_invalid_chars(self):
        ctx = MagicMock()
        param = MagicMock()
        with pytest.raises(click.BadParameter, match="Invalid Ethereum address"):
            validate_eth_address(
                ctx, param, "0xGGGG567890123456789012345678901234567890"
            )


class TestValidateDbUri:
    def test_valid_postgresql_uri(self):
        ctx = MagicMock()
        param = MagicMock()
        uri = "postgresql://user:pass@localhost/dbname"
        result = validate_db_uri(ctx, param, uri)
        assert result == uri

    def test_valid_postgresql_uri_with_port(self):
        ctx = MagicMock()
        param = MagicMock()
        uri = "postgresql://user:pass@localhost:5432/dbname"
        result = validate_db_uri(ctx, param, uri)
        assert result == uri

    def test_valid_uri_empty_password(self):
        ctx = MagicMock()
        param = MagicMock()
        uri = "postgresql://user:@localhost/dbname"
        result = validate_db_uri(ctx, param, uri)
        assert result == uri

    def test_invalid_uri_missing_protocol(self):
        ctx = MagicMock()
        param = MagicMock()
        with pytest.raises(click.BadParameter, match="Invalid database connection"):
            validate_db_uri(ctx, param, "user:pass@localhost/dbname")

    def test_invalid_uri_missing_database(self):
        ctx = MagicMock()
        param = MagicMock()
        with pytest.raises(click.BadParameter, match="Invalid database connection"):
            validate_db_uri(ctx, param, "postgresql://user:pass@localhost")

    def test_invalid_uri_missing_credentials(self):
        ctx = MagicMock()
        param = MagicMock()
        with pytest.raises(click.BadParameter, match="Invalid database connection"):
            validate_db_uri(ctx, param, "postgresql://localhost/dbname")


class TestValidateEnvName:
    def test_valid_env_variable_exists(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR", "some_value")
        ctx = MagicMock()
        param = MagicMock()
        result = validate_env_name(ctx, param, "TEST_VAR")
        assert result == "TEST_VAR"

    def test_invalid_env_variable_not_set(self, monkeypatch):
        monkeypatch.delenv("NONEXISTENT_VAR", raising=False)
        ctx = MagicMock()
        param = MagicMock()
        with pytest.raises(click.BadParameter, match="Empty environment variable"):
            validate_env_name(ctx, param, "NONEXISTENT_VAR")

    def test_invalid_env_variable_empty(self, monkeypatch):
        monkeypatch.setenv("EMPTY_VAR", "")
        ctx = MagicMock()
        param = MagicMock()
        with pytest.raises(click.BadParameter, match="Empty environment variable"):
            validate_env_name(ctx, param, "EMPTY_VAR")
