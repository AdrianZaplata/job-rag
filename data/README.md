# data/

Local-only reference data. NOT a runtime read path.

- `profile.json` — reference snapshot of Adrian's seed `user_profile` row. The canonical runtime
  source is the `user_profile` DB row, seeded by `alembic/versions/0006_seed_user_profile.py` from
  an embedded dict literal (PROF-01 / Phase 7 D-03, D-04). Update flow when seed contents change:
  edit `profile.json` + regenerate the dict literal in the migration in lockstep.
- `postings/` — markdown ingestion corpus; consumed by `job-rag ingest` (development only).
