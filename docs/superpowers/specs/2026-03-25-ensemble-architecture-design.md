# N-Model Ensemble Research Architecture

**Goal:** Enable EurekaClaw to run multiple LLM models concurrently across pipeline stages, with per-stage merge strategies and dynamic runtime configuration, to improve research breadth, creativity, and rigour through cross-model pollination.

**Core Insight:** Different LLMs have different training biases, knowledge coverage, and reasoning patterns. Running them in parallel and merging results — similar to genetic algorithm crossover — increases the probability of novel, well-validated research output.

---

## 1. Architecture Overview

```
MetaOrchestrator
    │
    │  calls ensemble.execute_stage(task, agent_factory)
    │
    ▼
EnsembleOrchestrator
    ├── ModelPool (N named LLM clients)
    ├── EnsembleConfig (per-stage: models + strategy, dynamic at runtime)
    ├── EnsembleRecommender (heuristic suggestions after each stage)
    ├── Gate integration (human prompt before ensemble stages)
    └── Mergers (pluggable per-stage):
          ├── UnionMerger (survey: combine + dedup)
          ├── AdversarialMerger (ideation: cross-review + rank)
          ├── ConsensusMerger (experiment: independent validation)
          └── AsymmetricMerger (theory: primary + reviewer)
```

**Key properties:**
- N-model support from day one — adding a model is 3 lines of config
- Dynamic per-stage — users choose models and strategies at runtime via gate prompts
- Agent-recommended adjustments — system suggests changes based on observed results
- Zero overhead when off — single-model fast path if ensemble not configured
- No existing code broken — ensemble wraps execution, doesn't replace it
- Pluggable mergers — new strategies are just new classes implementing `BaseMerger`

---

## 2. Model Pool

Singleton registry of named LLM clients, initialized from config at session start.

### Interface

```python
# eurekaclaw/ensemble/model_pool.py

class ModelPool:
    _clients: dict[str, LLMClient]       # "claude" -> adapter instance
    _model_names: dict[str, str]         # "claude" -> "claude-sonnet-4-6"
    _backends: dict[str, str]            # "claude" -> "anthropic"

    def register(name: str, client: LLMClient, model_name: str, backend: str) -> None
    def get(name: str) -> LLMClient
    def get_model_name(name: str) -> str
    def list_available() -> list[str]

    @classmethod
    def create_from_config() -> ModelPool
        # Reads ENSEMBLE_MODELS and MODEL_{NAME}_* from env
        # Falls back to single-model pool with just the default model
```

### Config Format (.env)

```env
# Named model entries
ENSEMBLE_MODELS=claude,gemini,gpt5

# Claude — uses existing anthropic settings (no extra config needed)
MODEL_CLAUDE_BACKEND=anthropic

# Gemini — direct Google API via OpenAI-compatible endpoint
MODEL_GEMINI_BACKEND=google
MODEL_GEMINI_API_KEY=AIza...
MODEL_GEMINI_MODEL=gemini-2.0-flash

# GPT-5 — via OpenRouter
MODEL_GPT5_BACKEND=openrouter
MODEL_GPT5_API_KEY=sk-or-...
MODEL_GPT5_MODEL=openai/gpt-5.4
```

### Backend Routing

| Backend value | Adapter | Base URL |
|---------------|---------|----------|
| `anthropic` | `AnthropicAdapter` | Default (or ANTHROPIC_BASE_URL) |
| `google` | `OpenAICompatAdapter` | `https://generativelanguage.googleapis.com/v1beta/openai/` |
| `openrouter` | `OpenAICompatAdapter` | `https://openrouter.ai/api/v1` |
| `openai` | `OpenAICompatAdapter` | `https://api.openai.com/v1` |
| `local` | `OpenAICompatAdapter` | `http://localhost:8000/v1` |

Adding a new model = 3 env vars. No code changes.

If `ENSEMBLE_MODELS` is not set, `ModelPool.create_from_config()` returns a pool with just the default model (from `LLM_BACKEND` / `EUREKACLAW_MODEL`). This preserves backward compatibility.

---

## 3. Stage Ensemble Configuration

Three-layer config: env defaults -> session overrides -> runtime decisions.

### Data Structures

