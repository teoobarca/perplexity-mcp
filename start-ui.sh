#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"

# Load .env if exists
if [ -f "$DIR/.env" ]; then
    set -a
    source "$DIR/.env"
    set +a
fi

exec "$DIR/.venv/bin/perplexity-server" "$@"
