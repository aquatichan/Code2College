#!/usr/bin/env bash
# Start the watcher for local development.
#
# On first run this creates a .env with a freshly generated HW_SECRET_KEY and a
# default invite code, then reuses them every time after. The key must stay
# stable: it decrypts stored Hirewheel sessions, so regenerating it would sign
# everyone out.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -f .env ]; then
    echo "→ first run: creating .env"
    {
        echo "HW_SECRET_KEY=$(python3 -m hwserver.keygen)"
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

echo "→ invite code: ${HW_INVITE_CODE}"
echo "→ listening on http://localhost:8000"
exec python3 -m hwserver
