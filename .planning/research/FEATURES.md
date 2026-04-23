# Feature Research

**Domain:** Personal job-market / career-investigation web app (dashboard + streaming AI chat) on top of an existing RAG + LangGraph backend
**Researched:** 2026-04-23
**Confidence:** HIGH on comparisons to public products; MEDIUM on the specific "portfolio-signal" calibration (subjective)
**Scope note:** This research covers ONLY the new milestone features (dashboard, chat UI, resume upload, skill taxonomy cleanup, structured location). Backend retrieval/matching/gap features already ship and are treated as given.

## Framing

The project sits in a crowded category but with a distinctive angle. Commercial competitors split cleanly:

- **Tracker / autofill category** (Huntr, Simplify, Teal): application-lifecycle workflow, kanban boards, autofill, bulk-tailored resumes. They assume you already know what jobs to apply for; they optimize the act of applying.
- **Compensation / data category** (Levels.fyi, Glassdoor, Dice): salary benchmarking, percentile charts, skill-demand reports. They help you *orient* to a market but are not personalized — they don't know your CV.
- **Enterprise resume-parsing category** (Affinda, Textkernel, Sovren, MokaHR, Airparser): extract structured data from candidate CVs *for recruiters*, not for the candidate. High-precision parsers, no personal market view.
- **AI-native premium layers** (Teal+, Huntr Pro, Simplify+, LinkedIn Premium Career): paid AI resume tailoring, match scoring, keyword gap, AI-generated bullets. All opaque black-box scoring.

This project is uniquely positioned as *personalized market intelligence on a curated corpus, with an inspectable agent*. It is NOT trying to compete with Huntr on application tracking (out of scope per PROJECT.md) or Teal on resume bullet rewriting (out of scope). The core competitive angle is: **"I can see exactly which of my skills match which postings and watch the AI reason about it."** That maps directly to the AI-Engineer portfolio story (transparent RAG / agent / MLOps).

## Feature Landscape

### Table Stakes (Users Expect These)

Features a competent reviewer (or Adrian himself, as the primary user) will assume exist. Missing any of these makes the product feel half-built.

| Feature | Why Expected | Complexity | Portfolio Signal | Notes |
|---------|--------------|------------|------------------|-------|
| **Top-N skills widget with must-have vs nice-to-have split** | Glassdoor, LinkedIn, Dice all show "top skills" for a role. Splitting must/nice is a unique insight this corpus already has — leaving it flat would *waste* existing signal. | LOW | MEDIUM | Backend already computes this (`/gaps`). Frontend is a sorted bar list + badge. Show top 8–10 with a "show more" drill. |
| **Salary bands (p25 / p50 / p75)** | Industry standard across Levels.fyi, Glassdoor, Payscale, databenchmarks.com. Users literally cannot orient without percentiles. | LOW-MEDIUM | MEDIUM | Requires SQL with PERCENTILE_CONT. Need to handle postings without salary (common — ~40-60% of EU postings omit salary). Display "N postings had salary data" as a footnote. |
| **Country / seniority / remote filter bar** | Levels.fyi and Glassdoor both default to location + level filters. Without them the numbers are meaningless (Berlin AI-Engineer ≠ SF AI-Engineer). | LOW | LOW | Unblocked by structured `Location` schema (Active requirement). Filters: Poland / Germany / EU / Worldwide + Junior/Mid/Senior/Lead + Remote toggle. Store filter state in URL query params so links are shareable. |
| **CV-vs-market match score** | Teal, Huntr, Simplify, Jobscan all show a 0–100% match score. Without one, the app looks like a read-only dashboard. | MEDIUM | HIGH | Backend already computes per-posting (`match_profile`). Aggregate = mean-of-means across filtered set. Show the number + a 1-line explanation ("matched X of Y must-haves across Z postings"). |
| **Streaming chat with incremental token render** | ChatGPT normalized this in 2023; anything slower than token-by-token feels broken. | LOW | LOW (table stakes now) | Backend already streams (`/agent/stream`). Frontend only needs an SSE reader that appends to the assistant bubble. |
| **Resume upload (PDF + DOCX)** | Every resume tool from Teal to Simplify accepts both. PDF-only is a red flag in EU markets where DOCX dominates. | MEDIUM | MEDIUM | Text extraction: `pypdf` for PDF, `python-docx` for DOCX. LLM parses to structured skills via Instructor (pattern already in codebase for postings). |
| **Reviewable extracted-skills panel (tick/untick/edit)** | Every parser that touches user data (Teal, Huntr, LinkedIn skill endorsements) has a "confirm" step. Skipping it = users feel the tool added wrong skills and lost trust. | MEDIUM | HIGH | This is also the single most direct "inspectable AI" demo in the product. Show each extracted skill with a checkbox, source line preview if feasible, and an inline edit. |
| **Login / identity (even for single user)** | With the app deployed publicly, a login wall is mandatory for the OpenAI-billed endpoints. Users expect "sign in" rather than a raw passphrase. | MEDIUM | HIGH | Entra ID External Identities is in Active scope. Table stakes *with* a portfolio-signal multiplier — direct Azure-identity talking point. |
| **Empty states and loading skeletons** | Every modern SaaS has them. An unhandled null state feels broken. | LOW | LOW | Dashboard needs skeletons for 3 widgets; chat needs a "thinking…" placeholder until first token. |
| **Error handling in chat (tool failure, timeout)** | If `/agent/stream` errors mid-stream, the UI must show a graceful message, not a silent freeze. | LOW | MEDIUM | Active requirement already covers backend (SSE error event + 60s timeout). Frontend just needs to render the error event. |

