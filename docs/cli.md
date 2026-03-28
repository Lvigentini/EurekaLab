# CLI Reference

Install the package (or run `python -m eurekalab`) to get the `eurekalab` command.

## Global Options

| Flag | Description |
|---|---|
| `--verbose`, `-v` | Enable DEBUG logging |

---

## Commands

### `prove` — Prove a conjecture

```bash
eurekalab prove "<conjecture>" [OPTIONS]
```

**Arguments:**
- `conjecture` — The mathematical conjecture or claim to prove (string)

**Options:**

| Option | Default | Description |
|---|---|---|
| `--domain`, `-d` | `""` | Research domain. Auto-inferred from conjecture if omitted |
| `--mode` | `skills_only` | Post-run learning mode: `skills_only`, `rl`, `madmax` |
| `--skills` | *(all)* | Pin specific skills by name (repeatable). Pinned skills always appear first in the injection regardless of usage score |
| `--gate` | `none` | Gate control: `human`, `auto`, `none` |
| `--output`, `-o` | `./results` | Output directory for artifacts |

**Example:**
```bash
eurekalab prove "UCB1 achieves O(sqrt(KT log T)) expected cumulative regret in the stochastic multi-armed bandit setting" \
  --domain "multi-armed bandit theory" \
  --skills ucb_regret_analysis --skills concentration_inequalities \
  --gate human \
  --output ./results
```

---

### `explore` — Explore a research domain

```bash
eurekalab explore "<domain>" [OPTIONS]
```

**Arguments:**
- `domain` — The research domain to explore (string)

**Options:**

| Option | Default | Description |
|---|---|---|
| `--query`, `-q` | `""` | Specific research question within the domain |
| `--mode` | `skills_only` | Post-run learning mode: `skills_only`, `rl`, `madmax` |
| `--gate` | `none` | Gate control: `human`, `auto`, `none` |
| `--output`, `-o` | `./results` | Output directory for artifacts |

**Example:**
```bash
eurekalab explore "multi-armed bandit theory" \
  --query "tight regret bounds for heavy-tailed rewards" --output ./results
```

---

### `from-papers` — Generate hypotheses from reference papers

```bash
eurekalab from-papers <paper_id> [<paper_id> ...] [OPTIONS]
```

**Arguments:**
- `paper_ids` — One or more arXiv IDs or Semantic Scholar IDs (variadic)

**Options:**

| Option | Default | Description |
|---|---|---|
| `--domain`, `-d` | *(required)* | Research domain |
| `--query`, `-q` | `""` | Specific research question or focus within the papers |
| `--mode` | `skills_only` | Post-run learning mode |
| `--skills` | *(all)* | Pin specific skills by name (repeatable). Pinned skills always appear first in the injection regardless of usage score |
| `--gate` | `none` | Gate control |
| `--output`, `-o` | `./results` | Output directory |

**Example:**
```bash
eurekalab from-papers 1602.01783 2301.00774 \
  --domain "bandit algorithms" --output ./results
```

---

### `pause` — Pause a running session

```bash
eurekalab pause <session_id>
```

**Arguments:**
- `session_id` — Session ID of the running proof to pause (found in the console header at startup)

Writes a `pause.flag` file to `~/.eurekalab/sessions/<session_id>/`. A background poller detects this flag within 1 second and cancels the running asyncio task immediately, interrupting any in-flight LLM call. The theory agent saves a checkpoint of all lemmas proved so far and raises `ProofPausedException`. The partial proof state is preserved in `~/.eurekalab/sessions/<session_id>/checkpoint.json`.

You can also pause by pressing **Ctrl+C** during a run. EurekaLab intercepts `SIGINT` and cancels the running task immediately — the pipeline stops at the next `await` rather than waiting for the current LLM call to finish.

**Example:**
```bash
# In a separate terminal while a proof is running:
eurekalab pause abc12345
```

---

### `resume` — Resume a paused session

```bash
eurekalab resume <session_id>
```

**Arguments:**
- `session_id` — Session ID of the paused proof to continue

Loads the checkpoint from `~/.eurekalab/sessions/<session_id>/checkpoint.json` and re-runs the theory agent starting from the saved stage, with all previously proved lemmas already in `TheoryState`. Passes the same domain and query as the original session.

