# sync-keys Documentation

Helper script for [eth-staking-charts](https://github.com/CryptoManufaktur-io/eth-staking-charts) that manages Ethereum validator keys. Decrypts validator keystores and syncs them to PostgreSQL for Web3Signer and validator clients.

## Quick Start

```bash
# Install
pip install -e .

# Import keystores to database
sync-keys sync-db \
  --db-url "postgresql://user:pass@localhost/dbname" \
  --private-keys-dir ./keystores \
  --validator-capacity 100

# Generates DECRYPTION_KEY - save this securely!
```

## Commands

### sync-db

Imports keystore files to PostgreSQL. Decrypts keystores with user password, re-encrypts with AES, stores in database.

```bash
sync-keys sync-db \
  --db-url "postgresql://user:pass@localhost/dbname" \
  --private-keys-dir /path/to/keystores \
  --validator-capacity 100 \
  --table-name keys
```

**Key directory structure:**
```
keystores/
  keystore-m_12345.json           # Uses default fee recipient
  0xFeeRecipientAddress/
    keystore-m_67890.json         # Uses specified fee recipient
```

**Output:** `DECRYPTION_KEY` environment variable value for web3signer pods.

### sync-validator-keys

Generates validator client configuration files. Run by init containers in validator pods.

```bash
export WEB3SIGNER_URL="http://web3signer:9000"
sync-keys sync-validator-keys \
  --db-url "postgresql://user:pass@localhost/dbname" \
  --output-dir /data/validators \
  --default-recipient "0x..."
```

**Generates:**
- `validator_definitions.yml` - Lighthouse config
- `signer_keys.yml` - Teku/Prysm config

**Validator index:** Determined from pod hostname (e.g., `validator-0` -> index 0).

### sync-web3signer-keys

Decrypts keys from database and generates Web3Signer key files.

```bash
export DECRYPTION_KEY="<from sync-db output>"
sync-keys sync-web3signer-keys \
  --db-url "postgresql://user:pass@localhost/dbname" \
  --output-dir /data/keys
```

**Generates:** `key_0.yaml`, `key_1.yaml`, etc. for Web3Signer.

---

## Database Schema

```sql
CREATE TABLE keys (
    public_key TEXT UNIQUE NOT NULL,      -- BLS public key (0x...)
    private_key TEXT UNIQUE NOT NULL,     -- AES-encrypted, base64
    nonce TEXT NOT NULL,                   -- AES nonce, base64
    validator_index TEXT NOT NULL,         -- Assigned validator index
    fee_recipient TEXT                     -- Optional fee recipient address
);
```

---

## API Overview

### Database Class

```python
from database import Database

db = Database(db_url="postgresql://...", table_name="keys")

# Store keys (replaces entire table)
db.update_keys(keys=[DatabaseKeyRecord(...)])

# Fetch all keys
keys = db.fetch_keys()

# Fetch by validator index
public_keys = db.fetch_public_keys_by_validator_index("0")
```

### Encoder/Decoder

```python
from encoder import Encoder, Decoder

# Encrypt
encoder = Encoder()
encrypted, nonce = encoder.encrypt("secret")
key = encoder.cipher_key_str  # Save this!

# Decrypt
decoder = Decoder(key)
original = decoder.decrypt(data=encrypted_b64, nonce=nonce_b64)
```

### Web3SignerManager

```python
from web3signer import Web3SignerManager

manager = Web3SignerManager(validator_capacity=100)
records = manager.process_transferred_keypairs(keypairs)
# Returns list of DatabaseKeyRecord with validator indices assigned
```

---

## Environment Variables

| Variable | Command | Description |
|----------|---------|-------------|
| `DECRYPTION_KEY` | sync-web3signer-keys | AES decryption key from sync-db |
| `WEB3SIGNER_URL` | sync-validator-keys | URL of Web3Signer service |

---

## Docker

```bash
docker build -t sync-keys .
docker run sync-keys sync-db --help
```

See [setup.md](setup.md) for detailed environment configuration.
