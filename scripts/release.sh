#!/bin/bash
# file: release.sh
# description: Tag master branch and release to PyPI.


## TODO: ensure this is the master branch

## TODO: get package version from pyproject.toml
CURRENT_VERSION=2.3.0

## Create GitHub Release
git tag -a -m "${CURRENT_VERSION}"
git push --tags

## TODO: publish to PyPI.