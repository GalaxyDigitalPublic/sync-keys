# syntax=docker/dockerfile:1
# Builder: python:3.13-alpine (musl). Everything the runtime needs is assembled here into /rootfs by docker/rootfs.sh;
# the final stage is FROM scratch. Base image pinned by digest so a moved tag cannot change what we ship.
# App user: uid/gid 1001, the validators chart's pod securityContext (runAsUser/fsGroup 1001). The charts run this
# image as an init container with runAsUser: 0 today, which overrides USER; the image works either way (/data is an
# emptyDir the pod mounts, not part of the image).
ARG APP_UID=1001
ARG APP_GID=1001

FROM python:3.13-alpine@sha256:9ef1a599f863231c3d91e941389bfdc4a2d6070557243d54df1a4e57015b960e AS builder

# Optional build secret "extra_ca" (local builds behind a TLS-intercepting proxy, e.g. Zscaler, only):
#   docker build --secret id=extra_ca,src=/path/to/ca.pem ...
# It is combined with the system bundle in a tmpfs (/run/ca) for the RUNs that download, and handed to apk/pip/git/
# urllib by env, so it never lands in any layer, builder stages included; the system bundle stays as the package ships
# it and is what the runtime gets. CI passes nothing and these steps are no-ops. apk upgrade pulls the latest Alpine
# fixes into the libraries the runtime copies; tzdata provides the UTC zoneinfo the runtime ships; git is only for the
# ethstaker-deposit checkout below and never reaches the runtime.
RUN --mount=type=secret,id=extra_ca,required=false \
    --mount=type=tmpfs,target=/run/ca \
    if [ -s /run/secrets/extra_ca ]; then \
      cat /etc/ssl/certs/ca-certificates.crt /run/secrets/extra_ca > /run/ca/bundle.pem && export SSL_CERT_FILE=/run/ca/bundle.pem; \
    fi && \
    apk upgrade --no-cache && \
    apk add --no-cache build-base libffi-dev linux-headers git libpq-dev tzdata

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

COPY requirements.lock requirements-build.lock ./

# Everything from the index is hash-locked (--require-hashes) and binary-only, except psycopg2-binary: its wheel
# vendors its own libpq, OpenSSL, krb5 and OpenLDAP, invisible to scanners and only updated with a psycopg2 release.
# It is compiled here from its hash-locked sdist (setuptools from the build lock, no build isolation) against Alpine's
# libpq, so it links the apk libpq/libssl that docker/rootfs.sh copies and the scanner sees. Same version and
# distribution name, so requirements.txt is unchanged.
RUN --mount=type=secret,id=extra_ca,required=false \
    --mount=type=tmpfs,target=/run/ca \
    if [ -s /run/secrets/extra_ca ]; then \
      cat /etc/ssl/certs/ca-certificates.crt /run/secrets/extra_ca > /run/ca/bundle.pem && export PIP_CERT=/run/ca/bundle.pem; \
    fi && \
    pip install --require-hashes --no-deps --only-binary :all: -r requirements-build.lock && \
    pip wheel --require-hashes --no-deps --no-build-isolation \
      --only-binary :all: --no-binary psycopg2-binary -w /wheels -r requirements.lock && \
    ! ls -d /wheels/*.tar.gz 2>/dev/null

# pip can't hash a git checkout, so ethstaker-deposit (keystore decryption for sync-db) is built into a wheel from
# the commit the v1.3.0 tag points to (keep it equal to requirements.txt; .github/scripts/check_lock.py checks it).
# No index and no build isolation: setuptools comes from the hashed build lock; its dependencies are in the lock.
ARG ETHSTAKER_DEPOSIT_REF=d8016bc8ca25d7f85e143828b6d99160f55a640f
RUN --mount=type=secret,id=extra_ca,required=false \
    --mount=type=tmpfs,target=/run/ca \
    if [ -s /run/secrets/extra_ca ]; then \
      cat /etc/ssl/certs/ca-certificates.crt /run/secrets/extra_ca > /run/ca/bundle.pem && export GIT_SSL_CAINFO=/run/ca/bundle.pem; \
    fi && \
    pip wheel --no-deps --no-build-isolation --no-index -w /wheels \
      "ethstaker-deposit @ git+https://github.com/ethstaker/ethstaker-deposit-cli@${ETHSTAKER_DEPOSIT_REF}"

# The venv gets local wheels only (pip runs from the system Python, so the venv carries no pip/setuptools). pip check
# fails the build if the lock misses a dependency; the last check fails it if a vendored psycopg2 libpq slipped in.
RUN python -m venv --without-pip /opt/venv && \
    pip --python /opt/venv/bin/python install --no-index --no-deps --only-binary :all: /wheels/*.whl && \
    pip --python /opt/venv/bin/python check && \
    ! ls -d /opt/venv/lib/python*/site-packages/psycopg2_binary.libs 2>/dev/null

