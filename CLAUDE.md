# CLAUDE.md

> Complete reference for Claude Code working with the sync-keys codebase.

## Quick Reference

| Aspect | Details |
|--------|---------|
| **Language** | Python 3.9+ |
| **Framework** | Click CLI |
| **Database** | PostgreSQL (psycopg2) |
| **Crypto** | PyCryptodome (AES-EAX), py-ecc (BLS) |
| **Package Manager** | pip / uv |

## Essential Commands

```bash
# Setup
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[test]"

# Run CLI
sync-keys <command>           # Installed entry point
python sync_keys/main.py <command>  # Direct execution

# Testing
pytest                        # Run all tests
pytest --cov=sync_keys        # With coverage
pytest tests/test_encoder.py  # Specific module

# Docker
docker build -t sync-keys .
```

## CLI Commands

| Command | Purpose | Key Options |
|---------|---------|-------------|
| `sync-db` | Import keystores to PostgreSQL | `--db-url`, `--validator-capacity`, `--private-keys-dir`, `--table-name` |
| `sync-validator-keys` | Generate validator client configs | `--db-url`, `--output-dir`, `--default-recipient` |
| `sync-web3signer-keys` | Generate Web3Signer YAML files | `--db-url`, `--output-dir`, `--decryption-key-env` |

## Key Files

| File | Purpose |
|------|---------|
| `sync_keys/main.py` | CLI entry point, command registration |
| `sync_keys/database.py` | PostgreSQL operations, `keys` table |
| `sync_keys/encoder.py` | AES-EAX encryption/decryption |
| `sync_keys/sync_db.py` | Keystore import workflow |
| `sync_keys/sync_validator_keys.py` | Validator config generation |
| `sync_keys/sync_web3signer_keys.py` | Web3Signer config generation |
| `sync_keys/web3signer.py` | Web3SignerManager for key processing |
| `sync_keys/validators.py` | Input validation callbacks |
| `sync_keys/typings.py` | Type definitions |
| `sync_keys/utils.py` | Utility functions |

## Data Flow

```
keystores --> sync-db --> PostgreSQL (encrypted)
                               |
        +----------------------+----------------------+
        |                                             |
   sync-validator-keys                       sync-web3signer-keys
        |                                             |
   Lighthouse/Teku configs                   Web3Signer YAML files
```

## Environment Variables

| Variable | Used By | Purpose |
|----------|---------|---------|
| `DECRYPTION_KEY` | `sync-web3signer-keys` | AES key to decrypt private keys from DB |
| `WEB3SIGNER_URL` | `sync-validator-keys` | URL of Web3Signer service |

## Security Considerations

- Private keys are AES-EAX encrypted before database storage
- `DECRYPTION_KEY` is generated per `sync-db` run - **store securely**
- Database contains encrypted BLS private keys - treat as sensitive
- Keystore passwords are prompted interactively, never stored

---

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

### Adding a New CLI Option

1. Add `@click.option` decorator in `sync_keys/sync_[command].py`
2. Add parameter to function signature
3. Add validation callback in `validators.py` if needed
4. Update tests to cover new option

### Adding a New Database Field

Files to modify:
1. `sync_keys/typings.py` - Add to DatabaseKeyRecord TypedDict
2. `sync_keys/database.py` - Update CREATE TABLE and INSERT statements
3. `sync_keys/web3signer.py` - Update process_transferred_keypairs()
4. `tests/conftest.py` - Update sample_key_records fixture
5. `tests/test_database.py` - Update relevant tests

---

## Testing Standards

### Test Structure

```
tests/
  __init__.py
  conftest.py          # Shared fixtures
  test_database.py     # Tests for database.py
  test_encoder.py      # Tests for encoder.py
  test_validators.py   # Tests for validators.py
  test_utils.py        # Tests for utils.py
```

### Naming Conventions

```python
class TestClassName:
    def test_method_does_expected_thing(self):
        """Method should do expected thing."""
        ...

    def test_method_handles_error_case(self):
        """Method should handle error gracefully."""
        ...
```

### Fixtures

Use fixtures from `conftest.py`:

```python
def test_with_fixtures(mock_cursor, mock_connection, sample_key_records):
    ...
```

### Mocking Database Connections

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

---