### Differentiators (Competitive Advantage)

Features that distinguish this product from the competitor landscape. Each is evaluated on the two axes that matter for this project: does it help Adrian's job hunt, and does it land in interviews?

| Feature | Value Proposition | Complexity | Portfolio Signal | Notes |
|---------|-------------------|------------|------------------|-------|
| **Inspectable agent tool calls (tool_start / tool_end chips)** | **THE** key differentiator. Teal, Huntr, Simplify all have opaque AI scoring. Rendering `"→ calling search_jobs({query: 'Azure', seniority: 'senior'})"` and then the output makes the reasoning legible. In interviews this is a direct demo of "I can ship production agent UX, not just call ChatGPT." | MEDIUM | **VERY HIGH** | shadcn/ai and assistant-ui both ship this pattern — study their SSE contract and build a shadcn-styled version. Use a collapsed chip by default, expandable to show args + result. |
| **CV-vs-market score *against a known corpus*, not a single JD** | Teal / Jobscan score your resume against *one* job description you paste in. This project scores against *all filtered postings simultaneously*. That's a different, more honest signal — you learn which markets fit you, not how to cheat one JD. | MEDIUM | HIGH | Reuses existing `match_profile` logic aggregated. Differentiates on *honesty*: no keyword-stuffing optimization loop. |
| **Show-and-confirm resume extraction with source-line evidence** | Most parsers return a JSON. Enterprise tools (Textkernel, Affinda) include "context where skill appeared." Consumer tools skip it. Doing this makes the AI auditable — a direct AI-Engineer interview talking point. | MEDIUM-HIGH | HIGH | Ambitious v1 variant: store the resume text chunk that justified each skill, so the review panel can show "extracted 'PostgreSQL' from: '...led migration from MySQL to PostgreSQL...'" Fallback: just the extracted-skills list with checkboxes. |
| **Country filter with ISO-coded structured location** | Glassdoor and LinkedIn tie salary to city strings (noisy). The structured `Location` schema (Active requirement) enables clean country rollups — especially the Poland / Germany / EU / Worldwide split that's directly relevant to Adrian's target market. | LOW-MEDIUM | MEDIUM | Depends on the one-time re-extraction with bumped PROMPT_VERSION. Once shipped, the filter is "cheap" to expose. |
| **Hard / soft / domain skill categorization filter** | Current `skill-gaps.json` has "communication 15.7%" polluting the top of the list — a textbook LLM extraction failure visible in the reviewer's first screenshot. The `SkillCategory` enum (Active requirement) fixes this. Default dashboard view: hide soft skills. | LOW on frontend (dropdown + enum check) | HIGH | This is also your "I know my own system's failure modes and have a mitigation" story. Exactly the kind of self-aware engineering signal interviewers look for. |
| **Curated corpus, not noisy firehose** | Indeed / LinkedIn feed you thousands of stale postings. 108 curated AI-Engineer postings is a *feature*, not a bug — every posting was hand-picked, so every number is meaningful. | ZERO (inherent to the scope) | MEDIUM | Worth a single sentence on the README / dashboard header: "Curated from ~108 Berlin/remote AI-Engineer postings (2025–2026)." Makes sample size visible instead of hiding it. |
| **Terraform-provisioned identity + container + Postgres on Azure free tier** | Not a UX feature, but the fact that the whole stack is IaC-on-Azure-free-tier is the implicit differentiator for the portfolio reading. Visible in the README, architecture diagram, and deploy pipeline. | (covered by separate milestone scope) | VERY HIGH | Out of scope for THIS features list — flagged so it's not lost. |
| **Filter state in URL query params (shareable dashboard views)** | Levels.fyi does this; most dashboards don't. Lets you link "Germany senior remote" and have someone else see the same numbers. | LOW | LOW-MEDIUM | A small quality signal that shows you care about the UX tail. |
| **Keyboard shortcuts in Linear style (/, G+D, G+C)** | Matches the Linear aesthetic from PROJECT.md. Most job tools are mouse-first. | LOW | LOW | Optional polish. Not v1-critical but fits the "dense" aesthetic commitment. |

