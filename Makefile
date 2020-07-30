#/bin/make

ANKI_SERVER_NAME ?= "Anki Sync Server"
ANKI_SERVER_VERSION ?= "v0.1.0"
ANKI_SERVER_DESCRIPTION ?= "Self-hosted Anki Sync Server."
ENV ?= local

-include config/.env.${ENV}
export

.DEFAULT_GOAL := help
.PHONY: help #: Display list of command and exit.
help:
	@awk 'BEGIN {FS = " ?#?: "; print ""${ANKI_SERVER_NAME}" "${ANKI_SERVER_VERSION}"\n"${ANKI_SERVER_DESCRIPTION}"\n\nUsage: make \033[36m<command>\033[0m\n\nCommands:"} /^.PHONY: ?[a-zA-Z_-]/ { printf "  \033[36m%-10s\033[0m %s\n", $$2, $$3 }' $(MAKEFILE_LIST)

.PHONY: docs #: Build and serve documentation.
docs: print-env
	@${MKDOCS} ${MKDOCS_OPTION} -f docs/mkdocs.yml

%:
	@test -f scripts/${*}.sh
	@${SHELL} scripts/${*}.sh