"""IdeationAgent — hypothesis generation, gap identification, cross-disciplinary connections."""

from __future__ import annotations

import json
import logging
import uuid

from eurekalab.agents.base import BaseAgent
from eurekalab.types.agents import AgentResult, AgentRole
from eurekalab.types.artifacts import ResearchDirection
from eurekalab.types.tasks import Task

logger = logging.getLogger(__name__)


class IdeationAgent(BaseAgent):
    """Generates novel research hypotheses from survey findings.

    Uses a DeepInnovator-style approach: identifies gaps, makes cross-domain
    connections, and ranks hypotheses by novelty × impact × feasibility.
    """

    role = AgentRole.IDEATION

    def get_tool_names(self) -> list[str]:
        return ["web_search", "arxiv_search"]

    _PROMPTS_BY_TYPE: dict[str, str] = {
        "proof": """\
You are the Ideation Agent. Generate novel research hypotheses.
Your process:
1. Gap analysis: identify what theorems are missing
2. Cross-domain connection: look for analogies
3. Hypothesis generation: formulate precise mathematical conjectures
4. Scoring: rate each on Novelty, Feasibility, Impact (0-1)

For each hypothesis, provide a precise mathematical statement, the key insight,
and a proof strategy sketch.""",
        "survey": """\
You are the Ideation Agent. Propose a survey structure for this research domain.
Your process:
1. Identify the major sub-areas and methodological families
2. Propose a taxonomy (3-7 top-level categories with subcategories)
3. Identify comparison dimensions (what makes methods different?)
4. Spot trends (what's growing, what's declining, what's converging?)
5. Flag open problems and under-explored combinations

For each proposed direction, provide:
- A clear title describing the survey angle
- The proposed taxonomy structure (brief outline)
- Key comparison dimensions
- 2-3 most interesting open problems

Score each on Coverage (0-1), Novelty of Organization (0-1), and Practical Value (0-1).""",
        "review": """\
You are the Ideation Agent. Define a systematic review protocol.
Your process:
1. Formulate 2-3 precise research questions (PICO framework if applicable)
2. Define inclusion criteria (what papers to include)
3. Define exclusion criteria (what to filter out)
4. Propose quality assessment dimensions
5. Plan the synthesis approach (narrative, thematic, or meta-analytic)

For each proposed direction, provide:
- Research questions
- Inclusion/exclusion criteria
- Target databases and search terms
- Expected scope (estimated number of papers)

Score each on Rigor (0-1), Feasibility (0-1), and Impact (0-1).""",
        "experimental": """\
You are the Ideation Agent. Generate testable experimental hypotheses.
Your process:
1. Identify measurable claims from the literature gaps
2. Formulate null and alternative hypotheses
3. Define independent, dependent, and control variables
4. Suggest appropriate experimental methodology
5. Identify required datasets or benchmarks

For each hypothesis, provide:
- A testable statement with clear variables
- Null hypothesis
- Suggested experimental method (simulation, benchmark, A/B test, etc.)
- Required resources (datasets, compute, baselines)

Score each on Testability (0-1), Novelty (0-1), and Impact (0-1).""",
        "discussion": """\
You are the Ideation Agent. Formulate a thesis for a discussion paper.
Your process:
1. Identify tensions, contradictions, or under-examined assumptions in the field
2. Formulate a clear, debatable thesis statement
3. Identify 3-5 supporting sub-claims
4. Anticipate the strongest counterarguments
5. Consider practical implications if the thesis holds

For each proposed thesis, provide:
- A clear, falsifiable thesis statement
- 3-5 sub-claims that support the thesis
- The strongest counterargument you can think of
- Why this thesis matters (implications)

Score each on Provocation (0-1), Defensibility (0-1), and Relevance (0-1).""",
    }

    def _role_system_prompt(self, task: Task) -> str:
        brief = self.bus.get_research_brief()
        paper_type = brief.paper_type if brief else "proof"
        role_prompt = self._PROMPTS_BY_TYPE.get(paper_type, self._PROMPTS_BY_TYPE["proof"])
        return f"""\
{role_prompt}

You may use at most 2 search tool calls. After that you MUST output the final
JSON immediately — no further tool calls, no planning text.
Your final message MUST be a JSON object and nothing else:
{{"directions": [{{...}}, ...]}}
"""

    async def execute(self, task: Task) -> AgentResult:
        brief = self.bus.get_research_brief()
        if not brief:
            return self._make_result(task, False, {}, error="No ResearchBrief found on bus")

        bib = self.bus.get_bibliography()
        papers_summary = ""
        if bib and bib.papers:
            top_papers = sorted(bib.papers, key=lambda p: p.relevance_score, reverse=True)[:10]
            papers_summary = "\n".join(
                f"- {p.title} ({p.year}): {p.abstract[:200]}" for p in top_papers
            )

        open_problems = "\n".join(f"- {p}" for p in brief.open_problems[:10])
        math_objects = ", ".join(brief.key_mathematical_objects[:10])

        user_message = f"""\
Based on this literature survey, generate 5 novel research directions.

Domain: {brief.domain}
Research Question: {brief.query}

Open Problems:
{open_problems or "(none identified yet)"}

Key Mathematical Objects: {math_objects or "(none identified yet)"}

Top Papers:
{papers_summary or "(no papers yet)"}

Generate exactly 5 research directions, each as a precise mathematical conjecture with:
1. A formal hypothesis statement in LaTeX
2. Novelty score (0-1) and rationale
3. Feasibility score (0-1) and proof sketch
4. Impact score (0-1) and significance
5. Key obstacle to overcome

Return as JSON: {{"directions": [{{...}}, ...]}}
"""

        try:
            text, tokens = await self.run_agent_loop(task, user_message, max_turns=6)
            directions_data = self._parse_directions(text)

            # Convert to ResearchDirection objects and store on brief
            directions = []
            for d in directions_data:
                def _as_str(v: object) -> str:
                    """Coerce LLM value to string (it sometimes returns a dict)."""
                    if isinstance(v, dict):
                        return v.get("statement", v.get("text", str(v)))
                    return str(v) if v is not None else ""

                rd = ResearchDirection(
                    direction_id=str(uuid.uuid4()),
                    title=_as_str(d.get("title", "Research Direction")),
                    hypothesis=_as_str(d.get("hypothesis", d.get("formal_statement", ""))),
                    approach_sketch=_as_str(d.get("proof_sketch", d.get("approach", ""))),
                    novelty_score=float(d.get("novelty_score", 0.5)),
                    soundness_score=float(d.get("feasibility_score", 0.5)),
                    transformative_score=float(d.get("impact_score", 0.5)),
                )
                rd.compute_composite()
                directions.append(rd)

            brief.directions = directions
            self.bus.put_research_brief(brief)

            self.memory.log_event(
                self.role.value,
                f"Generated {len(directions)} research directions",
            )

            return self._make_result(
                task,
                success=True,
                output={"directions": [d.model_dump() for d in directions]},
                text_summary=f"Generated {len(directions)} research directions",
                token_usage=tokens,
            )
        except Exception as e:
            logger.exception("Ideation agent failed")
            return self._make_result(task, False, {}, error=str(e))

    def _parse_directions(self, text: str) -> list[dict]:
        # 1. Fenced code block: ```json ... ```
        for fence in ("```json", "```"):
            if fence in text:
                try:
                    start = text.index(fence) + len(fence)
                    end = text.index("```", start)
                    data = json.loads(text[start:end].strip())
                    if isinstance(data, dict) and "directions" in data:
                        return data["directions"]
                    if isinstance(data, list):
                        return data
                except (json.JSONDecodeError, ValueError):
                    pass

        # 2. Find the JSON object that contains a "directions" key directly,
        #    rather than grabbing the first "{" which may be inside prose text.
        search = text
        while '{"directions"' in search or '"directions"' in search:
            try:
                idx = search.index("{")
                end = search.rindex("}") + 1
                data = json.loads(search[idx:end])
                if isinstance(data, dict) and "directions" in data:
                    return data["directions"]
                if isinstance(data, list):
                    return data
            except (json.JSONDecodeError, ValueError):
                pass
            # Advance past the first "{" and retry
            next_brace = search.find("{", 1)
            if next_brace == -1:
                break
            search = search[next_brace:]

        return []
