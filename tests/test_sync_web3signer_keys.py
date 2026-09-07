"""CLI-level tests for sync-web3signer-keys.

The cluster safeguards and the keystore prune live in the command callback rather than in
Database, and the prune deletes files holding private keys, so they are covered here through
the real click entrypoint rather than by calling Database directly.
"""

import sys
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

sys.path.insert(0, str(Path(__file__).parent.parent / "sync_keys"))

from sync_web3signer_keys import sync_web3signer_keys  # noqa: E402

DB_URL = "postgresql://user:pass@localhost:5432/dbname"
ENV = {"DECRYPTION_KEY": "ZGVjcnlwdGlvbi1rZXk="}


def _record(public_key: str, private_key: str) -> dict:
    return {"public_key": public_key, "private_key": private_key, "nonce": "bm9uY2U="}


def _invoke(output_dir, extra_args, *, has_column=True, rows=None):
    """Run the command with Database and Decoder mocked, returning the click result."""
    if rows is None:
        rows = [_record("0xaaa", "111"), _record("0xbbb", "222")]

    with (
        patch("sync_web3signer_keys.check_db_connection"),
        patch("sync_web3signer_keys.Database") as db_cls,
        patch("sync_web3signer_keys.Decoder") as decoder_cls,
    ):
        db = db_cls.return_value
        db.has_column.return_value = has_column
        db.fetch_keys.return_value = rows
        # the encrypted value stands in for its own plaintext, which is a decimal string
        decoder_cls.return_value.decrypt.side_effect = lambda data, nonce: data

        result = CliRunner().invoke(
            sync_web3signer_keys,
            ["--db-url", DB_URL, "--output-dir", str(output_dir), *extra_args],
            env=ENV,
        )
        return result, db


def _keystores(directory) -> set:
    return {p.name for p in Path(directory).glob("*.yaml")}


class TestClusterSafeguards:
    def test_both_selection_flags_is_rejected(self, tmp_path):
        result, db = _invoke(tmp_path, ["--client-cluster-id", "c1", "--all-clusters"])

        assert result.exit_code != 0
        assert "mutually exclusive" in result.output
        db.fetch_keys.assert_not_called()

    def test_omitting_cluster_on_a_scoped_table_fails_closed(self, tmp_path):
        """The table carries client_cluster_id, so an unscoped read would hand this signer
        other clusters' private keys."""
        result, db = _invoke(
            tmp_path, ["--table-name", "validator_keys"], has_column=True
        )

        assert result.exit_code != 0
        assert "client_cluster_id column" in result.output
        db.fetch_keys.assert_not_called()

    def test_omitting_cluster_on_a_legacy_table_is_allowed(self, tmp_path):
        """The default table has no such column, so existing deployments keep working."""
        result, db = _invoke(tmp_path, [], has_column=False)

        assert result.exit_code == 0, result.output
        db.fetch_keys.assert_called_once_with(client_cluster_ids=None)

    def test_all_clusters_overrides_the_guard(self, tmp_path):
        result, db = _invoke(
            tmp_path, ["--table-name", "validator_keys", "--all-clusters"]
        )

        assert result.exit_code == 0, result.output
        db.fetch_keys.assert_called_once_with(client_cluster_ids=None)

    def test_empty_cluster_id_is_rejected(self, tmp_path):
        """An empty value must not read as "no cluster given" and disable scoping."""
        result, db = _invoke(
            tmp_path, ["--table-name", "validator_keys", "--client-cluster-id", ""]
        )

        assert result.exit_code != 0
        db.fetch_keys.assert_not_called()

    def test_several_clusters_can_be_named(self, tmp_path):
        """A signer that legitimately serves more than one cluster names each of them, rather
        than reaching for --all-clusters, so a cluster added to the database later is not
        picked up silently."""
        result, db = _invoke(
            tmp_path,
            [
                "--table-name",
                "validator_keys",
                "--client-cluster-id",
                "us-hoodi-01",
                "--client-cluster-id",
                "qa-01",
            ],
        )

        assert result.exit_code == 0, result.output
        db.fetch_keys.assert_called_once_with(
            client_cluster_ids=("us-hoodi-01", "qa-01")
        )

    def test_named_cluster_is_passed_through(self, tmp_path):
        result, db = _invoke(
            tmp_path,
            ["--table-name", "validator_keys", "--client-cluster-id", "cluster-1"],
        )

        assert result.exit_code == 0, result.output
        db.fetch_keys.assert_called_once_with(client_cluster_ids=("cluster-1",))


