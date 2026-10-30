from __future__ import annotations

import io
import wave

import httpx
import pytest

from vouch_backend.meta_voice import transcribe_wav
from vouch_backend.providers import ProviderError

KEY = "test-provider-credential-123456"


def wav() -> bytes:
    data = io.BytesIO()
    with wave.open(data, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"\0\0" * 16000)
    return data.getvalue()


def test_voice_uses_multipart_and_validates_turns() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/asr/transcribe")
        assert "multipart/form-data" in request.headers["content-type"]
        return httpx.Response(
            200,
            json={
                "audioDurationMs": 1000,
                "turns": [
                    {
                        "turnId": 1,
                        "startMs": 100,
                        "endMs": 900,
                        "transcript": "Hello",
                        "speaker": "A",
                    }
                ],
            },
        )

    result = transcribe_wav(KEY, wav(), transport=httpx.MockTransport(handler))
    assert result.turns[0].transcript == "Hello"
    assert result.duration_ms == 1000


def test_invalid_audio_never_reaches_provider() -> None:
    with pytest.raises(ValueError):
        transcribe_wav(KEY, b"not a wav")


def test_invalid_timestamps_fail_closed() -> None:
    transport = httpx.MockTransport(
        lambda _: httpx.Response(
            200,
            json={
                "audioDurationMs": 1000,
                "turns": [{"turnId": 1, "startMs": 900, "endMs": 100, "transcript": "Hello"}],
            },
        )
    )
    with pytest.raises(ProviderError) as error:
        transcribe_wav(KEY, wav(), transport=transport)
    assert error.value.code == "INVALID_PROVIDER_OUTPUT"


def test_voice_timeout_keeps_outcome_unknown() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("private details", request=request)

    with pytest.raises(ProviderError) as error:
        transcribe_wav(KEY, wav(), transport=httpx.MockTransport(handler))
    assert error.value.code == "OUTCOME_UNKNOWN"
    assert error.value.retryable is False