```python
# eurekaclaw/ensemble/config.py

@dataclass
class StageEnsembleConfig:
    models: list[str]              # ["claude", "gemini"]
    strategy: str                  # "union" | "adversarial" | "consensus" | "asymmetric" | "single"
    reviewer: str | None = None    # only for asymmetric strategy
    locked: bool = False           # True = user explicitly chose, don't auto-override

@dataclass
class EnsembleRecommendation:
    stage: str                     # which upcoming stage
    suggested_models: list[str]
    suggested_strategy: str
    reason: str                    # human-readable explanation
    confidence: float              # 0-1

class EnsembleConfig:
    stages: dict[str, StageEnsembleConfig]

    @classmethod
    def from_env() -> EnsembleConfig
        # Reads ENSEMBLE_{STAGE}_MODELS, ENSEMBLE_{STAGE}_STRATEGY
        # Falls back to single-model if not configured

    def update_stage(stage: str, models: list[str], strategy: str) -> None
    def get_stage(stage: str) -> StageEnsembleConfig
```

### Env Config

```env
# Per-stage defaults (all optional — falls back to single model)
ENSEMBLE_SURVEY_MODELS=claude,gemini
ENSEMBLE_SURVEY_STRATEGY=union

ENSEMBLE_IDEATION_MODELS=claude,gemini
ENSEMBLE_IDEATION_STRATEGY=adversarial

ENSEMBLE_THEORY_MODELS=claude
ENSEMBLE_THEORY_REVIEWER=gemini
ENSEMBLE_THEORY_STRATEGY=asymmetric

ENSEMBLE_EXPERIMENT_MODELS=claude,gemini
ENSEMBLE_EXPERIMENT_STRATEGY=consensus

ENSEMBLE_WRITER_MODELS=claude
ENSEMBLE_WRITER_STRATEGY=single
```

### Runtime Dynamic Overrides

**Human gate prompt** (when `GATE_MODE=human`):

Before each ensemble stage, the system presents:
```
About to run: ideation
  Available models: claude, gemini, gpt5
  Suggested strategy: adversarial (2 models generate, cross-review)

  [1] Run as suggested (claude + gemini, adversarial)
  [2] Change models (select which)
  [3] Change strategy (union / adversarial / consensus)
  [4] Skip ensemble, run single model
  [5] Let the system decide

  ->
```

The `locked` flag tracks whether the user explicitly chose — if True, agent recommendations are shown but not auto-applied. Options 1-4 set `locked = True`. Option 5 ("let the system decide") sets `locked = False`.

**Auto mode** (when `GATE_MODE=auto`): Recommendations with `confidence > 0.7` auto-apply. Otherwise current config proceeds.

**None mode** (when `GATE_MODE=none`): Recommendations logged, never applied. Pure autopilot with env defaults.

---

## 4. Ensemble Orchestrator

Sits between MetaOrchestrator and agents. Only component that knows about multi-model execution.

### Interface

```python
# eurekaclaw/ensemble/orchestrator.py

class EnsembleOrchestrator:
    def __init__(
        self,
        model_pool: ModelPool,
        config: EnsembleConfig,
        bus: KnowledgeBus,
        gate_mode: str,
    )

    async def execute_stage(
        self,
        task: Task,
        agent_factory: Callable[[LLMClient], BaseAgent],
    ) -> AgentResult:
        """Run a stage with ensemble if configured, single-model otherwise."""

    def is_ensemble_stage(self, stage_name: str) -> bool
```

### Execution Flow

```
execute_stage(task, agent_factory)
    │
    ├── get StageEnsembleConfig for task.name
    │
    ├── if strategy == "single" or len(models) == 1:
    │       → fast path: single agent.execute()
    │
    ├── present gate prompt (if human mode)
    │       → user may modify config
    │
    ├── if strategy == "asymmetric":
    │       → _run_asymmetric(): primary executes, reviewer critiques
    │
    ├── else (union/adversarial/consensus):
    │       → _run_parallel(): asyncio.gather() N agents
    │       → merger.merge(results)
    │
    ├── generate recommendation for next stage
    │       → bus.put("ensemble_recommendation", rec)
    │
    └── return merged AgentResult
```

### Parallel Dispatch

**Bus isolation:** Each parallel agent gets a scoped bus wrapper that namespaces writes by model name (e.g., `bus.put("experiment_result")` becomes `bus.put("experiment_result__claude")`). The merger reads from all namespaces and writes the merged result to the canonical key. This prevents parallel agents from clobbering each other's bus entries.

