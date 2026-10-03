# HalfSpace Phase 0 Audit

Audit date: 2026-10-03  
Scope: repository source, configuration, documentation, CI, local browser runtime at `http://127.0.0.1:3000`  
Phase status: **complete; no feature code changed**

## Executive finding

The current repository is not the football broadcast-tracking application described in the requested acceptance criteria. It is a StatsBomb event/360 sequence-search and scouting workbench. The UI can search indexed event sequences, render event-location/360 snapshots, show deterministic sample animations, and generate a dossier. It does not reconstruct player and ball tracking from ordinary broadcast video.

This is a **P0 product-scope blocker**, not a polish issue. The requested ball, lineup, calibration, playback, and SoccerNet metric acceptance criteria cannot be satisfied by changing the current UI alone because the required data and ML pipeline do not exist in this repository.

## Evidence captured

- Browser capture: `/` initially renders an empty search state with no loaded match or clip.
- Browser capture: the first-run suggested search is hardcoded to “Show Arsenal counter-attacks into the box”.
- Browser capture: `/dossier?team=Arsenal` opens with Arsenal preselected and a populated “Sample report”.
- Browser capture: the dossier evidence drawer labels playback “Illustrative 11v11 sample animation · not match tracking”.
- Browser console during the suggested search: `Failed to load resource: the server responded with a status of 503 (Service Unavailable)`. The UI then falls back to sample mode.
- Browser capture: `/design` is a visual component catalog, including a “Mounted sequence sample” stress fixture, not a product tracking view.
- Editor diagnostics: no TypeScript/Python diagnostics were reported for the inspected files.
- The repository already contains uncommitted changes before this audit. They were not reverted or modified.

## Architecture map

### Runtime components

| Area | Location | Responsibility |
|---|---|---|
| Next.js web app | `apps/web/app` | Search workspace, dossier workspace, design catalog, SVG pitch and sample playback |
| Search route proxy | `apps/web/app/api/search/route.ts` | Proxies SSE search requests to `API_URL` |
| Dossier route proxy | `apps/web/app/api/scout/dossier/route.ts` | Proxies SSE dossier requests to `API_URL` |
| FastAPI service | `services/api/app/main.py` | `/health`, `/search`, `/scout/dossier` |
| Search/retrieval | `services/api/app/search.py`, `services/api/app/search_models.py` | Structured query parsing, Postgres/pgvector retrieval, reranking |
| Scouting graph | `services/api/app/agent_graph.py`, `services/api/app/scout_tools.py` | LangGraph planner/retriever/tactician/critic/verifier |
| StatsBomb ingestion | `services/api/app/ingest.py` and related modules | Loads open event/360 data into Postgres |
| ML encoder | `ml/` | PyTorch sequence embedding training/export/indexing |
| Local infrastructure | `docker-compose.yml` | Postgres/pgvector, Redis, API, web |
| CI | `.github/workflows/ci.yml` | Web build/E2E, API pytest, fixture checks, optional Promptfoo |

### Data flow

1. The browser sends natural-language sequence-search or dossier requests.
2. Next route handlers proxy requests to FastAPI as SSE.
3. FastAPI parses/retrieves StatsBomb-derived sequences from Postgres/pgvector and optionally invokes the scouting graph.
4. If the API request fails, the browser silently switches to deterministic local fixtures in `apps/web/app/lib/demo.ts`.
5. The pitch is SVG. Playback advances through prebuilt event/fixture frames; no video frames are decoded or inferred.

### Missing boundary

There is no source path for:

- broadcast video upload/decode/frame sampling;
- SoccerNet dataset download, labels, or ground-truth evaluator;
- player/ball detector or tiled high-resolution inference;
- temporal tracking, ReID, Kalman/physics association, or gap interpolation;
- camera calibration/homography estimation and refinement;
- tracking schema with per-frame confidence/state;
- 11-player/team/referee/goalkeeper constraints;
- tracking metrics in meters, ID switches, or per-stage pipeline timings.

## Findings

### P0 — Product and data-model mismatch

**Root cause:** the repository implements event-sequence retrieval rather than broadcast reconstruction.

**Evidence:** [README.md](/Users/kollicharanadithya/Desktop/HalfSpace/README.md:3) describes a “Football sequence search and scouting workbench”; [docs/ARCHITECTURE.md](/Users/kollicharanadithya/Desktop/HalfSpace/docs/ARCHITECTURE.md:3) describes StatsBomb ingestion, Postgres, pgvector, and LangGraph. [SequencePlayer.tsx](/Users/kollicharanadithya/Desktop/HalfSpace/apps/web/app/components/SequencePlayer.tsx:7) accepts arrays of already-materialized `SequenceFrame` objects, not video or tracker output.

**Impact:** all tracking-specific acceptance items are currently unimplementable without establishing a new ML/data pipeline and its contracts.

### P0 — Hardcoded teams and defaults violate the requested source-of-truth rule

**Root cause:** deterministic demo fixtures and URL defaults were authored as product content.

**Evidence:**

