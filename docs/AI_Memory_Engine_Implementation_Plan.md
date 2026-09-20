# AI Memory Engine — Full Implementation Plan (Intern Team Edition)

**Supersedes:** Sections 10, 12 (partial), 13 of the ADR, per external architecture review.
**Audience:** Intern engineering team — this document assumes no prior context beyond "read this and build it."
**Date:** September 7, 2026

---

## 0. What Changed From the ADR (Read This First)

The ADR was reviewed and three corrections are now mandatory, not optional:

1. **`llama-3.3-70b-versatile` is deprecated on Groq** (decommissioned per Groq's official deprecations page, announced June 17, 2026). The generation layer must use a **configurable model name**, not a hardcoded one. Current default: `openai/gpt-oss-120b` via Groq. Alternative: `qwen/qwen3.6-27b`. **Never hardcode a model string in application code — it goes in an environment variable.**
2. **`FastAPI BackgroundTasks` is not a durable job system.** A dyno restart mid-job can duplicate embeddings, duplicate Qdrant points, or silently lose a job. We are replacing it with a **Postgres-backed job queue with a separate worker process**, using `SELECT ... FOR UPDATE SKIP LOCKED` and idempotency keys.
3. **RLS must be transaction-scoped, not connection-scoped.** `SET app.user_id` on a pooled connection can leak into the next request if not reset. We use `set_config(..., true)` inside an explicit `BEGIN`/`COMMIT` per request.

Two more corrections that change file structure but not headline decisions:

4. `entity_id` is **nullable and multi-valued** per chunk (`entity_ids: []`), not a required scalar field — many chunks mention zero, one, or several people, and resolution happens *after* ingestion.
5. Qdrant sparse vectors need an **actual sparse encoder decision** (BM25 via FastEmbed, or a learned sparse model) — "configure a sparse vector" is not itself a retrieval strategy. This plan specifies FastEmbed's BM25 implementation as the starting default, with a mandatory evaluation step before trusting it on Urdu/Hinglish text.

---

## 1. Repository Structure

Two repos (or a monorepo with two top-level folders — team's choice, doesn't change the plan):

```
backend/
├── app/
│   ├── main.py                          # FastAPI app entrypoint
│   ├── core/
│   │   ├── config.py                    # env var loading (pydantic-settings)
│   │   ├── security.py                  # Clerk JWT verification, current_user dependency
│   │   └── db.py                        # connection pool + RLS transaction context manager
│   ├── api/v1/
│   │   ├── router.py
│   │   └── endpoints/
│   │       ├── auth.py
│   │       ├── chats.py
│   │       ├── uploads.py
│   │       ├── jobs.py
│   │       ├── entities.py
│   │       ├── query.py
│   │       ├── reports.py
│   │       ├── users.py
│   │       └── health.py
│   ├── schemas/                         # Pydantic request/response models
│   ├── repositories/                    # ALL database access goes through here
│   │   ├── chat_repository.py
│   │   ├── message_repository.py
│   │   ├── entity_repository.py
│   │   ├── job_repository.py
│   │   └── usage_repository.py
│   ├── services/
│   │   ├── parsing/
│   │   │   ├── whatsapp_parser.py
│   │   │   ├── ios_patterns.py
│   │   │   ├── android_patterns.py
│   │   │   └── anomaly_log.py
│   │   ├── privacy/
│   │   │   └── scrubber.py
│   │   ├── chunking/
│   │   │   ├── thread_detector.py
│   │   │   └── chunker.py
│   │   ├── enrichment/
│   │   │   ├── ambiguity_detector.py
│   │   │   └── enricher.py              # Gemini calls, selective only
│   │   ├── embeddings/
│   │   │   └── voyage_client.py         # SOLE embedding provider, no fallback
│   │   ├── entity_resolution/
│   │   │   ├── candidate_scanner.py     # free local heuristic, full corpus
│   │   │   └── llm_resolver.py          # targeted Gemini calls on new candidates
│   │   ├── retrieval/
│   │   │   ├── qdrant_client.py
│   │   │   ├── hybrid_search.py         # dense+sparse, server-side RRF
│   │   │   └── entity_aggregator.py     # chronological batching before generation
│   │   └── generation/
│   │       ├── llm_router.py            # Groq primary (configurable) + Gemini fallback
│   │       └── prompt_templates.py
│   ├── jobs/
│   │   ├── queue.py                     # Postgres SKIP LOCKED queue
│   │   ├── ingestion_pipeline.py        # orchestrates parse→scrub→chunk→enrich→embed→store
│   │   └── worker_entrypoint.py         # run via Heroku Scheduler, see §6
│   ├── db/migrations/                   # Alembic
│   └── tests/
│       ├── test_isolation.py            # cross-user RLS test — MUST run in CI
│       ├── test_parser_ios.py
│       ├── test_parser_android.py
│       ├── test_idempotency.py
│       └── test_retrieval_eval.py
├── Procfile
├── requirements.txt
├── runtime.txt
└── .env.example

frontend/
├── app/
│   ├── (auth)/sign-in/page.tsx
│   ├── (auth)/sign-up/page.tsx
│   ├── dashboard/page.tsx
│   ├── upload/page.tsx
│   ├── chats/[chatId]/
│   │   ├── layout.tsx
│   │   ├── processing/page.tsx
│   │   ├── review-entities/page.tsx
│   │   ├── chat/page.tsx
│   │   ├── report/page.tsx
│   │   └── entity/[entityId]/page.tsx
│   └── settings/page.tsx
├── components/
│   ├── UploadDropzone.tsx
│   ├── JobProgress.tsx
│   ├── AliasReviewPanel.tsx
│   ├── ChatQueryBox.tsx
│   ├── EvidenceCard.tsx
│   ├── EntityTimeline.tsx
│   └── ReportView.tsx
├── lib/
│   ├── api-client.ts
│   ├── useJobEvents.ts                  # SSE hook with Last-Event-ID reconnect
│   └── auth.ts
└── .env.local.example
```

---

## 2. Database Schema (Postgres — Heroku Mini, default)

```sql
-- Users mirror table (Clerk is source of truth for auth; this holds app-specific fields)
CREATE TABLE users (
    id              UUID PRIMARY KEY,           -- Clerk user ID
    email           TEXT NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);

CREATE TABLE chats (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id        UUID NOT NULL REFERENCES users(id),
    title           TEXT,
    status          TEXT NOT NULL DEFAULT 'uploaded', -- uploaded|processing|review_needed|ready|failed
    message_count   INT,
    created_at      TIMESTAMPTZ DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);

ALTER TABLE chats ENABLE ROW LEVEL SECURITY;
ALTER TABLE chats FORCE ROW LEVEL SECURITY;
CREATE POLICY chats_isolation ON chats
    USING (owner_id = current_setting('app.user_id', true)::uuid)
    WITH CHECK (owner_id = current_setting('app.user_id', true)::uuid);

CREATE TABLE ingestion_jobs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chat_id         UUID NOT NULL REFERENCES chats(id),
    owner_id        UUID NOT NULL REFERENCES users(id),
    status          TEXT NOT NULL DEFAULT 'queued', -- queued|claimed|running|done|failed
    stage           TEXT,                            -- parsing|scrubbing|chunking|enriching|embedding|entity_scan
    progress_current INT DEFAULT 0,
    progress_total  INT,
    claimed_at      TIMESTAMPTZ,
    claim_expires_at TIMESTAMPTZ,
    worker_id       TEXT,
    attempt_count   INT DEFAULT 0,
    available_at    TIMESTAMPTZ DEFAULT now(),
    last_error      TEXT,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE ingestion_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE ingestion_jobs FORCE ROW LEVEL SECURITY;
CREATE POLICY jobs_isolation ON ingestion_jobs
    USING (owner_id = current_setting('app.user_id', true)::uuid)
    WITH CHECK (owner_id = current_setting('app.user_id', true)::uuid);

CREATE TABLE parse_errors (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chat_id         UUID NOT NULL REFERENCES chats(id),
    line_number     INT,
    raw_line_hash   TEXT,
    error_type      TEXT,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE entities (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chat_id         UUID NOT NULL REFERENCES chats(id),
    owner_id        UUID NOT NULL REFERENCES users(id),
    canonical_name  TEXT NOT NULL,
    aliases         TEXT[] DEFAULT '{}',
    confirmed_by_user BOOLEAN DEFAULT false,
    created_at      TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE entities ENABLE ROW LEVEL SECURITY;
ALTER TABLE entities FORCE ROW LEVEL SECURITY;
CREATE POLICY entities_isolation ON entities
    USING (owner_id = current_setting('app.user_id', true)::uuid)
    WITH CHECK (owner_id = current_setting('app.user_id', true)::uuid);

CREATE TABLE entity_candidates (           -- pending, pre-HITL-confirmation
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chat_id         UUID NOT NULL REFERENCES chats(id),
    surface_form    TEXT NOT NULL,
    suggested_canonical TEXT,
    context_window  TEXT,                  -- the ±20 messages sent to Gemini
    confidence      FLOAT,
    status          TEXT DEFAULT 'pending', -- pending|confirmed|rejected|merged
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE embedding_usage (              -- token budget tracking against Voyage's 200M grant
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider        TEXT NOT NULL,
    model           TEXT NOT NULL,
    operation       TEXT NOT NULL,          -- embed_chunk|embed_query
    user_id         UUID,
    chat_id         UUID,
    job_id          UUID,
    estimated_tokens INT,
    actual_tokens   INT,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE llm_usage (                    -- Groq/Gemini generation + enrichment call tracking
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider        TEXT NOT NULL,
    model           TEXT NOT NULL,
    operation       TEXT NOT NULL,          -- enrichment|generation|entity_resolution
    user_id         UUID,
    chat_id         UUID,
    prompt_tokens   INT,
    completion_tokens INT,
    fell_back       BOOLEAN DEFAULT false,
    created_at      TIMESTAMPTZ DEFAULT now()
);
```

**Every table holding user data gets `ENABLE ROW LEVEL SECURITY` + `FORCE ROW LEVEL SECURITY` + a policy.** `FORCE` matters — without it, the table owner role bypasses RLS by default, which defeats the entire point.

---

## 3. RLS Transaction Wrapper (Backend Core)

This is the single most important file in the backend. Every database-touching request goes through it.

```python
# app/core/db.py
from contextlib import asynccontextmanager

@asynccontextmanager
async def user_scoped_transaction(pool, user_id: str):
    async with pool.acquire() as conn:
        async with conn.transaction():
            # `true` = transaction-local, NOT connection-local.
            # This is the exact fix for the pooled-connection leak risk.
            await conn.execute(
                "SELECT set_config('app.user_id', $1, true)", str(user_id)
            )
            yield conn
        # transaction ends -> setting is automatically discarded, connection is
        # safe to return to the pool for the next, different, user's request.
```

Every repository function takes a `conn` from this context manager — **no repository function opens its own connection**, and no API endpoint runs a raw query outside this wrapper.

**CI requirement (`test_isolation.py`):** create two fake users, insert chat data for both, run every list/get endpoint as User A, assert zero rows belonging to User B are returned. Additionally test **connection reuse specifically**: run User A's request, return the connection to the pool, immediately run User B's request on a connection acquired from the same pool, assert no data crosses over. This second test is the one most teams skip and the one the review specifically flagged as necessary.

---

## 4. API Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/chats/upload` | Upload `.txt` export → creates `chats` row + `ingestion_jobs` row, returns `job_id` |
| GET | `/api/v1/jobs/{job_id}` | Poll job status (fallback if SSE unavailable) |
| GET | `/api/v1/jobs/{job_id}/events` | SSE stream of progress (`stage`, `progress_current/total`) |
| GET | `/api/v1/chats` | List current user's chats |
| GET | `/api/v1/chats/{chat_id}` | Chat detail + status |
| DELETE | `/api/v1/chats/{chat_id}` | Delete chat: cascades to Postgres rows + Qdrant points |
| GET | `/api/v1/chats/{chat_id}/entities/candidates` | Pending alias candidates for HITL review |
| POST | `/api/v1/chats/{chat_id}/entities/confirm` | Submit confirmed/rejected/merged aliases → writes `entities`, updates Qdrant payloads only (no re-embedding) |
| POST | `/api/v1/chats/{chat_id}/query` | Ask a question → hybrid retrieval → generation → answer + cited chunk IDs |
| GET | `/api/v1/chats/{chat_id}/entities/{entity_id}/timeline` | Exhaustive entity trace (metadata filter, chronologically aggregated) |
| GET | `/api/v1/chats/{chat_id}/report` | Generate/fetch full relationship analysis report |
| DELETE | `/api/v1/users/me` | Account deletion — cascades Postgres, Qdrant, active jobs, Sentry scrubbing |
| GET | `/api/v1/health` | Health check — **no sensitive data, no stack traces, no chat content** |

**Response shape for `/query` (structured evidence, not raw text dump into the model):**

```json
{
  "answer": "string",
  "evidence": [
    {
      "chunk_id": "uuid",
      "date_range": "2025-03-01 to 2025-03-02",
      "participants": ["Participant_A", "Participant_B"],
      "retrieval_reasons": ["dense", "sparse"]
    }
  ],
  "confidence_note": "string, e.g. 'limited evidence in this period'"
}
```

---

## 5. External / LLM API Endpoints

All model IDs are **environment variables**, never hardcoded, per the Groq deprecation lesson.

```bash
# .env.example (backend)

# Generation (primary + fallback, both configurable)
GROQ_API_KEY=
GROQ_MODEL_PRIMARY=openai/gpt-oss-120b        # current Groq recommendation (was llama-3.3-70b-versatile — deprecated)
GEMINI_API_KEY=
GEMINI_MODEL_FALLBACK=gemini-2.5-flash
GEMINI_MODEL_ENRICHMENT=gemini-2.5-flash      # used for selective chunk enrichment + alias candidate resolution

# Embeddings — single provider, no fallback (see ADR §5)
VOYAGE_API_KEY=
VOYAGE_MODEL=voyage-4

# Vector storage
QDRANT_URL=
QDRANT_API_KEY=
QDRANT_COLLECTION=messages_voyage4_v1         # versioned collection name — never mutate dims/model in place

# Database
DATABASE_URL=                                  # Heroku Postgres connection string (or AWS RDS, see §8)

# Auth
CLERK_SECRET_KEY=
CLERK_PUBLISHABLE_KEY=

# Monitoring
SENTRY_DSN=
```

**`app/services/generation/llm_router.py` responsibilities:**
- Call Groq with `GROQ_MODEL_PRIMARY`.
- On `429` or Groq outage, fall back to Gemini using `GEMINI_MODEL_FALLBACK`. Log `fell_back=true` to `llm_usage`.
- **This fallback is safe** — it's text output, not indexed vectors. Contrast with embeddings, where fallback is forbidden.
- Both prompt variants (Groq-tuned, Gemini-tuned) must be tested for output parity before launch — don't assume identical behavior.

**Qdrant hybrid query (dense + sparse, server-side RRF):**

```python
# app/services/retrieval/hybrid_search.py
from qdrant_client import QdrantClient, models

def hybrid_search(client: QdrantClient, collection: str, dense_vec, sparse_vec, user_id, chat_id, limit=20):
    return client.query_points(
        collection_name=collection,
        prefetch=[
            models.Prefetch(query=dense_vec, using="dense", limit=limit * 2),
            models.Prefetch(query=sparse_vec, using="sparse", limit=limit * 2),
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        query_filter=models.Filter(must=[
            models.FieldCondition(key="user_id", match=models.MatchValue(value=str(user_id))),
            models.FieldCondition(key="chat_id", match=models.MatchValue(value=str(chat_id))),
        ]),
        limit=limit,
    )
```

**Sparse vector generation — mandatory decision, not optional config:** use `fastembed`'s BM25 sparse encoder as the MVP default (`Qdrant/bm25`). Before trusting hybrid search in production, run the retrieval evaluation set below.

**Retrieval evaluation set (build this before trusting hybrid search):**
Assemble 50–100 test queries across: exact-phrase lookups, Urdu queries, Hinglish/code-switched queries, named-person queries, conceptual/emotional queries, emoji-heavy queries. Run dense-only, sparse-only, and RRF-hybrid against each, and manually score top-5 relevance. This is a required deliverable in Phase 4 (see §7), not a nice-to-have.

**Critical security note on Qdrant filters:** `user_id`/`chat_id` filters on Qdrant queries are a **belt-and-suspenders measure, not the primary security boundary**. Always validate chat ownership in Postgres (which has RLS) *before* issuing the Qdrant query. Never treat Qdrant payload filtering as your authorization layer.

---

## 6. Job Queue (Durable Replacement for `BackgroundTasks`)

```sql
-- Claim a job (worker-side)
SELECT *
FROM ingestion_jobs
WHERE status = 'queued'
  AND available_at <= now()
ORDER BY created_at
FOR UPDATE SKIP LOCKED
LIMIT 1;
```

**Idempotency keys — required for every external side effect in the pipeline:**

```python
embedding_key = hash(chat_id + chunk_id + VOYAGE_MODEL)
qdrant_point_id = deterministic_uuid(embedding_key)  # re-running a batch overwrites, never duplicates
```

**Worker deployment — this is where Heroku's Eco tier constraints actually bite, so read carefully:**

Eco *web* dynos sleep after 30 minutes idle and don't consume dyno hours while asleep. **Eco *worker* dynos never sleep** — if you run one 24/7, it consumes roughly 720 of your 1,000 monthly Eco-hour pool by itself, leaving very little for your web dyno (which also needs hours whenever it's awake, including from your UptimeRobot keep-alive pings). Running an always-on worker dyno *and* an always-awake web dyno on a single $5 Eco pool does not fit.

