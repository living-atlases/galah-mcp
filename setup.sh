#!/usr/bin/env bash
#
# One-command setup for galah-mcp with Claude Code (user scope).
#
#   ./setup.sh
#
# It:
#   1. creates a local virtualenv (.venv) and installs the server + deps
#   2. registers the MCP server in Claude Code at user scope (available everywhere)
#
# Override defaults via env vars, e.g.:
#   GALAH_EMAIL=me@example.org GALAH_ATLAS=Australia ./setup.sh
#
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$DIR/.venv"
PY="$VENV/bin/python"

EMAIL="${GALAH_EMAIL:-john.doe@example.org}"
ATLAS="${GALAH_ATLAS:-Australia}"   # default atlas; e.g. Spain (gbif.es), GBIF, Austria…

echo ">> Creating virtualenv at $VENV"
python3 -m venv "$VENV"
"$PY" -m pip install -q -U pip
echo ">> Installing galah-mcp and dependencies (this may take a minute)"
"$PY" -m pip install -q -e "$DIR"

if ! command -v claude >/dev/null 2>&1; then
  echo
  echo "!! 'claude' CLI not found on PATH. The venv is ready; register manually with:"
  echo
  echo "   claude mcp add galah -s user --transport stdio \\"
  echo "     --env GALAH_EMAIL=$EMAIL --env GALAH_ATLAS=$ATLAS \\"
  echo "     -- $PY $DIR/server.py"
  echo
  exit 0
fi

echo ">> Registering 'galah' MCP server in Claude Code (user scope)"
# Remove any previous registration so this is idempotent.
claude mcp remove galah -s user >/dev/null 2>&1 || true
claude mcp add galah -s user \
  --transport stdio \
  --env GALAH_EMAIL="$EMAIL" \
  --env GALAH_ATLAS="$ATLAS" \
  -- "$PY" "$DIR/server.py"

echo
echo ">> Done. Atlas=$ATLAS  Email=$EMAIL"
echo "   Open Claude Code and run /mcp to verify, or: claude mcp list"
