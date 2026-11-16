"""Passwordless database auth (SYNC_KEYS_DB_AUTH): AWS RDS IAM tokens and Azure Entra ID tokens."""

import sys
import types
from unittest.mock import MagicMock, patch

import pytest

import database


@pytest.fixture
def connect():
    with patch("database.psycopg2.connect") as c:
        yield c


def test_default_is_password_from_the_url(connect, monkeypatch):
    monkeypatch.delenv("SYNC_KEYS_DB_AUTH", raising=False)
    database._get_db_connection("postgresql://u:secret@db.example:5432/keys")
    kw = connect.call_args.kwargs
    assert kw["password"] == "secret"
    assert kw["user"] == "u" and kw["host"] == "db.example" and kw["database"] == "keys"
    assert "sslmode" not in kw  # unchanged behaviour for existing deployments


def test_aws_iam_uses_an_rds_token_and_verifies_the_server(
    connect, monkeypatch, tmp_path
):
    ca = tmp_path / "rds.pem"
    ca.write_text("x")
    monkeypatch.setattr(database, "RDS_CA_BUNDLE", str(ca))
    monkeypatch.setenv("SYNC_KEYS_DB_AUTH", "aws-iam")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    rds = MagicMock()
    rds.generate_db_auth_token.return_value = "rds-token"
    fake_boto3 = types.SimpleNamespace(client=MagicMock(return_value=rds))
    with patch.dict(sys.modules, {"boto3": fake_boto3}):
        database._get_db_connection("postgresql://reader@db.example:5432/keys")
    fake_boto3.client.assert_called_once_with("rds", region_name="us-east-1")
    rds.generate_db_auth_token.assert_called_once_with(
        DBHostname="db.example", Port=5432, DBUsername="reader"
    )
    kw = connect.call_args.kwargs
    assert kw["password"] == "rds-token" and kw["sslmode"] == "verify-full"
    assert kw["sslrootcert"] == str(ca)


def test_azure_ad_uses_an_entra_token_and_verifies_the_server(connect, monkeypatch):
    monkeypatch.setenv("SYNC_KEYS_DB_AUTH", "azure-ad")
    credential = MagicMock()
    credential.get_token.return_value = types.SimpleNamespace(token="entra-token")
    fake_identity = types.SimpleNamespace(
        DefaultAzureCredential=MagicMock(return_value=credential)
    )
    with patch.dict(
        sys.modules,
        {"azure": types.ModuleType("azure"), "azure.identity": fake_identity},
    ):
        database._get_db_connection("postgresql://reader@db.example:5432/keys")
    credential.get_token.assert_called_once_with(
        "https://ossrdbms-aad.database.windows.net/.default"
    )
    kw = connect.call_args.kwargs
    assert kw["password"] == "entra-token" and kw["sslmode"] == "verify-full"
    assert kw["sslrootcert"] == "system"


def test_sslrootcert_in_the_url_is_kept(connect, monkeypatch, tmp_path):
    ca = tmp_path / "ca.pem"
    ca.write_text("x")
    monkeypatch.setenv("SYNC_KEYS_DB_AUTH", "aws-iam")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    rds = MagicMock(generate_db_auth_token=MagicMock(return_value="t"))
    with patch.dict(
        sys.modules,
        {"boto3": types.SimpleNamespace(client=MagicMock(return_value=rds))},
    ):
        database._get_db_connection(
            f"postgresql://reader@db.example:5432/keys?sslmode=verify-full&sslrootcert={ca}"
        )
    kw = connect.call_args.kwargs
    assert kw["sslmode"] == "verify-full" and kw["sslrootcert"] == str(ca)


@pytest.mark.parametrize("mode", ["aws-iam", "azure-ad"])
def test_token_modes_refuse_a_password_in_the_url(connect, monkeypatch, mode):
    monkeypatch.setenv("SYNC_KEYS_DB_AUTH", mode)
    with pytest.raises(ValueError, match="password"):
        database._get_db_connection("postgresql://reader:leftover@db.example:5432/keys")
    connect.assert_not_called()


@pytest.mark.parametrize("mode", ["aws-iam", "azure-ad"])
@pytest.mark.parametrize(
    "sslmode", ["disable", "allow", "prefer", "require", "verify-ca"]
)
def test_token_modes_refuse_anything_but_verify_full(
    connect, monkeypatch, mode, sslmode
):
    monkeypatch.setenv("SYNC_KEYS_DB_AUTH", mode)
    with pytest.raises(ValueError, match="verify-full"):
        database._get_db_connection(
            f"postgresql://reader@db.example:5432/keys?sslmode={sslmode}"
        )
    connect.assert_not_called()


