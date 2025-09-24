#!/bin/sh
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required to configure the Anthropic API key." >&2
  exit 1
fi
python3 "$SCRIPT_DIR/configure_api_key.py" "$@"

