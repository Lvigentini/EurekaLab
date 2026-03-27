# UI Overhaul — API Endpoints + Frontend Components

**Status:** Plan
**Date:** 2026-03-27
**Baseline:** v0.4.0 (193 tests, SQLite storage, non-linear pipeline)

---

## 1. Current State

The existing UI is a React 18 + TypeScript + Vite SPA (35 components, 231KB bundle) served by a pure-Python HTTP server. It supports session creation (prove/explore/from-papers), live pipeline tracking, 3 interactive gates, proof/paper/logs panels, pause/resume, and settings management.

**Communication:** HTTP polling (adaptive 500ms-3000ms), no WebSocket/SSE.
**State:** Zustand stores + localStorage persistence. Server has in-memory `UIServerState`.
**Gate system:** Thread-safe `review_gate.py` with blocking `wait_*()` / `submit_*()` pattern.

### What's Missing

10 backend features (v0.2-0.4) have zero UI support:

| # | Feature | Backend | API | UI |
|---|---------|---------|-----|----|
| 1 | Version history | VersionStore + SessionDB | None | None |
| 2 | Version diff | diff_versions() | None | None |
| 3 | Version checkout | VersionStore.checkout() | None | None |
| 4 | Content gap report | ContentGapAnalyzer | None | None |
| 5 | IdeationPool | IdeationPool model | None | None |
| 6 | Inject paper/idea/draft | CLI inject commands | None | None |
| 7 | from-bib entry | BibLoader + CLI | None | None |
| 8 | from-draft entry | DraftAnalyzer + CLI | None | None |
| 9 | from-zotero entry | ZoteroAdapter + CLI | None | None |
| 10 | Zotero push-back | ZoteroAdapter.push_* | None | None |

---

## 2. Phase A: API Endpoints (Python only)

All endpoints go in `eurekalab/ui/server.py`. No frontend changes needed.

### A1. Version History Endpoints

```
GET  /api/runs/<run_id>/versions
     → { versions: [{ version_number, trigger, timestamp, completed_stages, changes }] }

GET  /api/runs/<run_id>/versions/<version_number>
     → { version_number, trigger, timestamp, completed_stages, changes, snapshot_keys: [...] }
     (snapshot_keys = list of artifact keys in the snapshot, NOT the full snapshot_json)

POST /api/runs/<run_id>/versions/diff
     Body: { v1: int, v2: int }
     → { changes: ["Bibliography: +paper 'Smith 2024' (p1)", "Theory: +proven lemma L1 '...'"] }

POST /api/runs/<run_id>/versions/checkout
     Body: { version_number: int }
     → { ok: true, new_head: int, completed_stages: [...] }
     (creates a checkout version, restores artifacts to disk)
```

**Implementation notes:**
- Load `VersionStore` from `SessionDB` using the session's run_id
- For `GET /versions`: return metadata only (no snapshot_json — too large)
- For `/diff`: call `diff_versions()` from `eurekalab/versioning/diff.py`
- For `/checkout`: call `store.checkout()`, commit a new version, persist bus to disk

### A2. Content Gap Endpoint

```
GET  /api/runs/<run_id>/content-gap
     → {
         full_text: int,
         abstract_only: int,
         metadata_only: int,
         missing: int,
         has_gaps: bool,
         degraded_papers: [{ paper_id, title, content_tier, arxiv_id }]  (top 10)
       }
```

**Implementation:**
- Load bibliography from `runs/<run_id>/bibliography.json`
- Run `ContentGapAnalyzer.analyze(bib)`
- Return summary + top degraded papers

### A3. IdeationPool Endpoints

```
GET  /api/runs/<run_id>/ideation-pool
     → {
         directions: [{ title, hypothesis, composite_score, ... }],
         selected_direction: { ... } | null,
         injected_ideas: [{ text, source, injected_at, incorporated }],
         emerged_insights: [...],
         has_new_input: bool,
         version: int
       }

POST /api/runs/<run_id>/ideation-pool/inject
     Body: { type: "idea" | "paper" | "draft", text: str, source?: str }
     → { ok: true, pool_version: int, session_version: int }
     (for "paper": text is arXiv ID or path; for "idea": text is the idea; for "draft": text is file path)
```