## Troubleshooting Guide

### "Password incorrect" when running sync-db

**Symptom:**
```
Unable to decrypt keystore-m_12345.json with the provided password
Password incorrect
```

**Solutions:**
1. Verify the password is correct for the specific keystore
2. Group keystores by password into separate directories
3. Run sync-db multiple times for different password groups

### Database connection failed

**Symptom:**
```
Error: failed to connect to the database server with provided URL
```

**Solutions:**

1. Verify connection string format:
   ```
   postgresql://username:password@hostname:port/database
   ```

2. Test connection directly:
   ```bash
   psql "postgresql://user:pass@localhost/dbname"
   ```

3. Check database is running:
   ```bash
   docker ps | grep postgres
   # or
   systemctl status postgresql
   ```

### DECRYPTION_KEY not set or invalid

**Symptom:**
```
KeyError: 'DECRYPTION_KEY'
# or
Decryption failed / garbled output
```

**Solutions:**

1. Set the environment variable:
   ```bash
   export DECRYPTION_KEY="<key from sync-db output>"
   ```

2. If key was lost, re-run sync-db to generate a new key:
   ```bash
   sync-keys sync-db --db-url "..." --private-keys-dir ./keystores
   # Save the new DECRYPTION_KEY output!
   ```

### No keys found for validator index

**Symptom:**
```
The validator now uses 0 public keys.
```

**Solutions:**

1. Check pod hostname matches expected pattern:
   ```bash
   hostname  # Should be like "validator-0"
   ```

2. Verify keys in database:
   ```sql
   SELECT validator_index, COUNT(*) FROM keys GROUP BY validator_index;
   ```

3. Check validator_capacity used during sync-db matches your deployment

### Docker container can't connect to database

**Symptom:**
```
psycopg2.OperationalError: could not connect to server
```

**Solutions:**

1. Use host's IP or Docker network DNS:
   ```bash
   # Use host.docker.internal on Docker Desktop
   docker run sync-keys sync-db \
     --db-url "postgresql://user:pass@host.docker.internal:5432/db" ...

   # Or use Docker network
   docker run --network my-network sync-keys sync-db \
     --db-url "postgresql://user:pass@postgres:5432/db" ...
   ```

2. For Kubernetes, use service DNS:
   ```
   postgresql://user:pass@postgres-service.namespace.svc.cluster.local:5432/db
   ```

### Debug Commands

**Verify database contents:**
```sql
-- Connect to database
psql "postgresql://user:pass@localhost/dbname"

-- Check table exists
\dt keys

-- Count keys
SELECT COUNT(*) FROM keys;

-- Check validator distribution
SELECT validator_index, COUNT(*) FROM keys GROUP BY validator_index ORDER BY validator_index;

-- Sample records
SELECT public_key, validator_index, fee_recipient FROM keys LIMIT 5;
```

**Check environment variables:**
```bash
env | grep -E 'DECRYPTION_KEY|WEB3SIGNER_URL'
```

**Verify keystore files:**
```bash
# Count keystores
find ./keystores -name "keystore*.json" | wc -l

# Check file format
cat ./keystores/keystore-m_12345.json | python -m json.tool
```

---

## Architecture

