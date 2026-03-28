# UI Redesign Plan — Modern, Functional, Multi-Purpose

**Status:** Plan
**Date:** 2026-03-28

---

## 1. Design Goals

| Goal | Current | Target |
|------|---------|--------|
| Layout | Fixed sidebar (290px) + main | Top header bar + collapsible session tray + main |
| Navigation | Sidebar buttons (Research, Skills, Docs, Settings) | Header tabs with logo + version pill |
| Sessions | Embedded in sidebar, always visible | Collapsible left tray (can minimize to icon strip) |
| Language | Math/proof-centric ("Prove", "theorem", "lemma") | Multi-purpose research ("Research", "findings", "analysis") |
| Branding | "Claw" references, 🦞 emoji, ClawHub | Clean "EurekaLab" branding, neutral research icon |
| Look | Basic form fields, flat panels, 90s feel | Polished cards, subtle shadows, micro-interactions |
| Typography | Space Grotesk (keep) | Space Grotesk (keep) — works well |
| Colors | Warm beige + blue primary (keep) | Keep scheme — it's distinctive |
| Background | Squared paper grid (keep) | Keep — it's on-brand for research |

---

## 2. Layout Redesign

### Current Layout
```
┌──────────┬────────────────────────────────────┐
│          │                                    │
│ Sidebar  │          Main Content              │
│ (290px)  │                                    │
│          │                                    │
│ Logo     │   [View content based on           │
│ Nav      │    sidebar selection]               │
│ Sessions │                                    │
│ Settings │                                    │
│ Docs     │                                    │
│          │                                    │
└──────────┴────────────────────────────────────┘
```

### Target Layout
```
┌────────────────────────────────────────────────┐
│ Logo v0.6.1 │ Research │ Skills │ Docs │ ⚙ │ ☰ │  ← Header bar
├─────────┬──────────────────────────────────────┤
│         │                                      │
│ Session │         Main Content                 │
│  Tray   │                                      │
│ (collap-│   [Workspace / Skills / Docs /       │
│  sible) │    Settings content]                 │
│         │                                      │
│ [sess1] │                                      │
│ [sess2] │                                      │
│ [sess3] │                                      │
│         │                                      │
│  [+New] │                                      │
│         │                                      │
│  [◀]    │  ← Collapse button                   │
└─────────┴──────────────────────────────────────┘
```

### Header Bar
- Fixed top, full width, ~48px height
- Left: Logo (small, 28px) + "EurekaLab" + version pill
- Center: Tab buttons — Research, Skills, Docs (active tab highlighted)
- Right: Settings gear icon + tray toggle (hamburger ☰)
- Subtle bottom border, semi-transparent backdrop blur

### Session Tray (Left)
- Default: 260px width, shows session list
- Collapsed: 0px width (hidden), icon in header to toggle
- Smooth slide animation (200ms)
- Contains: session list + "New Session" button
- Remembers collapsed state in localStorage

---

## 3. Text & Language Updates

### Principle
Replace all proof-specific language with generic research terms. The UI should feel like a **multi-purpose research assistant**, not a theorem prover.

### Key Replacements

| Current | Replacement | Files |
|---------|-------------|-------|
| "What would you like to prove?" | "What would you like to research?" | NewSessionForm.tsx |
| "State a conjecture and get a full proof" | "State a claim and build a rigorous argument" | NewSessionForm.tsx |
| "generates theorems, and writes a complete mathematical proof" | "analyzes the literature, develops insights, and writes a complete paper" | NewSessionForm.tsx |
| "Prove" (mode label) | "Prove / Formalize" | NewSessionForm.tsx |
| "Proving the theorem" | "Developing core analysis" | ProofCtrl.tsx |
| "proof checkpoint" | "analysis checkpoint" | ProofCtrl.tsx |
| "Proof Strategies & Skills" | "Research Strategies" | SkillsView.tsx |
| "proof technique" | "research approach" | SkillLibrary.tsx |
| "proof strategies" | "research strategies" | WizardPanel.tsx |
| "mathematical question" | "research question" | WizardPanel.tsx |
| "formulating theorems, proving them" | "analyzing literature, developing insights" | WizardPanel.tsx |
| "Proof" (workspace tab) | "Analysis" | WorkspaceTabs.tsx |
| "ClawHub" | "SkillHub" | ClawHubPanel.tsx, SkillsView.tsx, SkillLibrary.tsx, SkillCard.tsx |
| 🦞 emoji | 🔬 or ✨ | WizardPanel.tsx |

### ProofPanel → AnalysisPanel
The "Proof" tab shows theorem statements, lemma DAGs, and proof status. For non-proof papers, it should show the relevant analysis output. Rename to "Analysis" and make it paper-type-aware:
- **proof**: Show theorem + lemma DAG (current behavior)
- **survey**: Show taxonomy + comparison summary
- **review**: Show screening log + synthesis themes
- **experimental**: Show hypothesis + results summary
- **discussion**: Show thesis + argument structure

---

## 4. Visual Polish

### Cards & Surfaces
- **Current**: Flat backgrounds with thin borders
- **Target**: Subtle elevation with `box-shadow: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04)`
- Slightly more rounded corners on interactive elements (12px → 14px)
- Hover states: gentle scale(1.01) + shadow increase on cards

### Session Items
- **Current**: Compact list items with status dots
- **Target**: Mini cards with more breathing room, clear status badges, paper-type indicator

