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

echo "→ invite code: ${HW_INVITE_CODE}"
echo "→ listening on http://localhost:8000"
exec python3 -m hwserver
