# yt-transcript Project Status and Roadmap

## Snapshot

Date: 2026-04-15

Verification completed in the project virtualenv:

- `.venv/bin/pytest -q` -> `49 passed`
- `.venv/bin/ruff check src tests` -> `All checks passed!`
- `small check --strict` -> `Verification passed`

The bare shell is not a valid verification environment for this repo unless the project virtualenv is active. Running `pytest` outside the venv currently fails because the package and dependencies are not available there.

## Product Definition

Current product intent, based on the running code, is narrow and coherent:

- Input: a YouTube URL or bare video ID
- Core action: retrieve transcript text with caption-first fallbacks
- Outputs:
  - transient ingest result
  - persisted transcript record in Postgres when enabled
  - markdown note export when enabled

This repo is currently an extraction and persistence service. It is not yet a summarizer, research assistant, browser tool, or general media intelligence system.

That boundary matters. The current codebase stays coherent when it is treated as a reliable transcript substrate that later features can build on.

## Code and Intent Alignment

Areas where intent and code align well:

- Single clear ingestion path in [`src/yt_transcript/lib/pipeline.py`](/Users/justin/jcnagent/Agent/Projects/web-platform/yt-transcript/src/yt_transcript/lib/pipeline.py)
- Thin surfaces in [`src/yt_transcript/cli/main.py`](/Users/justin/jcnagent/Agent/Projects/web-platform/yt-transcript/src/yt_transcript/cli/main.py) and [`src/yt_transcript/api/app.py`](/Users/justin/jcnagent/Agent/Projects/web-platform/yt-transcript/src/yt_transcript/api/app.py)
- Explicit optionality for DB persistence and note export
- Honest treatment of ASR as a fallback, not the primary path
- Good test coverage around parsing, CLI behavior, health checks, notes, and pipeline fallback behavior

Areas where intent is underspecified:

- Human-owned intent in [`.small/intent.small.yml`](/Users/justin/jcnagent/Agent/Projects/web-platform/yt-transcript/.small/intent.small.yml) is effectively empty, so product intent is inferred from code and README rather than being formally declared in the harness.
- The API exposes transcript lookup endpoints, but those endpoints currently return metadata and counts, not transcript content. The product name can imply more than the API actually returns.

## Coherency Gaps

These are the highest-value gaps between apparent intent and actual behavior.

### 1. Partial-success semantics now exist, but need a fuller artifact-state model

`IngestResult` now distinguishes `done` from `partial`, and sink failures after successful extraction no longer abort the whole ingest.

Impact:

- Operators can distinguish extraction success from sink failure, which is an improvement.
- Future multi-artifact workflows still need a fuller state model once summaries and other enrichments exist.

Recommendation:

- Decide on one contract and enforce it consistently.
- Extend the current `done` / `partial` contract into a broader artifact-state model once enrichments are introduced.

### 2. Readiness semantics are improved, but capability modeling is still coarse

The service can now skip DB readiness when `YT_TRANSCRIPT_DATABASE_ENABLED=false`, which makes ingest-only deployments cleaner.

Impact:

- The main ingest-only deployment case is handled.
- More capability-specific readiness will still matter if the service grows additional modes.

Recommendation:

- Keep moving toward capability-specific readiness instead of one global check.

### 3. API naming is clearer, but still split across metadata and content routes

The API now has dedicated `/content` endpoints for transcript text and ordered segments, while the original lookup endpoints remain metadata-first.

Impact:

- The split is explicit now, which reduces surprise.
- Future clients still need to understand which route is metadata and which is content.

Recommendation:

- Keep the split documented clearly, or later unify the resource shape if that proves easier for clients.

### 4. Language policy is implicit and English-biased

Caption retrieval, subtitle fallback, and ASR hints are all English-first. This is consistent in code, but not expressed as a formal product policy.

Impact:

- Non-English support will fail unevenly.
- Operators cannot reason clearly about expected behavior for multilingual content.

Recommendation:

- Make language policy explicit now, even if the answer is "English-only in v0.1.x."

## Hardening Opportunities

Highest-priority hardening work:

1. Deepen result-state contracts.
   `done` / `partial` is a solid start. Summaries and later enrichments will need per-artifact provenance and status.

2. Expand persisted diagnostics.
   Raw metadata and pipeline stage diagnostics can now be written into `raw_payload`, but downstream writes such as note-path updates still deserve richer audit detail.

3. Add real integration tests.
   Current tests are good unit and contract tests. Missing pieces are migration tests, DB write/read integration, and subprocess boundary tests for `yt-dlp`.

