# Configuration

All settings are read from environment variables (or a `.env` file in the project root). Copy `.env.example` to `.env` and edit before running.

## LLM Backend

| Variable | Default | Description |
|---|---|---|
| `LLM_BACKEND` | `anthropic` | Backend: `anthropic`, `openrouter`, `local`, `minimax` |
| `ANTHROPIC_API_KEY` | `""` | Anthropic API key. If empty, falls back to ccproxy OAuth (`~/.claude/.credentials.json`) |
| `ANTHROPIC_AUTH_MODE` | `api_key` | `api_key` or `oauth` (ccproxy) |
| `ANTHROPIC_BASE_URL` | `""` | Override base URL for the Anthropic client (e.g. for proxies or test servers) |
| `CCPROXY_PORT` | `8000` | Port for ccproxy server |
| `OPENAI_COMPAT_BASE_URL` | `""` | Base URL for OpenAI-compatible endpoint (OpenRouter / local vLLM) |
| `OPENAI_COMPAT_API_KEY` | `""` | API key for OpenAI-compatible endpoint |
| `OPENAI_COMPAT_MODEL` | `""` | Model name for OpenAI-compatible endpoint |

**Backend shortcuts:**

| `LLM_BACKEND` | Notes |
|---|---|
| `anthropic` | Default. Uses `ANTHROPIC_API_KEY` or ccproxy OAuth |
| `openrouter` | Set `OPENAI_COMPAT_API_KEY=sk-or-...` |
| `local` | Defaults to `http://localhost:8000/v1` (vLLM / Ollama) |
| `minimax` | Set `MINIMAX_API_KEY` and `MINIMAX_MODEL` |

**Minimax-specific variables:**

| Variable | Default | Description |
|---|---|---|
| `MINIMAX_API_KEY` | `""` | Minimax API key |
| `MINIMAX_MODEL` | `""` | Minimax model name (e.g. `abab7-chat`) |

## Models

| Variable | Default | Description |
|---|---|---|
| `EUREKACLAW_MODEL` | `claude-sonnet-4-6` | Main reasoning model (all agents) |
| `EUREKACLAW_FAST_MODEL` | `claude-haiku-4-5-20251001` | Fast/cheap model for compression, formalization, counterexample |

`settings.active_model` and `settings.active_fast_model` are **derived read-only properties** that resolve the correct model string for the active backend. All agents use these properties — never the raw `EUREKACLAW_MODEL` variable directly.

## External APIs

| Variable | Default | Description |
|---|---|---|
| `S2_API_KEY` | `""` | Semantic Scholar API key (optional — higher rate limits) |
| `BRAVE_SEARCH_API_KEY` | `""` | Brave Search API key (web search) |
| `SERPAPI_KEY` | `""` | SerpAPI key (web search fallback) |
| `WOLFRAM_APP_ID` | `""` | Wolfram Alpha app ID (symbolic computation) |

## Ensemble Configuration

| Variable | Default | Description |
|---|---|---|
| `ENSEMBLE_MODELS` | `""` | Comma-separated list of models for ensemble mode (e.g. `claude,gemini`) |
| `GEMINI_API_KEY` | `""` | Gemini API key (required when `ENSEMBLE_MODELS` includes `gemini`) |

When set, the EnsembleOrchestrator dispatches stages to multiple models in parallel and merges results using per-stage strategies (union, adversarial, consensus).

## Pipeline Modes

| Variable | Default | Options | Description |
|---|---|---|---|
| `EUREKACLAW_MODE` | `skills_only` | `skills_only`, `rl`, `madmax` | Post-run learning mode |
| `GATE_MODE` | `auto` | `auto`, `human`, `none` | Stage gate behavior |
| `THEORY_PIPELINE` | `default` | `default`, `memory_guided` | Which theory proof pipeline to use |
| `EXPERIMENT_MODE` | `auto` | `auto`, `true`, `false` | Experiment stage: auto-detect / force run / force skip *(future work — recommend `false`)* |

**Gate modes:**
- `none` — no stage cards or approval prompts
- `auto` — prints stage summary cards; prompts only when low-confidence lemmas detected
- `human` — prints cards and prompts at every gate; accepts text feedback injected into next agent

## Proof & Theory

| Variable | Default | Description |
|---|---|---|
| `THEORY_MAX_ITERATIONS` | `10` | Max proof iterations in LemmaDeveloper loop |
| `THEORY_REVIEW_MAX_RETRIES` | `3` | Max retries when human reviewer flags a proof step |
| `AUTO_VERIFY_CONFIDENCE` | `0.95` | Auto-accept proofs with confidence ≥ this threshold (skips LLM Verifier call) |
| `VERIFIER_PASS_CONFIDENCE` | `0.90` | Confidence threshold for the LLM Verifier to mark a lemma as passing |
| `STAGNATION_WINDOW` | `3` | Force Refiner if same error repeats N times |
| `ENFORCE_PROOF_STYLE` | `true` | Inject proof readability rules into WriterAgent prompts |

## Context & Compression

| Variable | Default | Description |
|---|---|---|
| `CONTEXT_COMPRESS_AFTER_TURNS` | `6` | Compress agent history every N turns using fast model |

## Token Limits (per call type)

