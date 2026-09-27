# YojnaSetu — Implementation Plan and Status

Source of truth: [`YojnaSetu.md`](../../YojnaSetu.md). This file tracks decisions, tasks, and
verified progress. Status key: `[✓]` done and verified · `[→]` in progress · `[ ]` pending ·
`[!]` manual action required · `[✗]` blocked.

## 1. Baseline (2026-09-27, before any implementation)

- `[✓]` Specification present (`YojnaSetu.md`, 53 features).
- `[ ]` No application code, no git history; GitHub repo exists and is empty.
- `[✓]` MongoDB Atlas project `YojnaSetu` exists — no cluster, no DB users, no network access entries.
  Free M0 cluster `yojnasetu-cluster` (AWS Singapore) created during setup.
- `[ ]` No credentials configured (Gemini, Groq, data.gov.in, API Setu, MongoDB URI).
- `[✗]` data.gov.in catalog/search returned 504 / edge errors during analysis (external outage).
- `[?]` myScheme search-response shape and LLM/embedding model IDs need live verification.

## 2. Decisions

| ID | Decision | Why |
|---|---|---|
| D1 | Detailed scheme content comes from the **official myScheme API published on API Setu** (MeitY), `GET https://apisetu.gov.in/meity/myscheme/srv/v7/...` (search, details, documents, FAQs), auth headers `X-APISETU-CLIENTID` / `X-APISETU-APIKEY`. | The spec requires official sources and forbids unofficial APIs. The spec assumed myScheme had no public API; API Setu documents one, so the official route is used. Every record keeps its myScheme page URL as the official source. |
| D2 | data.gov.in OGD API (`https://api.data.gov.in/resource/{id}`) supplies additional official datasets. Resource IDs are configured only after they are verified live — none are guessed. Tabular data is cleaned with SQL (Python stdlib `sqlite3`) before loading. | Spec §Government Data; OGD does not publish complete scheme details. |
| D3 | **Gemini** produces all embeddings and is the primary generator; **Groq** is the generation fallback. Model IDs are overridable by env var and verified with a live call. | Groq offers no embedding models; the fallback keeps AI answers available when one provider fails or rate-limits. |
| D4 | Semantic search uses **Atlas Vector Search** on `scheme_chunks.embedding`; related schemes reuse the same index. Keyword search uses a native MongoDB `$text` index. Local dev and tests use the `mongodb/mongodb-atlas-local` image. | Spec mandates Atlas storage for embeddings; no extra vector database. |
| D5 | FastAPI owns embeddings, retrieval, RAG and LLM calls. Spring Boot owns keyword search, filters, eligibility and orchestration, and is the only caller of FastAPI (shared internal token, fails closed when unset). | Spec §46–47. |
| D6 | Eligibility is a deterministic field-by-field rule engine in Spring Boot over structured rules stored on each scheme. Rules come only from official structured fields; unknown rules yield **More information needed**. The LLM only rephrases the engine's result. | Spec §6–12; no opaque scoring, no fabricated conditions. |
| D7 | Combined keyword + semantic results are merged with reciprocal rank fusion and de-duplicated by scheme id. | Spec §29; transparent, parameter-light. |
| D8 | Ingestion lives in the Python AI project (`AI/ingestion`) and reuses its embedding client; re-runs re-embed only chunks whose content hash changed. | Spec §40–42; one Python dependency set. |
| D9 | Deployment: backend + AI service as Docker web services on Render (Singapore); frontend on Vercel; CI in GitHub Actions triggers Render deploy hooks after tests pass. | Spec §50–53; Atlas cluster is co-located in Singapore. |
| D10 | AI endpoints are rate limited per client and globally (in-memory, single instance). | LLM cost and abuse control. |

## 3. Assumptions

- English content (`lang=en`) first; the spec does not require other languages.
- No user accounts: every public endpoint is read-only and eligibility inputs are never stored.
- Free tiers (Atlas M0, Render, Vercel Hobby, Gemini, Groq) are the deployment target.