- [demo.ts](/Users/kollicharanadithya/Desktop/HalfSpace/apps/web/app/lib/demo.ts:6) hardcodes eight club names and competitions.
- [ProductApp.tsx](/Users/kollicharanadithya/Desktop/HalfSpace/apps/web/app/components/ProductApp.tsx:207) hardcodes an Arsenal suggestion; [ProductApp.tsx](/Users/kollicharanadithya/Desktop/HalfSpace/apps/web/app/components/ProductApp.tsx:240) hardcodes the dossier URL with `team=Arsenal`.
- [DossierApp.tsx](/Users/kollicharanadithya/Desktop/HalfSpace/apps/web/app/components/DossierApp.tsx:32) initializes `team` to Arsenal.
- [DossierApp.tsx](/Users/kollicharanadithya/Desktop/HalfSpace/apps/web/app/components/DossierApp.tsx:64) falls back to Arsenal when no query parameter exists.
- [apps/web/e2e/product.spec.ts](/Users/kollicharanadithya/Desktop/HalfSpace/apps/web/e2e/product.spec.ts:8) encodes Arsenal as the primary product flow.

**Impact:** empty/no-match state cannot be the only source of truth; a stranger is led to a specific club and synthetic records before loading metadata.

### P0 — Sample data is structurally indistinguishable from product data

**Root cause:** fixtures contain complete 11v11 coordinates, IDs, scores, competitions, and claims, then are rendered as normal results with a small sample label.

**Evidence:** [demo.ts](/Users/kollicharanadithya/Desktop/HalfSpace/apps/web/app/lib/demo.ts:92) creates eight deterministic `DEMO_RESULTS`; [demo.ts](/Users/kollicharanadithya/Desktop/HalfSpace/apps/web/app/lib/demo.ts:49) manufactures both lineups and ball paths. [SequencePlayer.tsx](/Users/kollicharanadithya/Desktop/HalfSpace/apps/web/app/components/SequencePlayer.tsx:76) labels this only as “Illustrative 11v11 sample animation · not match tracking”.

**Impact:** the UI has no clip/match metadata picker, no distinction between loaded tracking and a bundled demo clip, and no valid path to team colors from data.

### P0 — No ball-tracking state or metrics

**Root cause:** the ball is a single coordinate in each precomputed frame.

**Evidence:** [SequencePlayer.tsx](/Users/kollicharanadithya/Desktop/HalfSpace/apps/web/app/components/SequencePlayer.tsx:7) types `ball` as `Point`; [Markers.tsx](/Users/kollicharanadithya/Desktop/HalfSpace/apps/web/app/components/Markers.tsx:23) always draws the ball; [demo.ts](/Users/kollicharanadithya/Desktop/HalfSpace/apps/web/app/lib/demo.ts:18) generates a mathematical path. There are no `tracked`, `interpolated`, `lost`, confidence, meter-error, recall, precision, or tracked-frame fields anywhere in the app.

**Impact:** no way to hide lost detections, reject teleporting/outliers, report confidence, or measure before/after quality on SoccerNet.

### P0 — Lineups and identities are synthetic, not constrained tracks

**Root cause:** the fixture generator always emits two arrays of 11 numbered markers.

**Evidence:** [demo.ts](/Users/kollicharanadithya/Desktop/HalfSpace/apps/web/app/lib/demo.ts:45) defines fixed home/away positions; [demo.ts](/Users/kollicharanadithya/Desktop/HalfSpace/apps/web/app/lib/demo.ts:74) maps both arrays into every frame. There is no referee class, goalkeeper role, off-screen state, ReID identity, track merging, or formation inference.

**Impact:** the requested “at most 11”, referee exclusion, entering/leaving behavior, ID-switch reduction, and lineup/formation panel have no input data or implementation boundary.

### P1 — Playback is discrete event-frame playback, not smooth broadcast playback

**Root cause:** rendering is driven by React state changes at source-frame boundaries.

**Evidence:** [SequencePlayer.tsx](/Users/kollicharanadithya/Desktop/HalfSpace/apps/web/app/components/SequencePlayer.tsx:25) stores `frameIndex` in React state; [SequencePlayer.tsx](/Users/kollicharanadithya/Desktop/HalfSpace/apps/web/app/components/SequencePlayer.tsx:44) advances until a source frame boundary and calls `setFrameIndex`; [SequencePlayer.tsx](/Users/kollicharanadithya/Desktop/HalfSpace/apps/web/app/components/SequencePlayer.tsx:94) scrubs by frame index. `requestAnimationFrame` is present, but there is no time-interpolated render state, One Euro/Savitzky-Golay filter, video clock, homography smoothing, or 60fps tracking playback.

**Impact:** the current implementation cannot prove no teleporting or sustained 60fps for 22 tracked entities plus overlays. The README’s 16.67 ms sample is a synthetic stress fixture, not a real clip profile.

### P1 — Required tactical overlays and view modes are absent

**Root cause:** the current pitch exposes only event-derived arrows, pressure rectangles, visible-area polygons, and a generic zone grid.