**MVP fix: don't run a permanent worker dyno. Use Heroku Scheduler instead** (a free add-on):
- Configure Heroku Scheduler to run `python -m app.jobs.worker_entrypoint --once` every 10 minutes.
- Each run: claim up to N queued jobs, process a bounded batch, persist checkpoint, exit.
- This only consumes dyno hours while actually processing, not while idle — fitting the Eco budget the way your web dyno does.
- Trade-off: worst-case latency of ~10 minutes before a queued job starts. Acceptable for a 20-user MVP; document it as a known limitation, not a bug.

**Document as a future upgrade trigger (not built now):** if job latency becomes a real UX problem, upgrade to a genuine always-on worker dyno — this requires either accepting the Eco hour trade-off above or moving to a Basic dyno (~$7/mo, no sleep, no shared-hour pool).

---

## 7. Frontend Screens

| Screen | Route | Key components | Function |
|---|---|---|---|
| Sign in / Sign up | `/sign-in`, `/sign-up` | Clerk prebuilt components | Auth |
| Dashboard | `/dashboard` | Chat list, "Upload new chat" button | List existing analyses, entry point |
| Upload | `/upload` | `UploadDropzone` | Accept `.txt` export, POST to `/chats/upload`, redirect to processing |
| Processing | `/chats/[chatId]/processing` | `JobProgress` (SSE via `useJobEvents`) | Live progress bar by stage; "waking up..." state for cold starts |
| Alias Review | `/chats/[chatId]/review-entities` | `AliasReviewPanel` | Show candidates from `/entities/candidates`, confirm/reject/merge, POST to `/entities/confirm` |
| Chat / Q&A | `/chats/[chatId]/chat` | `ChatQueryBox`, `EvidenceCard` | Ask questions, show answer + cited evidence chunks (not raw dumps) |
| Entity Timeline | `/chats/[chatId]/entity/[entityId]` | `EntityTimeline` | Exhaustive chronological trace for one person |
| Report | `/chats/[chatId]/report` | `ReportView` | Full generated relationship analysis |
| Settings | `/settings` | Privacy policy text, "Delete my account" | Deletion triggers cascading delete across Postgres + Qdrant |

