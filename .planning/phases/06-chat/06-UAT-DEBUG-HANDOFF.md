# Phase 6 Chat UAT — Debug Handoff (2026-05-25)

**Use this as the opening prompt for a fresh Claude Code session in `/Users/adrian/Developer/job-rag/`. Copy from "Mission" down — paste as your first message.**

---

## Mission

Continue debugging the Phase 6 chat surface UAT. Phase 6 plans are all executed and committed (waves 0–3 complete via gsd-executor, plan 06-05 UAT scaffold committed). M1 ("happy path: chip → submit → stream tokens → tool chip → final → composer re-enables") is the blocker — every variant hangs. We've ruled out 4 infra bugs along the way and isolated the hang to **inside the FastAPI route handler at `/agent/stream`**. The agent works in isolation but not when invoked through the route. Top remaining hypothesis: **uvloop incompatibility with LangGraph's `agent.astream_events(version="v2")`**.

## Project context (read these first)

- `./CLAUDE.md` — frozen stack: Python 3.12 / FastAPI / LangGraph 1.1.x / PostgreSQL+pgvector / SQLAlchemy 2.x async / Vite + React + TS + Tailwind + shadcn/ui / Azure-only / single-user. Linear-dense aesthetic. €0/mo Year 1 budget.
- `.planning/STATE.md` — overall project status
- `.planning/ROADMAP.md` — Phase 6: Chat (5 plans, 5 waves). Phase 6.1 inserted: "Terraform value_wo lifecycle hardening — prevent KV secret re-wipe on future apply"
- `.planning/phases/06-chat/` — Phase 6 artifacts:
  - `06-CONTEXT.md` (32 locked decisions D-01..D-32)
  - `06-RESEARCH.md` (technical research)
  - `06-UI-SPEC.md` (verbatim JSX skeletons)
  - `06-PATTERNS.md` (analog files)
  - `06-VALIDATION.md` (test map)
  - `06-{01..05}-PLAN.md` (5 executed plans)
  - `06-{01..04}-SUMMARY.md` (4 completed wave summaries)
  - `06-UAT.md` (scaffold with 6 M-markers, all still pending)
- Active memory (auto-loaded): see `~/.claude/projects/-Users-adrian-Developer-job-rag/memory/MEMORY.md` — relevant entries:
  - `openapi-snapshot-ci-backend-audience.md`
  - `terraform-value-wo-overwrites-secret.md`
  - `aca-deploy-verifier-trap.md`
  - `aca-cold-start-profile.md`
  - `entra-external-id-iss-subdomain.md`

## What's deployed

- SWA: `https://witty-flower-065dac003.7.azurestaticapps.net/chat` — Phase 6 frontend live (last Deploy SPA success: commit `c97bd43`)
- ACA: `jobrag-prod-api` in `jobrag-prod-rg` — current revision `0000024` running cpu=1.0, memory=2Gi (bumped from 0.5/1Gi earlier today after OOM discovery)
- Sign-in: `adrian@jobrag.onmicrosoft.com`

## Phase 6 implementation status

| Wave | Plan | What it built | Status |
|------|------|---------------|--------|
| 0 | 06-01 | shadcn collapsible+textarea, types, blink CSS, 4 test stubs, sseMockUtils, DebugAgentStream `{message}`→`{query}` fix | ✓ Complete (4 commits) |
| 1 | 06-02 | Backend `/agent/stream` GET→POST + AgentQuery body + tests + OpenAPI snapshot regen + types.ts codegen | ✓ Complete (4 commits) |
| 2 | 06-03 | `streamAgent(query, signal)` helper + `useChatStream` hook + 7 activated tests | ✓ Complete (3 commits) |
| 3 | 06-04 | 5 presentation components + `/chat` route + 3 activated component tests (82 tests total, all green) | ✓ Complete (4 commits) |
| 4 | 06-05 | Live UAT runbook scaffold | ✓ Scaffold committed (`e639a55`); M1–M6 execution **BLOCKED** |

Frontend trifecta on `master`: typecheck ✓, lint ✓, build ✓, vitest 82/82 ✓ (Chat chunk 16.04 kB / 5.76 kB gzipped). Backend pytest 233 green.

## 5 infra bugs discovered during M1 (all fixed except #5)

