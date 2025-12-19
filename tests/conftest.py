import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Add sync_keys to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "sync_keys"))


@pytest.fixture
def mock_cursor():
    """Create a mock database cursor."""
    cursor = MagicMock()
    cursor.fetchall.return_value = []
    cursor.fetchone.return_value = None
    return cursor


@pytest.fixture
def mock_connection(mock_cursor):
    """Create a mock database connection with cursor."""
    conn = MagicMock()
    conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    return conn


@pytest.fixture
def sample_key_records():
    """Sample DatabaseKeyRecord data for testing."""
    return [
        {
            "public_key": "0xabc123",
            "private_key": "encrypted_key_1",
            "nonce": "nonce_1",
            "validator_index": 0,
            "fee_recipient": "0x1234567890123456789012345678901234567890",
        },
        {
            "public_key": "0xdef456",
            "private_key": "encrypted_key_2",
            "nonce": "nonce_2",
            "validator_index": 0,
            "fee_recipient": None,
        },
    ]