def test_aws_iam_refuses_to_run_without_a_ca_bundle(connect, monkeypatch, tmp_path):
    monkeypatch.setenv("SYNC_KEYS_DB_AUTH", "aws-iam")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setattr(database, "RDS_CA_BUNDLE", str(tmp_path / "missing.pem"))
    with pytest.raises(ValueError, match="CA"):
        database._get_db_connection("postgresql://reader@db.example:5432/keys")
    connect.assert_not_called()


def test_ca_file_env_overrides_the_default(connect, monkeypatch, tmp_path):
    ca = tmp_path / "custom.pem"
    ca.write_text("x")
    monkeypatch.setenv("SYNC_KEYS_DB_AUTH", "azure-ad")
    monkeypatch.setenv("SYNC_KEYS_DB_CA_FILE", str(ca))
    cred = MagicMock(get_token=MagicMock(return_value=types.SimpleNamespace(token="t")))
    fake_identity = types.SimpleNamespace(
        DefaultAzureCredential=MagicMock(return_value=cred)
    )
    with patch.dict(
        sys.modules,
        {"azure": types.ModuleType("azure"), "azure.identity": fake_identity},
    ):
        database._get_db_connection("postgresql://reader@db.example:5432/keys")
    assert connect.call_args.kwargs["sslrootcert"] == str(ca)


def test_unknown_mode_fails_closed(connect, monkeypatch):
    monkeypatch.setenv(
        "SYNC_KEYS_DB_AUTH", "aws_iam"
    )  # typo must not fall back to password
    with pytest.raises(ValueError, match="SYNC_KEYS_DB_AUTH"):
        database._get_db_connection("postgresql://u:p@db.example/keys")
    connect.assert_not_called()


def test_aws_iam_needs_a_region(connect, monkeypatch, tmp_path):
    (tmp_path / "rds.pem").write_text("x")
    monkeypatch.setattr(database, "RDS_CA_BUNDLE", str(tmp_path / "rds.pem"))
    monkeypatch.setenv("SYNC_KEYS_DB_AUTH", "aws-iam")
    monkeypatch.delenv("AWS_REGION", raising=False)
    monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)
    with patch.dict(sys.modules, {"boto3": types.SimpleNamespace(client=MagicMock())}):
        with pytest.raises(ValueError, match="AWS_REGION"):
            database._get_db_connection("postgresql://reader@db.example:5432/keys")
    connect.assert_not_called()


def test_default_port_is_5432_for_the_token(connect, monkeypatch, tmp_path):
    (tmp_path / "rds.pem").write_text("x")
    monkeypatch.setattr(database, "RDS_CA_BUNDLE", str(tmp_path / "rds.pem"))
    monkeypatch.setenv("SYNC_KEYS_DB_AUTH", "aws-iam")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")
    rds = MagicMock(generate_db_auth_token=MagicMock(return_value="t"))
    with patch.dict(
        sys.modules,
        {"boto3": types.SimpleNamespace(client=MagicMock(return_value=rds))},
    ):
        database._get_db_connection("postgresql://reader@db.example/keys")
    rds.generate_db_auth_token.assert_called_once_with(
        DBHostname="db.example", Port=5432, DBUsername="reader"
    )


def test_password_mode_ignores_url_query_like_before(connect, monkeypatch):
    monkeypatch.delenv("SYNC_KEYS_DB_AUTH", raising=False)
    database._get_db_connection("postgresql://u:p@db.example:5432/keys?sslmode=require")
    assert "sslmode" not in connect.call_args.kwargs  # byte-for-byte old behaviour


def test_validator_accepts_a_passwordless_url_only_in_token_modes(monkeypatch):
    import click
    from validators import validate_db_uri

    url = "postgresql://reader@db.example:5432/keys"
    monkeypatch.delenv("SYNC_KEYS_DB_AUTH", raising=False)
    with pytest.raises(click.BadParameter):
        validate_db_uri(None, None, url)
    for mode in ("aws-iam", "azure-ad"):
        monkeypatch.setenv("SYNC_KEYS_DB_AUTH", mode)
        assert validate_db_uri(None, None, url) == url
