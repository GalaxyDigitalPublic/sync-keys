# System Architecture Overview

## Tech Stack

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

## High-Level Architecture

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

## Design Patterns

### Command Pattern (Click CLI)

Each command is a self-contained unit with its own options and logic:

```python
@click.command(help="...")
@click.option("--db-url", ...)
@click.option("--output-dir", ...)
def sync_validator_keys(db_url, output_dir, ...):
    # Command logic
```

Commands are registered in `main.py`:

```python
cli.add_command(sync_validator_keys)
cli.add_command(sync_web3signer_keys)
cli.add_command(sync_db)
```

### Repository Pattern (Database Class)

`Database` class encapsulates all data access:

```python
class Database:
    def __init__(self, db_url: str, table_name: str = "keys"):
        ...

    def update_keys(self, keys: List[DatabaseKeyRecord]) -> None:
        # Insert/update logic

    def fetch_keys(self) -> List[DatabaseKeyRecord]:
        # Read logic

    def fetch_public_keys_by_validator_index(self, index: str) -> List[Tuple]:
        # Filtered read logic
```

### Strategy Pattern (Encryption)

Separate `Encoder` and `Decoder` classes with consistent interface:

```python
class Encoder:
    def encrypt(self, data: str) -> Tuple[bytes, bytes]:
        ...

class Decoder:
    def decrypt(self, data: str, nonce: str) -> str:
        ...
```

## Module Dependencies

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

## Data Flow Details

### sync-db Flow

1. **Input**: Directory of `keystore*.json` files
2. **Password prompt**: Interactive, per directory
3. **Keystore decryption**: Using ethstaker-deposit library
4. **Fee recipient detection**: From subdirectory names (0x addresses)
5. **Validator index assignment**: Based on capacity (keys/validator)
6. **AES encryption**: New random key, unique nonce per key
7. **Database storage**: DROP TABLE + CREATE + INSERT
8. **Output**: `DECRYPTION_KEY` for later use

### sync-validator-keys Flow

1. **Input**: Pod hostname (determines validator index)
2. **Database query**: Fetch public keys for index
3. **Config generation**: Lighthouse YAML, Teku/Prysm format
4. **Idempotency check**: Skip if keys unchanged
5. **Output**: Config files in output directory

### sync-web3signer-keys Flow

1. **Input**: `DECRYPTION_KEY` environment variable
2. **Database query**: Fetch all encrypted keys
3. **Decryption**: AES-EAX with stored nonces
4. **Format conversion**: Hex-encode with zero-padding
5. **Idempotency check**: Skip if keys unchanged
6. **Output**: YAML key files for Web3Signer

## Security Architecture

### Encryption at Rest

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│   Keystore       │     │    AES-EAX       │     │   PostgreSQL     │
│   Password       │────▶│   Encryption     │────▶│   (encrypted)    │
│   (user input)   │     │   (random key)   │     │                  │
└──────────────────┘     └──────────────────┘     └──────────────────┘
                                  │
                                  ▼
                         DECRYPTION_KEY
                         (must be stored securely)
```

### Key Derivation

- Original keystore password: Known only to user, used once during import
- AES key: Randomly generated 32 bytes per `sync-db` run
- Nonces: Unique per encrypted key (AES-EAX requirement)

### Access Control

| Component | Secret Required | How Provided |
|-----------|-----------------|--------------|
| sync-db | Keystore password | Interactive prompt |
| sync-validator-keys | Database URL | CLI option |
| sync-web3signer-keys | Database URL + DECRYPTION_KEY | CLI + env var |

## Kubernetes Integration

### Pod Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        StatefulSet                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │validator-0  │  │validator-1  │  │validator-2  │  ...        │
│  │             │  │             │  │             │             │
│  │ Init:       │  │ Init:       │  │ Init:       │             │
│  │ sync-       │  │ sync-       │  │ sync-       │             │
│  │ validator-  │  │ validator-  │  │ validator-  │             │
│  │ keys        │  │ keys        │  │ keys        │             │
│  │             │  │             │  │             │             │
│  │ Container:  │  │ Container:  │  │ Container:  │             │
│  │ Lighthouse/ │  │ Lighthouse/ │  │ Lighthouse/ │             │
│  │ Teku/Prysm  │  │ Teku/Prysm  │  │ Teku/Prysm  │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
└─────────────────────────────────────────────────────────────────┘
```

### Validator Index Assignment

Derived from pod hostname in StatefulSet:
- `validator-0` -> index 0 -> keys 0 to (capacity-1)
- `validator-1` -> index 1 -> keys capacity to (2*capacity-1)
- etc.

## Diagrams

See [PlantUML diagrams](../diagrams/plantuml/) for detailed sequence and component diagrams.
