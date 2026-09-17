"""`python -m hwserver` — run the API + background scanner."""

from __future__ import annotations

import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "hwserver.api:app",
        host=os.environ.get("HW_HOST", "127.0.0.1"),
        port=int(os.environ.get("HW_PORT", 8000)),
        reload=False,
    )