### Anti-Features (Commonly Requested, Often Problematic)

Features that would seem obvious to add but are deliberately out. All of these appear in PROJECT.md's Out of Scope; restating here with explicit reasoning so the roadmap doesn't drift.

| Feature | Why Tempting | Why Problematic Here | Alternative |
|---------|--------------|---------------------|-------------|
| **Kanban job-application tracker** | Huntr / Teal / Simplify all have this — it's their flagship. | Adrian isn't tracking dozens of applications; he's investigating a market. Adding a kanban blurs the positioning ("is this Huntr or a research tool?") and triples the schema. | Out. If ever relevant, a single `applications` table with a lightweight status enum would suffice. |
| **AI resume bullet rewriter / tailored resume generator** | Huntr Pro ($40/mo) and Teal+ make this their core paid feature. | This project's core value is *honest* CV-vs-market fit. Keyword-stuffing a resume to game a JD is the opposite. Also — it's commodity now (Huntr wins on UX polish, this project wins on transparency). | Show the gap, let the user decide what to learn. No auto-rewrite. |
| **Chat conversation history / branching** | Every chat UI has it post-ChatGPT. | Explicitly out per PROJECT.md. The v1 story is "single-turn, clear-on-refresh." Persisting conversations means a `conversations`/`messages` schema, pagination, and a sidebar — weeks of scope for a single user. | Clear-on-refresh is fine. If history ever matters, the `user_id` column is already in place. |
| **Interactive drill-down dashboard (clickable charts, skill co-occurrence graphs, time-series trends)** | Looks impressive in demos. | Out per PROJECT.md. With 108 postings, time-series is noise; co-occurrence adds graph-DB complexity for marginal value. | Static snapshot with a "show more" expansion on the skills list is enough. |
| **Automated job-posting scrapers (LinkedIn / Indeed)** | "Real-time market data" is a headline feature in ads. | Scraping LinkedIn is against their ToS and would tank the portfolio story if noticed. Adrian curates manually via CLI; the `IngestionSource` Protocol accommodates future plug-ins. | Explicit value: "curated, not scraped." |
| **Multi-user sign-up / team workspaces** | "Platform-ready" is a pitch phrase. | Out per PROJECT.md. Schema carries `user_id` everywhere; adding sign-up UX is a full feature including email verification, invitations, RLS. | Entra ID tenant is configured; Adrian is the only seeded user. Structure is there; UX is not. |
| **Chrome extension for bookmarking postings** | Teal's #1 acquisition channel (4.9★, 50+ boards). | Scope explosion (manifest V3 permissions, cross-origin messaging). Adrian ingests via CLI, which is faster for him. | CLI `ingest` is the "extension." |
| **Autofill job applications across 100+ ATSes** | Simplify's flagship. | This is a 2-year engineering project involving fragile DOM adapters per ATS. Not what this app is for. | Out. No UI touches it. |
| **AI cover letter generator** | Huntr, Teal, Simplify all have it. | Commodity, opaque, easy to mis-demo ("why did the AI say I had 3 years of Kubernetes?"). Not the portfolio angle. | Out. |
| **Billing / payments / plan tiers** | Looks "product-y." | Single user, Adrian pays his own OpenAI bill. Stripe integration is a whole side-quest. | Out. |
| **Real-time salary updates / live data feeds** | Levels.fyi's pitch. | Requires continuous ingestion (scrapers, scheduled jobs) — antithetical to the curated-corpus premise. | Static snapshot with an "ingested up to {date}" label. |
| **Canonical skill taxonomy (full ESCO / O*NET alignment)** | The academically "right" thing. ESCO is EU-standard, 13,939 skills. | Out per PROJECT.md. `SkillCategory` (hard/soft/domain) is enough for v1 and closes the current soft-skill-noise gap with ~5% of ESCO's complexity. | v2 candidate. Gap between O*NET/ESCO and real postings is 12–18 months anyway — live data beats taxonomy for this scope. |
| **Progress tracking over time (skill-gap deltas week-over-week)** | Feels valuable. | Requires time-series schema, baseline snapshots, delta computation. With 108 static postings, the delta is zero. | Out. If time-series is ever added, a single `skill_gap_snapshots` table suffices. |
| **Interview question practice / mock interview mode** | Tempting cross-sell. | Completely out of scope — different product. | Out. Don't drift. |

