#!/bin/bash
# Phase 06.1 G-03 regression guard — behavioral tests for scripts/tf-apply-prod.sh.
#
# What this guards:
#   - The wrapper hard-codes the dual `-var-file=prod.tfvars -var-file=prod.tfvars.local`
#     invocation that prevents Phase 06 UAT Bug #3 (silent BACKEND_AUDIENCE /
#     ENTRA_TENANT_* env-var wipe on apply when prod.tfvars.local is omitted).
#   - The "no subcommand" path exits 3 with usage text.
#   - The "missing prod.tfvars.local" path exits 2 with the remediation message.
#   - The `--no-local` escape hatch shifts the missing-file check off so the
#     wrapper proceeds to terraform (we don't run terraform here — just confirm
#     the exit-2 guard does NOT fire when --no-local is passed).
#
# Why a temp-fixture mirror instead of testing against the real repo:
#   The wrapper resolves REPO_ROOT from its own location (`dirname $0`/..).
#   Renaming the real infra/envs/prod/prod.tfvars.local to test the exit-2
#   path would be destructive on Adrian's workstation. Instead, the test
#   copies the wrapper into a private tempdir that mirrors infra/envs/prod/
#   and toggles the prod.tfvars.local presence inside the mirror only. The
#   real file is never read, renamed, or touched.
#
# Run:
#   bash scripts/tests/test-tf-apply-prod.sh
#
# Exit codes:
#   0 — all assertions passed
#   1 — at least one assertion failed
#
# Dependencies: bash, mktemp, cp, grep. No bats, no terraform.

set -uo pipefail
# Note: NOT using -e — we want to keep running through all assertions and
# accumulate a pass/fail count so the operator sees every failure at once.

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
WRAPPER_SRC="$REPO_ROOT/scripts/tf-apply-prod.sh"

if [ ! -f "$WRAPPER_SRC" ]; then
  echo "FATAL: wrapper not found at $WRAPPER_SRC" >&2
  exit 1
fi

PASS=0
FAIL=0

pass() {
  PASS=$((PASS + 1))
  echo "  PASS — $1"
}

fail() {
  FAIL=$((FAIL + 1))
  echo "  FAIL — $1" >&2
}

# ── Build the temp fixture mirror ───────────────────────────────────────────
FIXTURE_ROOT="$(mktemp -d -t tf-apply-prod-test.XXXXXX)"
trap 'rm -rf "$FIXTURE_ROOT"' EXIT

mkdir -p "$FIXTURE_ROOT/scripts"
mkdir -p "$FIXTURE_ROOT/infra/envs/prod"

cp "$WRAPPER_SRC" "$FIXTURE_ROOT/scripts/tf-apply-prod.sh"
chmod +x "$FIXTURE_ROOT/scripts/tf-apply-prod.sh"

# Stage a minimal committed tfvars so the wrapper can find at least one var-file
# if it ever stat()s it (current wrapper does not, but harden against future
# checks). Empty file is fine — terraform never runs in this test.
: > "$FIXTURE_ROOT/infra/envs/prod/prod.tfvars"

WRAPPER_COPY="$FIXTURE_ROOT/scripts/tf-apply-prod.sh"
LOCAL_TFVARS="$FIXTURE_ROOT/infra/envs/prod/prod.tfvars.local"

echo "Fixture: $FIXTURE_ROOT"
echo

# ── Test 1: no subcommand → exit 3 with usage ────────────────────────────────
echo "Test 1: wrapper exits 3 with usage when invoked with no subcommand"
OUT="$(bash "$WRAPPER_COPY" 2>&1)"
RC=$?
if [ "$RC" -eq 3 ]; then
  pass "exit code = 3"
else
  fail "expected exit 3, got $RC"
fi
if echo "$OUT" | grep -q "no subcommand supplied"; then
  pass "stderr contains 'no subcommand supplied'"
else
  fail "stderr missing 'no subcommand supplied' — actual output: $OUT"
fi
if echo "$OUT" | grep -q "Usage:"; then
  pass "stderr contains usage line"
