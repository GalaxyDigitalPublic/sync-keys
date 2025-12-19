# Environment Setup

## Prerequisites

- Python 3.9+ (tested with 3.12, 3.13)
- PostgreSQL database
- Git (for ethstaker-deposit dependency)

## Local Development Setup

### 1. Clone and Create Virtual Environment

```bash
git clone https://github.com/CryptoManufaktur-io/sync-keys.git
cd sync-keys

python3 -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or: .venv\Scripts\activate  # Windows
```

### 2. Install Dependencies

```bash
# Development install with test dependencies
pip install -e ".[test]"

# Or production only
pip install -e .
```

### 3. Verify Installation

```bash
sync-keys --help
```

---

## PostgreSQL Setup

### Local PostgreSQL

```bash
# macOS (Homebrew)
brew install postgresql@15
brew services start postgresql@15

# Create database
createdb sync_keys_dev
```

### Docker PostgreSQL

```bash
docker run -d \
  --name sync-keys-postgres \
  -e POSTGRES_USER=synckeys \
  -e POSTGRES_PASSWORD=secret \
  -e POSTGRES_DB=keys \
  -p 5432:5432 \
  postgres:15

# Connection string
# postgresql://synckeys:secret@localhost:5432/keys
```

---

## IDE Configuration

### VS Code

`.vscode/settings.json`:
```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
  "python.testing.pytestEnabled": true,
  "python.testing.pytestArgs": ["tests"],
  "python.linting.enabled": true,
  "python.linting.flake8Enabled": true,
  "editor.formatOnSave": true,
  "python.formatting.provider": "black"
}
```

`.vscode/launch.json`:
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "sync-db",
      "type": "python",
      "request": "launch",
      "module": "sync_keys.main",
      "args": ["sync-db", "--help"],
      "cwd": "${workspaceFolder}",
      "env": {}
    },
    {
      "name": "pytest",
      "type": "python",
      "request": "launch",
      "module": "pytest",
      "args": ["-v", "tests/"],
      "cwd": "${workspaceFolder}"
    }
  ]
}
```

### PyCharm

1. Open project directory
2. Configure interpreter: `File > Settings > Project > Python Interpreter`
3. Select `.venv/bin/python`
4. Enable pytest: `File > Settings > Tools > Python Integrated Tools > Testing: pytest`

---

## Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=sync_keys --cov-report=html

# Specific test file
pytest tests/test_encoder.py -v

# Specific test class
pytest tests/test_database.py::TestUpdateKeys -v

# Watch mode (requires pytest-watch)
pip install pytest-watch
ptw
```

---

## Docker Build

```bash
# Build image
docker build -t sync-keys .

# Run commands
docker run --rm sync-keys sync-db --help

# With mounted keystores
docker run --rm \
  -v /path/to/keystores:/keystores:ro \
  sync-keys sync-db \
  --db-url "postgresql://user:pass@host/db" \
  --private-keys-dir /keystores
```

---

## Regenerating requirements.txt

```bash
pip install pip-tools
pip-compile --no-annotate pyproject.toml -o requirements.txt
```

---

## Common Development Tasks

### Adding a Dependency

1. Add to `pyproject.toml` under `[project.dependencies]`
2. Regenerate `requirements.txt`:
   ```bash
   pip-compile --no-annotate pyproject.toml
   ```
3. Install: `pip install -e ".[test]"`

### Running from Source

```bash
# Direct execution
python sync_keys/main.py sync-db --help

# Or with installed entry point
sync-keys sync-db --help
```

### Environment Variables for Testing

```bash
export DECRYPTION_KEY="test-key-base64"
export WEB3SIGNER_URL="http://localhost:9000"
```