## Feature Dependencies

```
Backend prep (CORS, SSE schema, reranker preload, timeout)
    └──required by──> Chat UI (all streaming features)
    └──required by──> Dashboard (all endpoints)

Structured Location schema + re-extraction
    └──required by──> Country filter
    └──required by──> EU/Germany/Poland dashboard views

SkillCategory enum + re-extraction
    └──required by──> Hard/Soft/Domain filter
    └──required by──> "Clean" top-skills widget (soft skills hidden by default)

UserProfile DB model (replaces data/profile.json)
    └──required by──> Resume upload persistence
    └──required by──> CV-vs-market match score (must read from DB, not JSON)
    └──required by──> Reviewable skills panel (writes confirmed skills back)

Resume upload endpoint (PDF/DOCX extract → Instructor)
    └──required by──> Reviewable skills panel
    └──enhances────> CV-vs-market match score (keeps it fresh without CLI edits)

Entra ID auth
    └──required by──> Any public deployment (currently the ONLY user context)
    └──required by──> user_id foreign keys having a real user to attach to

MSAL React + API client
    └──required by──> Chat and Dashboard network calls under auth

Frontend shell (Vite + React + Tailwind + shadcn/ui)
    └──required by──> Every frontend feature

Chat UI token rendering
    └──enhanced-by──> Tool-call chip rendering (separate SSE event types)

Dashboard filter bar
    └──shared-by──> Top-skills widget, salary bands widget, match score widget
    └──conflicts-with──> None (filters are purely additive)
```

### Dependency Notes

- **Re-extraction with PROMPT_VERSION bump is a hard prerequisite** for both Country filter and SkillCategory filter. These two features *should ship as a pair* — the one-time extraction cost happens once, and both filters become cheap on the frontend afterward.
- **UserProfile DB model is a blocker for three features** (resume upload persistence, match-score freshness, skills-review persistence). If it's delayed, those three features fall over together. Schedule it early.
- **Entra ID is a blocker for public deployment** but NOT for local development. The frontend shell can be built and tested against an unauth'd local API, then gated behind MSAL once the tenant is provisioned. This is the natural "build locally, wrap with auth last" sequencing.
- **Tool-call chips are additive on top of token streaming.** You can ship token streaming alone and have a working chat; chips are a layered enhancement. If scope tightens, chip rendering can slip 1 iteration without breaking chat.
- **Filter bar is a shared dependency for all three dashboard widgets.** Build the filter state + URL sync *once*, wire all three widgets to the same state. Doing widgets in isolation creates triplicate filter code.
- **No hard conflicts between listed features.** The only near-conflict is soft-skill display: the `SkillCategory` filter defaults MUST hide soft skills, otherwise the visible "communication 16%" gap undermines the product's credibility on first impression.

