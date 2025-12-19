# AI Pair Programming Guide

> Patterns, prompts, and domain knowledge for AI assistants working with sync-keys.

## Code Patterns in This Codebase

### 1. Click CLI Commands

All commands follow this pattern:

```python
# sync_keys/sync_db.py:20-51
@click.command(help="Synchronizes validator keystores in the database for web3signer")
@click.option(
    "--db-url",
    help="The database connection address.",
    prompt="Enter the database connection string...",
    callback=validate_db_uri,  # Validation callback
)
@click.option(
    "--validator-capacity",
    help="Keys count per validator.",
    type=int,
    default=100,
)
def sync_db(db_url: str, validator_capacity: int, ...) -> None:
    check_db_connection(db_url)
    # Command logic...
```

**Key conventions:**
- Use `callback=` for input validation
- Use `prompt=` for interactive input
- Always call `check_db_connection()` before database operations

### 2. Database Operations

Database class encapsulates all PostgreSQL operations:

```python
# sync_keys/database.py:11-14
class Database:
    def __init__(self, db_url: str, table_name: str = "keys"):
        self.db_url = db_url
        self.table_name = table_name
```

**Key patterns:**
- Context managers for connections (`with _get_db_connection() as conn`)
- `execute_values()` for bulk inserts
- Dynamic column checking for backwards compatibility (see `fetch_public_keys_by_validator_index`)

### 3. Encryption Pattern

AES-EAX encryption with random nonces:

```python
# sync_keys/encoder.py:27-42
class Encoder:
    @cached_property
    def cipher_key(self) -> bytes:
        return get_random_bytes(CIPHER_KEY_LENGTH)  # 32 bytes

    def encrypt(self, data: str):
        cipher = AES.new(self.cipher_key, AES.MODE_EAX)
        encrypted_data = cipher.encrypt(bytes(data, "ascii"))
        return encrypted_data, cipher.nonce  # Return both!
```

**Important:** Each encryption generates a unique nonce - store both encrypted data AND nonce.

### 4. Type Definitions

Use TypedDict for structured data:

```python
# sync_keys/typings.py:40-45
class DatabaseKeyRecord(TypedDict):
    public_key: HexStr
    private_key: str  # Encrypted, base64-encoded
    nonce: str        # Base64-encoded
    validator_index: int
    fee_recipient: Optional[str]
```

### 5. Validation Pattern

Click callbacks for input validation:

```python
# sync_keys/validators.py:13-17
def validate_db_uri(ctx, param, value):
    pattern = re.compile(r".+:\/\/.+:.*@.+\/.+")
    if not pattern.match(value):
        raise click.BadParameter("Invalid database connection string")
    return value
```

---

## Context-Aware Prompt Templates

### Debugging Prompts

**Database connection issues:**
```
Debug this database connection error in sync-keys. The error is: [ERROR]

Context:
- Using psycopg2 with URL parsing in database.py:115-123
- Connection string format: postgresql://user:pass@host/dbname
- Check _get_db_connection() and check_db_connection() functions
```

**Encryption/decryption failures:**
```
Debug this decryption error. The error is: [ERROR]

Context:
- AES-EAX mode in encoder.py
- Nonces are stored as base64 strings
- Check that DECRYPTION_KEY matches the key used during sync-db
- Verify base64 encoding/decoding in utils.py
```

### Testing Prompts

**Add tests for a new function:**
```
Write pytest tests for [FUNCTION_NAME] in sync_keys/[MODULE].py

Follow existing test patterns in tests/:
- Use unittest.mock for database connections
- Use fixtures from conftest.py (mock_cursor, mock_connection, sample_key_records)
- Test both success and error cases
- Name test classes as Test[ClassName] and methods as test_[description]
```

**Test database operations:**
```
Write tests for the Database.[METHOD] method.

Use this mock pattern from tests/test_database.py:
@patch("database._get_db_connection")
def test_method(self, mock_get_conn, mock_cursor):
    mock_get_conn.return_value.__enter__ = MagicMock(return_value=mock_get_conn.return_value)
    mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)
    mock_get_conn.return_value.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_get_conn.return_value.cursor.return_value.__exit__ = MagicMock(return_value=False)
    # Test logic...
```

### Refactoring Prompts

**Add a new CLI option:**
```
Add a new option --[OPTION_NAME] to the [COMMAND] command.

1. Add @click.option decorator in sync_keys/sync_[command].py
2. Add parameter to function signature
3. Add validation callback in validators.py if needed
4. Update tests to cover new option
```

**Add a new database field:**
```
Add a new field [FIELD_NAME] to the keys table.

Files to modify:
1. sync_keys/typings.py - Add to DatabaseKeyRecord TypedDict
2. sync_keys/database.py - Update CREATE TABLE and INSERT statements
3. sync_keys/web3signer.py - Update process_transferred_keypairs()
4. tests/conftest.py - Update sample_key_records fixture
5. tests/test_database.py - Update relevant tests
```

---

## Domain-Specific Knowledge

### Ethereum Validator Key Management

- **BLS keys**: Validators use BLS12-381 signatures
- **Keystores**: JSON files encrypted with user password (EIP-2335 format)
- **Fee recipients**: Ethereum addresses receiving transaction tips

### Web3Signer Integration

Web3Signer expects YAML key files:

```yaml
# Generated by sync-web3signer-keys
type: file-raw
keyType: BLS
privateKey: "0x..."  # Hex-encoded private key
```

### Validator Client Configs

**Lighthouse** (`validator_definitions.yml`):
```yaml
- enabled: true
  voting_public_key: "0x..."
  type: web3signer
  url: "http://web3signer:9000"
  suggested_fee_recipient: "0x..."
```

**Teku/Prysm** (`signer_keys.yml`):
```yaml
validators-external-signer-public-keys: ["0x...", "0x..."]
```

### Validator Index Assignment

Keys are assigned to validators based on capacity:

```python
# sync_keys/web3signer.py:42
validator_index=index // self.validator_capacity
```

With `validator_capacity=100`:
- Keys 0-99 -> validator_index 0
- Keys 100-199 -> validator_index 1
- etc.

### Kubernetes Pod Hostname Pattern

`sync-validator-keys` determines validator index from pod hostname:

```python
# sync_keys/sync_validator_keys.py:64-65
hostname = platform.node().split(".")[0]  # e.g., "validator-0"
index = hostname.split("-")[-1]           # "0"
```

---

## Common Modifications

### Adding Support for a New Validator Client

1. Add config generation function in `sync_validator_keys.py`
2. Add corresponding filename constant
3. Update `sync_validator_keys()` to write new config
4. Add tests

### Changing Database Schema

1. Update `DatabaseKeyRecord` in `typings.py`
2. Update `CREATE TABLE` in `database.py:update_keys()`
3. Update `INSERT INTO` in `database.py:update_keys()`
4. Update `fetch_keys()` to handle new field
5. Consider backwards compatibility with `fetch_public_keys_by_validator_index()` pattern

### Adding New Encryption Algorithm

1. Create new class in `encoder.py` following `Encoder`/`Decoder` pattern
2. Ensure nonce/IV handling is correct
3. Update `web3signer.py` to use new encoder
4. Thorough testing with roundtrip encryption/decryption