**Implementation:**
- Load ideation_pool from bus (`runs/<run_id>/ideation_pool.json` or `KnowledgeBus.load()`)
- For inject: load bus, inject into pool, persist_incremental (creates version), return version numbers

### A4. Alternative Entry Points

Extend the existing `POST /api/runs` handler to support new modes:

```
POST /api/runs
     Body: {
       mode: "detailed" | "reference" | "exploration" | "from_bib" | "from_draft" | "from_zotero",
       domain: str,
       query?: str,

       // from_bib specific
       bib_content?: str,        // raw .bib file content (pasted or uploaded)
       pdf_dir?: str,            // optional local path to PDFs

       // from_draft specific
       draft_content?: str,      // raw draft text (pasted or uploaded)
       draft_instruction?: str,  // free-text instruction

       // from_zotero specific
       zotero_collection_id?: str,

       // shared
       additional_context?: str,
       selected_skills?: str[]
     }
```

**Implementation:**
- `from_bib`: parse bib_content with `BibLoader`, optionally match PDFs, pre-populate bibliography on bus
- `from_draft`: analyze draft_content with `DraftAnalyzer`, set additional_context + draft_path
- `from_zotero`: call `ZoteroAdapter.import_collection()`, pre-populate bibliography

### A5. Zotero Endpoints

```
GET  /api/zotero/status
     → { configured: bool, api_key_set: bool, library_id: str }

GET  /api/zotero/collections
     → { collections: [{ key, name, num_items }] }
     (requires ZOTERO_API_KEY + ZOTERO_LIBRARY_ID)

POST /api/runs/<run_id>/push-to-zotero
     Body: { collection_name?: str }
     → { ok: true, papers_pushed: int, notes_pushed: int, collection_key: str }
```

**Implementation:**
- `/zotero/status`: check if settings have api_key and library_id
- `/zotero/collections`: create ZoteroAdapter, call `_zot.collections()` from pyzotero
- `/push-to-zotero`: load bus, find unfiled papers, call adapter.push_papers + push_note

### A6. Session Management Endpoints

```
GET  /api/sessions
     → { sessions: [{ session_id, domain, query, mode, status, created_at, completed_stages }] }
     (from SessionDB — richer than current /api/runs which only shows in-memory runs)

POST /api/sessions/clean
     Body: { older_than_days: int, status_filter?: "failed" | "completed" | "all" }
     → { removed: int, freed_kb: float }
```

---

## 3. Phase B: Frontend Components (React + TypeScript)

### B1. Version History Tab (new 5th workspace tab)

**Location:** `frontend/src/components/workspace/VersionPanel.tsx`

**UI Design:**
```
┌─────────────────────────────────────────────────────┐
│  Version History                          [Checkout] │
│                                                      │
│  ● v007  stage:writer:completed        2m ago        │
│  ● v006  stage:theory_review:completed 15m ago       │
│  ● v005  stage:theory:completed        22m ago       │
│  ○ v004  inject:idea:spectral_methods  25m ago       │
│  ● v003  stage:direction:selected      30m ago       │
│  ● v002  stage:ideation:completed      35m ago       │
│  ● v001  stage:survey:completed        40m ago       │
│                                                      │
│  ┌─ Diff v005 → v006 ───────────────────────┐       │
│  │  Theory: +proven lemma L3 'concentration' │       │
│  │  Theory: status in_progress -> proved     │       │
│  └───────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────┘
```

**Behavior:**
- Polls `GET /api/runs/<id>/versions` on the same adaptive interval
- Click a version to see its metadata (trigger, stages, changes)
- Select two versions to see diff (calls `/versions/diff`)
- "Checkout" button on any version → confirmation dialog → `POST /versions/checkout`
- Version entries color-coded: green (stage complete), yellow (injection), blue (checkout)

**Files to create:**
- `frontend/src/components/workspace/VersionPanel.tsx`
- `frontend/src/components/workspace/VersionTimeline.tsx` (vertical timeline)
- `frontend/src/components/workspace/VersionDiff.tsx` (diff display)

**Files to modify:**
- `frontend/src/components/workspace/WorkspaceTabs.tsx` (add "History" tab)
- `frontend/src/store/uiStore.ts` (add `'history'` to `ActiveWsTab` type)

### B2. Content Gap Banner (in Live panel)

**Location:** `frontend/src/components/workspace/ContentGapBanner.tsx`