**Per-model timeout:** Each parallel agent is wrapped in `asyncio.wait_for()` with a configurable timeout (default 300s). Timed-out models are excluded from merging with a warning logged.

```python
async def _run_parallel(self, task, agent_factory, config) -> dict[str, AgentResult]:
    per_model_timeout = 300  # seconds, configurable

    async def run_one(model_name):
        client = self.model_pool.get(model_name)
        # agent_factory creates a FRESH agent instance per model
        # (new AgentSession, new client binding — no shared mutable state)
        agent = agent_factory(client)
        scoped_bus = ScopedBus(self.bus, namespace=model_name)
        agent.bus = scoped_bus
        return await asyncio.wait_for(
            agent.execute(task.model_copy()),  # copy task to avoid mutation
            timeout=per_model_timeout,
        )

    coros = {name: run_one(name) for name in config.models}
    raw = await asyncio.gather(*coros.values(), return_exceptions=True)
    results = {}
    for name, result in zip(coros.keys(), raw):
        if isinstance(result, Exception):
            logger.warning("Ensemble model %s failed: %s", name, result)
        else:
            results[name] = result
    return results
```

`task.model_copy()` (Pydantic v2) creates an independent copy per model so no agent mutates the shared task object.

### Asymmetric Dispatch (Theory)

```python
async def _run_asymmetric(self, task, agent_factory, config) -> AgentResult:
    # Primary runs full execution
    primary_client = self.model_pool.get(config.models[0])
    primary_agent = agent_factory(primary_client)
    primary_result = await primary_agent.execute(task)

    # Reviewer critiques the output
    reviewer_client = self.model_pool.get(config.reviewer)
    review = await self._run_review(reviewer_client, primary_result, task)

    # Attach review to result
    primary_result.output["ensemble_review"] = review

    # If review found high-severity issues, re-run primary with feedback
    if review.get("issues") and any(i["severity"] == "high" for i in review["issues"]):
        # Create a task COPY with feedback injected (never mutate the original)
        revised_task = task.model_copy()
        revised_task.description += f"\n\n[Reviewer feedback]: {json.dumps(review['issues'])}"
        primary_result = await primary_agent.execute(revised_task)
        primary_result.output["ensemble_review"] = review
        primary_result.output["ensemble_revision"] = True

    return primary_result
```

### _run_review Method

The reviewer receives a structured prompt with the primary model's output and returns a JSON review:

```python
async def _run_review(
    self,
    reviewer_client: LLMClient,
    primary_result: AgentResult,
    task: Task,
) -> dict:
    """Ask a reviewer model to critique the primary model's output."""
    from eurekaclaw.config import settings

    review_prompt = (
        "You are an independent reviewer. Examine the following proof/analysis output "
        "and identify logical gaps, unjustified steps, missing edge cases, or errors.\n\n"
        f"Original task: {task.description[:500]}\n\n"
        f"Output to review:\n{json.dumps(primary_result.output, default=str)[:4000]}\n\n"
        "Respond with a JSON object:\n"
        '{"review_passed": bool, "issues": [{"lemma_id": "...", "severity": "high|medium|low", '
        '"description": "..."}], "confidence": 0.0-1.0, "summary": "1-2 sentence overall assessment"}'
    )

    response = await reviewer_client.messages.create(
        model=self.model_pool.get_model_name(self.config.get_stage(task.name).reviewer),
        max_tokens=settings.max_tokens_verifier,
        system="You are a rigorous mathematical reviewer. Output only valid JSON.",
        messages=[{"role": "user", "content": review_prompt}],
    )

    # Parse JSON from response, with fallback
    text = response.content[0].text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Reviewer returned non-JSON response, treating as pass")
        return {"review_passed": True, "issues": [], "confidence": 0.5}
```

---

## 5. Merger Strategies

All implement `BaseMerger`:

```python
# eurekaclaw/ensemble/mergers/base.py

class BaseMerger(ABC):
    @abstractmethod
    async def merge(
        self,
        results: dict[str, AgentResult],  # {model_name: result}
        task: Task,
        bus: KnowledgeBus,
    ) -> AgentResult
```

### 5.1 UnionMerger (Survey)

**Purpose:** Maximize literature coverage by combining all search results.

**Logic:**
1. Collect `papers` lists from each model's survey output
2. Deduplicate by `arxiv_id` (exact) or `title` (fuzzy — lowercased, stripped whitespace)
3. For duplicates, keep the entry with richer metadata (longer abstract, more authors)
4. Union `open_problems` and `key_mathematical_objects`, deduplicate by exact string match
5. Tag each item with `source_models: ["claude", "gemini"]` for provenance

