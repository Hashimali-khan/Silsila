# AI Memory Engine — Final Architecture Decision Record

**Status:** Locked for implementation planning
**Date:** August 27, 2026
**Scope:** WhatsApp-only MVP, 20 active users, up to 120,000 messages per chat log, zero out-of-pocket cost (free tiers + GitHub Student Pack credits)

---

## How to read this document

Each decision includes: the choice, why it wins for this project specifically, the real trade-off you're accepting (not hidden), and any follow-up action required before/during implementation. Where a decision depends on another, that's called out — this pipeline has real coupling between layers, not independent choices.

---

## 1. Ingestion & Parsing

**Decision:** Custom regex-based parser with explicit dual-pattern handling for iOS and Android WhatsApp export formats.

**Why it wins:** Zero cost, runs in milliseconds, and WhatsApp's export format is regular enough that an LLM-based parser would be pure waste — you'd be spending tokens and latency to solve a problem regex already solves deterministically.

**Trade-off accepted:** Any future format drift (WhatsApp changes its export structure) breaks the parser until you patch the regex. Acceptable — this is a maintenance cost, not a correctness risk, since a broken parser fails loudly (parse errors) rather than silently.

**Action:** Collect a handful of real iOS and Android export samples before writing the regex — don't guess at the format differences from memory.

---

## 2. Privacy & PII Scrubbing

**Decision:** Local regex scrubbing (phone numbers, exact name matches → `Participant_A`/`Participant_B` placeholders) before any external API call. No NER model.

**Why it wins:** 100% local, zero cost, zero added ML dependency on a resource-constrained Eco dyno. Removes the highest-risk identifiers (numbers, full names) before data ever leaves your server.

**Trade-off accepted — do not overstate this to users:** Regex will not catch nicknames, indirect references ("your sister," "the guy from work"), or names in nonstandard spelling. This is a real, known gap.

**Action:** Privacy policy language must say "we scrub known identifiers such as phone numbers and names as written" — not "fully anonymized." Don't oversell the guarantee.

---

## 3. Chunking Strategy

**Decision:** Adaptive, thread-based chunking using local time-gap detection (e.g., >4 hours of silence signals a new conversational unit), not fixed-size batches.

**Why it wins:** Preserves natural conversational boundaries instead of splitting an exchange mid-thread. Keeps chunk count — and therefore embedding/storage cost — proportional to actual conversational structure rather than arbitrary line counts.

**Trade-off accepted:** Requires the thread-detection logic to exist before chunking can run — this is a dependency, not a parallel task. Median-based adaptive thresholds (per your original implementation plan) handle chat-rhythm variance better than a single fixed gap value; keep that refinement.

**Action:** Build thread detection first; chunking is downstream of it.

---

## 4. Chunk Context Enrichment

**Decision:** Selective enrichment — only run LLM-based contextual summarization on chunks flagged as ambiguous (short replies, bare pronouns, single-emoji messages, no clear named referent). Everything else embeds raw.

**Why it wins:** Solves the actual problem your research identified (the "wo = Abdullah" isolated-chunk failure) without paying for full contextual retrieval on every chunk. Estimated 70–80% reduction in enrichment-layer LLM calls versus enriching everything, which matters directly for free-tier rate limits.

**Trade-off accepted:** The ambiguity-detection heuristic itself needs to be reasonably good, or you'll under- or over-flag chunks. Start conservative (flag more, not less) and tune down once you see false-positive rates.

**Action:** Define the ambiguity heuristic explicitly (message length threshold, pronoun-without-recent-referent, emoji-only) before building the enrichment step.

---

## 5. Embedding Model

**Decision:** Voyage AI (current `voyage-4` generation), as sole embedding provider for the entire corpus. No cross-provider fallback.

**Why it wins (verified against current 2026 pricing, not assumptions):**
- Voyage's free tier is a **one-time 200 million token grant** on the current model generation.
- Your worst-case volume: ~1.8M tokens per max-size (120k-message) chat log × 20 users ≈ 36M tokens total — comfortably inside the 200M pool with significant headroom for growth and re-embedding during development.
- Cohere's free trial key, by contrast, is capped at **1,000 total API calls per month across all endpoints combined** — this does not cover embedding tens of thousands of chunks per heavy user, even with request batching. The earlier assumption that Cohere was "unlimited, time-throttled" is outdated as of current pricing and does not hold.