### Bug #1: OpenAI KV secret was placeholder (FIXED ✓)
- **Symptom:** First M1 attempt → `Alert: Something went wrong / Error code: 401 - Incorrect API key provided: managed-*******band`
- **Root cause:** Commit `38f06eb` (2026-05-19) migrated 4 KV secrets from `value="managed-out-of-band"` to `value_wo + value_wo_version=1`. The `value_wo_version=1` trigger forced an unconditional KV write of the literal placeholder, wiping the real `sk-proj-…` key Adrian had seeded out-of-band on 2026-05-03. `lifecycle.ignore_changes = [value]` doesn't protect `value_wo`.
- **Fix applied:** `az keyvault secret set --vault-name jobrag-prod-kv --name openai-api-key --value '<real sk-proj-... key>'`
- **Memory captured:** `terraform-value-wo-overwrites-secret.md`

### Bug #2: Langfuse KV secrets also wiped (FIXED ✓)
- **Symptom:** After fixing #1, agent hung after `langfuse_handler_initialized` log
- **Root cause:** Same `38f06eb` migration wiped `langfuse-public-key` and `langfuse-secret-key` to the same `"managed-out-of-band"` placeholder. SDK got 401 from Langfuse Cloud. Handler initialization blocked the agent's first LLM call.
- **Fix applied:** Adrian set real `pk-lf-...` and `sk-lf-...` keys via `az keyvault secret set`, then `az containerapp update --set-env-vars _SECRET_REFRESH=...` to force new revision

### Bug #3: ACA `BACKEND_AUDIENCE` / `ENTRA_TENANT_ID` / `ENTRA_TENANT_SUBDOMAIN` env vars empty (FIXED ✓)
- **Symptom:** `fastapi_azure_auth` errored with `[Errno -2] Name or service not known` trying to load OpenID config; all auth endpoints returned 400
- **Root cause:** Values exist in `infra/envs/prod/prod.tfvars.local` (set 2026-05-23) but never propagated to ACA template — either `terraform apply` wasn't re-run with `-var-file=prod.tfvars.local`, or a prior `--set-env-vars` clobbered them. With empty subdomain + tenant_id, the OpenID URL becomes `https://.ciamlogin.com//v2.0/.well-known/openid-configuration` → DNS fails.
- **Fix applied:** `az containerapp update --set-env-vars "BACKEND_AUDIENCE=api://f4ced229-1b9d-4120-94aa-ade642e7fc43" "ENTRA_TENANT_ID=3fd51a76-f36e-43a1-aa37-564dad4c41fd" "ENTRA_TENANT_SUBDOMAIN=jobrag"`
- **Auth code reference:** `src/job_rag/api/auth.py` constructs URL from `settings.entra_tenant_subdomain` and `settings.entra_tenant_id`

### Bug #4: Container OOM (1 GiB too small) (FIXED ✓)
- **Symptom:** Agent hung silently after `agent_built` log; probe via `az containerapp exec` running `agent.astream_events(...)` produced `Killed` with exit code 137 (SIGKILL = OOM)
- **Root cause:** Container had `cpu=0.5, memory=1Gi`. Cross-encoder model preload (~600 MB with PyTorch) + FastAPI + SQLAlchemy + LangChain/LangGraph + agent invocation overhead exceeded 1 GiB. Kernel OOM-killed the process mid-request; ACA silently restarted; next request OOM'd again.
- **Fix applied:** `az containerapp update --cpu 1.0 --memory 2Gi` (Azure Consumption profile requires 1:2 CPU:GiB ratio; 0.5/2Gi was rejected with `ContainerAppInvalidResourceTotal`)
- **Long-term:** `infra/modules/compute/main.tf:104-105` hardcodes `cpu=0.5, memory="1Gi"` → next `terraform apply` reverts. Phase 6.1 scope should parameterize this.

