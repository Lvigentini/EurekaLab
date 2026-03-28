# Dialogic Architecture Pivot — From Paper Factory to Thinking Scaffold

**Status:** Plan
**Date:** 2026-03-29

---

## 1. The Philosophy

Two tenets:

> **Thinking scaffold** — make better papers, NOT create more AI-generated junk.

> **Dialogic architecture** — challenge the process at every step.

**What this means:** EurekaLab should equip the *writer* to do their best work with AI support. The human drives the research and writes the paper. AI does the grunt work (search, analysis, comparison) and provides critical, constructive feedback at each stage.

**What changes:**
- The AI is a **research assistant + critical reviewer**, not a ghost writer
- Every stage is a **conversation**, not an autonomous pipeline step
- The user sees and controls every decision (which papers, which direction, which arguments)
- The AI pushes back, asks hard questions, identifies gaps — but the human decides

---

## 2. Current vs. Target

### Current Model: Autonomous Pipeline
```
User gives topic → AI runs autonomously → AI writes paper → User reads output
```
- Human involvement: input + final review
- AI role: author
- Output: complete AI-written paper
- Problem: produces AI junk, user doesn't learn, no critical engagement

### Target Model: Dialogic Scaffold
```
User gives topic → AI researches → DIALOGUE about findings →
User gives direction → AI critiques → DIALOGUE about approach →
User writes sections → AI reviews critically → DIALOGUE about quality →
User refines → AI checks rigor → Final paper (human-authored, AI-assisted)
```
- Human involvement: every stage
- AI role: research assistant + Socratic critic
- Output: human-written paper, improved through AI dialogue
- Benefit: better papers, deeper thinking, transparent process

---

## 3. Stage-by-Stage Redesign

### Stage 1: Literature Search (AI does grunt work, human curates)

**Current:** Survey agent runs autonomously, finds ~20 papers, presents a summary.

**Target:**
- AI searches and presents papers **one batch at a time** (5-8 papers per round)
- For each paper: title, abstract, **why it's relevant**, **what it contributes to your question**
- User can: **accept**, **reject** (with reason — AI learns), **request more like this**, **ask for different angle**
- AI shows its search strategy: "I searched for X because Y. Should I also try Z?"
- User can inject their own papers at any point
- **Transparency panel**: shows exactly what was searched, what was found, why papers were ranked this way
- Ends when user says "I have enough papers" — not when AI decides

**Key change:** The user curates the bibliography, not the AI.

### Stage 2: Ideation (AI proposes, human debates)

**Current:** Ideation agent generates 5 directions, user picks one.

**Target:**
- AI proposes 3-5 directions with pros/cons for each
- For each direction, AI plays **devil's advocate**: "This could fail because...", "A reviewer would ask..."
- User can: **propose their own direction**, **combine directions**, **ask AI to argue for/against a specific angle**
- **Dialogue mode**: "What if I focused on X instead?" → AI responds with honest assessment including risks
- AI explicitly asks: "What's your thesis? What are you trying to show?"
- Direction is refined through back-and-forth, not selected from a menu

**Key change:** Directions emerge from dialogue, not from a dropdown.

### Stage 3: Structuring (AI scaffolds, human architects)

**Current:** Theory agent or Analyst agent runs autonomously, produces analysis.

**Target — for all paper types:**
- AI proposes an **outline** (sections, key arguments per section, what evidence goes where)
- User edits the outline — adds, removes, reorders sections
- For each section, AI identifies: "You'll need evidence for X. Currently you have papers A, B. Gap: nothing on Z."
- AI asks structural questions: "Why does section 3 come before section 4? A reviewer might expect..."
- **For proof papers**: AI proposes lemma structure, user approves each step
- **For surveys**: AI proposes taxonomy, user refines categories
- **For discussion**: AI identifies counterarguments the user must address

**Key change:** The user owns the paper structure, AI stress-tests it.

### Stage 4: Writing (Human writes, AI reviews)

**Current:** Writer agent produces the entire paper autonomously.

**Target:**
- User writes each section (in a built-in editor or pastes from external editor)
- AI reviews each section with **specific, actionable feedback**:
  - "Paragraph 2 claims X but your evidence only supports Y"
  - "This argument assumes Z — have you justified that?"
  - "A reviewer would flag: missing citation for this claim"
  - "This section is 3x longer than the others — consider tightening"
- AI can suggest **improvements** (not rewrites): "Consider mentioning paper A here" rather than rewriting the paragraph
- User can ask AI to **draft a section** as a starting point, but it's clearly labeled as AI-generated scaffold
- **Critical review mode**: AI acts as Reviewer 2 — tough but fair, specific and constructive

**Key change:** The human writes, the AI reviews. AI-generated text is explicitly labeled and optional.

### Stage 5: Rigor Check (AI as peer reviewer)

**Current:** Consistency checker runs automatically, reports pass/fail.

