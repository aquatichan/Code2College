#!/usr/bin/env bash
# Start the watcher for local development.
#
# On first run this creates a .env with a freshly generated HW_SECRET_KEY and a
# default invite code, then reuses them every time after. The key must stay
# stable: it decrypts stored Hirewheel sessions, so regenerating it would sign
# everyone out.
set -euo pipefail
cd "$(dirname "$0")"

# This script owns its own virtual environment under .venv/, independent of
# whatever Python or venv happens to be active in the calling shell. That way
# `./run-dev.sh` always works the same, with no manual `pip install` or venv
# activation step, and never fights macOS's "externally-managed-environment"
# protection on the system Python.
VENV_PY=".venv/bin/python3"
if [ ! -x "$VENV_PY" ]; then
    echo "→ first run: creating .venv"
    python3 -m venv .venv
fi

STAMP=".venv/.requirements.sha256"
if [ ! -f "$STAMP" ] || ! shasum -a 256 -c "$STAMP" >/dev/null 2>&1; then
    echo "→ installing dependencies into .venv (this takes a minute)"
    "$VENV_PY" -m pip install --quiet --upgrade pip
    "$VENV_PY" -m pip install --quiet -r requirements.txt
    shasum -a 256 requirements.txt > "$STAMP"
fi

if [ ! -f .env ]; then
    echo "→ first run: creating .env"
    {
        echo "HW_SECRET_KEY=$("$VENV_PY" -m hwserver.keygen)"
        echo "HW_INVITE_CODE=letmein"
        echo "HW_LOGIN_MODE=local"
    } > .env
    echo "  invite code: letmein"
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

PORT="${HW_PORT:-8000}"
if lsof -iTCP:"$PORT" -sTCP:LISTEN -t >/dev/null 2>&1; then
    # A second server can't bind the port, but it would still start its own
    # background scanner first — so refuse loudly instead of half-starting.
    echo "✗ port $PORT is already in use by pid $(lsof -iTCP:"$PORT" -sTCP:LISTEN -t | tr '\n' ' ')"
    echo "  a server is probably already running. Stop it with:"
    echo "    pkill -f -- '-m hwserver'"
    exit 1
fi

CHROMIUM_STAMP=".venv/.chromium-installed"
if [ ! -f "$CHROMIUM_STAMP" ]; then
    echo "→ installing Chromium for Playwright (one-time, also takes a minute)"
    "$VENV_PY" -m playwright install chromium
    touch "$CHROMIUM_STAMP"
fi

echo "→ invite code: ${HW_INVITE_CODE}"
echo "→ listening on http://localhost:8000"
exec "$VENV_PY" -m hwserver