**UI Design:**
```
┌─────────────────────────────────────────────────────┐
│  ⚠ Content Gaps Detected                            │
│                                                      │
│  Full text: 5  │  Abstract only: 8  │  Missing: 2   │
│                                                      │
│  Papers with limited content:                        │
│  ○ [abstract] Optimal Bounds for Bandits (2401.123)  │
│  ○ [metadata] Concentration Inequalities             │
│  ○ [missing]  Smith et al. 2024                      │
│                                                      │
│  [Provide PDF Directory]  [Skip]                     │
└─────────────────────────────────────────────────────┘
```

**Behavior:**
- Shown in LivePanel after survey completes (poll content-gap endpoint)
- "Provide PDF Directory" opens a text input for local path
- "Skip" dismisses the banner
- Auto-hides when all papers are full_text

**Files to create:**
- `frontend/src/components/workspace/ContentGapBanner.tsx`

**Files to modify:**
- `frontend/src/components/workspace/LivePanel.tsx` (conditionally render banner after survey)

### B3. IdeationPool Panel (in Live panel or new drawer)

**Location:** `frontend/src/components/workspace/IdeationPanel.tsx`

**UI Design:**
```
┌─────────────────────────────────────────────────────┐
│  Ideation Pool (v3)                    [Inject Idea] │
│                                                      │
│  Selected Direction:                                 │
│  ★ "Optimal regret bounds via..." (0.82)             │
│                                                      │
│  Other Directions:                                   │
│  ○ "Spectral approach to..." (0.71)                  │
│  ○ "Information-theoretic..." (0.65)                 │
│                                                      │
│  Injected Ideas (2):                                 │
│  💡 "What about spectral methods?" — user, 5m ago    │
│  💡 "New paper: Smith 2024" — inject:paper, 3m ago   │
│                                                      │
│  Insights from Theory (1):                           │
│  🔍 "Lemma L3 failed — assumption too strong"        │
└─────────────────────────────────────────────────────┘
```

**Behavior:**
- Polls `GET /api/runs/<id>/ideation-pool`
- "Inject Idea" opens a text input → `POST /ideation-pool/inject`
- Shows incorporated vs unincorporated ideas differently
- Visible when ideation has completed (directions exist)

**Files to create:**
- `frontend/src/components/workspace/IdeationPanel.tsx`

**Files to modify:**
- `frontend/src/components/workspace/LivePanel.tsx` (show IdeationPanel after ideation completes)

### B4. Injection Drawer (for paused sessions)

**Location:** `frontend/src/components/controls/InjectionDrawer.tsx`

**UI Design:**
```
┌─────────────────────────────────────────┐
│  Inject into Session                     │
│                                          │
│  ┌─ Type ────────────────────────────┐  │
│  │ ○ Paper (arXiv ID or PDF)         │  │
│  │ ○ Idea (free text)                │  │
│  │ ○ Draft (paste content)           │  │
│  └───────────────────────────────────┘  │
│                                          │
│  ┌─ Content ─────────────────────────┐  │
│  │                                    │  │
│  │ [text input / textarea]            │  │
│  │                                    │  │
│  └───────────────────────────────────┘  │
│                                          │
│  [Inject]  [Cancel]                      │
└─────────────────────────────────────────┘
```

**Behavior:**
- Accessible from session controls when status is `paused`
- Type selector changes the input field (single line for paper, textarea for idea/draft)
- Calls `POST /api/runs/<id>/ideation-pool/inject`
- Shows success with version number

**Files to create:**
- `frontend/src/components/controls/InjectionDrawer.tsx`

**Files to modify:**
- `frontend/src/components/controls/ProofCtrl.tsx` (add "Inject" button when paused)

### B5. New Session Form — Additional Entry Modes

**Location:** Modify `frontend/src/components/session/NewSessionForm.tsx`

Add 3 new modes to the MODES array:

```typescript
{
  key: 'from_bib',
  label: 'From .bib',
  description: 'Start from your bibliography + local PDFs',
  fields: ['bib_content', 'pdf_dir', 'domain'],
}
{
  key: 'from_draft',
  label: 'From Draft',
  description: 'Start from a draft paper with instructions',
  fields: ['draft_content', 'draft_instruction', 'domain'],
}
{
  key: 'from_zotero',
  label: 'From Zotero',
  description: 'Import papers from a Zotero collection',
  fields: ['zotero_collection_id', 'domain'],
  requires: 'zotero_configured',
}
```

