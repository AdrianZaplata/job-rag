"""CI grep-guard test - no DDL DEFAULT on user_id columns.

Enforces decisions D-08 (hardcoded SEEDED_USER_ID, no random uuid_generate_v4()
DEFAULT in migrations) and D-12 (CI grep guard prevents Pitfall 18 regression:
silent multi-user collision when two requests both fall through to a
DEFAULT-generated UUID).

This test is intentionally a no-op until Plan 02 lands the first migration.
After that, it actively scans every file in alembic/versions/ for the forbidden
pattern and fails loudly if found. Belt-and-suspenders: a workflow-level grep
step in CI also runs the same check (RESEARCH §"CI grep guard" lines 1118-1145).
"""

import re
from pathlib import Path

# Match either:
#   - DDL "DEFAULT '<uuid>'::uuid" (raw SQL inside op.execute or sa.text)
#   - SQLAlchemy "server_default=...uuid..." (inside op.add_column / op.create_table)
DEFAULT_UUID_PATTERN = re.compile(
    r"DEFAULT.*['\"]?[0-9a-f-]{36}['\"]?.*::?uuid|"
    r"server_default\s*=.*[Uu][Uu][Ii][Dd]",
    re.IGNORECASE,
)


def test_no_default_uuid_on_user_id_columns():
    """No Alembic migration may add a DDL DEFAULT to a user_id column."""
    versions_dir = Path(__file__).parent.parent / "alembic" / "versions"
    if not versions_dir.exists():
        # Plan 02 hasn't run yet - test is a no-op; passes trivially. As soon as
        # Plan 02 commits the baseline migration, this branch is bypassed and
        # the scanner below activates.
        return
    bad_files: list[tuple[Path, int, str]] = []
    for migration in versions_dir.glob("*.py"):
        for lineno, line in enumerate(migration.read_text().splitlines(), 1):
            if "user_id" in line and DEFAULT_UUID_PATTERN.search(line):
                bad_files.append((migration, lineno, line.strip()))
    assert not bad_files, (
        "Migrations adding DEFAULT to user_id columns:\n"
        + "\n".join(f"  {p.name}:{n}: {line}" for p, n, line in bad_files)
    )
