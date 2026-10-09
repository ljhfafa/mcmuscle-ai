#!/bin/zsh
set -eu
cd "$(dirname "$0")"
.venv/bin/python -m mcmuscle.mcp.credentials
