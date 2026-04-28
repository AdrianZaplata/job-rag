"""One-shot wrapper to resume `job-rag reextract` against the dev DB.

Reads POSTGRES_PASSWORD from the running db container, URL-encodes it,
points DATABASE_URL/ASYNC_DATABASE_URL at the socat sidecar (localhost:5433),
and execs `job-rag reextract` (default — stale-only).

Output is teed by the parent shell. This script just sets env and execs.
"""

from __future__ import annotations

import os
import subprocess
import sys
import urllib.parse


def main() -> int:
    # Pull password from running db container (avoids touching .env from a tool with no perm).
    pw_raw = subprocess.check_output(
        ["docker", "exec", "job-rag-db-1", "printenv", "POSTGRES_PASSWORD"],
        text=True,
    ).strip()
    pw_enc = urllib.parse.quote(pw_raw, safe="")

    sync_url = f"postgresql+psycopg2://postgres:{pw_enc}@127.0.0.1:5433/job_rag"
    async_url = f"postgresql+asyncpg://postgres:{pw_enc}@127.0.0.1:5433/job_rag"

    env = os.environ.copy()
    env["DATABASE_URL"] = sync_url
    env["ASYNC_DATABASE_URL"] = async_url

    # Exec job-rag reextract (default — stale-only). Inherits stdio so tee works.
    return subprocess.call(
        ["uv", "run", "job-rag", "reextract"],
        env=env,
    )


if __name__ == "__main__":
    sys.exit(main())