### Tech Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Runtime** | Python 3.9+ | Core application |
| **CLI Framework** | Click | Command-line interface |
| **Database** | PostgreSQL | Key storage |
| **DB Driver** | psycopg2 | PostgreSQL client |
| **Cryptography** | PyCryptodome | AES-EAX encryption |
| **Ethereum** | py-ecc, eth-utils | BLS signatures, address validation |
| **Keystores** | ethstaker-deposit | Keystore decryption (EIP-2335) |
| **Config** | PyYAML | YAML file generation |
| **Container** | Docker | Deployment |

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           IMPORT PHASE                                   │
│  ┌─────────────┐    ┌──────────────┐    ┌───────────────────────────┐  │
│  │  Keystores  │───▶│   sync-db    │───▶│      PostgreSQL           │  │
│  │  (JSON)     │    │              │    │  ┌─────────────────────┐  │  │
│  └─────────────┘    │  - Decrypt   │    │  │    keys table       │  │  │
│                     │  - Re-encrypt│    │  │  - public_key       │  │  │
│                     │  - Assign    │    │  │  - private_key (enc)│  │  │
│                     │    indices   │    │  │  - nonce            │  │  │
│                     └──────────────┘    │  │  - validator_index  │  │  │
│                            │            │  │  - fee_recipient    │  │  │
│                            ▼            │  └─────────────────────┘  │  │
│                     DECRYPTION_KEY      └───────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐   ┌─────────────────────┐   ┌─────────────────────┐
│ VALIDATOR PODS  │   │   WEB3SIGNER PODS   │   │   WEB3SIGNER PODS   │
│                 │   │                     │   │                     │
│ sync-validator- │   │ sync-web3signer-    │   │ sync-web3signer-    │
│ keys            │   │ keys                │   │ keys                │
│      │          │   │       │             │   │       │             │
│      ▼          │   │       ▼             │   │       ▼             │
│ Lighthouse/Teku │   │  Web3Signer YAML    │   │  Web3Signer YAML    │
│ configs         │   │  key files          │   │  key files          │
└─────────────────┘   └─────────────────────┘   └─────────────────────┘
```

### Design Patterns

**Command Pattern (Click CLI):**
Each command is a self-contained unit with its own options and logic.

**Repository Pattern (Database Class):**
`Database` class encapsulates all data access.

**Strategy Pattern (Encryption):**
Separate `Encoder` and `Decoder` classes with consistent interface.

### Module Dependencies

```
main.py
  ├── sync_db.py
  │     ├── database.py
  │     ├── validators.py
  │     ├── web3signer.py ─── encoder.py ─── utils.py
  │     └── typings.py
  │
  ├── sync_validator_keys.py
  │     ├── database.py
  │     ├── validators.py
  │     └── utils.py
  │
  └── sync_web3signer_keys.py
        ├── database.py
        ├── encoder.py
        ├── validators.py
        └── utils.py
```

---

## Code Style

### Python Standards

- **Python version**: 3.9+ compatible
- **Style guide**: PEP 8
- **Type hints**: Use throughout (see `typings.py` for examples)
- **Docstrings**: Use for public functions and classes

### Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Functions | snake_case | `fetch_public_keys_by_validator_index` |
| Classes | PascalCase | `Web3SignerManager` |
| Constants | UPPER_SNAKE_CASE | `DECRYPTION_KEY_ENV` |
| Private functions | Leading underscore | `_get_db_connection` |

---

## Git Workflow

### Branch Naming

```
feature/add-new-validator-client
bugfix/fix-decryption-error
docs/update-readme
refactor/simplify-database-class
```

### Commit Messages

Format: `<type>: <description>`

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `refactor`: Code refactoring
- `test`: Adding/updating tests
- `chore`: Maintenance tasks

Examples:
```
feat: Add support for Lodestar validator client
fix: Handle missing fee_recipient column in legacy databases
docs: Update troubleshooting guide
test: Add tests for encryption roundtrip
```

### AI-Generated Commits

When commits are generated with AI assistance, include the model:

```
AICOAUTH: Claude Opus 4.5
```

---

## Known Issues and Improvements

### Security Concerns

**SQL Injection (Medium):**
- **Location**: `database.py:21-31`, `database.py:55-82`, `database.py:90`
- **Issue**: Table names are interpolated directly into SQL strings using f-strings
- **Mitigation**: `table_name` has a default value and is set at initialization, not from user input
- **Recommendation**: Use parameterized SQL with `psycopg2.sql.Identifier()`

**Broad Exception Handling (Low):**
- **Location**: `sync_db.py:87-97`, `sync_db.py:133-143`
- **Issue**: Catching bare `Exception` hides specific errors
- **Recommendation**: Catch specific exceptions from the ethstaker-deposit library

### Test Coverage

- **Well tested**: Core utilities, database operations, encryption
- **Gaps**: CLI commands, Web3SignerManager
- **Recommendation**: Add CLI tests using Click's CliRunner

### Code Quality Issues

**Duplicate Keystore Decryption Logic:**
- **Location**: `sync_db.py:78-102` and `sync_db.py:124-148`
- **Recommendation**: Extract to helper function

**Missing Type Hints:**
- **Location**: `database.py:104`, `database.py:115`
- **Recommendation**: Add type hints for consistency