**Example:**
```bash
eurekalab resume abc12345
```

---

### `replay-theory-tail` — Replay theory tail stages

```bash
eurekalab replay-theory-tail <session_id> [OPTIONS]
```

**Arguments:**
- `session_id` — Session ID of a completed run

**Options:**

| Option | Default | Description |
|---|---|---|
| `--from` | `consistency_checker` | Stage to restart from: `assembler`, `theorem_crystallizer`, `consistency_checker` |

Re-runs the final stages of the theory pipeline (Assembler → TheoremCrystallizer → ConsistencyChecker) from a saved `theory_state.json` without repeating the survey, planning, or lemma proving phases. Useful for quickly iterating on crystallization or consistency-check failures.

**Example:**
```bash
eurekalab replay-theory-tail abc12345 --from assembler
```

---

### `test-paper-reader` — Test PaperReader on a single paper

```bash
eurekalab test-paper-reader <session_id> <paper_ref> [OPTIONS]
```

**Arguments:**
- `session_id` — Session ID of a completed run whose bibliography to use
- `paper_ref` — Paper ID, arXiv ID, or case-insensitive substring of the title

**Options:**

| Option | Default | Description |
|---|---|---|
| `--mode` | `both` | Extraction mode: `abstract`, `pdf`, `both` |
| `--direction` | `""` | Research direction override for extraction prompts |

Exercises PaperReader's abstract and/or PDF extraction on a single bibliography entry without running the full pipeline.

**Example:**
```bash
eurekalab test-paper-reader abc12345 "UCB1" --mode both
```

---

### `onboard` — Interactive configuration wizard

```bash
eurekalab onboard [OPTIONS]
```

**Options:**

| Option | Description |
|---|---|
| `--non-interactive` | Write defaults without prompting |
| `--reset` | Overwrite existing `.env` without merging |
| `--env-file` | Path to the `.env` file to write (default: `.env`) |

Walks you through LLM backend selection, API key setup, search tools, and system behaviour, then writes (or updates) `.env`.

**Example:**
```bash
eurekalab onboard
eurekalab onboard --env-file ~/.eurekalab/.env
```

---

### `skills` — List available skills

```bash
eurekalab skills
```

Prints a Rich panel listing all skills in the skill bank with:
- Skill name
- Tags
- Description
- Source (`seed`, `distilled`, or `manual`)

---

### `eval-session` — Evaluate a completed session

```bash
eurekalab eval-session <session_id>
```

**Arguments:**
- `session_id` — Session ID from a previous run (found in run directory name)

Prints an evaluation report with proof quality metrics.

---

### `install-skills` — Install seed skills

```bash
eurekalab install-skills [SKILLNAME] [--force]
```

**Arguments:**
- `skillname` *(optional)* — Install a specific skill from clawhub by name

**Options:**

| Option | Description |
|---|---|
| `--force`, `-f` | Overwrite existing skills in `~/.eurekalab/skills/` |

Without arguments, copies all bundled seed skills from the package to `~/.eurekalab/skills/`. When a skill name is provided, downloads that skill from clawhub instead.

---

### `ui` — Launch the browser UI

```bash
eurekalab ui [OPTIONS]
```

**Options:**

| Option | Default | Description |
|---|---|---|
| `--host` | `127.0.0.1` | Interface to bind to |
| `--port` | `8080` | Port to listen on |
| `--open-browser` / `--no-open-browser` | False | Auto-open browser on start |

**Example:**
```bash
eurekalab ui --open-browser
```

---

### `from-bib` — Start from a .bib file

```bash
eurekalab from-bib <bib_file> [OPTIONS]
```

**Arguments:**
- `bib_file` — Path to a `.bib` file (must exist)

**Options:**

| Option | Default | Description |
|---|---|---|
| `--pdfs`, `-p` | *(none)* | Directory containing local PDF files to match against .bib entries |
| `--domain`, `-d` | *(required)* | Research domain |
| `--query`, `-q` | `""` | Specific research question |
| `--mode` | `skills_only` | Post-run learning mode: `skills_only`, `rl`, `madmax` |
| `--gate` | `none` | Gate control: `human`, `auto`, `none` |
| `--output`, `-o` | `./results` | Output directory |

