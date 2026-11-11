#!/bin/sh
set -eu
cd "$(dirname "$0")"
umask 077

export OFFLINEAI_HOME="$PWD"
export PYTHONPATH="$PWD/app"
export PYTHONUTF8=1
export PYTHONUNBUFFERED=1
exec .venv/bin/python -m offlineai
