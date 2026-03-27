"""Shared Pydantic v2 models — the lingua franca of all EurekaLab modules."""

from eurekalab.types.agents import AgentMessage, AgentResult, AgentRole
from eurekalab.types.artifacts import (
    Bibliography,
    Counterexample,
    ExperimentResult,
    FailedAttempt,
    LemmaNode,
    Paper,
    ProofRecord,
    ResearchBrief,
    ResearchDirection,
    TheoryState,
)
from eurekalab.types.memory import CrossRunRecord, EpisodicEntry, KnowledgeNode
from eurekalab.types.skills import SkillMeta, SkillRecord
from eurekalab.types.tasks import InputSpec, ResearchOutput, Task, TaskPipeline, TaskStatus

__all__ = [
    "AgentMessage",
    "AgentResult",
    "AgentRole",
    "Bibliography",
    "Counterexample",
    "CrossRunRecord",
    "EpisodicEntry",
    "ExperimentResult",
    "FailedAttempt",
    "InputSpec",
    "KnowledgeNode",
    "LemmaNode",
    "Paper",
    "ProofRecord",
    "ResearchBrief",
    "ResearchDirection",
    "ResearchOutput",
    "SkillMeta",
    "SkillRecord",
    "Task",
    "TaskPipeline",
    "TaskStatus",
    "TheoryState",
]