Loads all papers from a `.bib` file and optionally matches them to local PDFs in the given directory (full text is extracted if a PDF match is found). EurekaLab then identifies gaps in the existing bibliography — missing related work, recent advances not represented, foundational papers that should be added — rather than re-fetching papers already present.

**Example:**
```bash
eurekalab from-bib refs.bib --pdfs ./papers/ \
  --domain "ML theory" --output ./results
```

---

### `from-draft` — Start from a draft paper

```bash
eurekalab from-draft <draft_file> [instruction] [OPTIONS]
```

**Arguments:**
- `draft_file` — Path to the draft paper (`.tex`, `.md`, or `.pdf`; must exist)
- `instruction` *(optional)* — Free-text instruction describing what to do with the draft (e.g. `"Strengthen the theory section"`)

**Options:**

| Option | Default | Description |
|---|---|---|
| `--domain`, `-d` | *(auto-inferred)* | Research domain (inferred from draft title if omitted) |
| `--query`, `-q` | `""` | Specific research question |
| `--mode` | `skills_only` | Post-run learning mode: `skills_only`, `rl`, `madmax` |
| `--gate` | `none` | Gate control: `human`, `auto`, `none` |
| `--output`, `-o` | `./results` | Output directory |

Analyzes the draft using `DraftAnalyzer` to extract its title, abstract, claims, citations, and any identified gaps/TODOs, then runs EurekaLab in exploration mode. The draft context (instruction, claims, gaps) is injected into the session so the pipeline can survey missing related work and strengthen the paper.

**Example:**
```bash
eurekalab from-draft paper.tex "This is a WIP, strengthen the theory" \
  --domain "ML theory" --output ./results

eurekalab from-draft paper.tex --domain "bandit algorithms"
```

---

### `from-zotero` — Start from a Zotero collection

```bash
eurekalab from-zotero <collection_id> [OPTIONS]
```

**Arguments:**
- `collection_id` — Zotero collection key (the short alphanumeric ID shown in the Zotero URL, e.g. `ABC123`)

**Options:**

| Option | Default | Description |
|---|---|---|
| `--domain`, `-d` | *(required)* | Research domain |
| `--query`, `-q` | `""` | Specific research question |
| `--mode` | `skills_only` | Post-run learning mode: `skills_only`, `rl`, `madmax` |
| `--gate` | `none` | Gate control: `human`, `auto`, `none` |
| `--output`, `-o` | `./results` | Output directory |

Requires `ZOTERO_API_KEY` and `ZOTERO_LIBRARY_ID` environment variables. Install the optional Zotero extra first: `pip install 'eurekalab[zotero]'`. Imports all items from the collection via the Zotero API and extracts full text from any locally available PDFs, then runs EurekaLab in reference mode to find gaps and missing work.

**Example:**
```bash
eurekalab from-zotero ABC123 --domain "ML theory" --output ./results
```

---

### `history` — Show version history for a session

```bash
eurekalab history <session_id>
```

**Arguments:**
- `session_id` — Session ID of a previous run

Prints a Rich table of all saved versions for the session, showing version number, relative age, the event that triggered the snapshot (`trigger`), and the last three completed stages. The current HEAD version is marked with `*`.

**Example:**
```bash
eurekalab history abc12345
```

---

### `diff` — Show changes between two versions

```bash
eurekalab diff <session_id> <v1> <v2>
```

**Arguments:**
- `session_id` — Session ID
- `v1` — Source version number (integer)
- `v2` — Target version number (integer)

Compares the two snapshots and prints a colour-coded list of changes: additions (green), removals (red), and neutral modifications (yellow).

**Example:**
```bash
eurekalab diff abc12345 1 3
```

---

### `checkout` — Restore session state to a specific version

```bash
eurekalab checkout <session_id> <version_number>
```

**Arguments:**
- `session_id` — Session ID
- `version_number` — Version number to restore to (integer, from `eurekalab history`)

Displays a summary of the target version and asks for confirmation. On confirmation, the current HEAD is snapshotted as a new version (preserving it), and the session state is restored to the selected version. Use `eurekalab resume <session_id>` afterwards to continue from that point.

**Example:**
```bash
eurekalab checkout abc12345 3
```

---

### `inject paper` — Inject a paper into a paused session

```bash
eurekalab inject paper <session_id> <paper_ref>
```

