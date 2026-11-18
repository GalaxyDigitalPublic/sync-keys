# syntax=docker/dockerfile:1
FROM python:3.13-slim-trixie@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90

ARG VERSION

LABEL org.label-schema.version=$VERSION

RUN apt-get update && apt-get install -y ca-certificates git gcc build-essential

# Conditionally install custom CA cert if provided as a build secret
RUN --mount=type=secret,id=ca-cert \
    if [ -f /run/secrets/ca-cert ]; then \
        cp /run/secrets/ca-cert /usr/local/share/ca-certificates/custom-ca.crt && \
        update-ca-certificates; \
    fi

COPY ./requirements.txt /src/requirements.txt

WORKDIR /src

# Install requirements (uses system CA bundle)
RUN --mount=type=secret,id=ca-cert \
    pip install -r requirements.txt

# Amazon RDS CA bundle for SYNC_KEYS_DB_AUTH=aws-iam (sslmode=verify-full). Pinned by checksum: a changed bundle fails
# the build; update RDS_CA_SHA256 deliberately when AWS rotates it.
ARG RDS_CA_URL=https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem
ARG RDS_CA_SHA256=90a6f1a7978a1b1b096dca6c57511ca48d3b8cf052f8e704baf358f34ea2f21b
RUN python -c "import hashlib,sys,urllib.request; d=urllib.request.urlopen(sys.argv[1],timeout=30).read(); \
h=hashlib.sha256(d).hexdigest(); assert h==sys.argv[2], 'RDS CA bundle checksum mismatch: '+h; \
open('/etc/ssl/certs/rds-global-bundle.pem','wb').write(d)" "$RDS_CA_URL" "$RDS_CA_SHA256"

COPY ./sync_keys/*.py /src/

ENTRYPOINT [ "python", "./main.py"]