## 4. Architecture

```
React (Vercel) ──REST/JSON──> Spring Boot (Render) ──> MongoDB Atlas (schemes, $text, filters)
                                   │  eligibility engine
                                   └──REST + internal token──> FastAPI (Render)
                                                                 ├─ Gemini: embeddings, generation
                                                                 ├─ Groq: generation fallback
                                                                 └─ Atlas Vector Search (scheme_chunks)
Government sources (API Setu myScheme, data.gov.in OGD) ──> AI/ingestion ──> MongoDB Atlas
```

## 5. Tasks

### Phase 1 — Foundation
- `[✓]` **YS-001** Repository foundation: ignore rules, env template, this plan. *Verify:* no secrets tracked; pushed.
- `[✓]` **YS-002** Local Atlas (compose) and proof that `$vectorSearch` + `$text` work on it. *Verify:* scripted probe returns expected nearest neighbour.
- `[✓]` **YS-003** AI service skeleton: settings, Mongo client, internal-token guard (fail closed), `/health`, Gemini/Groq clients with fallback. *Verify:* pytest with mock transports.
- `[✓]` **YS-004** Ingestion core: record validation (official https source on `.gov.in`/`.nic.in`), chunking, hashing, idempotent upsert, `$jsonSchema` validator, indexes. *Verify:* integration test on local Atlas.
- `[✓]` **YS-005** Ingestion sources: myScheme (API Setu v7) and OGD adapters (+ SQL cleaning). *Verify:* unit tests on documented shapes; live check in YS-019.

### Phase 2 — Backend and AI endpoints
- `[✓]` **YS-006** Spring Boot skeleton: Mongo, health, ProblemDetail errors, CORS, validation, Testcontainers.
- `[✓]` **YS-007** Scheme APIs: detail, keyword search, filters, categories, needs. *Features 2, 3, 13–20, 28, 31.*
- `[✓]` **YS-008** Eligibility engine and endpoint. *Features 5–12.*
- `[✓]` **YS-009** FastAPI `/search`, `/related`, `/ask`, `/explain`, `/explain-eligibility`. *Features 4, 21–27, 30, 32.*
- `[✓]` **YS-010** Spring Boot AI integration: combined search, degradation, rate limits. *Features 1, 29, 45–49.*

### Phase 3 — Frontend
- `[ ]` **YS-011** Scaffold: Vite + React (JS), router, API client, layout, design tokens.
- `[ ]` **YS-012** Home, search, category and needs browsing. *Features 1–4, 34–35.*
- `[ ]` **YS-013** Scheme detail: sections, "Not available from the official source", official source, Explain simply, related, compare selection. *Features 9, 13–20, 27, 32, 36–37, 43.*
- `[ ]` **YS-014** Eligibility question flow and results with guidance notice. *Features 6–12, 38.*
- `[ ]` **YS-015** Compare and Ask pages. *Features 22, 26, 33.*

### Phase 4 — Delivery
- `[ ]` **YS-016** Dockerfiles and full local stack (healthy and working). *Feature 50.*
- `[ ]` **YS-017** GitHub Actions CI with guarded deploy hooks. *Feature 51.*

### Phase 5 — Live integration
- `[ ]` **YS-018** Credentials configured locally (manual).
- `[ ]` **YS-019** Live probes: embedding + chat model IDs; myScheme search-response shape and any conditions/exclusions field; structured eligibility facets; real OGD resource IDs for `ogd_datasets.json`; adapter fixes.
- `[ ]` **YS-020** Real ingestion into Atlas; retrieval threshold calibration; grounding checks. *Features 40–44.*
- `[ ]` **YS-021** Render + Vercel deployment and smoke tests. *Features 52–53.*
- `[ ]` **YS-022** Final audit against every feature in the spec.

## 6. Checkpoint log

| Date | Current step | Completed | Blocked / manual |
|---|---|---|---|
| 2026-09-27 | YS-001 | Analysis, baseline, plan | data.gov.in outage (external) |