### Bug #5: Agent hangs inside FastAPI route handler (NOT FIXED — current blocker)
- **Symptom:** With all of #1–#4 fixed, sending a chat message still hangs. UI sits at "Warming up the agent — this can take ~4 minutes after idle…" forever. Backend logs end at `agent_built` with no further activity. No OOM, no error, no traceback.
- **Critical diagnostic:** Running the EXACT same `agent.astream_events(version="v2")` code inside the container via `az containerapp exec python3` **works perfectly — 30 events in 0.70s with full LangGraph flow** (chain_start → ChatOpenAI streaming → 14 chunks → chain_end).
- **What's different:** Probe uses `asyncio.run()` → stdlib asyncio event loop. Route handler runs inside uvicorn → **uvloop** (because `uvicorn[standard]` includes uvloop and uvicorn's `--loop=auto` default picks it).
- **Confirmed not the cause:**
  - Memory (2 GiB has headroom; no OOM)
  - Langfuse handler (removed via `--remove-env-vars LANGFUSE_PUBLIC_KEY LANGFUSE_SECRET_KEY`; still hangs)
  - OpenAI SDK / HTTPX network egress (raw `client.chat.completions.create(stream=True)` from inside container returned 10 chunks in 1.22s)
  - Auth / JWT validation (POST `/agent/stream` returns 200 OK; dashboard endpoints return 200 with real data)
  - LangChain debug logging (LANGCHAIN_DEBUG=true + LANGCHAIN_VERBOSE=true produces no output after `agent_built`)

## Current state of `/agent/stream` request lifecycle

Looking at `src/job_rag/api/routes.py:383-475` (the `agent_stream` handler):

```python
async def typed_event_generator():
    current_task = asyncio.current_task()
    if current_task is not None:
        app.state.active_streams.add(current_task)
    try:
        try:
            async with asyncio.timeout(settings.agent_timeout_seconds):  # 60s
                async for event in stream_agent(payload.query):  # ← hangs here on first __anext__
                    yield to_sse(event)
        except TimeoutError: ...
        except asyncio.CancelledError: ...
        except Exception as e: ...
    finally:
        if current_task is not None:
            app.state.active_streams.discard(current_task)

return EventSourceResponse(
    typed_event_generator(),
    ping=settings.heartbeat_interval_seconds,  # 15s
    ping_message_factory=_heartbeat_factory,
    shutdown_event=app.state.shutdown_event,
    shutdown_grace_period=30.0,
    headers={"X-Accel-Buffering": "no", "Content-Encoding": "identity"},
)
```

And `src/job_rag/agent/stream.py:36-78`:

```python
async def stream_agent(query: str) -> AsyncIterator[AgentEvent]:
    agent = build_agent()
    callbacks = get_langchain_callbacks()
    config: dict[str, Any] = {"callbacks": callbacks} if callbacks else {}
    async for event in agent.astream_events(  # ← hangs at first __anext__
        {"messages": [HumanMessage(content=query)]},
        config=config,
        version="v2",
    ):
        ...
```

`agent_built` fires inside `build_agent()`. Then the `async for event in agent.astream_events(...)` loop is entered. The FIRST `__anext__` never returns. Heartbeats from sse-starlette continue (every 15s), keeping the SSE connection alive client-side, which is why the cold-start UI persists indefinitely.

## TOP HYPOTHESIS — uvloop incompatibility

The probe uses stdlib asyncio. The route uses uvloop (uvicorn default with `[standard]` extras). LangGraph's `astream_events(version="v2")` may have a bug that manifests only on uvloop. Confirming this is the next test.

### Confirming probe (run first in the new session)

```bash
az containerapp exec --name jobrag-prod-api --resource-group jobrag-prod-rg --revision jobrag-prod-api--0000024
```

At `$`:

```bash
python3 <<'PYEOF'
import asyncio, time
import uvloop
uvloop.install()  # ← key: simulate uvicorn's event loop
from langchain_core.messages import HumanMessage
from job_rag.agent.graph import build_agent

async def test():
    print('Building agent...')
    t0 = time.time()
    agent = build_agent()
    print('  built in %.2fs' % (time.time() - t0))
    print('Starting astream_events v2 on uvloop (30s budget)...')
    t0 = time.time()
    count = 0
    try:
        async for event in agent.astream_events(
            {'messages': [HumanMessage(content='say hi briefly')]},
            version='v2',
        ):
            count += 1
            elapsed = time.time() - t0
            if count <= 5 or count % 10 == 0 or event.get('event') in ('on_chain_end', 'on_chat_model_end'):
                print('  [%.2fs] #%d event=%s name=%s' % (elapsed, count, event.get('event'), event.get('name')))
            if elapsed > 30:
                print('  bailing at 30s')
                break
    except Exception as e:
        print('  ERR after %.2fs: %s: %s' % (time.time()-t0, type(e).__name__, e))
    print('Done after %d events in %.2fs' % (count, time.time() - t0))

asyncio.run(test())
PYEOF
```

