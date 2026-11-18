#!/usr/bin/env bash
# Smoke-tests a built sync-keys image (the test job runs on the runner's Python, not the image's).
# Runs it the hardened way (non-root, no capabilities, read-only root, tmpfs /tmp and /data) and finishes with a real
# sync-validator-keys and sync-web3signer-keys run against a throwaway Postgres.
# Usage: .github/scripts/image_smoke_test.sh <image>
set -euo pipefail

IMG="${1:?usage: $0 <image>}"
PG_IMG="postgres:17-alpine@sha256:a77aa70e641402a21411b92b721c58d10f23b50ae5fdd2333efd22d166e1e5f7"
NAME="sk-smoke-$$"
UID_GID="$(docker image inspect -f '{{.Config.User}}' "$IMG")"
HARD=(--user "$UID_GID" --cap-drop ALL --security-opt no-new-privileges --read-only --tmpfs /tmp
  --tmpfs "/data:uid=${UID_GID%%:*},gid=${UID_GID##*:},mode=0755")
PY=(--entrypoint /opt/venv/bin/python)
cleanup() { docker rm -f "$NAME-pg" >/dev/null 2>&1 || true; docker network rm "$NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT

step() { echo "::group::$1"; }
end() { echo "::endgroup::"; }

step "runs as nonroot"
case "$UID_GID" in "" | root | 0 | 0:*) echo "image runs as root ($UID_GID)"; exit 1 ;; esac
echo "ok: user $UID_GID"
end

step "no shell in the image"
for sh in sh /bin/sh /bin/bash /bin/ash /bin/busybox /busybox/sh /sbin/apk /usr/bin/env; do
  if docker run --rm --entrypoint "$sh" "$IMG" -c true >/dev/null 2>&1; then
    echo "found a shell: $sh"; exit 1
  fi
done
echo "ok: no shell, busybox, env or apk"
end

step "python 3.13, every dependency and app module imports, no sqlite"
docker run --rm "${HARD[@]}" "${PY[@]}" "$IMG" -c "
import importlib, importlib.util, pkgutil, sys, sysconfig
assert sys.version_info[:2] == (3, 13), sys.version
deps = sorted(m.name for m in pkgutil.iter_modules([sysconfig.get_path('purelib')]) if not m.name.startswith('_'))
mods = ['main', 'database', 'encoder', 'sync_db', 'sync_validator_keys', 'sync_web3signer_keys', 'typings', 'utils',
        'validators', 'web3signer', 'ethstaker_deposit.key_handling.keystore', 'boto3', 'azure.identity',
        'psycopg2.extras', 'Crypto.Cipher.AES']
for name in deps + mods:
    importlib.import_module(name)
import psycopg2
assert importlib.util.find_spec('sqlite3') is None and importlib.util.find_spec('_sqlite3') is None, 'sqlite3 shipped'
assert sys.flags.safe_path and '' not in sys.path and sys.flags.dont_write_bytecode, sys.path
print('ok:', sys.version.split()[0], 'psycopg2', psycopg2.__version__, 'libpq', psycopg2.extensions.libpq_version(),
      len(deps), 'deps')
"
end

step "CLI entry points (the charts' invocations)"
# validators chart: args only, the image ENTRYPOINT runs main.py
docker run --rm "${HARD[@]}" "$IMG" sync-validator-keys --help >/dev/null
docker run --rm "${HARD[@]}" "$IMG" sync-web3signer-keys --help >/dev/null
docker run --rm "${HARD[@]}" "$IMG" sync-db --help >/dev/null
# web3signer chart: command `python ./main.py`, workingDir /src (python resolved on the image PATH)
docker run --rm "${HARD[@]}" --entrypoint python -w /src "$IMG" ./main.py sync-web3signer-keys --help >/dev/null
echo "ok: all --help exit 0"
end

step "writes /data and /tmp, cannot write the code or the root filesystem; UTC zoneinfo and CA bundles"
docker run --rm "${HARD[@]}" "${PY[@]}" "$IMG" -c "
import datetime, os, ssl, sys, tempfile, zoneinfo
open('/data/probe', 'w').close(); os.remove('/data/probe')
tempfile.NamedTemporaryFile(dir='/tmp').close()
for p in ('/src', '/src/main.py', '/opt/venv', '/usr/local/lib', '/etc'):
    try:
        open(os.path.join(p, 'evil.py') if os.path.isdir(p) else p, 'a').close()
    except OSError:
        continue
    sys.exit(f'{p} is writable by uid {os.getuid()}')
assert not os.access('/src/main.py', os.W_OK)
print('ok: utc', datetime.datetime.now(zoneinfo.ZoneInfo('UTC')).isoformat())
ssl.create_default_context().load_verify_locations('/etc/ssl/certs/ca-certificates.crt')
ssl.create_default_context().load_verify_locations('/etc/ssl/certs/rds-global-bundle.pem')
print('ok: uid', os.getuid(), 'wrote /data and /tmp; code and root fs read-only; CA bundles load')
"
end

