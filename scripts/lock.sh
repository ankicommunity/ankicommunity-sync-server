#!/bin/bash
# file: lock.sh
# description: Lock dependencies and export requirements.

poetry lock
poetry export --without-hashes -f requirements.txt > src/requirements.txt
poetry export --dev --without-hashes -f requirements.txt > src/requirements-dev.txt

echo "-e src/." >> src/requirements-dev.txt