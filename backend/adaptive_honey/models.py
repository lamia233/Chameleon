from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class VirtualFile(BaseModel):
    path: str
    content: str = ""
    owner: str = "root"
    mode: str = "644"
    is_dir: bool = False
    modified_at: str = Field(default_factory=now_iso)


class Persona(BaseModel):
    id: str
    label: str
    hostname: str
    os_release: str
    kernel: str
    architecture: str = "x86_64"
    description: str


class ProfileDimension(BaseModel):
    label: str
    confidence: float
    probabilities: dict[str, float]
    evidence: list[str] = Field(default_factory=list)


class BehaviorProfile(BaseModel):
    automation: ProfileDimension
    sophistication: ProfileDimension
    objective: ProfileDimension


class TechniqueEvidence(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    technique_id: str
    name: str
    confidence: float
    status: Literal["attempted", "simulated_success", "observed_artifact"]
    explanation: str
    event_ids: list[str]
    attack_version: str = "Enterprise ATT&CK v16"
    review_status: Literal["pending", "confirmed", "rejected"] = "pending"


class Indicator(BaseModel):
    kind: str
    value: str
    event_id: str


class DeceptionDecision(BaseModel):
    action: str
    reason: str
    eligible_actions: list[str]
    applied: bool
    timestamp: str = Field(default_factory=now_iso)


class ShellResponse(BaseModel):
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    proposed_state_changes: list[dict[str, Any]] = Field(default_factory=list)


class SessionEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    session_id: str
    sequence: int
    command: str
    response: ShellResponse
    cwd_before: str
    cwd_after: str
    timestamp: str = Field(default_factory=now_iso)
    latency_ms: float = 0
    state_diff: list[dict[str, Any]] = Field(default_factory=list)
    deception: DeceptionDecision | None = None


class SessionState(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    persona: Persona
    username: str = "deploy"
    uid: int = 1001
    gid: int = 1001
    cwd: str = "/home/deploy"
    env: dict[str, str] = Field(default_factory=lambda: {"SHELL": "/bin/bash", "LANG": "en_US.UTF-8", "USER": "deploy"})
    files: dict[str, VirtualFile]
    processes: list[dict[str, Any]] = Field(default_factory=list)
    services: dict[str, str] = Field(default_factory=dict)
    history: list[str] = Field(default_factory=list)
    exposed_artifacts: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=now_iso)
    status: Literal["active", "closed"] = "active"
    source_ip: str = "203.0.113.42"


class SessionSummary(BaseModel):
    id: str
    hostname: str
    username: str
    source_ip: str
    status: str
    created_at: str
    command_count: int
    profile: BehaviorProfile
    techniques: list[TechniqueEvidence]


class CreateSessionRequest(BaseModel):
    persona_id: Literal["development", "backup"] = "development"
    source_ip: str = "203.0.113.42"
    username: str = "deploy"


class CommandRequest(BaseModel):
    command: str = Field(min_length=1, max_length=2048)