# Amazon RDS CA bundle for SYNC_KEYS_DB_AUTH=aws-iam (sslmode=verify-full). Pinned by checksum: a changed bundle fails
# the build; update RDS_CA_SHA256 deliberately when AWS rotates it.
ARG RDS_CA_URL=https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem
ARG RDS_CA_SHA256=90a6f1a7978a1b1b096dca6c57511ca48d3b8cf052f8e704baf358f34ea2f21b
RUN --mount=type=secret,id=extra_ca,required=false \
    --mount=type=tmpfs,target=/run/ca \
    if [ -s /run/secrets/extra_ca ]; then \
      cat /etc/ssl/certs/ca-certificates.crt /run/secrets/extra_ca > /run/ca/bundle.pem && export SSL_CERT_FILE=/run/ca/bundle.pem; \
    fi && \
    python -c "import hashlib,sys,urllib.request; d=urllib.request.urlopen(sys.argv[1],timeout=30).read(); \
h=hashlib.sha256(d).hexdigest(); assert h==sys.argv[2], 'RDS CA bundle checksum mismatch: '+h; \
open('/build/rds-global-bundle.pem','wb').write(d)" "$RDS_CA_URL" "$RDS_CA_SHA256"

ARG APP_UID
ARG APP_GID

COPY docker/rootfs.sh /usr/local/sbin/rootfs.sh
RUN /usr/local/sbin/rootfs.sh /rootfs /etc/ssl/certs/ca-certificates.crt "$APP_UID" "$APP_GID" && \
    install -m 0644 /build/rds-global-bundle.pem /rootfs/etc/ssl/certs/rds-global-bundle.pem

# App code, root-owned with 0755 dirs / 0644 files, so the app user cannot change what gets imported.
COPY sync_keys/*.py /appsrc/
RUN chown -R 0:0 /appsrc && \
    chmod 0755 /appsrc && \
    find /appsrc -type f -exec chmod 0644 {} +

# Runtime: nothing but the assembled filesystem. No shell, no package manager, no busybox.
FROM scratch AS runtime
ARG VERSION
ARG APP_UID
ARG APP_GID

LABEL org.label-schema.version=$VERSION

COPY --from=builder /rootfs/ /
COPY --from=builder /appsrc/ /src/

# The only writable path in the image is /tmp; the charts mount /data (emptyDir) for the output. PYTHONSAFEPATH keeps
# the CWD / script dir off sys.path; /src (the flat modules main.py imports) is added explicitly instead.
ENV PATH=/opt/venv/bin:/usr/local/bin \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONSAFEPATH=1 \
    PYTHONPATH=/src \
    HOME=/tmp

WORKDIR /src

# Numeric, so a pod with runAsNonRoot: true can verify it (a user name cannot be checked by the kubelet).
USER ${APP_UID}:${APP_GID}

# Same as before: the validators chart passes only args (`sync-validator-keys --db-url ... --output-dir /data ...`);
# the web3signer chart overrides the command with `python ./main.py` and workingDir /src, which also works (python is
# on PATH as the venv interpreter, main.py is in /src). Absolute venv interpreter path: scratch has no /usr/bin/env
# and no shell, and the base interpreter in /usr/local/bin does not see the venv.
ENTRYPOINT ["/opt/venv/bin/python", "/src/main.py"]