**Target:**
- AI does a final **comprehensive review** of the complete paper:
  - Citation check: "You cite Smith 2024 but never discuss their findings"
  - Argument check: "Your conclusion doesn't follow from section 4"
  - Gap check: "You don't address the main counterargument to your thesis"
  - Novelty check: "How does this differ from Lee 2023 who made a similar claim?"
- Presents feedback as a **structured review** (like a real peer review with major/minor comments)
- User addresses each comment — AI tracks which are resolved
- Optional: AI generates a **response to reviewers** template

**Key change:** The AI acts as Reviewer 2 before submission, not as co-author.

---

## 4. UI Implications

### The Dialogue Panel (Central Feature)

The main workspace becomes a **conversation**, not a monitoring dashboard:

```
┌─────────────────────────────────────────────────────────────┐
│ Header: EurekaLab v0.6.2 │ Research │ Skills │ Docs │ ⚙    │
├──────────┬──────────────────────────────────────────────────┤
│          │                                                   │
│ Sessions │  [Stage indicator: Literature Search]              │
│          │                                                   │
│          │  ┌─────────────────────────────────────────────┐  │
│          │  │ AI: I found 6 papers on "transformer         │  │
│          │  │ efficiency". Here they are ranked by          │  │
│          │  │ relevance:                                    │  │
│          │  │                                               │  │
│          │  │ 1. Smith 2024 — "Efficient Attention..."     │  │
│          │  │    Relevance: addresses your exact question    │  │
│          │  │    [Accept] [Reject] [More like this]         │  │
│          │  │                                               │  │
│          │  │ 2. Jones 2023 — "Sparse Transformers..."     │  │
│          │  │    Relevance: competing approach               │  │
│          │  │    [Accept] [Reject] [More like this]         │  │
│          │  │                                               │  │
│          │  │ Should I search for more, or search a         │  │
│          │  │ different angle?                               │  │
│          │  └─────────────────────────────────────────────┘  │
│          │                                                   │
│          │  ┌─────────────────────────────────────────────┐  │
│          │  │ You: Accept 1 and 2. Can you find papers     │  │
│          │  │ that contradict Smith's approach?             │  │
│          │  └─────────────────────────────────────────────┘  │
│          │                                                   │
│          │  [Type your response...]              [Send]      │
│          │                                                   │
│          │  ── Side panels (tabs) ──────────────────────── │
│          │  [Papers] [Outline] [Draft] [Review] [History]   │
│          │                                                   │
└──────────┴──────────────────────────────────────────────────┘
```

### Side Panels (Always Accessible)

| Panel | What It Shows |
|-------|-------------|
| **Papers** | Curated bibliography with accept/reject status, content tiers, notes |
| **Outline** | Editable paper structure — sections, subsections, evidence mapping |
| **Draft** | The user's writing — section by section, with AI review comments inline |
| **Review** | AI's peer review of the current draft — major/minor comments, resolved/open |
| **History** | Version timeline (existing feature — works well here) |

### Interaction Modes

At each stage, the user can:
- **Chat** — free-form dialogue with the AI about the research
- **Command** — specific actions ("search for X", "review section 3", "what are the counterarguments?")
- **Write** — compose/edit paper text directly in the Draft panel
- **Approve/Reject** — binary decisions on AI proposals (papers, directions, outline sections)

---

## 5. Backend Architecture Changes

### From Pipeline to Dialogue Engine

**Current:** `MetaOrchestrator.run()` executes stages linearly. Each stage is an autonomous agent.

**Target:** `DialogueEngine` manages a conversation with the user. Agents are called on-demand based on user requests, not in a fixed sequence.

```python
class DialogueEngine:
    """Manages a research dialogue — user-driven, AI-assisted."""

    def __init__(self, bus: KnowledgeBus, ...):
        self.stage = "literature_search"  # current dialogue stage
        self.agents = { ... }  # same agent pool

    async def handle_user_message(self, message: str) -> DialogueResponse:
        """Process a user message and return AI response."""
        # 1. Understand intent (search, ask question, provide direction, write, etc.)
        # 2. Dispatch to appropriate agent or capability
        # 3. Return structured response with actions available

    async def handle_action(self, action: str, payload: dict) -> DialogueResponse:
        """Handle a structured action (accept paper, reject direction, etc.)."""
```

### Dialogue Stages (Not Pipeline Stages)

The dialogue has **phases** (not rigid stages). The user can move between phases freely:

| Phase | AI Capabilities | User Actions |
|-------|-----------------|-------------|
| **Literature** | Search, summarize, explain relevance | Accept/reject papers, request more, inject own |
| **Direction** | Propose, critique, play devil's advocate | Propose own, combine, debate |
| **Structure** | Propose outline, identify gaps, stress-test | Edit outline, assign evidence to sections |
| **Writing** | Review sections, suggest improvements, check citations | Write, edit, ask for draft scaffolds |
| **Review** | Comprehensive peer review, track resolved comments | Address comments, revise, finalize |

### Agent Role Changes

