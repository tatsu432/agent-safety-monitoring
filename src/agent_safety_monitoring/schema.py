"""Monitor-facing evidence is structurally separate from evaluation metadata."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Segment(StrictModel):
    id: str
    role: Literal["user", "assistant", "tool"]
    kind: Literal["text", "tool_call", "tool_result"]
    text: str
    source_message: int
    source_start: int = 0
    source_end: int
    interaction: int

    @model_validator(mode="after")
    def exact_span(self):
        if self.source_end - self.source_start != len(self.text):
            raise ValueError("Segment span length differs from exact text")
        return self


class CanonicalTrajectory(StrictModel):
    id: str  # opaque ID; contains no class, source filename, or split
    task: str
    segments: list[Segment]

    @model_validator(mode="after")
    def unique_steps(self):
        if len({s.id for s in self.segments}) != len(self.segments):
            raise ValueError("Duplicate segment identifiers")
        return self


class EvaluationRecord(StrictModel):
    trajectory_id: str
    task_id: str
    assignment: Literal["benign", "attack"]
    outcome: Literal["success", "failure", "ungraded", "not_applicable"]
    objective: str | None = None
    source_file: str
    source_sha256: str
    sample_id: str
    provenance: dict
    split: Literal["development", "calibration", "test", "excluded"] = "excluded"
    exclusion: str | None = None


class Judgment(StrictModel):
    score: StrictInt = Field(ge=1, le=5)
    explanation: str = Field(min_length=1, max_length=4000)
    citations: list[str]


class Quotation(StrictModel):
    step: str
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    text: str = Field(min_length=1)


class Extraction(StrictModel):
    quotes: list[Quotation]


class Summary(Judgment):
    summary: str = Field(min_length=1)


class Usage(StrictModel):
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int | None = None


class CallRecord(StrictModel):
    key: str
    stage: str
    attempt: int
    started: str
    completed: str
    latency_seconds: float
    usage: Usage = Field(default_factory=Usage)
    cached: bool = False
    response: str | None = None
    error: str | None = None
    finish_reason: str | None = None


class MonitoringResult(StrictModel):
    trajectory_id: str
    method: str
    config_hash: str
    status: Literal["valid", "invalid", "context_overflow", "error"]
    score: float | None = None
    explanation: str = ""
    citations: list[str] = Field(default_factory=list)
    artifacts: list[dict] = Field(default_factory=list)
    calls: list[CallRecord] = Field(default_factory=list)
    error: str | None = None

    @model_validator(mode="after")
    def score_status(self):
        if self.status == "valid" and (self.score is None or not 1 <= self.score <= 5):
            raise ValueError("Valid result requires a score in [1,5]")
        if self.status != "valid" and self.score is not None:
            raise ValueError("Failed results cannot have fabricated scores")
        return self