## MVP Definition

### Launch With (v1)

Ruthless MVP. Each item is necessary for the product to be demoable and honest.

- [ ] Frontend shell (Vite + React + TS + Tailwind + shadcn/ui), Linear-dense theme
- [ ] Top-nav with Dashboard / Chat, Entra ID login wall
- [ ] Dashboard filter bar (country / seniority / remote) with URL-state sync
- [ ] Top-skills widget with must-have / nice-to-have split + "show more"
- [ ] Salary bands widget (p25 / p50 / p75) with "N postings had salary" footnote
- [ ] CV-vs-market aggregate match score widget
- [ ] Chat page with streaming tokens (SSE reader against `/agent/stream`)
- [ ] Tool-call chips (collapsed by default, click to expand args + result)
- [ ] Resume upload endpoint (PDF + DOCX) with Instructor extraction
- [ ] Reviewable extracted-skills panel with tick/untick/edit and save
- [ ] `SkillCategory` filter defaults to hiding soft skills on the dashboard
- [ ] Structured `Location` backing the country filter
- [ ] Loading skeletons + empty states + SSE error rendering
- [ ] Single-turn chat with clear-on-refresh (no history)

### Add After Validation (v1.x)

Cheap enhancements once v1 works. Trigger is "Adrian uses it and wants more."

- [ ] Keyboard shortcuts (/ to focus chat input, G+D / G+C to navigate, Esc to clear)
- [ ] Dashboard widget: skill overlap heatmap (which of my skills appear across most postings)
- [ ] Resume extraction with source-line evidence (show which sentence justified each skill)
- [ ] Persist chat history for the current user (enabled by existing `user_id` column, not schema change)
- [ ] Export dashboard view as PDF / PNG (for sharing with career coaches, recruiters)
- [ ] Dark / light mode toggle (shadcn/ui makes this cheap)
- [ ] Basic analytics: "which postings contributed the most to my low match score"

### Future Consideration (v2+)

Real work. Defer until v1 proves useful and new need emerges.

- [ ] Interactive drill-down dashboard (clickable charts, skill co-occurrence graphs)
- [ ] Time-series / trend analysis (requires scheduled re-ingestion)
- [ ] Automated ingestion plug-ins (starting with a ToS-safe source)
- [ ] Multi-user sign-up / team workspace UX
- [ ] ESCO / O*NET canonical taxonomy integration
- [ ] Conversation branching / multi-threaded chat
- [ ] Full MLOps loop (drift detection, A/B harness)
- [ ] Career-investigation pivot: learning resource recommender, portfolio project generator

## Feature Prioritization Matrix

Priority reflects BOTH user-value (Adrian using it) AND portfolio-signal (interview story). A feature with LOW user-value but HIGH portfolio-signal still ranks P1 because the portfolio is a first-class goal for this project.

