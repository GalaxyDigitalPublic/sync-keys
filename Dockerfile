FROM python:3.14-slim-trixie

ARG VERSION

LABEL org.label-schema.version=$VERSION

RUN apt-get update && apt-get install -y git gcc

COPY ./requirements.txt /src/requirements.txt

WORKDIR /src

RUN pip install -r requirements.txt

COPY ./sync_keys/*.py /src/

ENTRYPOINT [ "python", "./main.py"]
