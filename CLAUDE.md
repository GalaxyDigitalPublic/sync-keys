# CLAUDE.md

> Entry point for Claude Code. See [docs/](docs/) for full documentation.

## Quick Reference

| Aspect | Details |
|--------|---------|
| **Language** | Python 3.9+ |
| **Framework** | Click CLI |
| **Database** | PostgreSQL (psycopg2) |
| **Crypto** | PyCryptodome (AES-EAX) |

## Essential Commands

```bash
# Setup
pip install -e ".[test]"

# Run CLI
sync-keys sync-db --help
sync-keys sync-validator-keys --help
sync-keys sync-web3signer-keys --help

# Tests
pytest
pytest --cov=sync_keys
```

## Key Files

| File | Purpose |
|------|---------|
| `sync_keys/main.py` | CLI entry point |
| `sync_keys/database.py` | PostgreSQL operations |
| `sync_keys/encoder.py` | AES encryption/decryption |
| `sync_keys/sync_db.py` | Keystore import |
| `sync_keys/sync_validator_keys.py` | Validator config generation |
| `sync_keys/sync_web3signer_keys.py` | Web3Signer config generation |

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

## Documentation

| Doc | Purpose |
|-----|---------|
| [docs/AI_CONTEXT.md](docs/AI_CONTEXT.md) | Full AI context |
| [docs/AGENTS.md](docs/AGENTS.md) | Code patterns, prompts |
| [docs/README.md](docs/README.md) | Quick start |
| [docs/troubleshooting.md](docs/troubleshooting.md) | Common issues |
| [docs/architecture/](docs/architecture/) | System design |