| Feature | User Value | Impl Cost | Portfolio Signal | Priority |
|---------|------------|-----------|------------------|----------|
| Frontend shell + login wall | HIGH | MEDIUM | HIGH (Entra ID story) | P1 |
| Filter bar (country / seniority / remote) | HIGH | LOW | MEDIUM | P1 |
| Top-skills widget with hard/soft filter | HIGH | LOW | HIGH (soft-skill cleanup story) | P1 |
| Salary bands p25/p50/p75 | HIGH | LOW-MEDIUM | MEDIUM | P1 |
| CV-vs-market match score | HIGH | MEDIUM | HIGH | P1 |
| Streaming chat (tokens only) | HIGH | LOW | MEDIUM | P1 |
| Tool-call chips (start/end) | MEDIUM | MEDIUM | **VERY HIGH** | P1 |
| Resume upload (PDF + DOCX) | HIGH | MEDIUM | HIGH | P1 |
| Reviewable extracted-skills panel | HIGH | MEDIUM | HIGH | P1 |
| Structured Location re-extraction | MEDIUM | MEDIUM (one-time) | MEDIUM | P1 |
| SkillCategory enum re-extraction | MEDIUM | LOW-MEDIUM | HIGH | P1 |
| Source-line evidence in skill extraction | MEDIUM | MEDIUM-HIGH | HIGH | P2 |
| URL-synced filter state | MEDIUM | LOW | LOW-MEDIUM | P2 |
| Loading skeletons | LOW | LOW | LOW (table stakes) | P2 |
| Keyboard shortcuts | LOW | LOW | LOW | P3 |
| Chat history persistence | MEDIUM | MEDIUM | LOW | P3 (post-v1) |
| Skill overlap heatmap | LOW | MEDIUM | MEDIUM | P3 |
| Dark mode toggle | LOW | LOW | LOW | P3 |
| Export dashboard as PDF/PNG | LOW | MEDIUM | LOW | P3 |
| Interactive drill-down | LOW | HIGH | LOW-MEDIUM | P3 (v2) |

**Priority key:**
- **P1** — Must have for v1 launch. In the Active requirements list.
- **P2** — Should have, land in v1 if time allows, otherwise first v1.x.
- **P3** — Defer to post-MVP. Protects against scope creep.

## Competitor Feature Analysis

Direct comparison of the five v1 features against the main competitor surfaces. Each row answers: how does each competitor do this, and what is *our* differentiated approach?

### Dashboard (top-skills, salary bands, match score, filters)

| Aspect | Levels.fyi | Glassdoor | Dice | Teal / Huntr | This Project |
|--------|------------|-----------|------|--------------|--------------|
| Data source | User-submitted offers, 1M+ data points | Salary estimates via ML model + reviews | User-submitted + employer postings | JDs user pastes in | Curated markdown corpus (~108 AI-Engineer postings) |
| Skill ranking | Skill Index in paid Google Sheet export | Per-role "skills section" (free-text) | "Most in-demand skills" in annual report | Keyword gap per resume vs one JD | Top-N must-have / nice-to-have per filtered slice |
| Salary percentiles | p25/p50/p75 per company+level+location | "Most likely range" = p25–p75 band | Median per role | Not a core feature | p25/p50/p75 per country / seniority / remote slice |
| Location filter | City + company-specific | City-level, noisy | US-centric | Not a filter (per-JD) | Country ISO-backed: Poland / Germany / EU / Worldwide |
| Seniority filter | Company-specific level (L3, E4, etc) | Title-string heuristic | Title-string heuristic | None | Structured `SeniorityLevel` enum |
| CV-vs-market | None (not personalized) | None | None | Per-JD match score, opaque | Aggregate across filtered corpus, with per-posting reasoning available via chat |
| "Portfolio moment" | N/A | N/A | N/A | N/A | Dense Linear-style dashboard + "my skills vs 108 real AI-Engineer postings" pitch |

### Chat (streaming, tool-call chips)

| Aspect | ChatGPT | Huntr AI Resume | Teal AI | LinkedIn Premium | This Project |
|--------|---------|-----------------|---------|------------------|--------------|
| Streaming | Token-by-token | Token-by-token | Token-by-token | Partial (some features) | Token-by-token via SSE |
| Tool-call visibility | Collapsed by default (Deep Research, browsing) | Hidden | Hidden | Hidden | **Inline chips with args + result preview** |
| Agent framework visible to user | No | No | No | No | **Yes (LangGraph ReAct with 3 named tools)** |
| Single-turn vs multi-turn | Multi-turn, history | Single-turn per feature | Single-turn per feature | Single-turn | Single-turn, clear-on-refresh (v1) |
| "Portfolio moment" | N/A | N/A | N/A | N/A | Ability to screen-record "watch the agent call `search_jobs`, then `analyze_gaps`, then synthesize" in 30s |

Differentiation: **transparency**. Every commercial tool above hides the agent scaffolding. Exposing tool calls is the one place this project can plausibly outshine a $40/mo SaaS.

