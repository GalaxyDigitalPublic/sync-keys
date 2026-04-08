import sys
from pathlib import Path

import yaml

# Add sync_keys to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "sync_keys"))

from sync_validator_keys import _generate_lighthouse_config, _generate_signer_keys_config


DEFAULT_RECIPIENT = "0x1111111111111111111111111111111111111111"
WEB3SIGNER_URL = "http://web3signer:9000"


class TestGenerateLighthouseConfig:
    def test_valid_fee_recipient_is_used(self):
        """When fee_recipient is a valid address, it should be used directly."""
        fee_recipient = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        keys = [("0xpubkey1", fee_recipient)]

        result = yaml.safe_load(
            _generate_lighthouse_config(keys, WEB3SIGNER_URL, DEFAULT_RECIPIENT)
        )

        assert result[0]["suggested_fee_recipient"] == fee_recipient

    def test_none_fee_recipient_falls_back_to_default(self):
        """When fee_recipient is None, the default should be used."""
        keys = [("0xpubkey1", None)]

        result = yaml.safe_load(
            _generate_lighthouse_config(keys, WEB3SIGNER_URL, DEFAULT_RECIPIENT)
        )

        assert result[0]["suggested_fee_recipient"] == DEFAULT_RECIPIENT

    def test_empty_string_fee_recipient_falls_back_to_default(self):
        """When fee_recipient is empty string, the default should be used."""
        keys = [("0xpubkey1", "")]

        result = yaml.safe_load(
            _generate_lighthouse_config(keys, WEB3SIGNER_URL, DEFAULT_RECIPIENT)
        )

        assert result[0]["suggested_fee_recipient"] == DEFAULT_RECIPIENT

    def test_mixed_fee_recipients(self):
        """Keys with valid, None, and empty fee recipients should be handled correctly."""
        valid_recipient = "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        keys = [
            ("0xpubkey1", valid_recipient),
            ("0xpubkey2", None),
            ("0xpubkey3", ""),
        ]

        result = yaml.safe_load(
            _generate_lighthouse_config(keys, WEB3SIGNER_URL, DEFAULT_RECIPIENT)
        )

        assert result[0]["suggested_fee_recipient"] == valid_recipient
        assert result[1]["suggested_fee_recipient"] == DEFAULT_RECIPIENT
        assert result[2]["suggested_fee_recipient"] == DEFAULT_RECIPIENT

    def test_config_structure(self):
        """Generated config should have the correct Lighthouse structure."""
        keys = [("0xpubkey1", None)]

        result = yaml.safe_load(
            _generate_lighthouse_config(keys, WEB3SIGNER_URL, DEFAULT_RECIPIENT)
        )

        entry = result[0]
        assert entry["enabled"] is True
        assert entry["voting_public_key"] == "0xpubkey1"
        assert entry["type"] == "web3signer"
        assert entry["url"] == WEB3SIGNER_URL

    def test_empty_keys_list(self):
        """Empty keys list should produce empty YAML list."""
        result = yaml.safe_load(
            _generate_lighthouse_config([], WEB3SIGNER_URL, DEFAULT_RECIPIENT)
        )

        assert result == []


class TestGenerateSignerKeysConfig:
    def test_extracts_public_keys_from_tuples(self):
        """Should extract only public keys from (pubkey, fee_recipient) tuples."""
        keys = [
            ("0xpubkey1", "0xfee1"),
            ("0xpubkey2", None),
            ("0xpubkey3", ""),
        ]

        result = _generate_signer_keys_config(keys, DEFAULT_RECIPIENT)

        assert '"0xpubkey1"' in result
        assert '"0xpubkey2"' in result
        assert '"0xpubkey3"' in result
        # Should NOT contain fee recipients or tuple representations
        assert "0xfee1" not in result
        assert "(" not in result

    def test_format(self):
        """Output should be valid Teku/Prysm signer keys format."""
        keys = [("0xpubkey1", None)]

        result = _generate_signer_keys_config(keys, DEFAULT_RECIPIENT)

        assert result == 'validators-external-signer-public-keys: ["0xpubkey1"]'

    def test_empty_keys_list(self):
        """Empty keys list should produce empty signer keys array."""
        result = _generate_signer_keys_config([], DEFAULT_RECIPIENT)

        assert result == "validators-external-signer-public-keys: []"
