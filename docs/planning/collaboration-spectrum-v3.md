# Collaboration Spectrum v3 — Adaptive Prompts + Adversarial Review

**Status:** Plan
**Date:** 2026-03-29

---

## 1. Core Design Principle

**No mode selectors. No level toggles. The UI adapts to what the user provides.**

The amount of AI involvement at each stage is determined by what the user puts in — not by a preset. If you give the system 3 papers and say "find more," it searches around your seeds. If you give it nothing, it searches broadly. If you give it your entire bibliography, it just checks for gaps. Same stage, same UI, different behaviour based on input.

This is **progressive disclosure through input**, not configuration.

---

## 2. The Adaptive Prompt Pattern

Each stage presents a **flexible input surface** — a combination of:
- **What do you want?** (text prompt — always available)
- **What do you already have?** (optional structured input — papers, outline, draft text, etc.)
- **How should AI help?** (optional guidance — implicit from what's provided)

The AI reads the ratio of user-provided vs. empty fields and adjusts:

```
User provides: nothing          → AI does everything, presents results for approval
User provides: seeds/hints      → AI builds on the user's starting point
User provides: complete input   → AI reviews, critiques, identifies gaps
```

This is not three modes. It's a **continuous spectrum** that the user navigates naturally by choosing what to fill in.

---

## 3. Stage-by-Stage Design

### Stage 1: Literature Search

**Input surface:**

```
┌─────────────────────────────────────────────────────────────┐
│  Literature Search                                           │
│                                                              │
│  What are you researching?                                   │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ [text field — topic, question, or domain]               ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
│  ▸ I already have some papers (optional)                     │
│    ┌───────────────────────────────────────────────────────┐│
│    │ [drop zone / text area for paper IDs, .bib, Zotero]  ││
│    │ Paste arXiv IDs, upload .bib, or connect Zotero       ││
│    └───────────────────────────────────────────────────────┘│
│                                                              │
│  [Start searching]                                           │
└─────────────────────────────────────────────────────────────┘
```

**AI behaviour by input:**

| User provides | AI does |
|---------------|---------|
| Just a topic | Broad search across databases. Presents papers in batches for curation. |
| Topic + 1-3 seed papers | Searches around the seeds: citation graph, similar papers, same authors. Fills gaps. |
| Topic + full .bib/Zotero | Gap analysis only: "You have 25 papers. You're missing X, Y, Z. Here are 8 candidates." |
| Topic + seed papers + "focus on methods that use spectral analysis" | Targeted search combining seeds + user direction. |

**After search completes — Paper Curation Panel:**

```
┌─────────────────────────────────────────────────────────────┐
│  Found 18 papers                                    [Search more] │
│                                                              │
│  ★ Smith 2024 — "Optimal Bounds for Bandits"                │
│    Why: Directly addresses your question. Cited by 3 of     │
│    your seed papers.                                         │
│    Content: [full text]  Source: [arXiv]                     │
│    [✓ Keep]  [✗ Remove]  [Find similar]                     │
│                                                              │
│  ○ Jones 2023 — "Concentration Inequalities"                 │
│    Why: Key technique paper. Used by 12 papers in this area.│
│    Content: [abstract only] ⚠                               │
│    [✓ Keep]  [✗ Remove]  [Find similar]  [Get full text]    │
│                                                              │
│  ... more papers ...                                         │
│                                                              │
│  Search strategy: "arXiv: 'contextual bandits regret bound' │
│  (142 results) → ranked by citation overlap with seeds"      │
│  [Modify search]                                             │
│                                                              │
│  [Proceed with 15 papers →]                                  │
└─────────────────────────────────────────────────────────────┘
```

**Key transparency features:**
- Every paper has a "Why" explanation
- Search strategy is visible and modifiable
- Content tier shown (full text / abstract / metadata) with action to get full text
- User can add/remove individual papers, request more like a specific one

---

### Stage 2: Direction / Framing

**Input surface:**

```
┌─────────────────────────────────────────────────────────────┐
│  Research Direction                                          │
│                                                              │
│  Based on your 15 papers, here are possible directions:      │
│                                                              │
│  1. "Regret bounds under non-stationarity"                   │
│     Strength: Gap in literature, 3 papers lay groundwork     │
│     Risk: May require assumptions that limit applicability   │
│     [Select]  [Modify]                                       │
│                                                              │
│  2. "Unified framework for linear and kernel bandits"        │
│     Strength: High novelty, combines two active threads      │
│     Risk: Technically ambitious, may not close cleanly       │
│     [Select]  [Modify]                                       │
│                                                              │
│  ▸ Or describe your own direction                            │
│    ┌───────────────────────────────────────────────────────┐│
│    │ [text area — your thesis, angle, or question]         ││
│    └───────────────────────────────────────────────────────┘│
│                                                              │
│  ▸ I already have a direction — just critique it             │
│    ┌───────────────────────────────────────────────────────┐│
│    │ [text area — paste your direction/thesis]             ││
│    │ [AI will challenge it: gaps, risks, counterarguments] ││
│    └───────────────────────────────────────────────────────┘│
│                                                              │
│  [Proceed with direction →]                                  │
└─────────────────────────────────────────────────────────────┘
```

**AI behaviour by input:**

| User provides | AI does |
|---------------|---------|
| Nothing (picks from AI proposals) | AI proposes 3-5 directions with pros/cons/risks |
| Modifies an AI proposal | AI refines: "Good adjustment. This changes the risk profile because..." |
| Types their own direction | AI evaluates: strengths, risks, what's needed, what could go wrong |
| Pastes existing direction + "critique it" | Full devil's advocate: "A reviewer would say...", "This assumes...", "Missing: ..." |

---

### Stage 3: Analysis / Core Work

**Input surface:**

```
┌─────────────────────────────────────────────────────────────┐
│  Analysis                                    [paper type: survey] │
│                                                              │
│  Your direction: "Unified framework for bandits"             │
│                                                              │
│  ▸ AI-proposed structure:                                    │
│    □ Taxonomy of bandit approaches (3 categories)            │
│    □ Per-category deep analysis                              │
│    □ Comparison table (7 dimensions)                         │
│    □ Gap identification                                      │
│    [Run this analysis]  [Modify structure]                   │
│                                                              │
│  ▸ Or provide your own analysis / outline                    │
│    ┌───────────────────────────────────────────────────────┐│
│    │ [text area — paste your outline, notes, or analysis]  ││
│    │ AI will review, fill gaps, and strengthen              ││
│    └───────────────────────────────────────────────────────┘│
│                                                              │
│  ▸ Ask AI for specific analysis tasks                        │
│    ┌───────────────────────────────────────────────────────┐│
│    │ "Compare Smith 2024 and Jones 2023 on sample          ││
│    │ complexity bounds"                                     ││
│    └───────────────────────────────────────────────────────┘│
│    [Run task]                                                │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**AI behaviour by input:**

| User provides | AI does |
|---------------|---------|
| Nothing (accepts AI structure) | Full autonomous analysis per paper type |
| Modifies AI structure | Runs modified analysis, flags if something important was removed |
| Pastes own analysis | Reviews it: missing evidence, logical gaps, unsupported claims |
| Specific task requests | Runs targeted analysis and presents results |

---

### Stage 4: Writing

**Input surface:**

```
┌─────────────────────────────────────────────────────────────┐
│  Writing                                                     │
│                                                              │
│  Sections:  [Introduction] [Background] [Analysis] ...       │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ [Rich text editor — write your section here]            ││
│  │                                                          ││
│  │ Or leave empty and [Generate scaffold for this section]  ││
│  │                                                          ││
│  │ ┌─ AI suggestions (live) ─────────────────────────────┐ ││
│  │ │ ℹ Consider citing Smith 2024 here (supports claim)  │ ││
│  │ │ ⚠ This paragraph claims X but your evidence shows Y │ ││
│  │ │ 💡 Strong opening. Consider adding a roadmap.        │ ││
│  │ └─────────────────────────────────────────────────────┘ ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
│  [Generate scaffold]  [Request review]  [Proceed →]          │
└─────────────────────────────────────────────────────────────┘
```

**AI behaviour by input:**

| User provides | AI does |
|---------------|---------|
| Nothing (clicks "Generate scaffold") | Generates a full draft section (clearly labelled as AI-generated) |
| Partial text + empty sections | Generates scaffolds for empty sections, reviews written sections |
| Complete section text | Real-time suggestions: citation gaps, logical issues, style notes |
| Full paper pasted | Comprehensive review (see Stage 5) |

**Scaffolds vs. user text:**
- AI-generated text is visually distinct (lighter background, "AI scaffold" label)
- User-edited text is tracked as user-owned
- Final output clearly attributes which sections were user-written vs. AI-scaffolded

---

### Stage 5: Review (The Critical Stage)

This is where the AI provides the most value. The review stage has **configurable reviewer personas** — the user chooses what kind of feedback they want.

**Input surface:**

```
┌─────────────────────────────────────────────────────────────┐
│  Review                                                      │
│                                                              │
│  Choose your reviewer:                                       │
│                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ 🔴       │  │ 🟡       │  │ 🟢       │  │ 🔵       │    │
│  │Adversary │  │ Rigorous │  │Construct-│  │ Journal  │    │
│  │          │  │          │  │ive       │  │ Specific │    │
│  │Tear it   │  │Thorough  │  │Focus on  │  │Review as │    │
│  │apart.    │  │fair      │  │how to    │  │if for a  │    │
│  │Find every│  │review.   │  │improve.  │  │specific  │    │
│  │weakness. │  │Major +   │  │Strengths │  │venue.    │    │
│  │          │  │minor.    │  │first.    │  │          │    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘    │
│                                                              │
│  ▸ Custom reviewer instructions (optional)                   │
│    ┌───────────────────────────────────────────────────────┐│
│    │ "Focus especially on whether my statistical methods   ││
│    │ are appropriate for the sample size"                   ││
│    └───────────────────────────────────────────────────────┘│
│                                                              │
│  [Run review]                                                │
│                                                              │
│  ── Review Results ──────────────────────────────────────── │
│                                                              │
│  🔴 MAJOR (3)                                                │
│  1. Section 3.2: Claim "X outperforms Y" is not supported   │
│     by your experimental setup. You tested on dataset A but  │
│     the claim generalises to all datasets.                   │
│     → Suggestion: Qualify the claim or add datasets B, C.    │
│     [Addressed ✓]  [Disagree — explain why]                  │
│                                                              │
│  2. Missing comparison with Lee 2024 — the most cited recent │
│     paper in this area. A reviewer will notice this omission.│
│     → Suggestion: Add comparison in Section 4 table.         │
│     [Addressed ✓]  [Disagree — explain why]                  │
│                                                              │
│  🟡 MINOR (5)                                                │
│  1. Abstract is 280 words — most venues target 200.          │
│     [Addressed ✓]  [Skip]                                    │
│  ...                                                         │
│                                                              │
│  💡 SUGGESTIONS (4)                                          │
│  1. Strong motivation in Section 1. Consider adding a        │
│     concrete example to make it more accessible.             │
│  ...                                                         │
│                                                              │
│  Progress: 2/3 major addressed, 3/5 minor addressed          │
│  [Re-run review]  [Generate response to reviewers]           │
└─────────────────────────────────────────────────────────────┘
```

**Reviewer Persona System:**

Reviewer personas are **pluggable files** — same architecture as the skills system. Built-in personas ship with EurekaLab; additional personas (journal-specific, expert reviewers) can be loaded from a registry, shared, or sold.

### Built-In Personas (Free, ships with EurekaLab)

| Persona | System Prompt Essence | Output Style |
|---------|----------------------|-------------|
| **Adversarial** (🔴) | "Your job is to find every weakness. Be the toughest reviewer this paper could face. If it survives you, it survives anyone. Attack assumptions, methodology, novelty, and claims." | Harsh but specific. Every critique has evidence. No softening. |
| **Rigorous** (🟡) | "You are a thorough, fair peer reviewer. Evaluate methodology, clarity, novelty, and completeness. Classify issues as major/minor. Be honest but balanced." | Standard peer review format. Major/minor/suggestion. Balanced tone. |
| **Constructive** (🟢) | "Your goal is to help the author improve. Start with strengths. For every weakness, suggest a specific improvement. Be encouraging but honest." | Strengths first. Every critique paired with actionable fix. Warm but rigorous. |

### Journal-Specific Personas (Loadable — Premium Potential)

Each journal persona is a `.md` or `.json` file that encodes:
- The journal's scope and aims
- Typical reviewer expectations (novelty threshold, methodology standards)
- Formatting requirements (word limits, section structure, citation style)
- Common rejection reasons for that venue
- Tone and depth expectations

```yaml
# Example: ~/.eurekalab/reviewers/neurips-2026.yaml
name: "NeurIPS 2026"
type: journal
icon: "🔵"
scope: "Machine learning, computational neuroscience, optimization, learning theory"
standards:
  novelty: "Must significantly advance the state of the art"
  methodology: "Formal proofs or rigorous experiments required"
  format: "9 pages + unlimited appendix, NeurIPS LaTeX template"
  common_rejections:
    - "Incremental improvement over existing work"
    - "Missing comparison with concurrent work"
    - "Experimental setup does not match claims"
review_prompt: |
  You are reviewing for NeurIPS 2026. This is a top-tier ML venue.
  Evaluate: significance, novelty, correctness, clarity, related work.
  Score 1-10 on each dimension. Provide overall recommendation:
  Accept / Weak Accept / Borderline / Weak Reject / Reject.
  Be calibrated to NeurIPS acceptance rate (~25%).
```

**Example journal personas:**
- NeurIPS, ICML, ICLR (ML conferences)
- Nature, Science (broad-scope journals)
- JMLR, PAMI, TPDS (domain-specific journals)
- PLOS ONE, Scientific Reports (open access)
- ACL, EMNLP (NLP conferences)
- CVPR, ECCV (computer vision)
- CHI, CSCW (HCI)

### Expert Reviewer Personas (Loadable — Premium Potential)

Expert personas simulate a reviewer with specific disciplinary expertise. They catch things a general reviewer would miss:

```yaml
# Example: ~/.eurekalab/reviewers/statistician.yaml
name: "Statistician"
type: expert
icon: "📊"
expertise: "Statistical methodology, experimental design, causal inference"
focus_areas:
  - "Appropriate statistical test selection"
  - "Sample size and power analysis"
  - "Multiple comparison corrections"
  - "Confidence interval interpretation"
  - "Effect size reporting"
  - "Assumption violations"
review_prompt: |
  You are a statistical methods expert reviewing this paper.
  Focus specifically on:
  - Are the statistical tests appropriate for the data?
  - Is the sample size sufficient? Was power analysis conducted?
  - Are assumptions (normality, independence, etc.) met or tested?
  - Are confidence intervals reported alongside p-values?
  - Are multiple comparisons properly corrected?
  - Are effect sizes reported and interpreted?
  Ignore: writing style, novelty, related work (other reviewers handle those).
```

**Example expert personas:**
- **Statistician** — statistical methods, experimental design, causal inference
- **Methodologist** — research design, validity threats, reproducibility
- **Domain Expert** (configurable) — deep knowledge of a specific sub-field
- **Ethics Reviewer** — ethical implications, bias, dual use, informed consent
- **Reproducibility Checker** — code availability, data access, method detail, parameter reporting
- **Writing Coach** — clarity, structure, academic English, readability scores
- **Citation Auditor** — citation completeness, self-citation ratio, missing key references
- **Accessibility Reviewer** — plain language, figure descriptions, colour-blind safety

### Persona Registry Architecture

```
~/.eurekalab/
  reviewers/                     # User's installed reviewer personas
    adversarial.yaml             # Built-in (shipped with app)
    rigorous.yaml                # Built-in
    constructive.yaml            # Built-in
    neurips-2026.yaml            # Installed from registry
    jmlr.yaml                    # Installed from registry
    statistician.yaml            # Installed from registry
    my-custom-reviewer.yaml      # User-created
```

**Persona file format:**
```yaml
name: "Display Name"
type: "builtin" | "journal" | "expert" | "custom"
icon: "emoji"
description: "One-line description shown in persona selector"
author: "Creator name"
version: "1.0"
# For journal type:
scope: "Journal scope description"
standards: { ... }
common_rejections: [...]
# For expert type:
expertise: "Area of expertise"
focus_areas: [...]
# For all types:
review_prompt: |
  The full system prompt for this reviewer persona.
  Can use {venue}, {paper_type}, {domain} placeholders.
# Optional:
scoring_dimensions: ["novelty", "rigor", "clarity", "significance"]
scoring_scale: "1-10"
recommendation_options: ["Accept", "Weak Accept", "Borderline", "Weak Reject", "Reject"]
```

**Loading and discovery:**
- Built-in personas ship in `eurekalab/reviewer_personas/` (package data)
- User personas in `~/.eurekalab/reviewers/`
- CLI: `eurekalab reviewer list`, `eurekalab reviewer install <name>`
- API: `GET /api/reviewers` (lists all available personas)
- Future: registry/marketplace for sharing and selling persona packs

### Multi-Reviewer Stacking

Users can run **multiple reviewers** on the same paper in sequence:

```
1. Run "Adversarial" → get worst-case critique
2. Address major issues
3. Run "NeurIPS 2026" → check venue fit
4. Run "Statistician" → verify methods
5. Run "Constructive" → final polish suggestions
```

Each reviewer's comments are tracked separately. The user sees a combined view with comments attributed to each reviewer persona.

### Revenue Model (Open Core)

| Tier | What's Included | Cost |
|------|----------------|------|
| **Free** (open source) | 3 built-in personas (adversarial, rigorous, constructive) + custom persona creation | Free |
| **Journal Packs** | Curated journal personas (e.g. "Top ML Venues" pack: NeurIPS, ICML, ICLR, JMLR, PAMI) | Paid per pack |
| **Expert Packs** | Expert reviewer personas (e.g. "Methods Pack": statistician, methodologist, reproducibility) | Paid per pack |
| **Custom** | User creates their own personas from the YAML template | Free (tool is free, content is user's) |

The app itself stays fully open source. The personas are text files — users can always create their own. The paid packs offer **curated, tested, calibrated** personas that have been validated against real journal standards.

**Review interaction features:**
- User marks each comment as **Addressed** or **Disagree** (with explanation)
- AI tracks resolution progress per reviewer persona
- Re-run review after revisions — AI checks if previous issues are resolved
- "Generate response to reviewers" — produces a structured rebuttal document
- Multiple review rounds (user can run adversarial first, then constructive, then journal-specific)
- Custom instructions stack on top of any persona: "Focus on statistical methods"
- Review history preserved in version store — see how feedback evolved

---

## 4. The Hidden Full Auto

For users who want the current autonomous pipeline (all AI, minimal interaction):

- **Not visible by default** in the UI
- Enabled via Settings → Advanced → "Enable full automation mode"
- When enabled, adds a toggle at session creation: "Run fully automated"
- Runs the current pipeline with auto-approve gates
- Output is clearly labelled: "This paper was generated autonomously by EurekaLab"
- Useful for: bulk exploration, initial reconnaissance, time pressure

---

## 5. What This Means Architecturally

### Backend: Mostly unchanged

The pipeline, agents, and version store all remain. What changes:

| Component | Change |
|-----------|--------|
| **GateController** | Enhanced to present richer input surfaces (paper curation, direction debate, outline approval) |
| **MetaOrchestrator** | Reads what the user provided at each gate and adjusts agent behaviour accordingly |
| **ReviewerAgent** (new) | Dedicated agent with pluggable persona registry (built-in + journal + expert + custom) |
| **WriterAgent** | Gains a "scaffold" mode (generates section drafts) and a "review" mode (critiques user text) |
| **SurveyAgent** | Gains transparency output: search strategy, per-paper relevance explanation |
| **InputSpec** | No new fields needed — the existing `additional_context`, `paper_ids`, `draft_content` etc. already capture user input |

### Frontend: Significant redesign of workspace panels

| Panel | Change |
|-------|--------|
| **Live** | Becomes the adaptive prompt surface — shows current stage with input fields |
| **Papers** | Enhanced with accept/reject, relevance explanations, search transparency |
| **Analysis** (was Proof) | Shows analysis structure, editable outline, AI vs. user content |
| **Draft** (new, replaces Paper tab) | Writing editor with inline AI suggestions and scaffold generation |
| **Review** (new) | Reviewer persona selector, structured feedback, resolution tracking |
| **History** | Unchanged — works even better in this model |

### New Agent: ReviewerAgent with Persona Registry

```python
class ReviewerPersona:
    """A loadable reviewer persona — from YAML file."""
    name: str
    type: str           # builtin, journal, expert, custom
    icon: str
    description: str
    review_prompt: str
    scoring_dimensions: list[str]
    # ... loaded from YAML

class ReviewerAgent(BaseAgent):
    """Critical reviewer with pluggable persona registry."""

    def __init__(self, ...):
        super().__init__(...)
        self._personas = self._load_personas()  # built-in + ~/.eurekalab/reviewers/

    def _load_personas(self) -> dict[str, ReviewerPersona]:
        """Load all personas: built-in package data + user directory."""
        ...

    async def review(
        self,
        paper_text: str,
        persona_name: str = "rigorous",
        custom_instructions: str = "",
        previous_comments: list[dict] | None = None,
    ) -> ReviewResult:
        persona = self._personas[persona_name]
        system = persona.review_prompt
        if custom_instructions:
            system += f"\n\nAdditional focus: {custom_instructions}"
        if previous_comments:
            system += f"\n\nPrevious review had {len(previous_comments)} comments. Check if addressed."
        ...

    def list_personas(self) -> list[ReviewerPersona]:
        """Return all available personas for the UI selector."""
        ...
```

```
eurekalab/
  reviewer_personas/              # Built-in (shipped with package)
    adversarial.yaml
    rigorous.yaml
    constructive.yaml
  agents/reviewer/
    agent.py                      # ReviewerAgent
    persona.py                    # ReviewerPersona loader
    registry.py                   # Discover + load from both dirs
```

---

## 6. Implementation Phases

### Phase 1: ReviewerAgent + Persona Registry + Review UI
**Highest value, most differentiated feature.** Build first.
- ReviewerPersona loader (YAML-based, same pattern as skills)
- 3 built-in personas (adversarial, rigorous, constructive) shipped as package data
- ReviewerAgent with persona selection + custom instruction stacking
- Persona directory: `~/.eurekalab/reviewers/` for user-installed personas
- Review API endpoints: `GET /api/reviewers` (list), `POST /api/runs/<id>/review`
- Review panel in workspace with persona selector card grid and comment tracking
- Multi-reviewer stacking (run multiple, combined view with attribution)
- Comment resolution tracking (addressed / disagree with explanation)
- Works on any text — user can paste a paper and get a review immediately

### Phase 1b: Journal + Expert Persona Packs
- Create 5 journal personas (NeurIPS, ICML, Nature, JMLR, PLOS ONE) with calibrated prompts
- Create 4 expert personas (Statistician, Methodologist, Ethics, Writing Coach)
- CLI: `eurekalab reviewer list`, `eurekalab reviewer install <name>`
- Persona install from URL or local file

### Phase 2: Enhanced Literature Gate
- Paper curation panel after survey (accept/reject per paper, relevance explanations)
- Search transparency (queries shown, modifiable)
- "Find similar" button per paper
- Works within existing survey flow — just richer gate UI

### Phase 3: Adaptive Direction Gate
- Direction proposals with pros/cons/risks
- User can modify, propose own, or submit for critique
- Works within existing direction gate — just richer content

### Phase 4: Writing Panel
- Section-by-section editor in the workspace
- "Generate scaffold" per section (labelled as AI-generated)
- Inline AI suggestions (live, as user types)
- Integration with ReviewerAgent for per-section review

### Phase 5: Analysis Structure Approval
- Show proposed analysis/outline before execution
- User can modify structure
- Targeted analysis requests ("compare these two papers")

### Phase 6: Full Auto Toggle
- Settings checkbox to enable autonomous mode
- Session creation toggle when enabled
- Auto-approve all gates, run current pipeline
- Output labelling

---

## 7. Value Proposition vs. Chat AI

This design creates clear differentiation from ChatGPT/Claude/Gemini:

| Feature | Chat AI | EurekaLab |
|---------|---------|-----------|
| Literature search | "Find papers about X" → one-shot list, no provenance | Systematic search with transparency, per-paper relevance, accept/reject curation, multiple rounds |
| Research state | Gone when you close the tab | Persistent sessions, version history, bibliography management across days/weeks |
| Methodology | Whatever the AI decides to do | Structured pipeline per paper type (PRISMA, taxonomy, experimental design) with visible methodology |
| Writing support | "Write me a paper" → AI junk | Adaptive: scaffold what you need, write what you want, AI reviews what you wrote |
| Review | "Review my paper" → generic feedback | 4 reviewer personas (adversarial to constructive), structured comments, resolution tracking, venue-specific standards |
| Provenance | Black box | Every paper has "why selected", every claim traces to source, search strategy visible |
| Granularity | One conversation, one mode | Different AI involvement per stage — search broadly but write yourself |
| Auditability | No trail | Full version history with diff, checkout, rollback |

---

## 8. What We Keep, What Changes, What's New

### Keeps (no changes)
- Pipeline types (proof, survey, review, experimental, discussion)
- Entry modes (explore, prove, from-bib, from-draft, from-zotero)
- VersionStore, SessionDB, IdeationPool
- All existing agents (Survey, Ideation, Theory, Analyst, Experiment, Writer)
- Zotero integration, content tiers, PDF extraction
- CLI commands, API endpoints
- SQLite storage, auto-migration

### Changes (modifications)
- GateController: richer input surfaces at each gate
- WriterAgent: gains scaffold mode + review integration
- SurveyAgent: adds transparency output (search strategy, relevance explanations)
- Workspace tabs: Live → adaptive prompt, Proof → Analysis, Paper → Draft + Review
- NewSessionForm: simplified (adaptive prompt removes need for rigid mode/level selection)

### New
- ReviewerAgent with 4 personas + custom instructions
- Review panel with structured feedback and resolution tracking
- Paper curation UI (accept/reject with explanations)
- Writing editor with inline AI suggestions
- Search transparency panel
- "Generate scaffold" for individual sections
- Full Auto toggle (hidden in Settings)
