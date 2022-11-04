#!/usr/bin/env make

ANKISYNCD_NAME ?= Anki Sync Server
ANKISYNCD_VERSION ?= v2.4.0
ANKISYNCD_DESCRIPTION ?= Self-hosted Anki Sync Server.

ENV ?= local
-include config/.env.${ENV}
-include config/secrets/.env.*.${ENV}
export

.DEFAULT_GOAL := help
.PHONY: help #: Display list of command and exit.
help:
	@${AWK} 'BEGIN {FS = " ?#?: "; print "${ANKISYNCD_NAME} ${ANKISYNCD_VERSION}\n${ANKISYNCD_DESCRIPTION}\n\nUsage: make \033[36m<command>\033[0m\n\nCommands:"} /^.PHONY: ?[a-zA-Z_-]/ { printf "  \033[36m%-10s\033[0m %s\n", $$2, $$3 }' $(MAKEFILE_LIST)

.PHONY: docs #: Build and serve documentation.
docs:
	@${MKDOCS} ${MKDOCS_CMD} -f docs/mkdocs.yml ${MKDOCS_OPTS}

.PHONY: tests #: Run unit tests.
tests:
	@${UNITTEST} discover -s tests

.PHONY: run
run:
	@${PYTHON} -m ankisyncd

# Run scripts using make
%:
	@if [[ -f "scripts/${*}.sh" ]]; then \
	${BASH} "scripts/${*}.sh"; fi

.PHONY: config #: Create new config file.
config: config/.env.${ENV}
config/.env.%:
	@cp -n config/.env.example config/.env.${ENV}

.PHONY: init #: Download Python dependencies.
init:
	@${POETRY} install

.PHONY: build
build:
	@${POETRY} build

.PHONY: release #: Create new Git release and tags.
release: release-branch release-tags

.PHONY: publish
publish: build
	@${POETRY} publish

.PHONY: clean
clean:
	@find . -name __pycache__ -not -path */.venv/* -print0 | xargs -0 rm -r

.PHONY: open
open:
	@${OPEN} ${ANKISYNCD_URL}