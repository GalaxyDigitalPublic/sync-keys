# Developer Guidelines

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

### Type Hints

```python
from typing import List, Optional, Dict
from eth_typing import HexStr

def process_keys(
    keypairs: Dict[HexStr, DBKeyInfo],
    capacity: int = 100,
) -> List[DatabaseKeyRecord]:
    ...
```

Use `TypedDict` for structured dictionaries:

```python
class DatabaseKeyRecord(TypedDict):
    public_key: HexStr
    private_key: str
    nonce: str
    validator_index: int
    fee_recipient: Optional[str]
```

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

### Running Tests

```bash
pytest                           # All tests
pytest -v                        # Verbose
pytest --cov=sync_keys           # With coverage
pytest -x                        # Stop on first failure
pytest -k "test_encrypt"         # Run matching tests
```

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

When commits are generated with AI assistance, include the model in the commit message:

```
AICOAUTH: Claude Opus 4.5
```

Full example:
```
feat: Add custom table name support

Allow users to specify a custom table name for storing validator keys
instead of the default 'keys' table.

AICOAUTH: Claude Opus 4.5
```

### Pull Request Process

1. Create feature branch from `main`
2. Make changes with tests
3. Run tests locally: `pytest`
4. Push and create PR
5. Ensure CI passes
6. Request review

---

## Security Guidelines

### Secrets Handling

- Never log or print private keys
- Use environment variables for sensitive data
- Keystore passwords are prompted interactively, never stored
- `DECRYPTION_KEY` should be stored in secure secrets management

### Code Review Checklist

- [ ] No secrets in code
- [ ] Input validation present
- [ ] SQL injection prevention (parameterized queries)
- [ ] Error messages don't leak sensitive info
- [ ] Tests cover security-relevant code paths

### Cryptographic Operations

- Use established libraries (PyCryptodome)
- Generate random nonces for each encryption
- Use appropriate key lengths (32 bytes for AES-256)
- See `encoder.py` for reference implementation

---

## Adding New Features

### New CLI Command

1. Create `sync_keys/sync_<name>.py`
2. Add Click command with options
3. Import and register in `main.py`:
   ```python
   from sync_<name> import sync_<name>
   cli.add_command(sync_<name>)
   ```
4. Add tests in `tests/test_<name>.py`
5. Update documentation

### New Database Field

1. Update `DatabaseKeyRecord` in `typings.py`
2. Update `CREATE TABLE` in `database.py`
3. Update `INSERT INTO` in `database.py`
4. Update `fetch_keys()` result mapping
5. Consider backwards compatibility
6. Update tests

### New Validator Client Support

1. Add config generation function in `sync_validator_keys.py`
2. Add filename constant
3. Update command to generate new config
4. Test with actual validator client

---

## Documentation

### When to Update Docs

- Adding new commands or options
- Changing database schema
- Modifying environment variables
- Adding new features or workflows

### Doc Locations

| Topic | File |
|-------|------|
| Quick reference | `docs/README.md` |
| Setup instructions | `docs/setup.md` |
| Troubleshooting | `docs/troubleshooting.md` |
| Architecture | `docs/architecture/system-overview.md` |
| AI assistance | `docs/AGENTS.md` |