**Arguments:**
- `session_id` — Session ID of a paused session
- `paper_ref` — arXiv ID (e.g. `2401.12345`) or path to a local `.pdf` file

Adds the paper to the session's bibliography. If `paper_ref` is a local PDF, its full text is extracted. The paper is also registered in the ideation pool as a new input signal. A version snapshot is saved automatically. Resume the session with `eurekalab resume <session_id>`.

**Example:**
```bash
eurekalab inject paper abc12345 2401.12345
eurekalab inject paper abc12345 ./my-paper.pdf
```

---

### `inject idea` — Inject an idea into a paused session

```bash
eurekalab inject idea <session_id> <text>
```

**Arguments:**
- `session_id` — Session ID of a paused session
- `text` — Free-text idea to inject into the ideation pool

Adds the idea to the session's ideation pool so that it will be considered when the session resumes. A version snapshot is saved automatically.

**Example:**
```bash
eurekalab inject idea abc12345 "What if we apply spectral methods here?"
```

---

### `inject draft` — Inject a draft paper into a paused session

```bash
eurekalab inject draft <session_id> <draft_file> [instruction]
```

**Arguments:**
- `session_id` — Session ID of a paused session
- `draft_file` — Path to the draft file (must exist)
- `instruction` *(optional)* — Instruction describing how to use the draft

Analyzes the draft (extracts title, abstract, claims, and citations) and injects it into the session. Claims are added to the ideation pool and the research brief is updated with draft context. A version snapshot is saved automatically.

**Example:**
```bash
eurekalab inject draft abc12345 paper.tex "Consider these new results"
eurekalab inject draft abc12345 paper.tex
```

---

### `push-to-zotero` — Push session results to Zotero

```bash
eurekalab push-to-zotero <session_id> [OPTIONS]
```

**Arguments:**
- `session_id` — Session ID of a completed run

**Options:**

| Option | Default | Description |
|---|---|---|
| `--collection`, `-c` | `EurekaLab Results` | Zotero collection name to push results into |

Requires `ZOTERO_API_KEY` and `ZOTERO_LIBRARY_ID` environment variables and `pip install 'eurekalab[zotero]'`. Creates (or reuses) the named collection in your Zotero library, pushes all newly discovered papers (those not already in Zotero), and attaches a session summary note to the primary source paper.

**Example:**
```bash
eurekalab push-to-zotero abc12345
eurekalab push-to-zotero abc12345 --collection "Bandit Theory Survey"
```

---

### Global Option: `--paper-type`

Available on all research entry commands (`prove`, `explore`, `from-papers`, `from-bib`, `from-draft`, `from-zotero`):

| Option | Default | Description |
|---|---|---|
| `--paper-type`, `-t` | varies | Type of paper to produce: `proof`, `survey`, `review`, `experimental`, `discussion` |

**Defaults by command:**
| Command | Default |
|---|---|
| `prove` | `proof` |
| `explore` | `survey` |
| `from-papers` | `survey` |
| `from-bib` | `survey` |
| `from-draft` | `proof` |
| `from-zotero` | `survey` |

**Example:**
```bash
eurekalab explore "transformer architectures" --paper-type survey
eurekalab explore "AI alignment" --paper-type discussion
eurekalab from-bib refs.bib --domain "ML" --paper-type review
```

---

### `sessions` — List all sessions

```bash
eurekalab sessions
```

Shows a Rich table of all sessions from the SQLite database: session ID, domain, mode, status, completed stages, and age.

---

### `clean` — Remove old sessions

```bash
eurekalab clean [OPTIONS]
```

| Option | Default | Description |
|---|---|---|
| `--older-than` | `30` | Remove sessions older than N days |
| `--status` | *(all)* | Only remove sessions with this status: `failed`, `completed`, `all` |
| `--dry-run` | off | Show what would be removed without removing |

**Example:**
```bash
eurekalab clean --older-than 30 --status failed
eurekalab clean --dry-run
```

---

### `housekeep` — Global maintenance

```bash
eurekalab housekeep [OPTIONS]
```

| Option | Default | Description |
|---|---|---|
| `--push-papers/--no-push-papers` | off | Push unfiled papers from all sessions to Zotero |
| `--collection`, `-c` | `EurekaLab Library` | Zotero collection name |