4. Add retry and timeout policy around external boundaries.
   `yt-dlp`, caption fetch, and the ASR worker are failure-prone edges. Current behavior is mostly single-attempt.

5. Make ASR configuration explicit.
   The hardcoded `base.en` model and shared-filesystem topology are acceptable for local use but too implicit for broader deployment.

6. Define content-return strategy.
   Decide whether transcript text should be returned from the API, streamed, paginated, or intentionally left as a DB-only concern.

## Paths for Scale

The clean scaling path is additive, not a rewrite.

### Path 1: Stronger extraction substrate

Keep this repo focused on deterministic extraction and storage:

- stable record IDs
- raw metadata capture
- explicit ingest states
- transcript-content API
- cache and dedupe policy

This is the best next step because everything else depends on it.

### Path 2: Enrichment as a separate layer

Add summaries, keywords, outlines, chapters, or embeddings as separate artifacts generated from an already-ingested transcript.

Why this fits:

- preserves current ingestion reliability
- avoids coupling extraction failures to LLM provider failures
- keeps future AI work resumable and auditable

Suggested model:

- `ingest` produces transcript artifacts
- `enrich` produces derived artifacts
- each artifact has its own status and provenance

### Path 3: Asynchronous orchestration

Once enrichment exists, a queue or job table becomes justified. It is not yet necessary for the current narrow product.

Only add this when:

- ingest volume grows
- enrichment fan-out exists
- retries and resumability matter operationally

### Path 4: Multi-surface clients

A browser extension, desktop helper, or UI should come after the extraction and enrichment contracts are stable. Otherwise the UI will hardcode unstable behavior.

## Focused Inspiration from `steipete/summarize`

Reference repo: [steipete/summarize](https://github.com/steipete/summarize)

Useful ideas from its README and product shape:

- transcript-first media flow with fallback transcription
- output modes beyond prose, including JSON diagnostics
- cache-aware, metrics-aware execution
- smart defaults that avoid unnecessary summarization work
- optional slide extraction for video workflows

Features worth borrowing first, without importing its complexity:

### 1. Summary as a separate command and artifact

Do not merge summarization into the existing ingest path. Add a second stage such as:

```bash
yt-transcript summarize "https://youtu.be/VIDEO_ID"
yt-transcript summarize --from-db VIDEO_ID
```

This should read an existing transcript artifact and emit a new summary artifact with explicit provenance.

### 2. JSON diagnostics mode

Expose timings, retrieval path, sink outcomes, quality flags, and future summary metadata in machine-readable JSON.

This is high leverage and low bloat.

### 3. Content-aware caching

Avoid recomputing enrichments for the same transcript content and prompt profile.

A simple cache key based on transcript hash + summary profile is enough to start.

### 4. Smart default modes

Separate:

- `extract`
- `summarize`
- `normalize`
- later: `slides`

Do not hide these behind one overloaded command.

### 5. Video structure extraction later

The most interesting advanced feature to borrow is slide or scene extraction with timestamps, but only after transcript and summary artifacts are stable.

What not to borrow yet:

- browser extension and daemon architecture
- large provider matrix
- broad file-type support
- agent/chat UI
- heavy packaging and distribution work

Those are useful in `summarize` because it is a broad product. They would dilute this repo right now.

## Recommended Next Steps

Phase 1: tighten the extraction contract

1. Add explicit ingest outcome states: `done`, `partial`, `failed`.
2. Add a transcript-content API response shape.
3. Persist raw metadata and stage diagnostics.
4. Make readiness conditional on enabled capabilities.

Phase 2: add minimal summarization

1. Introduce a summary artifact model and storage contract.
2. Add `yt-transcript summarize` as a separate command.
3. Support one provider path first, with JSON output and caching.
4. Keep prompt profiles explicit and versioned.

Phase 3: add media intelligence

1. Add chaptering or section extraction from transcript structure.
2. Evaluate slide extraction for YouTube videos with clear timestamp linkage.
3. Add asynchronous orchestration only when enrichment fan-out justifies it.

## Architectural Guardrail

The highest-risk future mistake is turning `yt-transcript` into a bloated all-in-one media AI tool before its core artifact model is stable.

The durable path is:

- reliable transcript extraction
- explicit persisted artifacts
- derived enrichments as separate stages
- narrow, composable surfaces

If you borrow from `summarize`, borrow the execution patterns and artifact boundaries, not the breadth.
