# Troubleshooting Guide

## Top 10 Issues and Solutions

### 1. "Password incorrect" when running sync-db

**Symptom:**
```
Unable to decrypt keystore-m_12345.json with the provided password
Password incorrect
```

**Causes:**
- Wrong password for the keystore files
- Different passwords for different keystores in the same directory

**Solutions:**
1. Verify the password is correct for the specific keystore
2. Group keystores by password into separate directories
3. Run sync-db multiple times for different password groups

---

### 2. Database connection failed

**Symptom:**
```
Error: failed to connect to the database server with provided URL
```

**Causes:**
- Incorrect connection string format
- Database not running
- Network/firewall issues
- Wrong credentials

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

---

### 3. DECRYPTION_KEY not set or invalid

**Symptom:**
```
KeyError: 'DECRYPTION_KEY'
# or
Decryption failed / garbled output
```

**Causes:**
- Environment variable not set
- Using wrong DECRYPTION_KEY (from different sync-db run)
- Key was not saved after sync-db

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

---

### 4. WEB3SIGNER_URL not set

**Symptom:**
```
KeyError: 'WEB3SIGNER_URL'
```

**Cause:** Environment variable not set for sync-validator-keys.

**Solution:**
```bash
export WEB3SIGNER_URL="http://web3signer:9000"
sync-keys sync-validator-keys --db-url "..." --output-dir ./keys
```

---

### 5. No keys found for validator index

**Symptom:**
```
The validator now uses 0 public keys.
```

**Causes:**
- Wrong validator index being queried
- Keys not imported yet
- validator_capacity mismatch

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

---

### 6. Invalid Ethereum address for fee recipient

**Symptom:**
```
Error: Invalid Ethereum address
```

**Causes:**
- Address doesn't start with 0x
- Address has wrong length (not 42 characters)
- Invalid hex characters

**Solution:**
Use valid checksum address:
```bash
sync-keys sync-validator-keys \
  --default-recipient "0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed" \
  ...
```

---

### 7. Keys already synced message but files outdated

**Symptom:**
```
Keys already synced to the last version.
```
But the key files are actually stale.

**Causes:**
- Comparison logic found matching keys
- Files exist but content differs

**Solutions:**

1. Delete existing key files and re-run:
   ```bash
   rm -rf /data/keys/*.yaml
   sync-keys sync-web3signer-keys ...
   ```

2. For validator keys:
   ```bash
   rm /data/validators/validator_definitions.yml
   sync-keys sync-validator-keys ...
   ```

---

### 8. Table "keys" does not exist

**Symptom:**
```
psycopg2.errors.UndefinedTable: relation "keys" does not exist
```

**Cause:** sync-db hasn't been run yet, or database was reset.

**Solution:**
Run sync-db first to create the table:
```bash
sync-keys sync-db --db-url "..." --private-keys-dir ./keystores
```

---

### 9. Private key hex padding issues

**Symptom:**
Web3Signer rejects keys or signatures fail.

**Cause:** Private keys need zero-padding to 64 hex characters.

**Context:** The code handles this at `sync_web3signer_keys.py:63`:
```python
private_keys.append(f"0x{hex[2:].zfill(64)}")
```

**If issue persists:**
1. Verify generated YAML files have 66-character keys (0x + 64 hex)
2. Check for encoding issues in the key files

---

### 10. Docker container can't connect to database

**Symptom:**
```
psycopg2.OperationalError: could not connect to server
```

**Causes:**
- Using localhost in Docker (container network isolation)
- Database not accessible from container network

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

---

## Debug Commands

### Verify database contents
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

### Check environment variables
```bash
env | grep -E 'DECRYPTION_KEY|WEB3SIGNER_URL'
```

### Verify keystore files
```bash
# Count keystores
find ./keystores -name "keystore*.json" | wc -l

# Check file format
cat ./keystores/keystore-m_12345.json | python -m json.tool
```

### Test encryption roundtrip
```python
from encoder import Encoder, Decoder
from utils import bytes_to_str

encoder = Encoder()
encrypted, nonce = encoder.encrypt("test")
print(f"Key: {encoder.cipher_key_str}")

decoder = Decoder(encoder.cipher_key_str)
decrypted = decoder.decrypt(bytes_to_str(encrypted), bytes_to_str(nonce))
print(f"Decrypted: {decrypted}")
```