else
  fail "stderr missing 'Usage:' — actual output: $OUT"
fi
echo

# ── Test 2: missing prod.tfvars.local → exit 2 with remediation ─────────────
echo "Test 2: wrapper exits 2 with remediation when prod.tfvars.local missing"
# Ensure the local file does NOT exist
rm -f "$LOCAL_TFVARS"
OUT="$(bash "$WRAPPER_COPY" plan 2>&1)"
RC=$?
if [ "$RC" -eq 2 ]; then
  pass "exit code = 2"
else
  fail "expected exit 2, got $RC"
fi
if echo "$OUT" | grep -q "Missing infra/envs/prod/prod.tfvars.local"; then
  pass "stderr contains 'Missing infra/envs/prod/prod.tfvars.local'"
else
  fail "stderr missing 'Missing infra/envs/prod/prod.tfvars.local' — actual output: $OUT"
fi
if echo "$OUT" | grep -q "Remediation:"; then
  pass "stderr contains 'Remediation:' guidance"
else
  fail "stderr missing 'Remediation:' — actual output: $OUT"
fi
if echo "$OUT" | grep -q -- "--no-local"; then
  pass "stderr documents --no-local escape hatch"
else
  fail "stderr missing '--no-local' escape-hatch hint — actual output: $OUT"
fi
echo

# ── Test 3: --no-local escape hatch skips the missing-file guard ─────────────
echo "Test 3: --no-local skips the missing-file guard (does NOT exit 2)"
# Local file is still absent from Test 2. Use a PATH-shimmed `terraform` that
# echoes its argv and exits 0 — that way we can confirm the wrapper reached
# the `exec terraform` line AND that it built the single-var-file argv form.
SHIM_DIR="$FIXTURE_ROOT/shim-bin"
mkdir -p "$SHIM_DIR"
cat > "$SHIM_DIR/terraform" <<'SHIM'
#!/bin/bash
# Echo the argv so the test can verify the wrapper assembled the expected
# command line, then exit 0 so the wrapper propagates 0.
echo "TERRAFORM_ARGV: $*"
exit 0
SHIM
chmod +x "$SHIM_DIR/terraform"

OUT="$(PATH="$SHIM_DIR:$PATH" bash "$WRAPPER_COPY" --no-local plan -refresh=false 2>&1)"
RC=$?
if [ "$RC" -eq 0 ]; then
  pass "--no-local plan exits 0 via terraform shim"
else
  fail "expected exit 0 from shim, got $RC — output: $OUT"
fi
if echo "$OUT" | grep -q "TERRAFORM_ARGV: plan -var-file=prod.tfvars -refresh=false"; then
  pass "--no-local builds single-var-file argv (prod.tfvars only)"
else
  fail "--no-local argv shape unexpected — output: $OUT"
fi
echo

# ── Test 4: default invocation (with prod.tfvars.local present) loads BOTH ──
echo "Test 4: default invocation builds dual-var-file argv"
# Stage the local tfvars so the missing-file guard passes
echo '# fixture local tfvars' > "$LOCAL_TFVARS"
OUT="$(PATH="$SHIM_DIR:$PATH" bash "$WRAPPER_COPY" plan -refresh=false 2>&1)"
RC=$?
if [ "$RC" -eq 0 ]; then
  pass "default plan exits 0 via terraform shim"
else
  fail "expected exit 0 from shim, got $RC — output: $OUT"
fi
if echo "$OUT" | grep -q "TERRAFORM_ARGV: plan -var-file=prod.tfvars -var-file=prod.tfvars.local -refresh=false"; then
  pass "default invocation builds dual-var-file argv"
else
  fail "default argv shape unexpected — output: $OUT"
fi
echo

# ── Summary ─────────────────────────────────────────────────────────────────
echo "──────────────────────────────────────────────"
echo "Passed: $PASS"
echo "Failed: $FAIL"
if [ "$FAIL" -gt 0 ]; then
  echo "RESULT: FAIL"
  exit 1
fi
echo "RESULT: PASS"
exit 0
