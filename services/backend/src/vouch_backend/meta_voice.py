"""Bounded Meta transcription transport; not connected to campaign execution."""

from __future__ import annotations

import io
import json
import wave
from dataclasses import dataclass, field
from uuid import uuid4

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .meta_api import MAX_RESPONSE_BYTES, META_API_BASE_URL, MetaModelClient
from .providers import ProviderError


class VoiceTurn(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    turnId: int = Field(ge=0)
    startMs: int = Field(ge=0)
    endMs: int = Field(ge=0)
    transcript: str = Field(max_length=8000, repr=False)
    speaker: str | None = Field(default=None, max_length=32)


class VoiceResponse(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    audioDurationMs: int = Field(ge=0)
    turns: list[VoiceTurn] = Field(max_length=2000)


@dataclass(frozen=True, slots=True)
class TranscriptionResult:
    turns: tuple[VoiceTurn, ...] = field(repr=False)
    duration_ms: int


def transcribe_wav(
    api_key: str, wav_bytes: bytes, *, transport: httpx.BaseTransport | None = None
) -> TranscriptionResult:
    """Send mono PCM WAV only after the caller establishes scope, consent and paid budget."""
    MetaModelClient(api_key)
    if not 44 <= len(wav_bytes) <= 30_000_000:
        raise ValueError("WAV size is outside the accepted range.")
    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as audio:
            rate = audio.getframerate()
            if (
                audio.getnchannels() != 1
                or audio.getsampwidth() != 2
                or rate not in {16000, 24000}
                or audio.getcomptype() != "NONE"
            ):
                raise ValueError("Expected mono 16-bit PCM at 16 or 24 kHz.")
            frames = audio.getnframes()
            if frames <= 0 or frames > rate * 600:
                raise ValueError("WAV duration is outside the accepted range.")
            duration_ms = (frames * 1000 + rate - 1) // rate
            if len(audio.readframes(frames)) != frames * 2:
                raise ValueError("WAV payload is truncated.")
    except (wave.Error, EOFError) as error:
        raise ValueError("Invalid WAV file.") from error

    request = {"mode": "DIARIZATION", "model": "muse-voice-transcribe-1.0", "audioEncoding": "WAV"}
    try:
        with (
            httpx.Client(
                timeout=90, follow_redirects=False, trust_env=False, transport=transport
            ) as client,
            client.stream(
                "POST",
                f"{META_API_BASE_URL}/asr/transcribe",
                params={"sessionId": str(uuid4())},
                headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
                files={
                    "request": (None, json.dumps(request), "application/json"),
                    "audio": ("audio.wav", wav_bytes, "audio/wav"),
                },
            ) as response,
        ):
            MetaModelClient._raise_for_inference_status(response.status_code)
            raw = bytearray()
            for chunk in response.iter_bytes():
                raw.extend(chunk)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise ProviderError(
                        "INVALID_PROVIDER_OUTPUT", "Voice response too large.", retryable=False
                    )
    except httpx.ConnectError:
        raise ProviderError(
            "PROVIDER_UNAVAILABLE", "Meta could not be reached.", retryable=True
        ) from None
    except httpx.HTTPError:
        raise ProviderError(
            "OUTCOME_UNKNOWN", "Meta request outcome is unknown.", retryable=False
        ) from None
    try:
        parsed = VoiceResponse.model_validate_json(raw)
        if abs(parsed.audioDurationMs - duration_ms) > 1000:
            raise ValueError("duration mismatch")
        if any(
            turn.endMs < turn.startMs or turn.endMs > duration_ms + 1000 for turn in parsed.turns
        ):
            raise ValueError("invalid turn bounds")
        return TranscriptionResult(tuple(parsed.turns), duration_ms)
    except (ValueError, ValidationError):
        raise ProviderError(
            "INVALID_PROVIDER_OUTPUT", "Voice response failed validation.", retryable=False
        ) from None
