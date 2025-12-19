# AI Context for sync-keys

> Entry point for AI assistants working with this codebase.

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
| `sync-db` | Import keystores to PostgreSQL | `--db-url`, `--validator-capacity`, `--private-keys-dir` |
| `sync-validator-keys` | Generate validator client configs | `--db-url`, `--output-dir`, `--default-recipient` |
| `sync-web3signer-keys` | Generate Web3Signer YAML files | `--db-url`, `--output-dir`, `--decryption-key-env` |

## Key Data Flow

```
keystore*.json  -->  sync-db  -->  PostgreSQL (encrypted)
                                        |
        +-------------------------------+-------------------------------+
        |                                                               |
        v                                                               v
sync-validator-keys                                          sync-web3signer-keys
        |                                                               |
        v                                                               v
Lighthouse/Teku/Prysm configs                                Web3Signer YAML files
```

## Documentation Index

| Document | Purpose | Audience |
|----------|---------|----------|
| [README.md](README.md) | Quick start, API overview | All |
| [AGENTS.md](AGENTS.md) | AI pair programming patterns | AI Assistants |
| [setup.md](setup.md) | Environment setup, IDE config | Developers |
| [developer-guidelines.md](developer-guidelines.md) | Code style, git workflow | Contributors |
| [architecture/system-overview.md](architecture/system-overview.md) | Tech stack, design patterns | Architects |
| [architecture/code-analysis.md](architecture/code-analysis.md) | Code quality, test coverage | Reviewers |
| [troubleshooting.md](troubleshooting.md) | Common issues and fixes | Operators |
| [INDEX.md](INDEX.md) | Role-based navigation | All |

## Critical Files

| File | Purpose |
|------|---------|
| `sync_keys/main.py` | CLI entry point, command registration |
| `sync_keys/database.py` | PostgreSQL operations, `keys` table |
| `sync_keys/encoder.py` | AES-EAX encryption/decryption |
| `sync_keys/sync_db.py` | Keystore import workflow |
| `sync_keys/sync_validator_keys.py` | Validator config generation |
| `sync_keys/sync_web3signer_keys.py` | Web3Signer config generation |
| `sync_keys/typings.py` | Type definitions |

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