**If this hangs (no events):** uvloop confirmed. Fix path:
1. Modify `scripts/docker-entrypoint.sh:line N` from `exec uvicorn job_rag.api.app:app --host 0.0.0.0 --port 8000` to `exec uvicorn job_rag.api.app:app --host 0.0.0.0 --port 8000 --loop asyncio`
2. OR remove `uvicorn[standard]` and use `uvicorn` (without uvloop/httptools extras)
3. Commit, push, wait for Deploy API, retry M1

**If this streams events (works on uvloop too):** uvloop ruled out. Move to backup hypotheses below.

## Backup hypotheses (if uvloop is ruled out)

### Hypothesis 2: `asyncio.timeout` + nested async generator interaction
Python 3.11+ `asyncio.timeout()` wrapping `async for` over a nested async generator has subtle edge cases. Test by temporarily replacing `asyncio.timeout(...)` with a no-op `nullcontext` in `routes.py`, redeploy, retest.

### Hypothesis 3: sse-starlette `EventSourceResponse` consumer issue
Maybe `EventSourceResponse` is not pumping the generator properly when `shutdown_event` is wired. Test by removing `shutdown_event=app.state.shutdown_event` and `ping_message_factory` from the EventSourceResponse construction.

### Hypothesis 4: Memory pressure inside uvicorn context (despite 2 GiB)
The standalone probe builds a fresh agent. Uvicorn's cached agent + cross-encoder + active connection pool + middleware stack may push memory near limit causing fragmentation that slows the event loop to a crawl. Test by bumping to 3 GiB (`--cpu 1.5 --memory 3Gi`) and checking if it works.

### Hypothesis 5: `app.state.shutdown_event` is incorrectly set
If the anyio event is already triggered (e.g., from a stale lifespan state), sse-starlette would suppress pings AND not pump the generator. Add a debug log to check `app.state.shutdown_event.is_set()` at request entry.

## Key file paths

| Path | Purpose |
|------|---------|
| `src/job_rag/api/routes.py:383-475` | `/agent/stream` POST handler with wrapping |
| `src/job_rag/agent/stream.py:36-78` | `stream_agent` async generator (calls `agent.astream_events`) |
| `src/job_rag/agent/graph.py` | `build_agent()` — creates ChatOpenAI + create_react_agent |
| `src/job_rag/observability.py` | Langfuse handler init (currently disabled in prod env) |
| `src/job_rag/api/auth.py` | `B2CMultiTenantAuthorizationCodeBearer` with openid_config_url |
| `src/job_rag/config.py` | Pydantic Settings — reads env vars |
| `scripts/docker-entrypoint.sh` | `exec uvicorn ...` line — modify for `--loop asyncio` |
| `infra/modules/compute/main.tf:104-105` | hardcoded `cpu=0.5, memory="1Gi"` |
| `infra/envs/prod/main.tf:136-180` | KV secret resources with `value_wo + value_wo_version=1` |
| `infra/envs/prod/prod.tfvars.local` | Real auth values (gitignored) |
| `frontend/src/components/chat/useChatStream.ts` | Hook with AbortController + cold-start timer |
| `frontend/src/api/agent.ts` | `streamAgent(query, signal)` POST wrapper |
| `frontend/src/routes/Chat.tsx` | `/chat` route composition |
| `.planning/phases/06-chat/06-UAT.md` | 6 M-markers (M1 blocked; M2 deferred — ACA warm; M3-M6 pending) |

## Key commands cheat sheet

```bash
# Active revision
az containerapp revision list --name jobrag-prod-api --resource-group jobrag-prod-rg --query "[?properties.active && properties.runningState=='RunningAtMaxScale'].name | [0]" -o tsv

# Latest logs
ACTIVE=$(az containerapp revision list --name jobrag-prod-api --resource-group jobrag-prod-rg --query "[?properties.active && properties.runningState=='RunningAtMaxScale'].name | [0]" -o tsv)
az containerapp logs show --name jobrag-prod-api --resource-group jobrag-prod-rg --revision "$ACTIVE" --type console --tail 60

# Interactive shell into container
az containerapp exec --name jobrag-prod-api --resource-group jobrag-prod-rg --revision "$ACTIVE"

# Force new revision (refresh KV secrets, env vars)
az containerapp update --name jobrag-prod-api --resource-group jobrag-prod-rg --set-env-vars _RESTART=$(date +%s)

# KV secret prefix check (no value leak)
az keyvault secret show --vault-name jobrag-prod-kv --name openai-api-key --query "{prefix_sk: value | starts_with(@,'sk-'), prefix_managed: value | starts_with(@,'managed'), length: length(value), updated: attributes.updated}" -o jsonc
```