| Agent | Current Role | New Role |
|-------|-------------|----------|
| **Survey** | Autonomous search → bibliography | Search on demand, present with explanations, let user curate |
| **Ideation** | Generate 5 directions | Propose directions + critique them, engage in debate |
| **Theory/Analyst** | Autonomous analysis | On-demand analysis: "analyze this paper", "compare these approaches" |
| **Writer** | Write entire paper | **Review** user's writing, suggest improvements, optional scaffold generation |
| **Experiment** | Run experiments autonomously | Help design experiments, review methodology, run on request |

### New Components

```
eurekalab/
  dialogue/
    engine.py           # DialogueEngine — orchestrates the conversation
    intent.py           # Classify user messages into intents
    response.py         # Structured dialogue responses
    stages.py           # Stage-specific handlers
  agents/
    reviewer/           # NEW: critical review agent (Reviewer 2 mode)
      agent.py
    scaffold/           # NEW: optional scaffold generator (labeled as AI-generated)
      agent.py
```

---

## 6. The "Reviewer 2" Agent

A dedicated critical reviewer that:
- Reviews the user's writing section by section
- Identifies logical gaps, unsupported claims, missing citations
- Scores on: clarity, rigor, novelty, completeness
- Generates structured feedback (major comments + minor comments)
- Tracks which comments have been addressed across revisions
- Can be invoked at any time: "Review my introduction" or "Do a full paper review"

```python
class ReviewerAgent(BaseAgent):
    """Critical but constructive peer reviewer."""

    _SYSTEM_PROMPT = """You are a rigorous but constructive peer reviewer.
    Your job is to help the author improve their paper, not to gatekeep.

    For each issue you find:
    - State the problem clearly
    - Explain WHY it matters (what a reader/reviewer would think)
    - Suggest a specific improvement

    Classify issues as:
    - MAJOR: must be addressed before publication
    - MINOR: should be addressed but not blocking
    - SUGGESTION: optional improvement

    Be honest but respectful. The author is trying to do good work."""
```

---

## 7. Transparency Features

### Search Transparency
- Show exactly what queries were sent to arXiv/Semantic Scholar/OpenAlex
- Show how many results each query returned
- Explain why each paper was ranked where it was
- Let user modify search queries directly

### Decision Transparency
- Every AI recommendation comes with reasoning
- "I suggest this direction because..." not just "Direction 1: ..."
- When AI plays devil's advocate, it labels its arguments clearly
- AI explicitly states its uncertainty: "I'm not confident about this claim because..."

### Provenance Tracking
- Every piece of information in the paper traces back to a source
- "This claim is supported by Smith 2024 (section 3.2, accepted by user on March 28)"
- Gap warnings: "This claim has no source — consider adding evidence"

---

## 8. Implementation Phases

### Phase 1: Dialogue-First UI
- Replace the autonomous monitoring view with a chat-based dialogue interface
- Keep side panels (Papers, Outline, Draft, Review, History)
- Stage indicator at top showing current phase
- User types messages, AI responds with structured content
- Actions are buttons within AI responses (Accept/Reject/More)

### Phase 2: Interactive Literature Search
- Survey agent becomes on-demand: responds to "search for X"
- Presents papers with relevance explanations and accept/reject buttons
- Shows search strategy transparently
- User curates bibliography through dialogue

### Phase 3: Dialogic Ideation
- Ideation agent proposes directions with pros/cons/devil's advocate
- User can debate, combine, propose own directions
- Direction emerges from dialogue, not menu selection

### Phase 4: Reviewer Agent
- New agent: ReviewerAgent for critical section-by-section review
- Structured feedback with major/minor/suggestion classification
- Comment tracking across revisions
- "Review my intro" / "Do a full paper review" commands

### Phase 5: Writing Support (Not Writing)
- Draft panel for user to write in
- AI reviews on demand, suggests improvements (not rewrites)
- Optional scaffold generation clearly labeled as AI-generated
- Citation suggestions, gap identification, argument checking

### Phase 6: Rigor Check
- Final comprehensive review before submission
- Structured peer review output
- Response-to-reviewers template

---

## 9. What We Keep

- **Paper types** — still valid (survey, review, experimental, discussion, proof)
- **Version history** — even more valuable in a dialogic model (track how the paper evolved)
- **IdeationPool** — becomes the dialogue's "working memory" for directions and ideas
- **Content tier tracking** — still important for paper quality
- **Zotero integration** — even more useful when user curates bibliography
- **CLI commands** — power users may prefer terminal-based dialogue
- **SQLite storage** — sessions are now dialogue transcripts + artifacts

## 10. What Changes Fundamentally

| Aspect | Before | After |
|--------|--------|-------|
| Who writes the paper | AI | Human (with AI support) |
| Pipeline execution | Autonomous, linear | User-driven, conversational |
| Gates | Approval checkpoints | Continuous dialogue |
| Main UI | Monitoring dashboard | Chat + side panels |
| AI output | Complete paper | Feedback, suggestions, scaffolds |
| Success metric | Paper generated | Paper improved through dialogue |
| User engagement | Passive (watch and approve) | Active (write, debate, decide) |