**Output metrics on bus:**
```python
bus.put("ensemble_survey_stats", {
    "per_model": {"claude": 6, "gemini": 9},
    "merged_total": 13,
    "overlap_count": 2,
    "overlap_ratio": 0.15,
})
```

### 5.2 AdversarialMerger (Ideation)

**Purpose:** Generate diverse hypotheses and filter through cross-model scrutiny.

**Phase 1 — Generate:** Each model produces 5 ResearchDirection objects independently. N models = N*5 raw directions.

**Phase 2 — Cross-review:** Each model reviews the OTHER models' directions via a lightweight LLM call using the fast model (~1k tokens per review). For N models this is N*(N-1) review calls.

Cross-review prompt template:
```
Score each research direction on three dimensions (0.0-1.0):
- novelty: How original is this idea?
- soundness: Is the mathematical reasoning plausible?
- feasibility: Can this be proved with known techniques?

Directions to review:
[JSON array of directions from other models]

Return JSON: [{"direction_id": "...", "novelty": 0.8, "soundness": 0.7, "feasibility": 0.6, "critique": "..."}]
```

If a cross-review call fails or returns malformed JSON, that reviewer's scores are excluded (the direction keeps its self-score only).

**Phase 3 — Rank:** Each direction gets a final score:
```
self_score = direction.compute_composite()  # 0.4*novelty + 0.35*soundness + 0.25*transformative
avg_cross_score = mean of all cross-reviewer composite scores for this direction
bonus = originality_bonus OR convergence_bonus (mutually exclusive)

final_score = 0.4 * avg_cross_score + 0.3 * self_score + 0.3 * bonus
```
Where `bonus` is:
- `originality_bonus` (0.2) if only one model proposed this direction (unique = potentially novel)
- `convergence_bonus` (0.15) if 2+ models independently proposed similar directions (detected by title cosine similarity > 0.7 using lowercased word overlap, not embeddings)
- These are mutually exclusive. A direction is either unique to one model or converged across multiple.

Top 5-7 directions proceed, each tagged with:
```python
{
    "source_model": "gemini",
    "cross_scores": {"claude": 0.8, "gpt5": 0.6},
    "consensus": "high" | "contested" | "unique",
}
```

### 5.3 ConsensusMerger (Experiment)

**Purpose:** Independent empirical validation — agreement = high confidence.

**Logic:**
1. Each model independently generates experiment code and runs it (via `execute_python` tool)
2. Compare `ExperimentResult.bounds` across models:
   - **Agree** (within 10% tolerance): mark as `confirmed`
   - **Disagree**: mark as `contested`, keep both values
3. Merged result:
```python
{
    "confirmed_bounds": [...],         # all models agree
    "contested_bounds": [              # models disagree
        {"name": "regret_bound", "claude": 0.92, "gemini": 0.71, "gap": 0.21}
    ],
    "agreement_ratio": 0.75,          # fraction confirmed
    "overall_confidence": 0.82,       # weighted by agreement
}
```

### 5.4 AsymmetricMerger (Theory)

Not a separate merger class — handled directly in `EnsembleOrchestrator._run_asymmetric()` as described in Section 4. The reviewer produces:

```python
{
    "review_passed": bool,
    "issues": [
        {"lemma_id": "L3", "severity": "high" | "medium" | "low",
         "description": "Gap in induction step..."}
    ],
    "confidence": 0.85,
}
```

### Merger Registry

```python
MERGER_REGISTRY: dict[str, type[BaseMerger] | None] = {
    "union": UnionMerger,
    "adversarial": AdversarialMerger,
    "consensus": ConsensusMerger,
    "asymmetric": None,  # handled by orchestrator._run_asymmetric()
    "single": None,      # no merging needed
}
```

The `asymmetric` strategy is handled by the orchestrator directly, not via a merger.

---

## 6. Recommendation Engine

Heuristic-based suggestions for ensemble adjustments after each stage.

```python
# eurekaclaw/ensemble/recommender.py

class EnsembleRecommender:
    def recommend(
        self,
        completed_stage: str,
        results: dict[str, AgentResult],
        merged: AgentResult,
        available_models: list[str],
        current_config: EnsembleConfig,
    ) -> EnsembleRecommendation | None
```

