import os, subprocess, urllib.parse
pw_raw = subprocess.check_output(["docker","exec","job-rag-db-1","printenv","POSTGRES_PASSWORD"], text=True).strip()
pw_enc = urllib.parse.quote(pw_raw, safe="")
env = os.environ.copy()
env["DATABASE_URL"] = f"postgresql+psycopg2://postgres:{pw_enc}@127.0.0.1:5433/job_rag"
env["ASYNC_DATABASE_URL"] = f"postgresql+asyncpg://postgres:{pw_enc}@127.0.0.1:5433/job_rag"
subprocess.call(["uv","run","job-rag","list","--stats"], env=env)
