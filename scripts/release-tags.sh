#!/usr/bin/env bash
# file: release-tags.sh
# description: Automatic consistent release tags following the SemVer convension.

# set -x
# trap read debug

## Build release context as environment variables.
GIT_BRANCH=$(git symbolic-ref --short HEAD)

## TODO: ensure this is the main branch
if [[ "${GIT_BRANCH}" != "main" ]]; then
	echo 'Please switch to the main branch to create release tags.'
	exit 0
fi

## TODO: get package version from pyproject.toml
CURRENT_VERSION=${ANKISYNCD_VERSION}

## Create GitHub Release
git tag -a ${CURRENT_VERSION} -m "v${CURRENT_VERSION}"

if [[ -z "${CI}" ]]; then
	echo "Please confirm the release tag is correct."
	read -p "Press enter to continue"
	echo
fi

git push --tags

## TODO: publish to PyPI.

