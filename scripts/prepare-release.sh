#!/bin/bash
# file: prepare-release.sh
# description: Prepare a release branch from develop to master.

## TODO: get package version from pyproject.toml
CURRENT_VERSION=2.2.0
## TODO: get new package version e.g. minor, major, bugfix
LATEST_VERSION=2.3.0

## TODO: ensure you're on the develop branch else fail

## Create release branch
git checkout -b "release/${LATEST_VERSION}" develop

## TODO: bump package version in pyproject.toml
## TODO: commit changes to pyproject.toml
## TODO: generate new CHANGELOG entry from commits
## TODO: commit changes to CHANGELOG

## Push branch and tags
git push origin "release/${LATEST_VERSION}"

## TODO: create PR for review