**Evidence:** [Pitch.tsx](/Users/kollicharanadithya/Desktop/HalfSpace/apps/web/app/components/Pitch.tsx:31) renders the zone grid; [SequencePlayer.tsx](/Users/kollicharanadithya/Desktop/HalfSpace/apps/web/app/components/SequencePlayer.tsx:74) renders `PressZone`, `PassArrow`, and `visibleArea`. No pitch-control layer, passing network, formation/compactness layer, half-space toggle, or legend/explanation contract exists.

### P1 — API failures are masked by success-shaped fallback

**Root cause:** broad `catch` blocks replace any error with sample output after an artificial delay.

**Evidence:** [ProductApp.tsx](/Users/kollicharanadithya/Desktop/HalfSpace/apps/web/app/components/ProductApp.tsx:158) catches all search failures and calls `demoSearch`; [DossierApp.tsx](/Users/kollicharanadithya/Desktop/HalfSpace/apps/web/app/components/DossierApp.tsx:55) catches all dossier failures and installs `DEMO_DOSSIER`. The browser observed a 503 during search, but the user is shown sample results rather than a recoverable error.

**Impact:** outages, invalid input, and real data failures are hidden; there is no explicit error state with retry/recovery context.

### P1 — Hard constraint against LLMs/paid APIs is violated by the runtime design

**Root cause:** the current product’s core parsing, embedding, reranking, and dossier architecture depends on optional/required generative and embedding services.

**Evidence:** [services/api/pyproject.toml](/Users/kollicharanadithya/Desktop/HalfSpace/services/api/pyproject.toml:1) includes `openai`, `langgraph`, `langfuse`, and `sentence-transformers`; [docker-compose.yml](/Users/kollicharanadithya/Desktop/HalfSpace/docker-compose.yml:31) configures `OPENAI_API_KEY`, `gpt-4o-mini`, and `text-embedding-3-small`; [README.md](/Users/kollicharanadithya/Desktop/HalfSpace/README.md:5) says live retrieval and generated dossiers require an OpenAI key.

**Impact:** the current primary architecture is incompatible with the no-LLM/no-paid-API constraint, even though a local sample fallback exists.

### P1 — Metrics and reproducible tracking regression gates do not exist

**Root cause:** evaluation is focused on parser/search fixtures and UI smoke flows.

**Evidence:** [.github/workflows/ci.yml](/Users/kollicharanadithya/Desktop/HalfSpace/.github/workflows/ci.yml:22) runs API pytest and fixture checks; [README.md](/Users/kollicharanadithya/Desktop/HalfSpace/README.md:60) explicitly marks retrieval accuracy and search p95 as not measured and reports only synthetic mounted-player timing. No SoccerNet metric command, fixed tracking clip, ID-switch threshold, ball error threshold, or pipeline-stage benchmark was found.

### P2 — Documentation overstates readiness for the requested product

**Root cause:** existing documentation accurately describes the current search demo but not the requested broadcast-tracking product.

**Evidence:** [README.md](/Users/kollicharanadithya/Desktop/HalfSpace/README.md:62) reports Lighthouse 100/100 and a 201-player synthetic frame sample; [docs/EVALS.md](/Users/kollicharanadithya/Desktop/HalfSpace/docs/EVALS.md:1) describes sample data and two product flows. Neither is evidence for broadcast tracking, real ball error, lineup constraints, or device-level 60fps.

## Acceptance checklist baseline

| Criterion | Phase 0 result | Evidence |
|---|---|---|
| Zero hardcoded teams/defaults | **Fail** | Arsenal defaults and fixture clubs listed above |
| Ball tracked/interpolated/lost + measured error | **Fail** | Ball is only a `Point`; no evaluator |
| Lineups constrained and identity-aware | **Fail** | Fixed synthetic 11v11 arrays |
| Smooth playback and 60fps profile | **Fail / unmeasured** | Source-frame React state playback; only synthetic timing claim |
| Loading/empty/error states, accessibility, no console errors | **Partial** | Loading and empty exist; broad fallback hides errors; browser observed a 503 console error |
| Tactical overlays correct and toggleable | **Fail** | Only event arrows/press zone/zone grid |
| Tests/CI/one-command run | **Partial** | `make demo-up` and CI exist for current search product; no tracking tests |
| Free-tier deploy-ready | **Partial** | Vercel/Fly docs exist, API path requires paid/LLM services |
| First-time sample onboarding | **Partial** | Sample search is clickable, but it teaches event search rather than broadcast tracking |

## Phase 0 recommended implementation boundary

Do not start by polishing the existing search UI. The first implementation slice should establish a free, deterministic tracking vertical:

1. Define a typed tracking schema for clip metadata, calibrated player/ball frames, confidence/state, team colors, and evaluation annotations.
2. Add a bundled or downloaded open sample clip and a reproducible preprocessing command.
3. Implement a baseline detector/tracker and evaluator before changing the UI.
4. Expose the baseline through a local/precomputed artifact format so the frontend can work without a paid backend.
5. Replace hardcoded demo teams with metadata-derived teams and a true empty/onboarding state.
6. Only then add smoothing, constraints, overlays, and playback profiling against real outputs.

This sequencing is required to make the requested metrics and acceptance evidence measurable rather than cosmetic.