### New Session Form
- **Current**: Mode cards in a row, textarea fields
- **Target**: Mode cards as a proper selector grid (2×3 for 6 modes), paper-type dropdown below modes, cleaner field styling

### Stage Track
- **Current**: Horizontal step dots with emojis
- **Target**: Clean progress stepper with line connectors, active stage highlighted, completed stages ticked

### Config Form
- **Current**: Dense form with many fields
- **Target**: Tabbed sections (LLM, Output, Theory, Advanced) — same content, better organization

### Workspace Tabs
- **Current**: Basic tab bar
- **Target**: Pill-style tabs with subtle background on active, smooth underline transition

---

## 5. Specific Component Changes

### Header (NEW: `components/layout/Header.tsx`)
```
Logo [v0.6.1]  │  Research  Skills  Docs  │  ⚙  ☰
```
- 48px height, backdrop-blur, border-bottom
- Tabs use the same active view state as current sidebar
- Settings icon (gear) replaces the text "Settings"
- Tray toggle (hamburger) shows/hides session tray

### SessionTray (RENAME from Sidebar: `components/layout/SessionTray.tsx`)
- Just the session list + "New Session" button
- Collapsible (width transitions from 260px to 0)
- No nav items (moved to header)
- No brand block (moved to header)

### App.tsx Layout Change
```css
.app-shell {
  display: grid;
  grid-template-rows: var(--header-height) 1fr;
  grid-template-columns: auto 1fr;  /* auto = tray width (0 when collapsed) */
}
.app-header { grid-column: 1 / -1; }  /* spans full width */
.session-tray { grid-row: 2; }
.main-shell { grid-row: 2; }
```

### Skills Page
- Rename "Proof Strategies & Skills" → "Research Strategies"
- Rename "ClawHub" → "SkillHub" throughout
- Update description text to be paper-type-agnostic

### Onboarding Wizard
- Replace 🦞 with 🔬
- Update all proof-specific language
- Add step mentioning paper types
- Update pipeline description: "Survey → Ideation → Analysis → Writing"

---

## 6. Files to Change

### New Files
| File | Purpose |
|------|---------|
| `components/layout/Header.tsx` | Top navigation header bar |
| `components/layout/SessionTray.tsx` | Collapsible session list tray |

### Major Rewrites
| File | Change |
|------|--------|
| `App.tsx` | Grid layout from sidebar+main → header+tray+main |
| `Sidebar.tsx` | Delete (replaced by Header + SessionTray) |
| `NewSessionForm.tsx` | Language updates, mode grid layout |
| `WorkspaceTabs.tsx` | Rename "Proof" → "Analysis" |
| `ProofPanel.tsx` | Rename, make paper-type-aware |
| `ProofCtrl.tsx` | Rename labels, update running messages |
| `WizardPanel.tsx` | Remove proof language, add paper types step |
| `SkillsView.tsx` | Rename hero, update descriptions |
| `ClawHubPanel.tsx` | Rename to SkillHubPanel |
| `SkillLibrary.tsx` | Update search placeholder, ClawHub references |
| `SkillCard.tsx` | Update source label from "ClawHub" to "SkillHub" |

### Text-Only Updates
| File | What |
|------|------|
| `StageTrack.tsx` | Emoji and label for "Proof" stage |
| `TheoryFeedback.tsx` | Label text |
| `PaperPanel.tsx` | "proven" count label |
| `ConfigForm.tsx` | Section labels and field descriptions |
| `TheoryDrawerBody.tsx` | Empty state text |
| `LivePanel.tsx` | Completed/idle state messages |

### CSS Changes
| Section | Change |
|---------|--------|
| `.app-shell` | Grid from 2-col → 2-row+2-col |
| `.sidebar` | Remove, replace with `.app-header` + `.session-tray` |
| `.nav-item` | Move to header tab styles |
| `.brand-block` | Move to header, make compact |
| Cards/surfaces | Add subtle shadows, polish hover states |
| Tab bar | Pill-style active indicator |
| `.session-item` | More breathing room, paper-type badge |

### Type Changes
| File | What |
|------|------|
| `types/skill.ts` | `'clawhub'` → `'skillhub'` source type |

---

## 7. Implementation Order

### Phase 1: Layout (header + tray)
1. Create Header.tsx and SessionTray.tsx
2. Rewrite App.tsx grid layout
3. Update CSS (remove sidebar, add header + tray styles)
4. Delete old Sidebar.tsx
5. Add tray collapse toggle with localStorage persistence

### Phase 2: Language cleanse
1. Bulk text replacements across all 17 files
2. Rename ClawHub → SkillHub (5 files)
3. Update WizardPanel steps
4. Rename ProofPanel → AnalysisPanel

### Phase 3: Visual polish
1. Card elevation and hover states
2. Pill-style workspace tabs
3. Session item cards with paper-type badges
4. Stage track redesign (line-connected stepper)
5. Config form tabbed layout

### Phase 4: Build + test
1. TypeScript check
2. Production build
3. Visual testing with `eurekalab ui`
4. Commit and push

---

## 8. What NOT to Change

- **Color scheme** — warm beige + blue works
- **Font** — Space Grotesk is good
- **Squared paper background** — distinctive, on-brand
- **Workspace tabs concept** — Live, Analysis, Paper, Logs, History
- **Session list functionality** — rename/rerun/delete actions
- **Gate system** — direction selection, theory review overlays
- **Content gap banner, IdeationPanel, InjectionDrawer** — recently built, good
- **DocsView** — just built, works