### Heuristic Rules

| After Stage | Signal | Recommendation | Confidence |
|-------------|--------|---------------|------------|
| Survey | overlap < 20% | Widen ideation to N+1 models | 0.8 |
| Survey | overlap > 70% | Narrow ideation to 2 models (save tokens) | 0.6 |
| Survey | one model found 0 papers | Exclude that model from ideation | 0.9 |
| Ideation | >3 directions cluster on one theme | Add a model with different training bias | 0.7 |
| Ideation | a direction scored >0.9 cross-model | Theory can run single-model (strong starting point) | 0.6 |
| Ideation | all cross-scores < 0.5 | Suggest human review before proceeding | 0.8 |
| Theory | >2 low-confidence lemmas | Add reviewer model for experiment stage | 0.7 |
| Theory | all lemmas verified | Single-model experiment sufficient | 0.5 |
| Experiment | agreement_ratio < 0.5 | Add third model as tiebreaker | 0.8 |

### Presentation

When `GATE_MODE=human`:
```
Done: survey (claude + gemini, union)
  claude: 6 papers | gemini: 9 papers | merged: 13 (overlap: 15%)

  Recommendation: Low overlap (15%). Consider running ideation with
  all 3 available models to maximize creative coverage.

  Suggested: ideation -> claude + gemini + gpt5 (adversarial)

  [1] Accept recommendation
  [2] Keep current config (claude + gemini, adversarial)
  [3] Modify
  ->
```

When `GATE_MODE=auto`: recommendations with `confidence > 0.7` auto-apply, others logged.

When `GATE_MODE=none`: all recommendations logged, never applied.

---

## 7. Per-Stage Strategy Rationale

This documents WHY each stage uses a specific default merge strategy.

| Stage | Strategy | Rationale |
|-------|----------|-----------|
| **Survey** | Union + dedup | Search benefits from **breadth**. Different models have different knowledge coverage and generate different search queries. Union maximizes paper discovery. Low risk — more papers never hurts. |
| **Ideation** | Adversarial cross-review | Hypothesis generation benefits from **creative tension**. Each model has different biases — one may overfit to popular approaches while another finds unconventional angles. Cross-review filters weak ideas while preserving genuinely novel ones. The originality/convergence bonuses reward both divergent thinking and independent validation. |
| **Theory** | Asymmetric (primary + reviewer) | Proof is the most token-intensive stage. Running N full proof loops is wasteful. Instead, one model proves and another reviews — catching blind spots (missing edge cases, unjustified steps) that the prover's own verification might miss due to confirmation bias. |
| **Experiment** | Independent consensus | Empirical validation benefits from **independent replication**. If both models design different experiments that reach the same conclusion, confidence is high. Disagreements surface specific bounds that need scrutiny — exactly the kind of issue that would otherwise be missed. |
| **Writer** | Single model | Paper generation is deterministic given the inputs (proven theorem, validated experiments). No benefit from ensemble — just token cost. |

---

## 8. Integration with Existing Code

### Changes to MetaOrchestrator

**`__init__`** — add ensemble initialization:
```python
self.model_pool = ModelPool.create_from_config()
self.ensemble_config = EnsembleConfig.from_env()
self.ensemble = EnsembleOrchestrator(
    model_pool=self.model_pool,
    config=self.ensemble_config,
    bus=self.bus,
    gate_mode=settings.gate_mode,
)
```

**Task execution loop** — replace direct agent call:
```python
# Before:
agent = self.router.resolve(task)
result = await agent.execute(task)

# After:
if self.ensemble.is_ensemble_stage(task.name):
    agent_factory = lambda client: self.router.create_agent(task, client)
    result = await self.ensemble.execute_stage(task, agent_factory)
else:
    agent = self.router.resolve(task)
    result = await agent.execute(task)
```

### Changes to TaskRouter

Add a factory method that creates **fresh agent instances** (not references to shared singletons). This is critical for parallel dispatch — shared agents would have their `client` and `session` state mutated by concurrent coroutines.

```python
def create_agent(self, task: Task, client: LLMClient) -> BaseAgent:
    """Create a NEW agent instance for this task with the given client.

    Unlike resolve() which returns shared singletons, this creates
    independent instances safe for parallel ensemble execution.
    Each gets its own AgentSession, client, and bus reference.
    """
    agent_cls = self._agent_class_for_role(task.agent_role)
    return agent_cls(
        bus=self.bus,
        tool_registry=self.tool_registry,
        skill_injector=self.skill_injector,
        memory=self.memory,
        client=client,
    )
```

