FROM python:3.12-slim-bookworm

ARG VERSION

LABEL org.label-schema.version=$VERSION

COPY ./requirements.txt /src/requirements.txt

WORKDIR /src

RUN apt-get update && apt-get install -y git
RUN pip install -r requirements.txt

COPY ./*.py /src/

ENTRYPOINT [ "python", "./main.py"]