**`useJobEvents.ts` must handle:** stream disconnects, reconnection via `Last-Event-ID`, job already completed before the stream opens, expired jobs, and dyno cold starts (show the honest "waking up, up to 30 seconds" message per ADR §11 rather than a blank spinner).

**Privacy policy copy (must match what the pipeline actually does — do not overstate):**
> "We remove known identifiers such as phone numbers and names as written before any external processing. Conversation content may still contain other identifying information (locations, employers, indirect references). No automated system can guarantee complete anonymization."

---

## 8. Deployment

### 8A. Heroku (Web + Backend)

```
# Procfile
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Steps:
1. `heroku create <app-name>` (personal app, required for Eco dynos).
2. `heroku addons:create heroku-postgresql:mini` — provisions the default DB (see 8B for AWS alternative).
3. Set all env vars from §5 via `heroku config:set`.
4. Add **Heroku Scheduler** add-on (free) — configure the job-processing command from §6, every 10 minutes.
5. Deploy via `git push heroku main` or GitHub auto-deploy.
6. Configure UptimeRobot to hit `/api/v1/health` every ~25 minutes — **but check remaining Eco hours monthly**; disable the keep-alive automatically if the account is close to the 1,000-hour ceiling, since scheduler runs also consume hours.

### 8B. Postgres — Two Supported Paths

**Path 1 (default, per locked ADR): Heroku Mini Postgres.** Provisioned by the addon command above. Zero setup beyond that — connection string is auto-injected as `DATABASE_URL`.

**Path 2 (alternative, if the team specifically wants AWS): Amazon RDS for PostgreSQL, free tier.**
1. AWS Console → RDS → Create database → Standard create → PostgreSQL.
2. Template: **Free tier** (this matters — free tier is time-limited to 12 months from AWS account creation, then billing begins automatically; Heroku Mini has no such expiry as long as student credits last).
3. Instance class: `db.t3.micro` or `db.t4g.micro` (whichever the free tier currently covers — check the RDS console at creation time, this changes).
4. Storage: 20GB gp2/gp3 (within free tier).
5. Public access: **No** unless your Heroku dyno needs direct internet access to it — prefer a VPC security group that allow-lists Heroku's egress, or use Heroku's private networking add-ons if going this route.
6. Security group: inbound rule allowing port 5432 only from your backend's IP range.
7. Enable "Force SSL" — set `sslmode=require` in your `DATABASE_URL`.
8. Note the free-tier expiry date on your team calendar — this is a real cost cliff, not a permanent free option like the Heroku path.

**Recommendation to the team:** stay on Path 1 unless there's a specific reason (e.g., wanting AWS experience, or needing RDS-specific features). Path 2 introduces a 12-month cost cliff that Path 1 doesn't have.

### 8C. Qdrant Cloud
1. Create a free cluster at Qdrant Cloud.
2. Confirm your cluster tier supports the Query API's `FusionQuery(fusion=Fusion.RRF)` parameter (some older/free tiers lag — verify before building retrieval around it).
3. Create the collection with named dense + sparse vectors matching `voyage-4`'s output dimensionality and your BM25 sparse config.

### 8D. Vercel (Frontend)
1. Connect the frontend repo, framework preset: Next.js.
2. Set `NEXT_PUBLIC_API_BASE_URL` to the Heroku backend URL.
3. Set Clerk publishable key as an env var.
4. Deploy — Vercel's free tier handles this scale without configuration changes.

### 8E. Monitoring
- Sentry: create project, set `SENTRY_DSN`, **scrub chat content from breadcrumbs and error payloads** — never let raw message text reach Sentry.
- UptimeRobot: monitor `/api/v1/health` (returns `{"status": "ok"}` only — no diagnostic detail).

---

## 9. Phased Build Plan (Assign to Interns by Phase)

### Phase 1 — Safe Ingestion Foundation
- WhatsApp parser (iOS + Android patterns) + parse-anomaly logging
- Local deterministic scrubbing
- Postgres schema + RLS policies + transaction wrapper
- Repository layer (no raw queries outside it)
- CI isolation tests (including connection-reuse test)
- **Acceptance:** two fake users, cross-user leak test passes; parser handles both export formats + malformed lines without crashing.

### Phase 2 — Single-Provider Retrieval (Dense Only)
- Thread-based chunking with time-gap detection + token-bounded hard limits
- Voyage embedding client with token-usage logging against the 200M budget
- Qdrant dense-vector storage, deterministic point IDs, idempotent upserts
- Basic dense-only retrieval, filtered by `user_id`/`chat_id`
- **Acceptance:** re-running ingestion on the same file does not create duplicate points.

### Phase 3 — Durable Ingestion
- Postgres job queue (`SKIP LOCKED`), Heroku Scheduler wiring
- Idempotency keys on every external call
- SSE progress endpoint + frontend `useJobEvents` hook
- **Acceptance:** killing the worker process mid-job and re-running the scheduler resumes correctly with no duplicate embeddings.

### Phase 4 — Hybrid Search
- BM25 sparse encoder (FastEmbed) integration
- Retrieval evaluation set (50–100 queries, dense vs. sparse vs. RRF scored)
- **Acceptance:** evaluation results documented; RRF chosen only if it measurably beats dense-only on the test set, not by default assumption.

### Phase 5 — Entity Resolution
- Full-corpus local candidate scanner
- Targeted Gemini resolution on new candidates only
- `AliasReviewPanel` frontend + confirm/reject/merge endpoint
- Payload-only Qdrant updates (no re-embedding) after confirmation
- `entity_id` exhaustive timeline endpoint with chronological aggregation (not a raw dump of every matching chunk into the LLM context)
- **Acceptance:** confirming an alias updates retrieval behavior without re-processing the full corpus.

### Phase 6 — Generation
- `llm_router.py` with configurable Groq model + Gemini fallback
- Structured evidence format (chunk IDs, not raw text blobs) into prompts
- Prompt-parity testing across both providers
- Report generation + Q&A endpoints
- **Acceptance:** model outputs cite evidence, state uncertainty when evidence is thin, and avoid diagnosing mental health/personality conditions or asserting intent from ambiguous messages — verify this explicitly with adversarial test prompts, not just happy-path ones.

---

## 10. Non-Negotiable Cross-Cutting Rules

1. No cross-provider fallback for embeddings — ever. Fallback is fine for generation only.
2. Every database table with user data has RLS + `FORCE ROW LEVEL SECURITY` + a CI isolation test.
3. Every job step persists progress to Postgres with an idempotency key — never trust in-memory state to survive a restart.
4. Model IDs are environment variables, never hardcoded — this plan exists partly because the ADR's original hardcoded model was deprecated mid-project.
5. Privacy policy copy must match actual scrubbing behavior — no "fully anonymized" claims.
6. Qdrant filters are defense-in-depth, not the security boundary — Postgres RLS is authoritative.
