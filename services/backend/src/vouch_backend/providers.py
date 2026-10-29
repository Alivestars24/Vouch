from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProviderError(Exception):
    def __init__(self, code: str, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.code = code
        self.safe_message = message
        self.retryable = retryable


class EvidenceResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    modality: Literal["speech", "visual", "track"]
    complete: bool
    start_ms: int | None = None
    end_ms: int | None = None
    precision: Literal["turn", "sampled_frame", "interval"]
    description: str
    missing_intervals: list[tuple[int, int]] = Field(default_factory=list)


class FindingResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: str
    rule_version: str
    severity: Literal["critical", "major", "minor"]
    evidence_indexes: list[int]
    start_ms: int | None = None
    end_ms: int | None = None
    evidence_text: str
    uncertainty: str
    suggested_action: str


@dataclass(frozen=True, slots=True)
class ProviderContext:
    organization_id: UUID
    analysis_id: UUID
    duration_ms: int
    caption: str
    scenario: str
    attempt: int


class Transcriber(Protocol):
    def transcribe(self, context: ProviderContext) -> EvidenceResult: ...


class Segmenter(Protocol):
    def segment(self, context: ProviderContext) -> EvidenceResult: ...


class Reasoner(Protocol):
    def evaluate(
        self, context: ProviderContext, evidence: list[EvidenceResult]
    ) -> list[FindingResult]: ...


class TryOnProvider(Protocol):
    def create_preview(self, *_args: object, **_kwargs: object) -> object: ...


class CampaignDossier(Protocol):
    def synthesize(self, *_args: object, **_kwargs: object) -> object: ...


class FixtureTranscriber:
    def transcribe(self, context: ProviderContext) -> EvidenceResult:
        if context.scenario == "provider_down":
            raise ProviderError(
                "PROVIDER_UNAVAILABLE", "Fixture Voice provider is unavailable.", retryable=True
            )
        if context.scenario == "transient_then_success" and context.attempt == 1:
            raise ProviderError(
                "PROVIDER_UNAVAILABLE", "Fixture Voice provider failed transiently.", retryable=True
            )
        if context.scenario == "partial_voice":
            opening_end = min(1500, context.duration_ms)
            has_readable_turn = opening_end < context.duration_ms
            return EvidenceResult(
                modality="speech",
                complete=False,
                start_ms=opening_end if has_readable_turn else None,
                end_ms=context.duration_ms if has_readable_turn else None,
                precision="turn",
                description=(
                    "Synthetic speech after 00:01.500 was readable; the opening was inaudible."
                    if has_readable_turn
                    else "Synthetic speech evidence is unavailable throughout this short clip."
                ),
                missing_intervals=[(0, opening_end)],
            )
        return EvidenceResult(
            modality="speech",
            complete=True,
            start_ms=0,
            end_ms=min(4000, context.duration_ms),
            precision="turn",
            description="Creator introduces the product; disclosure wording is ambiguous.",
        )


class FixtureSegmenter:
    def segment(self, context: ProviderContext) -> EvidenceResult:
        return EvidenceResult(
            modality="visual",
            complete=True,
            start_ms=min(1000, context.duration_ms - 1),
            end_ms=min(5000, context.duration_ms),
            precision="sampled_frame",
            description="Eyewear appears in sampled frames; exact SKU identity is not asserted.",
        )


class FixtureReasoner:
    def evaluate(
        self, context: ProviderContext, evidence: list[EvidenceResult]
    ) -> list[FindingResult]:
        if context.scenario == "invalid_output":
            raise ProviderError(
                "INVALID_PROVIDER_OUTPUT",
                "Fixture Reasoner returned output that failed schema validation.",
                retryable=False,
            )
        if context.scenario == "clean":
            return []
        speech = evidence[0]
        if speech.start_ms is None or speech.end_ms is None:
            # Missing speech is unknown, never a fabricated statement about its contents.
            return []
        return [
            FindingResult(
                rule_id="DISCLOSURE_AUDIO",
                rule_version="1.0",
                severity="major",
                evidence_indexes=[0],
                start_ms=speech.start_ms,
                end_ms=min(speech.start_ms + 4000, speech.end_ms),
                evidence_text="The spoken relationship disclosure is ambiguous.",
                uncertainty="Fixture observation; a reviewer must inspect the cited turn.",
                suggested_action="Use an explicit spoken sponsorship disclosure at the opening.",
            )
        ]


@dataclass(frozen=True, slots=True)
class FixtureProviders:
    transcriber: Transcriber = field(default_factory=FixtureTranscriber)
    segmenter: Segmenter = field(default_factory=FixtureSegmenter)
    reasoner: Reasoner = field(default_factory=FixtureReasoner)
