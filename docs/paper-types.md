# Paper Types

EurekaLab supports 5 types of academic paper, each with its own pipeline, agent behavior, and output structure.

## Selecting a Paper Type

Use `--paper-type` (or `-t`) on any entry command:

```bash
eurekalab explore "transformer architectures" --paper-type survey
eurekalab explore "AI alignment risks" --paper-type discussion
eurekalab from-bib refs.bib --domain "ML" --paper-type review
eurekalab prove "regret bound" --paper-type proof
```

## The 5 Paper Types

### Proof Paper (`proof`)

**Default for:** `prove`

Produces a mathematical paper with theorems, lemmas, and formal proofs.

**Pipeline:** survey → ideation (hypotheses) → theory (7-stage proof loop) → experiment (numerical validation) → writer

**Output structure:**
- Abstract, Introduction, Preliminaries
- Main Results (theorems + proofs)
- Experiments (optional, bounds validation)
- Related Work, Conclusion

**When to use:** You have a precise mathematical statement to prove, or want to discover and prove new theorems in a domain.

---

### Survey Paper (`survey`)

**Default for:** `explore`, `from-papers`, `from-bib`, `from-zotero`

Produces a narrative survey with taxonomy, comparison tables, trends, and open problems.

**Pipeline:** survey → ideation (taxonomy proposal) → analyst (categorize, compare, identify gaps) → writer

**Output structure:**
- Abstract, Introduction, Background
- Taxonomy (hierarchical categorization)
- Detailed Analysis (per-category)
- Comparison Tables
- Trends and Open Problems
- Conclusion

**When to use:** You want to map a research field, organize methods into categories, compare approaches, and identify where the field is heading.

---

### Systematic Review (`review`)

**Default for:** none (must be explicitly selected)

Produces a PRISMA-style systematic literature review with rigorous methodology.

**Pipeline:** survey → ideation (protocol + criteria) → analyst (screen, assess quality, extract, synthesize) → writer

**Output structure:**
- Abstract (structured), Introduction
- Methods (search strategy, criteria, quality assessment)
- Results (PRISMA flow, study characteristics, synthesis)
- Discussion, Conclusion

**When to use:** You need a rigorous, reproducible review with explicit inclusion/exclusion criteria, quality assessment, and transparent methodology. Required for meta-analyses and evidence-based reviews.

---

### Experimental Study (`experimental`)

**Default for:** none (must be explicitly selected)

Produces a paper with hypothesis, methodology, experiments, statistical analysis, and results.

**Pipeline:** survey → ideation (testable hypotheses) → analyst (experiment design) → experiment (run) → writer

**Output structure:**
- Abstract, Introduction, Related Work
- Methodology (setup, datasets, baselines, metrics)
- Results (tables, statistical significance)
- Discussion, Conclusion

**When to use:** You have a testable claim and want to design, run, and analyze experiments to validate it.

---

### Discussion Paper (`discussion`)

**Default for:** none (must be explicitly selected)

Produces a position/opinion paper with thesis, evidence, counterarguments, and synthesis.

**Pipeline:** survey → ideation (thesis formulation) → analyst (evidence, counterarguments, synthesis) → writer

**Output structure:**
- Abstract, Introduction, Background
- Thesis Development (2-3 argument sections)
- Counterarguments (fairly presented)
- Response to Counterarguments
- Implications, Conclusion

**When to use:** You want to advance a specific position or interpretation, argue for a new perspective, or critically analyze assumptions in a field.

---

## How Paper Type Affects Each Agent

| Agent | proof | survey | review | experimental | discussion |
|-------|-------|--------|--------|-------------|-----------|
| **Survey** | Targeted gap search | Broad domain coverage | Systematic protocol | Baseline-focused | Evidence-focused |
| **Ideation** | Mathematical hypotheses | Taxonomy proposals | Research questions + criteria | Testable hypotheses | Thesis + claims |
| **Core Work** | Theory Agent (prove lemmas) | Analyst (categorize, compare) | Analyst (screen, assess, extract) | Analyst + Experiment | Analyst (evidence, counterarguments) |
| **Writer** | Theorems + proofs | Taxonomy + tables + trends | PRISMA + synthesis tables | Methods + results + stats | Arguments + rebuttals |

## Combining Paper Type with Entry Mode

Paper type (`--paper-type`) and entry mode (the command) are orthogonal:

| | `prove` | `explore` | `from-papers` | `from-bib` | `from-draft` | `from-zotero` |
|---|---|---|---|---|---|---|
| **proof** | Natural fit | Works | Works | Works | Works | Works |
| **survey** | Unusual | Natural fit | Natural fit | Natural fit | Works | Natural fit |
| **review** | Unusual | Works | Works | Natural fit | Works | Natural fit |
| **experimental** | Unusual | Works | Works | Works | Works | Works |
| **discussion** | Unusual | Works | Works | Works | Natural fit | Works |

## Reviewing Your Paper

After writing (or at any stage), use the **Review** tab to get structured feedback:

```bash
# From the terminal
eurekalab review paper.tex --persona adversarial
eurekalab review paper.tex --persona constructive --instructions "focus on the methodology"

# From the UI
# Click the Review tab → select a persona → Run Review
```

Three built-in reviewer personas:
- **Adversarial** — finds every weakness, toughest possible review
- **Rigorous** — balanced peer review with major/minor classification
- **Constructive** — strengths first, every critique paired with actionable fix

Additional personas (journal-specific, expert reviewers) can be installed from YAML files.
