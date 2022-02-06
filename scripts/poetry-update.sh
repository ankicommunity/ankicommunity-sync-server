#!/usr/bin/env bash
# file: poetry-update.sh
# description: Update Python dependencies to latest.

# POETRY_UPDATE_OPTS=--dry-run
# POETRY_UPDATE_ARGS=anki
poetry update "${POETRY_UPDATE_OPTS}" "${POETRY_UPDATE_ARGS}"

# TODO: Run poetry export
# TODO: Create git branch and commit