"""Boot the FastAPI app via uvicorn briefly and capture lifespan log lines."""
import os
import subprocess
import sys
import time
import urllib.parse

pw_raw = subprocess.check_output(
    ["docker", "exec", "job-rag-db-1", "printenv", "POSTGRES_PASSWORD"], text=True
).strip()
pw_enc = urllib.parse.quote(pw_raw, safe="")

env = os.environ.copy()
env["DATABASE_URL"] = f"postgresql+psycopg2://postgres:{pw_enc}@127.0.0.1:5433/job_rag"
env["ASYNC_DATABASE_URL"] = f"postgresql+asyncpg://postgres:{pw_enc}@127.0.0.1:5433/job_rag"
env["ALLOWED_ORIGINS"] = "http://localhost:5173"

proc = subprocess.Popen(
    ["uv", "run", "uvicorn", "job_rag.api.app:app", "--host", "127.0.0.1", "--port", "8765", "--log-level", "info"],
    env=env,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
)
deadline = time.time() + 15
captured = []
while time.time() < deadline:
    line = proc.stdout.readline()
    if not line:
        if proc.poll() is not None:
            break
        continue
    sys.stdout.write(line)
    captured.append(line)
    if "prompt_version_check_clean" in line or "prompt_version_drift" in line or "prompt_version_check_failed" in line:
        time.sleep(1)
        break
proc.terminate()
try:
    proc.wait(timeout=5)
except subprocess.TimeoutExpired:
    proc.kill()