### Resume upload + reviewable panel

| Aspect | Affinda / Textkernel / Sovren | Airparser | Teal / Huntr | Simplify | This Project |
|--------|-------------------------------|-----------|--------------|----------|--------------|
| Target user | Recruiters | Recruiters | Job seekers | Job seekers | Job seekers (self) |
| Formats | PDF, DOCX, +more | GPT-based, many formats | PDF, DOCX | PDF, DOCX | PDF + DOCX |
| Extraction engine | Proprietary NLP | GPT-powered | GPT-powered | GPT-powered | Instructor + GPT-4o-mini |
| Review step | Bulk dashboard for recruiters | Per-document review | "Confirm" UX varies | Minimal; extracted data used silently | **Explicit tick/untick/edit panel before save** |
| Evidence / source context | Yes (section context + inferred proficiency) | Per-field confidence | No | No | **Aspirational for v1** (source-line preview if storage allows) |
| Auditable LLM step | No (black box) | Yes (configurable prompts) | No | No | **Yes (extraction endpoint + review panel)** |

Differentiation: **user-facing transparency of an LLM extraction step**. Recruiters get this from Affinda; job seekers currently don't. Showing the user "here's what the LLM thought you had, check it" is an underexposed UX pattern and an AI-Engineer interview asset.

### Skill taxonomy (hard / soft / domain)

| Aspect | ESCO / O*NET | LinkedIn skills graph | Dice skill tags | Teal / Huntr keyword gap | This Project |
|--------|--------------|----------------------|-----------------|-------------------------|--------------|
| Classification | Full multi-level taxonomy (13,939 skills) | Proprietary, opaque | Tag-based, flat | Free-text keywords from JD | 3-enum: hard / soft / domain |
| Soft-skill noise | Categorized separately | Included but surfaced as endorsements | Rarely tagged | Included (keyword match!) | **Filtered out of default dashboard view** |
| Alignment to markets | Static (12–18mo lag vs live data) | Dynamic, proprietary | Live data | Per-JD | Live from curated corpus |
| Complexity to implement | Months (14k skills, multilingual) | N/A (proprietary) | Simple tag model | N/A (no real taxonomy) | Days (enum + prompt update) |

Differentiation: **pragmatic minimum-viable taxonomy**. Three-bucket enum solves 80% of the soft-skill noise problem for ~5% of ESCO's complexity. The *decision* to skip full ESCO is itself a portfolio point ("I picked the smallest taxonomy that closed the visible defect").

### Structured location

| Aspect | Levels.fyi | Glassdoor | LinkedIn Jobs | Teal / Huntr | This Project |
|--------|------------|-----------|---------------|--------------|--------------|
| Representation | Free-text city, company-normalized | Free-text city | Free-text, parsed by LinkedIn | Free-text (copied from JD) | **Structured: country ISO + city + region + remote_allowed** |
| Country rollup | Per-country pages, partly manual | City → country lookup | Inferred | None | **Native on filter bar (Poland / Germany / EU / Worldwide)** |
| Remote handling | "Remote" as a location string | "Remote" flag | Remote tag | Free-text | **Boolean + free-text combo** |

Differentiation: **analytical SQL on ISO-coded location** — small, but exactly the right shape for the target use case ("show me Germany vs EU vs remote AI-Engineer market") and for honest percentile math.

## Portfolio-Signal Summary

What makes this project land in an AI-Engineer interview, ranked by strength:

1. **Inspectable agent (tool-call chips)** — unique vs every listed competitor. Screen-recordable in 30s.
2. **Reviewable LLM extraction (resume skills panel)** — consumer-tool version of enterprise-grade auditability.
3. **SkillCategory cleanup with a visible "before"** — "Here's the soft-skill noise the LLM produced; here's how I fixed it with a typed enum and prompt version bump." Direct story about knowing your system's failure modes.
4. **Entra ID External Identities + Terraform + Azure free tier** — covered by other research files, flagged here so features research doesn't double-count.
5. **CV-vs-corpus match score (not vs a single JD)** — intellectually honest. Easy to explain why.
6. **Linear-dense dashboard with URL-shareable filters** — signals front-end craft without being flashy.

