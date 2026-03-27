<p align="center">
  <img src="assets/logo-cropped.svg" width="700" alt="EurekaLab  — The Research Claw">
</p>

<p align="center">
  <strong>The AI that catches your Eureka moments.</strong><br/>
  Crawls arXiv · Generates theorems · Proves lemmas · Writes LaTeX papers · Runs experiments<br/>
  All from your chat or terminal.
</p>

<p align="center">
  <a href="https://github.com/EurekaLab/EurekaLab/stargazers"><img src="https://img.shields.io/github/stars/EurekaLab/EurekaLab?style=flat-square&color=yellow" alt="Stars"/></a>
  <img src="https://img.shields.io/badge/License-Apache_2.0-blue.svg?style=flat-square" alt="License: Apache 2.0">
  <img src="https://img.shields.io/badge/python-3.11%2B-007ACC?style=flat-square&color=yellow" alt="Python 3.11+"/>
  <img src="https://img.shields.io/badge/local--first-private%20by%20default-1F8AD2?style=flat-square" alt="Local-first"/>
</p>

<p align="center">
  <a href="https://www.eurekalab.ai/"><img src="https://img.shields.io/badge/🌐%20Website-eurekalab.ai-007ACC?style=flat-square" alt="Website"/></a>
  <a href="https://eurekalab.github.io/"><img src="https://img.shields.io/badge/📚%20Docs-eurekalab.github.io-007ACC?style=flat-square&color=green" alt="Docs"/></a>
  <a href="https://www.xiaohongshu.com/user/profile/69bf26c7000000003402ea57"><img src="https://img.shields.io/badge/📕%20RedNote-Follow%20Us-FF2442?style=flat-square" alt="RedNote"/></a>
  <a href="https://discord.gg/SprC5BgmcW"><img src="https://img.shields.io/badge/💬%20Discord-Join%20Us-5865F2?style=flat-square" alt="Discord"/></a>
</p>

```
$ eurekalab prove "Find recent papers on sparse attention + prove efficiency bound"

🦞 Crawling arXiv cs.LG (2024–2025)...
📄 Found 23 relevant papers. Summarizing...
💡 Hypothesis generated: O(n log n) via topological filtration
✨ Theorem 3.1 drafted. LaTeX ready. Proof complete.
🦞 Eureka! Paper draft saved to ./results/
```