class TestKeystoreReconciliation:
    def test_removes_keystores_left_by_a_larger_previous_run(self, tmp_path):
        for i in range(4):
            (tmp_path / f"key_{i}.yaml").write_text("privateKey: '0xold'\n")

        result, _ = _invoke(
            tmp_path, ["--table-name", "validator_keys", "--client-cluster-id", "c1"]
        )

        assert result.exit_code == 0, result.output
        assert _keystores(tmp_path) == {"key_0.yaml", "key_1.yaml"}

    def test_preserves_files_it_did_not_generate(self, tmp_path):
        """Only key_<n>.yaml is this command's to delete. Anything else in the directory
        belongs to something else and must survive."""
        (tmp_path / "keep.yaml").write_text("unrelated: true\n")
        (tmp_path / "web3signer-config.yaml").write_text("unrelated: true\n")
        (tmp_path / "key_9.yaml").write_text("privateKey: '0xstale'\n")

        result, _ = _invoke(
            tmp_path, ["--table-name", "validator_keys", "--client-cluster-id", "c1"]
        )

        assert result.exit_code == 0, result.output
        survivors = _keystores(tmp_path)
        assert "keep.yaml" in survivors
        assert "web3signer-config.yaml" in survivors
        assert "key_9.yaml" not in survivors

    def test_zero_rows_fails_and_leaves_the_directory_untouched(self, tmp_path):
        """Reconciling to empty would stop an already-serving signer from signing."""
        (tmp_path / "key_0.yaml").write_text("privateKey: '0xexisting'\n")

        result, _ = _invoke(
            tmp_path,
            ["--table-name", "validator_keys", "--client-cluster-id", "c1"],
            rows=[],
        )

        assert result.exit_code != 0
        assert "No keys found" in result.output
        assert _keystores(tmp_path) == {"key_0.yaml"}

    def test_allow_no_keys_starts_empty(self, tmp_path):
        """A signer that is deployed but serves no validators must still start. QA's
        euw1/hoodi-2 runs 3/3 ready with zero rows in its keystore table, so failing
        unconditionally on zero rows would stop it from starting at all."""
        result, _ = _invoke(
            tmp_path,
            [
                "--table-name",
                "validator_keys",
                "--client-cluster-id",
                "c1",
                "--allow-no-keys",
            ],
            rows=[],
        )

        assert result.exit_code == 0, result.output
        assert "empty keystore" in result.output
        assert _keystores(tmp_path) == set()

    def test_zero_rows_names_the_opt_out(self, tmp_path):
        """The failure has to tell the operator how a legitimately empty signer proceeds."""
        result, _ = _invoke(
            tmp_path,
            ["--table-name", "validator_keys", "--client-cluster-id", "c1"],
            rows=[],
        )

        assert result.exit_code != 0
        assert "--allow-no-keys" in result.output

    def test_writes_one_keystore_per_key(self, tmp_path):
        result, _ = _invoke(
            tmp_path,
            ["--table-name", "validator_keys", "--client-cluster-id", "c1"],
            rows=[_record("0xa", "1"), _record("0xb", "2"), _record("0xc", "3")],
        )

        assert result.exit_code == 0, result.output
        assert _keystores(tmp_path) == {"key_0.yaml", "key_1.yaml", "key_2.yaml"}