## Open tasks (from this session)

- [ ] Confirm uvloop hypothesis via probe above
- [ ] If uvloop is the cause: modify `scripts/docker-entrypoint.sh` to add `--loop asyncio` flag, deploy, retest M1
- [ ] Once M1 passes: continue with M3 (tool chip + Dialog), M4 (Stop mid-stream), M5 (zero storage residue), M6 (≤30s recording). M2 (cold-start) deferred to next cold-ACA window
- [ ] Transcribe all M-marker results into `.planning/phases/06-chat/06-UAT.md`
- [ ] Flip 06-UAT.md frontmatter `status: testing` → `status: complete`
- [ ] Mark CHAT-01..06 complete in `.planning/REQUIREMENTS.md`
- [ ] Run `node "$HOME/.claude/get-shit-done/bin/gsd-tools.cjs" phase complete 06` to update ROADMAP/STATE
- [ ] Phase 6.1 scope expansion (currently single-fix for `value_wo` lifecycle) — add:
  - Parameterize `cpu`/`memory` in `infra/modules/compute/main.tf` (currently hardcoded 0.5/1Gi → need 1.0/2Gi for prod)
  - Migrate auth env vars (`BACKEND_AUDIENCE`, `ENTRA_TENANT_*`) to a state that survives `--set-env-vars` operations
  - Investigate root cause of bug #5 (uvloop or whichever it turns out to be) and add a regression test
  - Add `is_enabled()` placeholder check in `observability.py` (`value != "managed-out-of-band"` guard)
- [ ] Re-enable Langfuse after M1 passes (currently removed via `--remove-env-vars`) — re-add KV secretRefs

## Recent commits (last 24h)

```
26aa3c8 fix(06): regen openapi.snapshot.json with CI BACKEND_AUDIENCE for /access_as_user scope key
c97bd43 docs(04.1): close human_needed verification — 4/4 deferred items resolved
ab6bf6c chore(06): refresh STATE.md last_updated after UAT scaffold
e639a55 docs(06-05): scaffold 06-UAT.md with 6 M-markers as pending
2e82389 docs(06-04): rephrase Chat.tsx docstring
f8cb4fe docs(06-04): complete frontend presentation plan
7d56992 feat(06-04): wire /chat route + activate ToolChip/ChatComposer/ChatTranscript tests
82c6edc feat(06-04): build 5 chat presentation components per UI-SPEC §6a-§6e
c3eaa83 docs(06-03): complete frontend data layer plan
9946f2d feat(06-03): implement useChatStream hook + activate covering tests
ecc6ea2 feat(06-03): fill streamAgent typed POST wrapper for /agent/stream
66f409a docs(06-02): complete backend /agent/stream POST flip plan
d166450 style(06-02): collapse multi-line client.post call to single line
14bf177 feat(06-02): regenerate openapi.snapshot.json + types.ts for POST /agent/stream
7208a01 feat(06-02): flip /agent/stream from GET ?q= to POST {query} body
e6ae588 docs(06-01): complete chat Wave 0 foundation plan
bf94d6b feat(06-01): sseMockUtils + 4 skip-stub tests + DebugAgentStream body-key fix
3c5e323 feat(06-01): add chat types module + blink keyframes for streaming cursor
e8fbf2d feat(06-01): install shadcn collapsible + textarea primitives
cc66f83 docs(06): add validation strategy
c95c3e6 docs(06): research phase domain
3b045ef docs(06): create Phase 6 chat plans (5 plans, 4 waves)
d65bcf6 docs(06): record planning complete for chat phase
5bb3062 docs(06): pattern map analog files + code excerpts
```

## Start the new session like this

Open Claude Code in `/Users/adrian/Developer/job-rag/` and paste:

> Read `.planning/phases/06-chat/06-UAT-DEBUG-HANDOFF.md`, then follow it. Pick up at "TOP HYPOTHESIS — uvloop incompatibility" and run the confirming probe first.