| Variable | Default | Applies to |
|---|---|---|
| `MAX_TOKENS_AGENT` | `8192` | Main agent reasoning loop (all agents) |
| `MAX_TOKENS_PROVER` | `4096` | Proof generation (Prover) |
| `MAX_TOKENS_PLANNER` | `4096` | Research direction planning (diverge); converge uses half |
| `MAX_TOKENS_DECOMPOSER` | `4096` | Lemma decomposition (LemmaDecomposer, KeyLemmaExtractor) |
| `MAX_TOKENS_ASSEMBLER` | `6144` | Proof assembly narrative (Assembler) |
| `MAX_TOKENS_CRYSTALLIZER` | `4096` | Final theorem statement extraction (TheoremCrystallizer) |
| `MAX_TOKENS_ARCHITECT` | `3072` | Proof plan generation (ProofArchitect) |
| `MAX_TOKENS_ANALYST` | `1536` | Analysis stages (MemoryGuidedAnalyzer, TemplateSelector, ProofSkeletonBuilder) |
| `MAX_TOKENS_SKETCH` | `1024` | Lean4/Coq sketch generation (SketchGenerator) |
| `MAX_TOKENS_FORMALIZER` | `4096` | Formalization, Refiner, CounterexampleSearcher, ResourceAnalyst, PaperReader |
| `MAX_TOKENS_VERIFIER` | `2048` | Proof verification (Verifier) and peer review |
| `MAX_TOKENS_COMPRESS` | `512` | Context compression summaries (fast model) |

All 12 values are adjustable from the Settings tab in the web UI.

## Paper Reader

| Variable | Default | Description |
|---|---|---|
| `PAPER_READER_USE_PDF` | `true` | Enable/disable full-text PDF extraction |
| `PAPER_READER_ABSTRACT_PAPERS` | `10` | Max papers to read abstracts from |
| `PAPER_READER_PDF_PAPERS` | `3` | Max papers to extract full text from per session |
| `PAPER_READER_PDF_BACKEND` | `pdfplumber` | PDF extraction backend: `pdfplumber` (lightweight) or `docling` (ML-powered) |

## Output Format

| Variable | Default | Description |
|---|---|---|
| `OUTPUT_FORMAT` | `all` | Output format: `all` (.md + .tex + .pdf), `latex` (.tex + .pdf), `markdown` (.md only) |

## Institutional Library Access

Configures a university library proxy so EurekaLab can download paywalled PDFs. Use the `library-auth` CLI commands to set these values interactively; they are stored in `~/.eurekalab/library_session.json`. The environment variables below serve as fallback defaults.

| Variable | Default | Description |
|---|---|---|
| `LIBRARY_PROXY_URL` | `""` | University library proxy URL (e.g. `https://ezproxy.library.edu/login?url=`) |
| `LIBRARY_PROXY_MODE` | `none` | Proxy rewriting mode: `prefix`, `suffix`, `vpn`, `none` |
| `LIBRARY_CONTACT_EMAIL` | `""` | Contact email sent in HTTP User-Agent for polite crawling |
| `PDF_CACHE_DIR` | `""` | Directory to cache downloaded PDFs (empty = no persistent cache) |
| `PDF_DOWNLOAD_TIMEOUT` | `60` | Timeout in seconds for PDF download requests |
| `PDF_AUTO_DOWNLOAD` | `true` | Automatically attempt to download PDFs when searching papers |

**Quick setup:**
```bash
eurekalab library-auth set-proxy "https://ezproxy.library.edu/login?url="
eurekalab library-auth set-cookie "ezproxy=ABC123; EZproxySID=xyz"
eurekalab library-auth test "10.1109/TIT.2023.1234567"
```

## Zotero Integration

| Variable | Default | Description |
|---|---|---|
| `ZOTERO_ENABLED` | `false` | Enable Zotero integration |
| `ZOTERO_API_KEY` | `""` | Zotero Web API key (get at zotero.org/settings/keys) |
| `ZOTERO_LIBRARY_ID` | `""` | Zotero library ID |
| `ZOTERO_LIBRARY_TYPE` | `user` | Library type: `user` or `group` |
| `ZOTERO_LOCAL_DATA_DIR` | `""` | Path to local Zotero data dir for direct PDF access |
| `ZOTERO_SYNC_BACK` | `false` | Push discoveries back to Zotero |

## Turn Limits

| Variable | Default | Description |
|---|---|---|
| `SURVEY_MAX_TURNS` | `8` | Tool-use turns in SurveyAgent loop |
| `THEORY_STAGE_MAX_TURNS` | `6` | Turns per inner theory stage |
| `WRITER_MAX_TURNS` | `4` | Turns for WriterAgent |

## Search & Retrieval

| Variable | Default | Description |
|---|---|---|
| `ARXIV_MAX_RESULTS` | `10` | Hard cap on arXiv search results |

## Retry & Resilience

| Variable | Default | Description |
|---|---|---|
| `LLM_RETRY_ATTEMPTS` | `5` | Retry count on 5xx / rate-limit errors |
| `LLM_RETRY_WAIT_MIN` | `4` | Minimum exponential backoff (seconds) |
| `LLM_RETRY_WAIT_MAX` | `90` | Maximum exponential backoff (seconds) |

## File Paths & Tools

| Variable | Default | Description |
|---|---|---|
| `EUREKACLAW_DIR` | `~/.eurekalab` | Base directory for skills, memory, and run artifacts |
| `LEAN4_BIN` | `lean` | Path to the Lean4 binary |
| `LATEX_BIN` | `pdflatex` | Path to the pdflatex binary |
| `USE_DOCKER_SANDBOX` | `false` | Use Docker container for Python code execution *(future work — sandbox not fully integrated)* |

## Derived Paths (read-only properties on `settings`)

| Property | Value |
|---|---|
| `settings.skills_dir` | `EUREKACLAW_DIR/skills` |
| `settings.memory_dir` | `EUREKACLAW_DIR/memory` |
| `settings.runs_dir` | `EUREKACLAW_DIR/runs` |
| `settings.fast_model` | `EUREKACLAW_FAST_MODEL` (falls back to main model if unset) |