**Example:**
```bash
eurekalab housekeep --push-papers --collection "My Research"
```

---

### `library-auth` — University library proxy configuration

`library-auth` is a command group for configuring institutional library access to download paywalled PDFs.

---

### `library-auth set-proxy` — Set the proxy URL

```bash
eurekalab library-auth set-proxy <proxy_url> [OPTIONS]
```

**Arguments:**
- `proxy_url` — The university library proxy URL (e.g. `https://ezproxy.library.edu/login?url=`)

**Options:**

| Option | Default | Description |
|---|---|---|
| `--mode`, `-m` | `prefix` | Proxy rewriting mode: `prefix`, `suffix`, `vpn` |

**Example:**
```bash
eurekalab library-auth set-proxy "https://ezproxy.library.edu/login?url="
eurekalab library-auth set-proxy "https://ezproxy.library.edu/login?url=" --mode suffix
```

---

### `library-auth set-cookie` — Add authentication cookie

```bash
eurekalab library-auth set-cookie <cookie_string>
```

**Arguments:**
- `cookie_string` — Cookie header value copied from browser DevTools on a proxied page (e.g. `ezproxy=ABC123; EZproxySID=xyz`)

Parses the cookie string and merges it into the stored library session, preserving any existing proxy settings.

**Example:**
```bash
eurekalab library-auth set-cookie "ezproxy=ABC123; EZproxySID=xyz"
```

---

### `library-auth import-cookies` — Import cookies from a file

```bash
eurekalab library-auth import-cookies <cookie_file>
```

**Arguments:**
- `cookie_file` — Path to a Netscape-format `cookies.txt` file (must exist). Many browser extensions can export cookies in this format.

**Example:**
```bash
eurekalab library-auth import-cookies ~/Downloads/cookies.txt
```

---

### `library-auth status` — Show authentication status

```bash
eurekalab library-auth status
```

Prints a panel showing whether a library session is configured and, if so, the proxy URL, proxy mode, number of stored cookies, and last-updated timestamp.

**Example:**
```bash
eurekalab library-auth status
```

---

### `library-auth test` — Test PDF download access

```bash
eurekalab library-auth test <doi>
```

**Arguments:**
- `doi` — DOI of the paper to test (e.g. `10.1109/TIT.2023.1234567`)

Runs the full `PdfDownloader` cascade (Unpaywall → CrossRef → library proxy) for the given DOI and reports success or failure. If no library session is configured, it falls back to open-access sources only.

**Example:**
```bash
eurekalab library-auth test "10.1109/TIT.2023.1234567"
```

---

## Output Artifacts

All three research commands (`prove`, `explore`, `from-papers`) write artifacts to `<output>/<session_id>/`:

```
<output>/<session_id>/
├── paper.tex              LaTeX source
├── paper.pdf              Compiled PDF (requires pdflatex + bibtex)
├── references.bib         Bibliography in BibTeX format
├── theory_state.json      Full proof state (lemmas, proofs, status)
├── research_brief.json    Planning state (directions, selected direction)
└── experiment_result.json Numerical validation results (if run)
```

Paused sessions also write a checkpoint to `~/.eurekalab/sessions/<session_id>/checkpoint.json`.

## Theory Review Gate

After the Theory Agent finishes and before the Writer runs, EurekaLab displays a numbered proof sketch and asks for approval:

```
──────────────── Proof Sketch Review ────────────────
  L1  [✓] arm_pull_count_bound  verified
       For arm a with mean gap Δ_a ...
  L2  [~] regret_decomposition  low confidence
       Total regret decomposes as ...
  L3  [✓] main_theorem          verified
       UCB1 achieves O(√(KT log T)) regret ...
──────────────────────────────────────────────────────

Does this proof sketch look correct?
  y  — Proceed to writing
  n  — Flag the most logically problematic step
→
```

- **y / Enter** — proceed to the WriterAgent
- **n** — you are asked which step has the most critical logical gap (e.g. `L2` or the full lemma ID) and to describe the issue. The TheoryAgent re-runs once with your feedback injected into its task, then shows the updated sketch one more time.

The theory review gate is **always shown** regardless of `--gate` mode.

## Exit Codes

| Code | Meaning |
|---|---|
| `0` | Success — paper generated |
| `1` | Runtime error (see console output) |
