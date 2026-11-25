#!/usr/bin/env bash
set -e

BASEDIR=$(dirname "$0")
pushd "$BASEDIR"
python scripts/sync-requirements.py
rm -fr dist/*
python -m build
popd