**UI additions:**
- `from_bib`: textarea for pasting .bib content + optional PDF directory path
- `from_draft`: textarea for pasting draft content + instruction field
- `from_zotero`: dropdown populated from `GET /api/zotero/collections` (disabled if not configured)

**Files to modify:**
- `frontend/src/components/session/NewSessionForm.tsx` (add modes, conditional fields)
- `frontend/src/types/run.ts` (extend InputSpec with new fields)

### B6. Zotero Push Button (on completed sessions)

**Location:** Add to `frontend/src/components/session/SessionTopBar.tsx`

**Behavior:**
- Button visible when session is `completed` and Zotero is configured
- Calls `POST /api/runs/<id>/push-to-zotero`
- Shows result: "Pushed 5 papers to 'EurekaLab Results'"

### B7. Sessions Management View

**Location:** `frontend/src/components/session/SessionsManager.tsx`

**Replaces/enhances:** The sidebar session list gets a "manage" view with:
- Full session table from `GET /api/sessions` (SQLite-backed, shows all sessions including old ones)
- Bulk selection + delete
- Filter by status, domain, age
- "Clean old sessions" button (calls `POST /api/sessions/clean`)

---

## 4. Implementation Order

### Phase A (Python — no frontend build needed)
| Task | Endpoint | Complexity | Depends On |
|------|----------|-----------|-----------|
| A1 | Version endpoints (4) | Medium | VersionStore |
| A2 | Content gap endpoint | Low | ContentGapAnalyzer |
| A3 | IdeationPool endpoints (2) | Medium | IdeationPool |
| A4 | Extended POST /api/runs | High | BibLoader, DraftAnalyzer, ZoteroAdapter |
| A5 | Zotero endpoints (3) | Medium | ZoteroAdapter |
| A6 | Session management endpoints (2) | Low | SessionDB |

**Estimated:** 6 tasks, ~400 lines of Python in server.py

### Phase B (React + TypeScript — requires npm install + build)
| Task | Component | Complexity | Depends On |
|------|-----------|-----------|-----------|
| B1 | VersionPanel + timeline + diff | High | A1 |
| B2 | ContentGapBanner | Low | A2 |
| B3 | IdeationPanel | Medium | A3 |
| B4 | InjectionDrawer | Medium | A3 |
| B5 | NewSessionForm extensions | High | A4, A5 |
| B6 | Zotero push button | Low | A5 |
| B7 | SessionsManager | Medium | A6 |

**Estimated:** 7 tasks, ~1500 lines of React/TypeScript

### Recommended Start
1. **Phase A first** (Python only, testable via curl, unblocks Phase B)
2. **Phase B in priority order:** B2 (gap banner) → B3+B4 (ideation+injection) → B1 (version history) → B5 (entry modes) → B6+B7 (Zotero+management)

---

## 5. Technical Considerations

### File Upload
The current server uses basic `http.server` — no multipart form handling. For file uploads (bib, draft, PDF):
- **Option 1:** Accept raw text content in JSON body (paste into textarea — works for .bib and .tex)
- **Option 2:** Add multipart handling to the server (more complex but proper file upload)
- **Recommendation:** Start with Option 1 (paste). Add proper file upload later if needed.

### Polling vs. Pushing for Version Updates
The version timeline should update in near-real-time during a running session. Current polling (1200ms for active sessions) is sufficient — versions are committed at stage boundaries which are minutes apart.

### Session State Sync
The UI currently maintains its own session list in localStorage + in-memory. The new `GET /api/sessions` (SQLite-backed) should be the source of truth. Migration path:
1. Add `/api/sessions` endpoint that returns SessionDB data
2. Frontend merges: DB sessions (historical) + in-memory sessions (live)
3. Eventually drop localStorage persistence for sessions

### Build Pipeline
Frontend development requires:
```bash
cd frontend && npm install    # one-time
make dev                      # hot-reload on :5173, API proxy to :7860
make build                    # production build → eurekalab/ui/static/
```

React components should follow existing patterns:
- CSS modules in `frontend/src/styles/`
- Zustand stores for state
- `apiGet`/`apiPost` from `frontend/src/api/client.ts`
- TypeScript strict mode
