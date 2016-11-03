#!/usr/bin/env bash
cd "$(dirname ${BASH_SOURCE[0]})/anki-bundled"
patch -p0 < ../libanki.patch