Note: `_agent_class_for_role()` maps `AgentRole` to the class (SurveyAgent, IdeationAgent, etc.). This is a simple dict lookup extracted from the existing role-to-agent mapping in MetaOrchestrator.

### Changes to config.py

Add ensemble-related settings. All optional with sensible defaults.

### Changes to factory.py

Add `google` backend alias:
```python
_BACKEND_ALIASES = {
    "openrouter": ("openai_compat", "https://openrouter.ai/api/v1"),
    "local": ("openai_compat", "http://localhost:8000/v1"),
    "google": ("openai_compat", "https://generativelanguage.googleapis.com/v1beta/openai/"),
    ...
}
```

### ScopedBus (new utility)

A thin wrapper around KnowledgeBus that namespaces writes during parallel execution:

```python
# eurekaclaw/ensemble/scoped_bus.py

class ScopedBus:
    """Wraps KnowledgeBus to namespace writes by model name during parallel dispatch."""

    def __init__(self, bus: KnowledgeBus, namespace: str):
        self._bus = bus
        self._ns = namespace

    def put(self, key, value):
        self._bus.put(f"{key}__{self._ns}", value)

    def get(self, key, default=None):
        # Try namespaced first, fall back to canonical
        return self._bus.get(f"{key}__{self._ns}") or self._bus.get(key, default)

    # Delegate read-only methods directly to the underlying bus
    def get_research_brief(self): return self._bus.get_research_brief()
    def get_bibliography(self): return self._bus.get_bibliography()
    def get_theory_state(self): return self._bus.get_theory_state()
```

Mergers read from all namespaces and write the merged result to the canonical (un-namespaced) key.

### Per-Model Token Tracking

Each ensemble execution tracks tokens per model:
```python
# Stored on bus after merge
bus.put("ensemble_token_usage", {
    "stage": "ideation",
    "per_model": {
        "claude": {"input": 4200, "output": 1800},
        "gemini": {"input": 3900, "output": 2100},
    },
    "merge_overhead": {"input": 800, "output": 400},  # cross-review calls etc.
    "total": {"input": 8900, "output": 4300},
})
```

### No Changes To

- BaseAgent (interface unchanged — ensemble creates fresh instances with different clients)
- SurveyAgent, IdeationAgent, TheoryAgent, ExperimentAgent, WriterAgent
- LLM adapters (OpenAICompatAdapter already handles Gemini via OpenAI-compat endpoint)
- Tool registry

The ensemble layer wraps agents — it doesn't modify them.

---

## 9. File Structure

```
eurekaclaw/ensemble/
    __init__.py
    model_pool.py              # ModelPool: named LLM client registry
    config.py                  # EnsembleConfig: per-stage config with dynamic overrides
    orchestrator.py            # EnsembleOrchestrator: dispatch + merge coordination
    recommender.py             # EnsembleRecommender: heuristic suggestions
    scoped_bus.py              # ScopedBus: namespaced bus wrapper for parallel isolation
    mergers/
        __init__.py
        base.py                # BaseMerger ABC
        union.py               # UnionMerger (survey)
        adversarial.py         # AdversarialMerger (ideation)
        consensus.py           # ConsensusMerger (experiment)

tests/
    test_model_pool.py
    test_ensemble_config.py
    test_ensemble_orchestrator.py
    test_union_merger.py
    test_adversarial_merger.py
    test_consensus_merger.py
    test_recommender.py
```

**Modified existing files:**
- `eurekaclaw/config.py` — add ENSEMBLE_* settings
- `eurekaclaw/orchestrator/meta_orchestrator.py` — instantiate ensemble, use in task loop
- `eurekaclaw/orchestrator/router.py` — add `resolve_with_client()`
- `.env.example` — add ensemble config section

---

## 10. Backward Compatibility

If `ENSEMBLE_MODELS` is not set in `.env`:
- `ModelPool.create_from_config()` returns a pool with one model (the default from `LLM_BACKEND`)
- `EnsembleConfig.from_env()` returns all stages as `strategy=single`
- `EnsembleOrchestrator.execute_stage()` always hits the fast path (direct agent call)
- Net result: identical behavior to current codebase with zero overhead
