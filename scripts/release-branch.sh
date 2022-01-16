#!/usr/bin/env bash
# file: release-branch.sh
# description: Prepare a release branch from develop to master.

## Build release context as environment variables.
GIT_BRANCH=$(git symbolic-ref --short HEAD)

## TODO: get package version from pyproject.toml
CURRENT_VERSION=v2.2.0
## TODO: get new package version e.g. minor, major, bugfix
NEW_VERSION=v2.3.0

## TODO: ensure you're on the develop branch else fail
if [[ "${GIT_BRANCH}" != "develop" ]]; then
	echo 'Please switch to to the develop branch to create a release branch.'
	exit 0
fi

## Create release branch
git checkout -b "release/${NEW_VERSION}" develop

## TODO: bump package version in pyproject.toml
## TODO: commit changes to pyproject.toml
## TODO: generate new CHANGELOG entry from commits
## TODO: commit changes to CHANGELOG

## Return to develop
git checkout develop

if [[ -z "${CI}" ]]; then
	echo "Please confirm the release branch is correct."
	read -p "Press enter to continue"
	echo
fi

## Push branch and tags
git push origin "release/${NEW_VERSION}"

## TODO: create PR for review