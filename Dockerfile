# syntax=docker/dockerfile:1
FROM python:3.13-slim-trixie

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

COPY ./sync_keys/*.py /src/

ENTRYPOINT [ "python", "./main.py"]
