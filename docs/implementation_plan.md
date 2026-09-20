# Silsila AI Memory Engine — Agent Implementation Plan

> **Source Docs Reviewed:** Architecture Decision Record, Project Plan, Full Implementation Plan, Stitch UI Mockup  
> **Stack (locked):** FastAPI (Render) + Next.js 15 (Vercel) + Supabase (PostgreSQL + pgvector) + Gemini API + Voyage AI + Qdrant  
> **Notation:** 🤖 = Agent builds it | 👤 = User must provide

---

## Pre-Phase: Architecture Reconciliation

> [!IMPORTANT]
> Two different versions of the stack exist in your docs. The **Architecture Decision Record** (ADR, dated Aug 27 2026 — the final locked document) supersedes the older `implementation_plan.md` (dated Aug 6 2026) in several critical areas. This plan follows the **ADR as the source of truth**.

| Layer | Old Plan (Aug 6) | ADR Final (Aug 27) — **USE THIS** |
|---|---|---|
| Embeddings | Gemini `text-embedding-004` | **Voyage AI `voyage-4`** (200M token free grant) |
| Vector Store | Supabase pgvector | **Qdrant Cloud** (persistent, no idle-pause) |
| Retrieval | Supabase FTS + pgvector RRF | **Native Qdrant hybrid (dense + sparse BM25, server-side RRF)** |
| Backend Hosting | Render | **Heroku Eco Dynos** (GitHub Student Pack credits) |
| Auth | Supabase Auth | **Clerk** |
| Relational DB | Supabase PostgreSQL | **Heroku Mini Postgres** (no 7-day idle-pause) |
| LLM | Gemini Flash | **Groq Llama 3.3 70B** (primary) + Gemini Flash (fallback) |
| Frontend | Vercel | **Vercel** (unchanged) |

> [!WARNING]
> **Before any code is written**, the user must confirm which stack to use. The agent will implement the **ADR version** unless told otherwise.

---

## PHASE 0 — Accounts & Credentials Setup

> This phase is **100% user action**. The agent cannot proceed to Phase 1 without these.

### 👤 User Must Provide:

| Service | What to do | Where to get |
|---|---|---|
| **Heroku** | Create account. Apply GitHub Student Pack credit (`$13/mo` in credits). | [heroku.com](https://heroku.com) + GitHub Education |
| **Heroku Mini Postgres** | Provision a Mini Postgres add-on on your Heroku app. | Heroku dashboard → Resources |
| **Clerk** | Create a Clerk application. Copy: `CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY`, `CLERK_JWT_ISSUER`. | [clerk.com](https://clerk.com) |
| **Voyage AI** | Sign up for the free tier. Copy: `VOYAGE_API_KEY`. Confirm 200M token grant is active on your account. | [voyageai.com](https://voyageai.com) |
| **Qdrant Cloud** | Create a free cluster. Copy: `QDRANT_URL`, `QDRANT_API_KEY`. **Confirm**: the free tier supports the Query API with server-side RRF fusion (not just dual-vector storage). | [cloud.qdrant.io](https://cloud.qdrant.io) |
| **Groq** | Get a free API key. Copy: `GROQ_API_KEY`. | [console.groq.com](https://console.groq.com) |
| **Gemini** | Get a free API key (fallback LLM + entity suggestion). Copy: `GEMINI_API_KEY`. | [aistudio.google.com](https://aistudio.google.com) |
| **Sentry** | Create a free project for FastAPI (backend) and Next.js (frontend). Copy both DSNs. | [sentry.io](https://sentry.io) |
| **UptimeRobot** | Create a free account. (Monitors configured in Phase 6.) | [uptimerobot.com](https://uptimerobot.com) |
| **Vercel** | Link your GitHub repo. Set region to `sin1` (Singapore). | [vercel.com](https://vercel.com) |
| **WhatsApp Export Samples** | Export 2–3 real chats: one iOS, one Android, one large group. These are **required** before the parser can be built correctly (ADR §1 requires real samples to validate dual-pattern regex). | WhatsApp → Chat → Export Chat → Without Media |

### 👤 User Must Also Confirm:

- [ ] Which GitHub repo the project lives in (agent needs to know for CI/CD setup)
- [ ] Your Vercel domain (e.g., `silsila.vercel.app`)
- [ ] Your Heroku app name (e.g., `silsila-api`)

### 🤖 Agent Does in Phase 0:

- Creates the `.env.example` file with all required variables documented
- Creates the full repository folder structure (backend + frontend + supabase dirs)
- Creates the Heroku `Procfile` and `runtime.txt`
- Creates `render.yaml` (kept for reference, but Heroku is primary per ADR)

---

## PHASE 1 — Foundations

> **Goal:** Upload WhatsApp .txt → parse → store in Heroku Postgres → browse messages → keyword search  
> **Outcome:** A working app with auth, upload, message browser, and basic search

### Step 1: Project Scaffolding

🤖 **Agent builds:**
- Next.js 15 frontend (`npx create-next-app@latest`) with TypeScript, App Router, Clerk auth middleware
- FastAPI backend with `asyncpg` pool connected to Heroku Postgres
- `GET /api/health` endpoint
- Full folder structure matching the architecture

👤 **User provides:**
- All credentials from Phase 0 (inserted into Heroku env vars and Vercel env vars)
- Confirmation that `npm run dev` and `uvicorn` both start clean

---

### Step 2: Database Schema (Heroku Postgres + Native RLS)

🤖 **Agent builds:**
- Full migration SQL for all tables: `profiles`, `chats`, `people`, `aliases`, `messages`, `conversation_threads`, `message_threads`, `message_chunks`, `events`, `relationships`, `analysis_cache`, `ingestion_jobs`, `emotion_labels`, `alias_suggestions`
- Native PostgreSQL RLS policies using `current_setting('app.user_id')` session variable (ADR §12)
- All indexes including GIN for full-text search and HNSW placeholder (Qdrant handles vectors — Postgres stores only relational data)
- Centralized repository functions in `db/queries/` (no raw queries in routers)
- Cross-user isolation CI test (User A cannot see User B's data across all tables)

👤 **User provides:**
- Heroku Postgres `DATABASE_URL` connection string (from Heroku dashboard → Postgres → Settings → View Credentials)
- Confirmation that all tables are visible after migration runs

---

### Step 3: Clerk Auth (Backend + Frontend)

🤖 **Agent builds:**
- FastAPI JWT validation dependency using Clerk's JWKS endpoint
- Next.js middleware protecting all `/app/*` routes except public pages
- Login/signup page using Clerk's hosted components
- Profile auto-creation trigger in Postgres on first login
- Session cookies compatible with Next.js SSR

👤 **User provides:**
- `CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY`, `CLERK_JWT_ISSUER` (from Clerk dashboard)

---

### Step 4: WhatsApp Parser

🤖 **Agent builds:**
- `backend/app/services/whatsapp_parser.py` — dual-pattern regex for iOS and Android
- Both date format variants: `DD/MM/YYYY, HH:MM - Sender: Message` and `[DD/MM/YYYY, HH:MM:SS] Sender: Message`
- Edge case handling: multi-line messages, system messages, `<Media omitted>`, deleted messages, Urdu/emoji/Hinglish
- Streaming parse (line-by-line, never loads full file into memory)
- Auto-detect DD/MM vs MM/DD from first few lines
- Unit tests in `tests/test_parser.py` with full edge case coverage

👤 **User provides:**
- **2–3 real WhatsApp export `.txt` files** (iOS + Android + a large group) to validate the regex against real formats
- Confirmation that parse output is correct for all sample files

> [!IMPORTANT]
> The ADR explicitly states: *"Collect a handful of real iOS and Android export samples before writing the regex — don't guess at the format differences from memory."* The agent will write best-effort regex but **the user must validate it against real exports**.

---

### Step 5: Ingestion Pipeline (Background Worker)

🤖 **Agent builds:**
- `backend/app/workers/ingestion.py` — full pipeline: Parse → Create People → Create Chat → Bulk Insert Messages → Thread Detection → Update Stats
- Adaptive thread detection (`thread_detector.py`): median-based gap threshold, clamped to [30min, 4hrs]
- Job progress persisted to `ingestion_jobs` table (not in-memory) — survives dyno restarts (ADR §11 idempotency requirement)
- Idempotent design: if job fails mid-way, resume from last checkpoint on retry
- Heroku `BackgroundTasks` integration
- UptimeRobot keep-alive setup for `/api/health` endpoint (prevents Eco dyno sleep)
- `POST /api/parse/whatsapp` endpoint returning `202 { job_id }`

👤 **User provides:**
- Nothing at this step (builds on previous)

---

### Step 6: File Upload UI + Real-Time Progress

🤖 **Agent builds:**
- Frontend upload page (`/upload`) — drag-and-drop matching the **Stitch UI mockup** (`.ZIP archive`, `.TXT file` badges, orange CTA button, cloud_upload icon, dashed border dropzone)
- Real-time job progress: SSE subscription to job status updates (no polling)
- Frontend shows: "Waking up analysis engine (up to 30s)" if cold start detected (ADR §11 mitigation)
- Progress bar with step labels: `parsing → storing → threading → complete`
- Redirect to `/chat/{chatId}` on completion

👤 **User provides:**
- Nothing (builds on previous steps)

---

### Step 7: Message Browser UI

🤖 **Agent builds:**
- Dashboard (`/`) — grid of chat cards with name, message count, date range, participant count
- Chat view (`/chat/[chatId]`) — scrollable message list, color-coded by sender, date headers, infinite scroll (100 msgs/page)
- System messages rendered as centered muted text
- Full-text keyword search with `ts_headline` highlighting
- Basic statistics: total messages, messages per person, messages-per-day chart
- UI matching the **Stitch mockup** color palette (orange primary `#EA580C`, warm neutral backgrounds, Plus Jakarta Sans + Inter fonts)

👤 **User provides:**
- Nothing

---

### Phase 1 Checkpoint ✓

**What the app can do at this point:**
- Sign up / log in via Clerk
- Upload a WhatsApp `.txt` file with real-time progress
- Browse messages in a chat-like UI
- Search by keyword (full-text)
- See basic statistics
- Data is fully isolated per user (native Postgres RLS)

---

## PHASE 2 — AI Search

> **Goal:** Natural language Q&A with evidence-backed streaming answers  
> **New external services activated: Voyage AI (embeddings) + Qdrant (vector store) + Groq (LLM)**

### Step 8: Voyage AI Embedding Service

🤖 **Agent builds:**
- `backend/app/services/embedding.py` using Voyage AI `voyage-4` model
- Batch embedding (up to 128 texts per call)
- Exponential backoff on 429 rate limit errors (ADR §5: never switch providers on error)
- Cumulative token counter stored in Postgres, alerting at 150M / 200M token usage milestones (ADR §5 action item)
- **No cross-provider fallback** for embeddings (ADR §5 cross-cutting rule)

👤 **User provides:**
- `VOYAGE_API_KEY`

---

### Step 9: Conversation Window Chunk Builder

🤖 **Agent builds:**
- `backend/app/services/chunk_builder.py` — sliding windows of 8 messages with 3-message overlap per thread
- Skip chunks that are entirely system messages or media
- Store as `message_chunks` rows with `message_ids` array, `thread_id`, timestamps
- Integrated into ingestion pipeline after thread detection (Step 5)

👤 **User provides:**
- Nothing

---

### Step 10: Qdrant Vector Store Integration

🤖 **Agent builds:**
- `backend/app/services/qdrant_client.py` — Qdrant Cloud connection
- Collection creation with both **dense** (Voyage `voyage-4`, 1024-dim) and **sparse** (BM25) vectors per chunk
- Payload fields: `user_id`, `chat_id`, `thread_id`, `message_ids`, `content`, `start_time`, `end_time`
- `entity_id` tags as required payload field from day one (ADR §9: retrofitting is expensive)
- Batch upsert during ingestion
- SPARSE differential privacy noise applied before storage (ADR §6 + §32 from impl plan)

👤 **User provides:**
- `QDRANT_URL`, `QDRANT_API_KEY` (from Qdrant Cloud dashboard)
- **Must confirm**: Qdrant Cloud free tier supports Query API with server-side RRF fusion. If not, report back — the retrieval strategy must be adjusted.

---

### Step 11: Hybrid Retrieval Engine

🤖 **Agent builds:**
- `backend/app/services/hybrid_search.py` — native Qdrant hybrid search using Query API
- Dense (semantic) + Sparse (BM25) simultaneous search with server-side RRF fusion
- Sender/alias name match filter (if query mentions a known person name)
- Multilingual BM25 tokenization — tested explicitly against Urdu/Hinglish text (ADR §7 action)
- Endpoint: `POST /api/search/hybrid`

👤 **User provides:**
- A few sample queries in Urdu, Hinglish, and English to validate multilingual retrieval works

---

### Step 12: Evidence Builder

🤖 **Agent builds:**
- `backend/app/services/evidence_builder.py`
- Thread-bounded context expansion (±N messages within same thread, never cross-thread)
- Evidence blocks formatted with matched message highlights
- Token budget cap (~4000 tokens for LLM context)
- Deduplication by message ID

---

### Step 13: Groq LLM Streaming Q&A

🤖 **Agent builds:**
- `backend/app/services/llm.py` — Groq Llama 3.3 70B primary, Gemini Flash automatic fallback on 429 (ADR §10)
- System prompt: evidence-only answers, citation requirement, multilingual support, empathetic tone
- SSE streaming endpoint: `POST /api/chat`
- Status events streamed: `searching → found N messages → analyzing → tokens...`
- The ADR §10 note: test system prompt against **both** Groq and Gemini before launch

👤 **User provides:**
- `GROQ_API_KEY`

---

### Step 14: Chat Q&A Interface (Frontend)

🤖 **Agent builds:**
- Search/Q&A page matching the **Stitch UI's Memory Q&A section**
- Status indicators: animated "Searching..." → "Found 18 messages across 6 threads" → streaming tokens
- Collapsible evidence panel with raw evidence blocks
- Citation cards: sender, timestamp, message preview — click to jump to that message in chat view
- Matches Stitch UI warm color palette and card styles

---

### Phase 2 Checkpoint ✓

**What the app can do at this point:**
- Everything from Phase 1 +
- Ask natural language questions in English/Urdu/Hinglish
- Get streaming, evidence-backed answers with cited messages
- Hybrid semantic + lexical search working
- Voyage AI embeddings stored in Qdrant with differential privacy noise

---

## PHASE 3 — Intelligence

> **Goal:** The system understands *who* people are and *how* they're connected  
> **New component: GLiNER (runs locally on CPU)**

### Step 15: GLiNER Entity Extraction

🤖 **Agent builds:**
- `backend/app/services/entity_extractor.py` with GLiNER `urchade/gliner_multi-v2.1` model
- Labels: `["Person", "Location", "Event", "Topic"]`
- Two-tier detection (ADR §8):
  1. Free local heuristic scan: repeated capitalized/proper-noun tokens across ALL messages (not just first 1000 lines)
  2. Targeted Gemini LLM pass on only newly flagged ambiguous candidates with surrounding ±20 message window
- Entity frequency threshold (ADR §8 action: define "unseen candidate" before implementation)
- GLiNER pre-downloaded in Dockerfile at build time (prevents 2GB download on cold start)
- Runs as post-processing step after ingestion (not during initial upload — too slow)

👤 **User provides:**
- Confirmation of Render/Heroku plan — GLiNER requires CPU compute (~205M params). Confirm the dyno type can handle it.

---

### Step 16: Alias Resolution (Human-in-the-Loop)

🤖 **Agent builds:**
- `backend/app/services/coreference.py` — confidence-tiered alias suggestion engine
  - High confidence (>0.85): auto-merge silently
  - Medium confidence (0.5–0.85): surface for human review
  - Low (<0.5): skip
- `alias_suggestions` table population with context snippets
- `backend/app/routers/alias_suggestions.py` — CRUD endpoints for accept/reject/new-person
- Re-linking: accepted aliases trigger message re-assignment to correct `person_id` in Postgres AND payload update in Qdrant chunks (entity_id update)
- SSE/Realtime notification: "5 new aliases detected — review them"

🤖 **Agent builds (frontend):**
- `AliasReviewPanel` component matching Stitch UI's **"Who is Who?"** section
- Dashboard notification badge: "3 aliases need your review"
- Cards: context snippet + Yes / No / New Person actions
- Live toast notification on new alias detection

👤 **User provides:**
- **Must review and confirm alias suggestions for their own chat data** — this step requires human judgment. The quality of entity resolution determines the quality of all downstream features.

---

### Step 17: People Profiles + Relationship Graph

🤖 **Agent builds:**
- Auto-generated character profiles stored in `people.profile` JSONB
- `backend/app/db/queries/graph.py` — recursive CTE for multi-hop relationship traversal (max 3 hops)
- Relationship edge creation from co-occurrence analysis in threads
- Force-directed relationship graph UI (`react-force-graph` or D3)
  - Nodes sized by message count
  - Edges weighted by interaction strength
  - Click to re-center on person, show profile card
- Matches Stitch UI's interactive relationship explorer section

---

### Phase 3 Checkpoint ✓

**What the app can do at this point:**
- Everything from Phase 2 +
- Entity extraction across entire chat history (not just first N lines)
- Human-confirmed alias resolution (Abd = Abdullah)
- Character profiles auto-generated
- Interactive relationship graph

---

## PHASE 4 — Insights

> **Goal:** Automated behavioral analysis, emotion tracking, Memory Cards, Story Mode

### Step 18: Sentiment & Emotion Analysis

🤖 **Agent builds:**
- `backend/app/services/sentiment.py` — Gemini batch labeling (20 messages/call)
- Labels: Happy, Sad, Angry, Romantic, Awkward, Jealous, Supportive, Confused, Neutral
- Stored in `emotion_labels` table
- Time-series aggregation for graphs

---

### Step 19: Event Detection

🤖 **Agent builds:**
- `backend/app/services/event_detector.py`
- Ghosting detection: reply latency spike (>5x rolling average) after negative sentiment message (ADR §4 signals)
- Fight/Argument: Angry cluster + message frequency spike
- Celebration: Happy cluster + birthday/event keywords
- Confession, Distance events
- Stored in `events` table with evidence message IDs and confidence scores

---

### Step 20: Emotion Graph + Conversation Health UI

🤖 **Agent builds:**
- `components/EmotionGraph.tsx` — time-series line chart
- Composite "Conversation Health" metric: frequency + sentiment + reply latency
- Visual trajectory cards: Peak → Conflict → Distance → Recovery
- Matches Stitch UI analytics/insights section

---

### Step 21: Memory Cards + Story Mode

🤖 **Agent builds:**
- Memory Cards generation: First conversation, First nickname, Longest silence, Most romantic exchange, etc.
- Story Mode: structured 5-chapter narrative generated by Gemini from relationship arc
- Book-like reading UI with chapter navigation and embedded citation cards
- Matches Stitch UI's "Stories & Timeline" section

---

### Phase 4 Checkpoint ✓

**What the app can do at this point:**
- Everything from Phase 3 +
- Emotion trajectory graphs per relationship
- Auto-detected life events (ghosting, fights, confessions)
- Personalized Memory Cards
- Story Mode narrative summaries with chapter citations

---

## PHASE 5 — AI Detective

> **Goal:** Investigation workspace for complex multi-hop relational queries  
> This is the core differentiator — shown prominently in the Stitch UI mockup

### Step 22: Investigation Workspace

🤖 **Agent builds:**
- `app/investigate/page.tsx` — full investigation UI matching the Stitch UI hero investigator section
- Natural language investigation queries
- Structured report output:
  - Direct mentions count
  - Indirect mentions (resolved via coreference)
  - Known aliases
  - First-degree connections
  - Interactive timeline
  - Relationship trajectory summary
  - Key events (clickable, cited)
- `backend/app/services/investigator.py` — orchestrates:
  1. Multi-hop Qdrant metadata filter (exhaustive entity recall via `entity_id` payload, not just top-k)
  2. Recursive CTE graph traversal (temporal + frequency + sentiment analysis per entity)
  3. Gemini narrative synthesis of investigation findings

---

### Step 23: Multi-Turn Investigation Follow-Ups

🤖 **Agent builds:**
- Conversation context maintained across investigation turns
- Follow-up queries: "Did Aimi become distant after meeting Abdullah?" → temporal correlation analysis with cited evidence

---

### Phase 5 Checkpoint ✓

**What the app can do at this point:**
- Full AI Detective investigation workspace
- Complex relational queries with multi-hop graph traversal
- Timeline intersection analysis with cited evidence
- Multi-turn investigation conversations

---

## PHASE 6 — Production Hardening

> **Goal:** Secure, monitored, resilient product ready for real users

### Step 24: Security Hardening

🤖 **Agent builds:**
- Rate limiting: `slowapi` — 30 req/min (search), 10 req/min (chat), 5 req/min (upload)
- File validation: valid UTF-8 only, reject binaries, max 50MB, max 500K lines
- Input sanitization: strip HTML/script from all inputs
- Heroku Postgres RLS automated CI test (cross-user isolation on every PR)
- Content Security Policy headers in `next.config.ts`
- CORS locked to production Vercel domain only

---

### Step 25: SPARSE Differential Privacy

🤖 **Agent builds:**
- `backend/app/services/privacy.py` — Mahalanobis noise on sensitive embedding dimensions
- Sensitivity mask learned from 1000 embedding sample (high-variance dimensions = sensitive)
- Applied to all Qdrant-stored embeddings before upsert
- Retrieval quality benchmark: must maintain >95% recall@20 vs. un-noised baseline

---

### Step 26: Error Handling, Resilience, Testing

🤖 **Agent builds:**
- Tenacity retry logic for Groq + Gemini (3 attempts, exponential backoff 2→4→8s)
- Global FastAPI exception handler with Sentry capture
- React Error Boundaries per UI section
- Offline detection banner
- Unit tests: parser, thread detector, chunk builder, hybrid search, evidence builder, privacy
- Integration tests: full upload → search → chat flow
- CI/CD pipeline: `.github/workflows/ci.yml` (PR → tests → preview, merge → production)

---

### Step 27: Performance Optimization

🤖 **Agent builds:**
- Virtualized message list (`@tanstack/react-virtual`)
- Dynamic imports for heavy components (relationship graph, emotion graph, story)
- GZipMiddleware on FastAPI
- asyncpg connection pool tuning (min=5, max=20)
- Analysis cache TTL in FastAPI (5 min)

---

### Step 28: Monitoring + UptimeRobot

🤖 **Agent builds:**
- Sentry integration (backend + frontend)
- Structured JSON logging middleware
- Health endpoint with DB connectivity check

👤 **User provides:**
- `SENTRY_DSN` (backend) + `SENTRY_DSN` (frontend) from Sentry dashboard
- UptimeRobot: create 3 monitors (frontend, backend `/api/health`, Supabase) — agent provides the URLs

---

### Step 29: Data Management + Privacy Policy

🤖 **Agent builds:**
- `DELETE /api/account` — cascade deletes all user data
- `GET /api/export/{chat_id}` — ZIP export of all user data (messages, people, events, stats)
- Privacy policy page and Terms of Service page

👤 **User provides:**
- Review and approval of the privacy policy language, particularly the honest statement about PII scrubbing gaps (ADR §2: must NOT claim "fully anonymized")
- Decision on Gemini API tier: free tier may allow Google to use inputs for model training. For production with sensitive data, consider paid tier (ADR implementation plan §39d warning)

---

### Step 30: Deployment Configuration

🤖 **Agent builds:**
- `backend/Dockerfile` with GLiNER pre-downloaded
- Heroku `Procfile` and `runtime.txt`
- `frontend/vercel.json` with Singapore region
- Production env var documentation

👤 **User provides:**
- Heroku Git remote set up and `heroku login` done
- Vercel project connected to GitHub repo
- All production env vars entered in both dashboards
- Confirmation that `GET /api/health` returns 200 from production URL
- **Pre-launch security checklist sign-off** (43 items in the impl plan — agent will present these as a checklist)

---

## Summary: What User Must Provide per Phase

| Phase | User Must Provide |
|---|---|
| **Phase 0** | All service accounts + API keys + WhatsApp export samples + repo name + domain name |
| **Phase 1** | Credentials entered into dashboards. Validate parser against real export files. |
| **Phase 2** | Qdrant API key + confirm RRF Query API support. Sample multilingual queries for validation. |
| **Phase 3** | Confirm Heroku dyno supports GLiNER CPU. **Review and approve alias suggestions** for their own chat data. |
| **Phase 4** | Nothing (fully automated by agent) |
| **Phase 5** | Nothing (fully automated by agent) |
| **Phase 6** | Sentry DSNs. Privacy policy review. Production deployment sign-off. Gemini tier decision. |

---

## Open Questions (Resolve Before Starting)

> [!IMPORTANT]
> These must be answered before Phase 0 begins:

1. **Stack confirmation**: Use ADR (Heroku + Clerk + Voyage + Qdrant + Groq) or old plan (Render + Supabase Auth + Gemini + pgvector)?
2. **Repo structure**: Is the frontend going in this same repo (`c:\data\webdev\silsila`) or a separate one? The backend already exists at `backend/`.
3. **Starting phase**: Backend `backend/` directory already has files (`requirements.txt`, `app/`, `tests/`). Should the agent **start from the existing backend code** and build onto it, or start fresh?
4. **WhatsApp samples**: Can the user provide real export files now, or will the parser be written against the documented format and validated later?
5. **Heroku vs. Render**: The existing `backend/Dockerfile` exists — is the user already on Render? Or migrating to Heroku per the ADR?