Things that are *table stakes* and don't move the needle alone (but missing them would hurt): streaming chat, PDF+DOCX upload, login wall, empty states, error handling.

## Sources

- [Teal HQ Review 2026 (ResumeHog)](https://resumehog.com/blog/posts/teal-hq-review-2026-is-this-job-search-tool-worth-it.html)
- [Teal Resume-Job Description Match tool](https://www.tealhq.com/tool/resume-job-description-match)
- [Huntr.co homepage and product pages](https://huntr.co/)
- [Huntr AI Resume Tailor](https://huntr.co/product/resume-tailor)
- [Simplify Copilot (autofill + AI resumes)](https://simplify.jobs/copilot)
- [Simplify Jobs Review 2026 (AutoApplier)](https://www.autoapplier.com/blog/simplify-jobs)
- [Levels.fyi — main site](https://www.levels.fyi/)
- [Levels.fyi real-time compensation benchmarking](https://www.levels.fyi/offerings/data/)
- [Levels.fyi salary range and compensation charts](https://www.levels.fyi/charts.html)
- [Glassdoor Worklife Trends 2026](https://www.glassdoor.com/blog/worklife-trends-2026/)
- [Glassdoor Data Engineer salary (Germany)](https://www.glassdoor.com/Salaries/germany-data-engineer-salary-SRCH_IL.0,7_IN96_KO8,21.htm)
- [Dice Tech Job Report (February 2026)](https://www.dice.com/recruiting/ebooks/dice-tech-job-report/)
- [Dice Tech Salary Report](https://www.dice.com/technologists/ebooks/tech-salary-report/)
- [LinkedIn Premium Career features](https://premium.linkedin.com/careers/career)
- [LinkedIn skill-match tool announcement (Social Media Today)](https://www.socialmediatoday.com/news/linkedin-releases-new-tool-to-highlight-how-your-skills-match-advertised-po/523493/)
- [Best AI Resume Screening Tools 2026 (HackerEarth)](https://www.hackerearth.com/blog/ai-resume-screening-tools)
- [Resume parsing with LLMs (Datumo)](https://www.datumo.io/blog/parsing-resumes-with-llms-a-guide-to-structuring-cvs-for-hr-automation)
- [ResumeFlow: LLM-facilitated resume pipeline (arXiv)](https://arxiv.org/html/2402.06221v1)
- [Resume parsing with LLM + Sensible](https://www.sensible.so/blog/how-to-extract-data-from-resumes-with-llms-and-sensible)
- [Unstract — LLMs for structured PDF extraction](https://unstract.com/blog/comparing-approaches-for-using-llms-for-structured-data-extraction-from-pdfs/)
- [ESCO Classification (European Commission)](https://esco.ec.europa.eu/en/classification)
- [ESCO Skills and Competences pillar](https://esco.ec.europa.eu/en/classification/skill_main)
- [ESCOX: LLM-based ESCO skill extractor (ScienceDirect)](https://www.sciencedirect.com/science/article/pii/S2665963825000326)
- [shadcn/ai React components for AI chat](https://www.shadcn.io/ai)
- [Blazity shadcn-chatbot-kit (GitHub)](https://github.com/Blazity/shadcn-chatbot-kit)
- [assistant-ui (tool-call rendering primitive)](https://www.assistant-ui.com/)
- [Vercel AI SDK 6 release notes](https://vercel.com/blog/ai-sdk-6)
- [AI SDK streaming foundations docs](https://ai-sdk.dev/docs/foundations/streaming)
- [Linear design aesthetic in UI libraries (LogRocket)](https://blog.logrocket.com/ux-design/linear-design-ui-libraries-design-kits-layout-grid/)
- [Dashboard design patterns 2026 (Art of Styleframe)](https://artofstyleframe.com/blog/dashboard-design-patterns-web-apps/)
- [Europe data salary benchmark (databenchmarks.com)](https://www.databenchmarks.com/salary-benchmark)

---
*Feature research for: personal job-market / career-investigation web app*
*Researched: 2026-04-23*