**Why no fallback:** Different embedding models produce vectors in incompatible spaces (different dimensionality, different geometry). If some chunks are embedded with Voyage and others silently fall back to a different provider on a rate-limit error, cosine similarity search becomes meaningless for the mismatched subset — and this fails silently (degraded retrieval quality), not loudly (an error you'd notice).

**Trade-off accepted:** The 200M token grant is one-time, not renewing monthly. You will eventually exhaust it as you scale past 20 users or re-embed during iteration.

**Action:** Build a simple cumulative token counter against the 200M ceiling from day one, so you have visibility before you hit it — not after. If a request hits a rate limit, retry against Voyage with backoff; never switch providers mid-corpus.

---

## 6. Vector Storage

**Decision:** Qdrant (managed Cloud free tier) as a dedicated vector database, storing both dense and sparse vectors per chunk.

**Why it wins:** 1GB free, persistent, no auto-pause — solves the in-memory ChromaDB volatility problem (data loss on dyno restart/redeploy) and avoids Supabase's 7-day idle-pause policy. Storing raw text alongside vectors in Qdrant's payload avoids a data-sync problem between two databases.

**Trade-off accepted:** One more service to manage/monitor beyond your Postgres instance. Acceptable given the persistence and native hybrid-search payoff (see #7).

**Action:** Confirm your specific Qdrant Cloud free-tier account supports the Query API's server-side RRF fusion parameter (not just dual-vector storage) before architecting retrieval around it — some hosted tiers lag newer API features.

---

## 7. Retrieval Strategy

**Decision:** Native Qdrant dense + sparse (BM25) hybrid search using the Query API, with server-side Reciprocal Rank Fusion — not a client-side merge across two separate databases.

**Why it wins:** Captures both query modes your users actually need — conceptual ("why are we drifting apart") via dense vectors, and exact-phrase ("what did she say about the vacation") via sparse/BM25. Runs both in parallel in a single server-side call with native RRF, eliminating cross-database orchestration and network round-trips entirely. This corrects an earlier assumption (that Qdrant's text filtering was boolean-only and required a separate Postgres full-text ranker) — Qdrant's dual-vector architecture makes that unnecessary.

**Trade-off accepted:** Ties your retrieval architecture more tightly to Qdrant-specific features rather than portable SQL — acceptable given the operational simplicity gained.

**Action:** Verify sparse vector (BM25) tokenization settings suit code-switched/multilingual text (Urdu/Hinglish) — test this explicitly rather than assuming default tokenization handles it well.

---

## 8. Entity & Alias Resolution

**Decision:** Two-tier detection, not a one-time front-loaded scan:
1. **Free local pass (whole corpus):** heuristic scan for repeated capitalized/proper-noun-shaped tokens not already in the known-alias set — runs across all 120k messages at zero cost.
2. **Targeted LLM pass (only on new candidates):** when the local pass flags an unseen candidate, send a small surrounding window (~±20 messages) to Gemini to resolve whether it's a name/alias and for whom.
3. **Single consolidated Human-in-the-Loop review screen** presenting all candidates for user confirmation before final processing.

**Why it wins:** Solves the real gap in a "first 1,000 lines only" scan — new people can be introduced deep into a multi-month or multi-year chat history, not just at the start. Keeps LLM cost low (only ambiguous/new candidates get sent to Gemini, not the whole corpus) while achieving full-corpus coverage via the free local heuristic. The HITL confirmation step protects against silent misattribution corrupting the vector database — critical given this data is people's private relationship history and a wrong guess propagates everywhere.

**Trade-off accepted:** More moving parts than a single upfront scan; the local heuristic needs reasonable precision to avoid flooding the review screen with false positives.

**Action:** Define what counts as an "unseen candidate" (frequency threshold, capitalization pattern) before implementation.

---

## 9. Knowledge Graph Layer

**Decision:** Pure RAG for MVP — no dedicated graph database (Neo4j, etc.) — but with **resolved-entity metadata tagging** on every chunk once alias resolution (from #8) confirms an identity.

**Why it wins:** Avoids the complexity and sync overhead of a third database system on a zero-dollar budget, appropriate for 20 users. The metadata-tagging addition fixes a real limitation of pure semantic search: vector retrieval is inherently top-k and will miss chunks that are topically related to an entity but semantically distant. Tagging chunks with a resolved `entity_id` lets a query like "trace every connection of Abdullah" become an **exhaustive metadata filter** (all chunks tagged `entity_id=Abdullah`) fed to the LLM, rather than relying on semantic proximity to surface every mention.

**Trade-off accepted:** This still isn't true graph traversal (multi-hop relationship queries across entities) — it's exhaustive single-entity recall, which covers your MVP's actual stated use cases without the infrastructure cost of a graph database.

**Action:** Add `entity_id` (and multiple aliases resolved to the same ID) as a required payload field on every Qdrant chunk from the start — retrofitting this later means re-processing the whole corpus.

---

## 10. Generation Layer (Conversational LLM)

**Decision:** Llama 3.3 70B via Groq as primary, with automatic fallback to Gemini Flash if Groq's ~30 RPM free-tier limit is hit.

**Why it wins:** Higher conversational nuance and emotional-intelligence alignment for reading passive-aggression, drifting interest, and relationship dynamics — the actual core value proposition of the product. This fallback is safe (unlike the embedding-layer fallback in #5) because the output is generated text, not something indexed into a shared mathematical space — there's no corruption risk from switching providers mid-session.

**Trade-off accepted:** Two providers to maintain prompt-parity across (a Groq-tuned prompt may not perform identically on Gemini). Acceptable given the fallback is a safety net for spikes, not the primary path.

**Action:** Test your actual system prompts against both models before launch, not just one — don't assume the fallback performs equivalently untested.

---

## 11. Backend Framework & Hosting

**Decision:** FastAPI on Heroku Eco Dynos, funded by GitHub Student Pack credits.

**Why it wins:** $0 out-of-pocket cost, full Python NLP ecosystem access, async-native for the I/O-bound calls this pipeline makes constantly (Groq, Voyage, Qdrant, Gemini).

**Trade-off accepted (corrected from initial assumption):** Eco dynos **do sleep** after 30 minutes of no web traffic — this is not "24/7 unlimited execution." Cold starts take 10–30 seconds. `BackgroundTasks` runs in the same process as web traffic, so a large ingestion job competes with live requests on the same dyno.

**Mitigations (locked in):**
1. **UptimeRobot keep-alive ping** against a `/health` endpoint every ~25 minutes — prevents most sleep cycles for free, using monitoring you've already selected (see #15).
2. **Honest frontend loading state:** if a request takes >3s with no response, show "waking up your analysis engine, this can take up to 30 seconds" instead of a silent/blank spinner.
3. **Idempotent job design:** store ingestion progress (e.g., "chunks 4,000 of 12,000 embedded") in Postgres, not just in memory, so a dyno restart mid-job resumes rather than restarts from zero or double-spends your Voyage token budget re-embedding.
4. **Documented future upgrade path (not built now):** if simultaneous large uploads start degrading the experience for browsing users, Heroku's dedicated worker dyno type separates background jobs from web traffic — a config change, not a rearchitecture, when you actually hit this ceiling.

**Action:** Implement #1–#3 before launch. Treat #4 as a documented trigger condition, not a build task.

---

## 12. Relational Database & Auth

**Decision:** Heroku Mini Postgres + Clerk for auth, with **native PostgreSQL Row-Level Security (RLS)** enforced at the database level, plus a centralized query/repository layer and automated cross-user isolation tests in CI.

**Why it wins:** Heroku Mini Postgres avoids Supabase's 7-day idle-auto-pause, which would disrupt a low-traffic 20-user app between usage cycles. Clerk removes auth boilerplate for free up to far more users than you need. Critically: **native Postgres RLS is not a Supabase-exclusive feature** — enabling `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` with a policy filtering on a per-request session variable (`current_setting('app.user_id')`) recovers the same database-level guarantee Supabase provided, on plain Heroku Postgres, at zero extra cost.

**Why this matters more than usual for this project:** the data here is people's private relationship messages. A single forgotten `WHERE user_id = ...` in application code is a full cross-user data leak. Relying on developer discipline to catch this in every query is not an acceptable control for this data sensitivity.

**Layered defense (all three, not just one):**
1. **Native Postgres RLS policy** — makes it structurally impossible for a query to return another user's rows, regardless of application-layer bugs.
2. **Centralized repository functions** (e.g., `get_messages_for_chat(chat_id, current_user)`) — no route handler writes raw queries directly; the `user_id` scoping lives in one place, not scattered across endpoints.
3. **Automated CI isolation test** — create two fake users, insert data for both, assert every list/read endpoint for User A returns zero rows belonging to User B. Run on every PR, not just pre-launch.

**Trade-off accepted:** More setup work upfront than trusting Supabase's built-in RLS — but this converts a "must remember every time" risk into a database-enforced guarantee, which is the property that mattered about Supabase in the first place.

**Action:** Write the RLS policy and repository layer before any endpoint touches message data — this is foundational, not a later hardening pass.

---

## 13. Background Job Processing

**Decision:** FastAPI `BackgroundTasks` for ingestion, with native WebSockets or Server-Sent Events for real-time progress push to the frontend — no polling, no Supabase Realtime dependency.

**Why it wins:** A 120k-message ingestion (parse → scrub → chunk → selectively enrich → embed → store) can take well beyond Heroku's ~30-second router timeout on a synchronous request. Returning an immediate `{"status": "processing", "job_id": ...}` and pushing progress over a live connection avoids both the timeout and the wasted cycles of polling.

**Trade-off accepted:** Runs in-process with web traffic (see #11's mitigations — idempotent job design in particular protects this path).

**Action:** Persist job progress to Postgres (not just an in-memory dict) so progress survives a dyno cycle — same requirement as #11's idempotency point; don't implement it twice.

---

## 14. Frontend

**Decision:** Next.js 15 on Vercel (App Router).

**Why it wins:** Free tier is generous at this scale, native streaming/SSR support fits a chat-style Q&A interface and long-form generated reports well, and it's an uncontroversial, well-supported choice with no real competing trade-off at this project's scope.

**Trade-off accepted:** A second deploy target to manage alongside the Heroku backend — acceptable, standard practice for this stack pattern.

---

## 15. Monitoring & Operations

**Decision:** Sentry (free tier) for error tracking + UptimeRobot for uptime/health monitoring — including reuse of UptimeRobot as the Eco dyno keep-alive mechanism from #11.

**Why it wins:** Zero-maintenance, standard, sufficient coverage for a 20-user MVP without the setup/maintenance cost of a full observability stack.

**Trade-off accepted:** None significant at this scale.

---

## Cross-Cutting Rules (apply across every layer above)

1. **No cross-provider fallback for anything that gets indexed into a shared mathematical space** (embeddings). Fallback is safe for generation (text output) but never safe for retrieval (vector space).
2. **User data isolation is enforced at the database layer (RLS), not trusted to application code discipline alone** — layered with a repository pattern and CI tests as backup, not as the primary control.
3. **Every long-running job persists its progress to Postgres**, not memory — this single requirement protects you against dyno sleep, dyno restarts, and deploys simultaneously.
4. **Privacy claims to end users must match what the scrubbing pipeline actually guarantees** — no overstating "full anonymization" when regex-based scrubbing has known gaps (nicknames, indirect references).

---

## Summary Table

| Layer | Decision | Primary Risk Mitigated |
|---|---|---|
| 1. Parsing | Regex dual-pattern (iOS/Android) | Format drift (low risk, loud failure) |
| 2. Privacy/PII | Local regex scrubbing | Cost/complexity; documented gap on nicknames |
| 3. Chunking | Adaptive thread-based (time-gap) | Context loss from arbitrary splits |
| 4. Enrichment | Selective (ambiguity-flagged only) | Rate limits / cost at full-corpus enrichment |
| 5. Embeddings | Voyage AI, single provider, no fallback | Cross-provider vector space corruption |
| 6. Vector storage | Qdrant Cloud (persistent, dense+sparse) | Data loss from in-memory/ephemeral storage |
| 7. Retrieval | Native Qdrant hybrid (server-side RRF) | Cross-database orchestration complexity |
| 8. Alias resolution | Local full-corpus scan + targeted LLM + HITL | Missed entities introduced late in history |
| 9. Knowledge graph | Pure RAG + entity_id metadata tagging | Top-k retrieval missing exhaustive entity mentions |
| 10. Generation | Groq Llama 3.3 70B + Gemini fallback | EQ/nuance quality; safe fallback for text-only output |
| 11. Backend/hosting | FastAPI on Heroku Eco + keep-alive + idempotent jobs | Dyno sleep, cold starts, job loss on restart |
| 12. DB & Auth | Heroku Postgres + Clerk + native RLS + CI tests | Cross-user data leak (highest-severity risk in this app) |
| 13. Job processing | BackgroundTasks + WebSockets/SSE | Request timeout on large ingestion |
| 14. Frontend | Next.js 15 on Vercel | — (uncontroversial) |
| 15. Monitoring | Sentry + UptimeRobot | Blind spots on errors/uptime |

---

*This document reflects decisions finalized through architectural review. Next step: translate into a phased implementation plan (parsing → storage → retrieval → generation → production hardening).*