step "real run against a throwaway Postgres"
docker network create "$NAME" >/dev/null
docker run -d --name "$NAME-pg" --network "$NAME" --tmpfs /var/lib/postgresql/data -e POSTGRES_PASSWORD=smoke -e POSTGRES_DB=keys "$PG_IMG" >/dev/null
for _ in $(seq 1 30); do docker exec "$NAME-pg" pg_isready -U postgres -d keys >/dev/null 2>&1 && break; sleep 1; done
sleep 2
DB_URL="postgresql://postgres:smoke@$NAME-pg:5432/keys"
# Encrypt two BLS private keys the way sync-db does (the image's own Encoder), schema as Database.update_keys.
rows="$(docker run --rm "${HARD[@]}" "${PY[@]}" "$IMG" -c "
from encoder import Encoder
from utils import bytes_to_str
e = Encoder()
print(e.cipher_key_str)
for i, (pk, sk) in enumerate([('0x' + 'a1' * 48, 12345), ('0x' + 'b2' * 48, 67890)]):
    data, nonce = e.encrypt(str(sk))
    fee = \"'0x\" + '1' * 40 + \"'\" if i == 0 else 'NULL'
    print(f\"('{pk}', '{bytes_to_str(data)}', '{bytes_to_str(nonce)}', '0', {fee})\")
")"
key="$(head -1 <<<"$rows")"
values="$(tail -n +2 <<<"$rows" | paste -sd, -)"
docker exec -i "$NAME-pg" psql -q -v ON_ERROR_STOP=1 -U postgres -d keys <<SQL
CREATE TABLE keys (public_key TEXT UNIQUE NOT NULL, private_key TEXT UNIQUE NOT NULL, nonce TEXT NOT NULL,
  validator_index TEXT NOT NULL, fee_recipient TEXT);
INSERT INTO keys (public_key, private_key, nonce, validator_index, fee_recipient) VALUES $values;
SQL

# Hostname validators-0 -> validator_index 0, as in the StatefulSet.
# The chart's exact invocation (args to the ENTRYPOINT).
out="$(docker run --rm "${HARD[@]}" --network "$NAME" --hostname validators-0 -e WEB3SIGNER_URL=http://web3signer:6174 \
  "$IMG" sync-validator-keys --db-url "$DB_URL" --output-dir /data \
  --default-recipient "0x$(printf '2%.0s' $(seq 1 40))" 2>&1)" || { echo "$out"; exit 1; }
echo "$out"
grep -q "uses 2 public keys" <<<"$out"
# Same run, then check the written files from inside (the /data tmpfs only lives for one container).
docker run --rm "${HARD[@]}" --network "$NAME" --hostname validators-0 -e WEB3SIGNER_URL=http://web3signer:6174 \
  -e DB_URL="$DB_URL" "${PY[@]}" "$IMG" -c "
import os, runpy, sys, yaml
sys.argv = ['main.py', 'sync-validator-keys', '--db-url', os.environ['DB_URL'], '--output-dir', '/data',
            '--default-recipient', '0x' + '2' * 40]
try:
    runpy.run_path('/src/main.py', run_name='__main__')
except SystemExit as e:
    assert not e.code, e.code
defs = yaml.safe_load(open('/data/validator_definitions.yml'))
assert sorted(d['voting_public_key'] for d in defs) == ['0x' + 'a1' * 48, '0x' + 'b2' * 48], defs
assert {d['suggested_fee_recipient'] for d in defs} == {'0x' + '1' * 40, '0x' + '2' * 40}, defs
assert all(d['url'] == 'http://web3signer:6174' and d['type'] == 'web3signer' for d in defs), defs
assert open('/data/signer_keys.yml').read().startswith('validators-external-signer-public-keys: ['), 'signer_keys.yml'
print('ok: validator_definitions.yml + signer_keys.yml written as uid', os.getuid())
"
docker run --rm "${HARD[@]}" --network "$NAME" -e DECRYPTION_KEY="$key" -e DB_URL="$DB_URL" "${PY[@]}" "$IMG" -c "
import glob, os, runpy, sys, yaml
sys.argv = ['main.py', 'sync-web3signer-keys', '--db-url', os.environ['DB_URL'], '--output-dir', '/data/keystore']
try:
    runpy.run_path('/src/main.py', run_name='__main__')
except SystemExit as e:
    assert not e.code, e.code
keys = sorted(yaml.safe_load(open(f))['privateKey'] for f in glob.glob('/data/keystore/key_*.yaml'))
assert keys == sorted('0x' + format(k, '064x') for k in (12345, 67890)), keys
print('ok: web3signer keystores written and decrypted:', len(keys))
"
end

echo "image smoke test passed"