> **Fork Notice:** This is a fork of [EurekaLab/EurekaLab](https://github.com/EurekaLab/EurekaLab) with significant improvements to resilience, multi-model support, and research quality. See [What's New in This Fork](#whats-new-in-this-fork) below.

---

**EurekaLab** is a multi-agent AI research assistant that goes from a question to a publishable result — autonomously. It crawls the literature, generates and stress-tests hypotheses, runs experiments, and writes up findings, all from your terminal or browser UI.

> **Open Source · Local-First · Privacy by Design · Apache 2.0 License**

---

## What EurekaLab Does

| | Feature | Description |
|---|---|---|
| 🔍 | **Literature Crawler** | Fetch, summarize, and cross-reference papers from arXiv and Semantic Scholar |
| 💡 | **Idea Generator** | Brainstorm novel hypotheses by synthesizing patterns across thousands of papers |
| 🔢 | **Theorem Prover** | Generate, verify, and formalize proofs via a 7-stage bottom-up pipeline |
| 📄 | **Paper Writer** | Draft camera-ready LaTeX papers with theorem environments and citations |
| 🖥️ | **Runs Locally** | Compatible with Every Major Model API — Privacy by Design |
| 🧠 | **Continual Learning** | Distills proof strategies into skills after every session, improving over time |
| 🧪 | **Experiment Runner** *(under development)* | Numerically validates theoretical bounds; flags low-confidence lemmas |
| 🌐 | **Browser UI** | React + TypeScript interface — live agent track, proof sketch, pause/resume, skills manager |

---

## What's New in This Fork

This fork ([Lvigentini/EurekaLab](https://github.com/Lvigentini/EurekaLab)) adds three major contributions over the upstream project:

### 1. N-Model Ensemble Architecture
Run multiple LLMs (Claude, Gemini, GPT, Kimi, etc.) concurrently across pipeline stages with per-stage merge strategies:

| Stage | Strategy | What It Does |
|-------|----------|-------------|
| Survey | Union + dedup | Broader literature coverage from multiple models |
| Ideation | Adversarial cross-review | Models challenge each other's hypotheses |
| Theory | Asymmetric (primary + reviewer) | Independent proof verification catches blind spots |
| Experiment | Consensus | Both models must agree for high confidence |

Configure via environment variables — add `ENSEMBLE_MODELS=claude,gemini` and per-stage strategies. Adding a new model is 3 lines of config.

### 2. Crash Resilience
- **Incremental checkpointing** — state saved after each pipeline stage, not just at session end
- **Full-pipeline resume** — `eurekalab resume <session_id>` detects progress from any stage
- **Circuit breaker** — fails fast after 3 consecutive API failures instead of burning tokens
- **Error classification** — auth errors (401/403) fail immediately, server errors retry with backoff
- **ccproxy health monitoring** — auto-restarts OAuth proxy if it crashes mid-session
- **Token waste tracking** — reports tokens spent on failed retries at session end

### 3. Enhanced Search
- **Gemini parallel search** — Google Gemini with grounding searches alongside arXiv/Semantic Scholar for broader coverage, especially on interdisciplinary topics
- **Structured error handling** — tool failures return JSON errors that agents can reason about
- **Dynamic ensemble recommendations** — system suggests widening or narrowing model participation based on observed results

### 4. Non-Linear Pipeline & Version History
- **Git-like session versioning** — every state change is tracked, diffable, and reversible (`history`, `diff`, `checkout` commands)
- **Content tier tracking** — papers are classified as full_text/abstract/metadata/missing; the system prompts you to fill gaps via institutional access instead of silently degrading
- **Multiple entry points** — start from `.bib` files, draft papers, or Zotero collections, not just cold-start search
- **Mid-session injection** — pause a session, inject papers/ideas/drafts, and resume with enriched context
- **Continuous ideation** — ideas from the user, from papers, and from failed proofs accumulate in an IdeationPool that feeds into every stage
- **Zotero integration** — bidirectional sync: import your curated library, push discoveries back

### 5. Flexible Output
- **Custom output naming** — the system prompts for a file base name at the end of each session instead of generic `paper.tex`/`references.bib`
- **pdfplumber PDF backend** — lightweight alternative to Docling for full-text extraction, configurable via `PAPER_READER_PDF_BACKEND`

---

## Installation

**macOS / Linux**

```bash
curl -fsSL https://eurekalab.ai/install.sh | bash
```

**Windows** *(under development — not fully supported yet)*

```powershell
powershell -c "irm https://eurekalab.ai/install_win.ps1 | iex"
```

The macOS/Linux installer clones the repo, creates a virtual environment, installs EurekaLab, and adds the `eurekalab` command to your PATH. Run `eurekalab onboard` afterwards to configure your API key and settings.

> **Windows users:** native Windows support is under active development. In the meantime, use [WSL 2](https://learn.microsoft.com/en-us/windows/wsl/install) (Ubuntu) and follow the macOS/Linux instructions inside the WSL terminal.

<details>
<summary>Manual install (all platforms)</summary>

**Requirements:** Python ≥ 3.11, Node.js ≥ 20, Git

```bash
git clone https://github.com/EurekaLab/EurekaLab
cd EurekaLab
make install                  # pip install -e "." + npm install (frontend)
```
</details>

---

## Quick Start

```bash
eurekalab onboard            # interactive setup wizard (creates .env)
# — or — cp .env.example .env and add ANTHROPIC_API_KEY manually

eurekalab install-skills     # install built-in proof skills (do once)

# Browser UI — build frontend and open in browser
make open

# CLI — prove a conjecture
eurekalab prove "The sample complexity of transformers is O(L·d·log(d)/ε²)" \
    --domain "ML theory" --output ./results

# CLI — explore a domain
eurekalab explore "multi-armed bandit theory"

# CLI — start from arXiv papers
eurekalab from-papers 1706.03762 2005.14165 --domain "attention mechanisms"

# CLI — start from your existing bibliography
eurekalab from-bib references.bib --pdfs ./papers/ --domain "ML theory"

# CLI — start from a draft paper
eurekalab from-draft paper.tex "Help me strengthen the theory section"

# CLI — start from your Zotero library
export ZOTERO_API_KEY=your_key ZOTERO_LIBRARY_ID=your_id
eurekalab from-zotero ABC123 --domain "information theory"

# Mid-session: inject a paper or idea into a paused session
eurekalab inject paper <session-id> 2401.12345
eurekalab inject idea <session-id> "What about spectral methods?"

# Version management: view history, compare, roll back
eurekalab history <session-id>
eurekalab diff <session-id> 1 3
eurekalab checkout <session-id> 2
```

> No API key? Use a Claude Pro/Max subscription via [OAuth](https://github.com/EurekaLab/EurekaLab/blob/main/docs/configuration.md#llm-backend).

---

## Pipeline

<p align="center">
  <img src="docs/images/pipeline-overview.svg" alt="EurekaLab Pipeline" width="640"/>
</p>

---

## Input Modes

| Command | When to use |
|---|---|
| `eurekalab prove "<conjecture>"` | You have a precise mathematical statement to prove |
| `eurekalab from-papers <ids>` | You want to extend or find gaps in specific papers |
| `eurekalab explore "<domain>"` | You have a broad research area but no conjecture yet |
| `eurekalab from-bib refs.bib --pdfs ./papers/` | You have a .bib file and local PDFs from your research |
| `eurekalab from-draft paper.tex "Strengthen theory"` | You have a draft paper and want to extend/complete it |
| `eurekalab from-zotero <collection-id>` | You want to start from your Zotero library (institutional access) |

---

## Documentation

See detailed documentation in https://eurekalab.github.io/ .

| | |
|---|---|
| 📖 [**User Guide**](https://eurekalab.github.io/user-guide/index.html) | Installation, walkthrough, gate modes, tuning, troubleshooting |
| ⚙️ [**Configuration**](https://eurekalab.github.io/reference/configuration.html) | All `.env` variables with defaults |
| 🏗️ [**Architecture**](https://eurekalab.github.io/reference/architecture.html) | Pipeline stages, data flow, component design |
| 🤖 [**Agents**](https://eurekalab.github.io/reference/agents.html) | Each agent's role, inputs, outputs, and tool usage |
| 🔧 [**Tools**](https://eurekalab.github.io/reference/tools.html) | arXiv, Semantic Scholar, Lean4, WolframAlpha, code execution |
| 💻 [**CLI Reference**](https://eurekalab.github.io/reference/cli.html) | All commands and options |
| 🐍 [**Python API**](https://eurekalab.github.io/reference/api.html) | `EurekaSession`, `KnowledgeBus`, data models |
| 🧠 [**Memory System**](https://eurekalab.github.io/reference/memory.html) | Episodic, persistent, and knowledge graph tiers |
| ✨ [**Skills**](https://eurekalab.github.io/reference/skills.html) | Skill registry, injection, distillation, writing custom skills |
| 🔌 [**Domain Plugins**](https://eurekalab.github.io/reference/domains.html) | Plugin architecture, MAB domain, adding new domains |
| 🌐 [**UI Design**](https://eurekalab.github.io/user-guide/browser-ui.html) | React/TS architecture, component tree, run commands |

---

## Configuration Essentials

```bash
cp .env.example .env
```

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | API key (or use OAuth, see [User Guide](https://github.com/EurekaLab/EurekaLab/blob/main/docs/user-guide.md#authentication)) |
| `EUREKALAB_MODEL` | `claude-sonnet-4-6` | Main reasoning model |
| `GATE_MODE` | `auto` | `none` · `auto` · `human` |
| `THEORY_PIPELINE` | `default` | `default` or `memory_guided` |
| `OUTPUT_FORMAT` | `latex` | `latex` or `markdown` |
| `EXPERIMENT_MODE` | `auto` | `auto` · `true` · `false` |
| `THEORY_MAX_ITERATIONS` | `10` | Max proof loop iterations |

Full reference → [configuration.md](https://github.com/EurekaLab/EurekaLab/blob/main/docs/configuration.md)

---

## Evaluation

EurekaLab includes a **Scientist-Bench** evaluator:

| Dimension | Weight |
|---|---|
| Formal correctness (Lean4 / LLM peer review) | 0.35 |
| Novelty (embedding distance from known results) | 0.25 |
| Experimental alignment | 0.15 |
| Proof depth (lemma count) | 0.15 |
| Citation coverage | 0.10 |

```bash
eurekalab eval-session <session_id>
```

---

## Contributing

```bash
# Unit tests (no API key needed)
pytest tests/unit/ -v

# Integration tests
ANTHROPIC_API_KEY=sk-... pytest tests/integration/ -v

# Frontend type-check
make typecheck

# Frontend development (hot-reload)
make dev
```

To add a **custom skill**, drop a `.md` file into `~/.eurekalab/skills/` — see [skills.md](https://github.com/EurekaLab/EurekaLab/blob/main/docs/skills.md).

To add a **new research domain**, subclass `DomainPlugin` — see [domains.md](https://github.com/EurekaLab/EurekaLab/blob/main/docs/domains.md).

To add a **new tool**, subclass `BaseTool` and register it — see [tools.md](https://github.com/EurekaLab/EurekaLab/blob/main/docs/tools.md).

---

## Acknowledgements

EurekaLab builds on ideas and inspiration from the broader AI-for-science community. We thank the authors of the following projects:

- [MetaClaw](https://github.com/aiming-lab/MetaClaw) — multi-agent research orchestration
- [AutoResearchClaw](https://github.com/aiming-lab/AutoResearchClaw) — automated research orchestration
- [EvoScientist](https://github.com/EvoScientist/EvoScientist) — evolutionary hypothesis generation
- [AI-Researcher](https://github.com/hkuds/ai-researcher) — automated research pipeline
- [Awesome AI for Science](https://github.com/ai-boost/awesome-ai-for-science) — curated resource list
- [Dr. Claw](https://github.com/OpenLAIR/dr-claw) — open research agent framework
- [OpenClaw](https://github.com/openclaw/openclaw) — open-source research claw
- [ClawTeam](https://github.com/HKUDS/ClawTeam) — collaborative research agents
- [ScienceClaw](https://github.com/beita6969/ScienceClaw) — science-focused research agent

---

## Citation

If you use EurekaLab in your research, please cite:

```bibtex
@misc{eurekalab2026,
  title     = {EurekaLab: An AI Agent for Capturing Eureka Moments},
  author    = {Li, Xuheng and Di, Qiwei and Zhang, Chenggong and Ji, Kaixuan and Zhao, Qingyue and Liu, Yifeng and Zhang, Shiyuan and Gu, Quanquan},
  year      = {2026},
  url       = {https://github.com/EurekaLab/EurekaLab}
}
```

---

## License

Apache 2.0 License. See [LICENSE](LICENSE) for details.

---

<p align="center">
  Built for researchers who believe the next breakthrough is one Eureka moment away. 🦞
</p>
