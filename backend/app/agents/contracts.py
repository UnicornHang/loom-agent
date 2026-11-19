"""Typed handoff and visible execution contracts shared by future Agent nodes.

These models do not execute an LLM. Runtime, persistence, and authorization are
added with the workflow engine in the next implementation stage.
"""

from enum import StrEnum

from pydantic import BaseModel, Field


class AgentKind(StrEnum):
    DISCOVERY = "discovery"
    ANALYSIS = "analysis"
    ARTICLE = "article"
    ARTWORK = "artwork"
    SCRIPT = "script"
    STORYBOARD = "storyboard"
    REVIEW = "review"


class AgentEventKind(StrEnum):
    STARTED = "started"
    PLAN_SUMMARY = "plan_summary"
    EVIDENCE_FOUND = "evidence_found"
    TOOL_STARTED = "tool_started"
    TOOL_FINISHED = "tool_finished"
    DRAFT_CREATED = "draft_created"
    SELF_CHECK = "self_check"
    REVISION = "revision"
    NEEDS_INPUT = "needs_input"
    COMPLETED = "completed"
    FAILED = "failed"


class ArtifactRef(BaseModel):
    artifact_version_id: str
    content_hash: str


class AgentHandoff(BaseModel):
    handoff_id: str
    workflow_id: str
    from_agent: AgentKind
    to_agent: AgentKind
    input_artifacts: list[ArtifactRef] = Field(default_factory=list)
    product_snapshot_id: str | None = None
    config_version_id: str


class VisibleAgentEvent(BaseModel):
    workflow_id: str
    agent_run_id: str
    sequence: int = Field(ge=1)
    agent: AgentKind
    kind: AgentEventKind
    title: str
    summary: str
    evidence_refs: list[str] = Field(default_factory=list)
    artifact_version_id: str | None = None
