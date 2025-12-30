# GitHub Copilot Instructions for sync-keys

## Project Context

sync-keys is a Python CLI tool for managing Ethereum validator keys. It handles:
- Importing encrypted keystores to PostgreSQL
- Generating validator client configs (Lighthouse, Teku, Prysm)
- Generating Web3Signer key files

**Full documentation:** See [docs/](../docs/) folder, especially:
- [docs/AI_CONTEXT.md](../docs/AI_CONTEXT.md) - Full AI context
- [docs/AGENTS.md](../docs/AGENTS.md) - Code patterns and prompts

## Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.9+ |
| CLI | Click |
| Database | PostgreSQL (psycopg2) |
| Crypto | PyCryptodome (AES-EAX) |
| Testing | pytest |

## Commands

```bash
pip install -e ".[test]"
sync-keys sync-db --help
sync-keys sync-validator-keys --help
sync-keys sync-web3signer-keys --help
pytest
```

## Code Patterns

### CLI Commands (Click)

```python
@click.command(help="Description")
@click.option("--db-url", required=True, callback=validate_db_uri)
@click.option("--output-dir", type=click.Path())
def command_name(db_url: str, output_dir: str) -> None:
    check_db_connection(db_url)
    database = Database(db_url=db_url)
    # ... implementation
```

### Database Class

```python
from database import Database

db = Database(db_url="postgresql://...", table_name="keys")
db.update_keys(records)  # Replace all keys
keys = db.fetch_keys()   # Get all keys
public_keys = db.fetch_public_keys_by_validator_index("0")
```

### Encryption

```python
from encoder import Encoder, Decoder

# Encrypt
encoder = Encoder()
encrypted, nonce = encoder.encrypt("secret")
key = encoder.cipher_key_str  # 32-byte AES key, base64

# Decrypt
decoder = Decoder(key)
original = decoder.decrypt(encrypted_b64, nonce_b64)
```

### Type Definitions

```python
from typings import DatabaseKeyRecord

record = DatabaseKeyRecord(
    public_key="0x...",
    private_key="encrypted_base64",
    nonce="nonce_base64",
    validator_index=0,
    fee_recipient="0x..."
)
```

## Testing Patterns

```python
from unittest.mock import MagicMock, patch

@patch("database._get_db_connection")
def test_database_operation(mock_get_conn, mock_cursor):
    mock_get_conn.return_value.__enter__ = MagicMock(return_value=mock_get_conn.return_value)
    mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)
    mock_get_conn.return_value.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_get_conn.return_value.cursor.return_value.__exit__ = MagicMock(return_value=False)
    # Test logic...
```

## Naming Conventions

- Functions: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Private: `_leading_underscore`

## AI-Assisted Commits

When commits are AI-generated, include:
```
AICOAUTH: <model name>
```
