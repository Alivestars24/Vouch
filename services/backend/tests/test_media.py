from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from vouch_backend import media
from vouch_backend.errors import ApiError
from vouch_backend.media import DockerMediaProcessor, FixtureMediaProcessor, ProcessedMedia


def metadata(**changes: object) -> dict[str, Any]:
    return {
        "mode": "decoded", "processor_version": "ffmpeg-sandbox-v1", "duration_ms": 2000,
        "width": 320, "height": 240, "frame_rate": 25.0, "audio_present": False,
        "normalized_sha256": "a" * 64,
        **changes,
    }


def test_fixture_media_is_explicit_and_does_not_invoke_docker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def deny_runtime() -> list[str]:
        pytest.fail("Fixture processing must not discover or contact Docker.")

    monkeypatch.setattr(media, "_docker_command", deny_runtime)
    result = FixtureMediaProcessor().process(b"synthetic fixture", "video/mp4")
    assert result.mode == "fixture" and result.duration_ms == 10_000
    assert result.processor_version == "fixture-media-v1"
    assert result.normalized_sha256 is None and result.image_digest is None


def test_docker_metadata_and_invocation_have_immutable_isolated_bounds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[list[str]] = []

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        commands.append(command)
        return subprocess.CompletedProcess(
            command, 0, stdout=b"sha256:" + b"b" * 64 if "image" in command else b"",
        )

    def decode(command: list[str], body: bytes, timeout: float, cleanup: object) -> bytes:
        commands.append(command)
        assert body == b"synthetic" and timeout == 30
        return json.dumps(metadata()).encode()

    monkeypatch.setattr(media, "_docker_command", lambda: ["docker", "--host", "unix:///local"])
    monkeypatch.setattr(media.subprocess, "run", run)
    monkeypatch.setattr(media, "_run_bounded", decode)
    result = DockerMediaProcessor().process(b"synthetic", "video/mp4")
    assert result.image_digest == "sha256:" + "b" * 64
    command = next(command for command in commands if "create" in command)
    assert command[command.index("--network") + 1] == "none"
    assert command[command.index("--user") + 1] == "65532:65532"
    assert command[command.index("--memory") + 1] == "512m"
    assert command[command.index("--memory-swap") + 1] == "512m"
    assert command[command.index("--cap-drop") + 1] == "ALL"
    assert command[command.index("--pull") + 1] == "never"
    assert command[command.index("--log-driver") + 1] == "none"
    assert "--read-only" in command and "--env" not in command and "--mount" not in command
    assert command[-2:] == ["sha256:" + "b" * 64, "video/mp4"]
    name = command[command.index("--name") + 1]
    assert name.startswith("vouch-media-")
    assert any(command[-3:] == ["--attach", "--interactive", name] for command in commands)
    assert commands[-1][-4:] == ["--filter", f"name=^/{name}$", "--format", "{{.ID}}"]


@pytest.mark.parametrize("stdout", [b"not json", b"{}", b'{"mode":"fixture"}'])
def test_invalid_sandbox_metadata_never_becomes_fixture_success(
    stdout: bytes, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(media, "_docker_command", lambda: ["docker"])
    monkeypatch.setattr(
        media.subprocess, "run",
        lambda command, **kwargs: subprocess.CompletedProcess(
            command, 0, stdout=b"sha256:" + b"a" * 64 if "image" in command else b"",
        ),
    )
    monkeypatch.setattr(media, "_run_bounded", lambda *args: stdout)
    with pytest.raises(ApiError) as failure:
        DockerMediaProcessor().process(b"synthetic", "video/mp4")
    assert failure.value.code == "MEDIA_VALIDATION_FAILED"


def test_missing_local_image_fails_retryably_without_remote_pull(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(media, "_docker_command", lambda: ["docker"])

    def unavailable(*args: object, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        raise subprocess.CalledProcessError(1, "docker", stderr=b"private details must not escape")

    monkeypatch.setattr(media.subprocess, "run", unavailable)
    with pytest.raises(ApiError) as failure:
        DockerMediaProcessor().process(b"synthetic", "video/mp4")
    assert failure.value.code == "MEDIA_PROCESSOR_UNAVAILABLE" and failure.value.retryable
    assert "private details" not in str(failure.value)


@pytest.mark.parametrize("endpoint", ["tcp://remote.example:2375", "ssh://user@remote.example"])
def test_remote_docker_context_is_never_given_private_media(
    endpoint: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(media.shutil, "which", lambda _: "docker")
    monkeypatch.setattr(
        media.subprocess, "run",
        lambda *args, **kwargs: subprocess.CompletedProcess([], 0, stdout=endpoint.encode()),
    )
    with pytest.raises(ApiError) as failure:
        media._docker_command()
    assert failure.value.code == "MEDIA_PROCESSOR_UNAVAILABLE"


@pytest.mark.parametrize(
    "code,script,timeout",
    [
        ("MEDIA_VALIDATION_FAILED", "import sys; sys.stdout.write('x'*20000)", 2.0),
        ("MEDIA_VALIDATION_TIMEOUT", "import time; time.sleep(5)", 0.05),
    ],
)
def test_watchdog_and_stdout_are_bounded(code: str, script: str, timeout: float) -> None:
    cleaned = []
    with pytest.raises(ApiError) as failure:
        media._run_bounded(
            [sys.executable, "-c", script], b"", timeout, lambda: cleaned.append(True)
        )
    assert failure.value.code == code
    if code == "MEDIA_VALIDATION_TIMEOUT":
        assert cleaned == [True]


def test_decoded_metadata_cannot_claim_unsupported_mapping_or_missing_provenance() -> None:
    with pytest.raises(ValidationError):
        ProcessedMedia.model_validate(metadata())  # Immutable image identity is required.
    with pytest.raises(ValidationError):
        ProcessedMedia.model_validate(
            metadata(
                image_digest="sha256:" + "a" * 64, source_time_mapping={"source_origin_ms": 100}
            )
        )


@pytest.mark.skipif(os.getenv("VOUCH_TEST_MEDIA") != "1", reason="Opt-in local Docker media smoke.")
@pytest.mark.parametrize("extension,audio", [("mp4", False), ("webm", False), ("mp4", True)])
def test_real_sandbox_fully_decodes_trusted_synthetic_clip(
    tmp_path: Path, extension: str, audio: bool,
) -> None:
    ffmpeg = shutil.which("ffmpeg")
    assert ffmpeg, "Install ffmpeg to generate the trusted local synthetic smoke fixture."
    path = tmp_path / f"synthetic.{extension}"
    codec = ["-c:v", "libx264", "-pix_fmt", "yuv420p"] if extension == "mp4" else [
        "-c:v", "libvpx-vp9", "-pix_fmt", "yuv420p"
    ]
    subprocess.run(
        [ffmpeg, "-nostdin", "-v", "error", "-f", "lavfi", "-i", "color=c=blue:s=320x240:r=25",
         *(["-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000"] if audio else []),
         "-t", "2", *codec, *(["-c:a", "aac"] if audio else ["-an"]), str(path)],
        check=True, capture_output=True, timeout=20,
    )
    body = path.read_bytes()
    result = DockerMediaProcessor().process(body, f"video/{extension}")
    assert result.mode == "decoded" and result.duration_ms == 2000
    assert result.width == 320 and result.height == 240 and result.frame_rate == 25
    assert result.audio_present is audio and result.normalized_sha256
    assert result.image_digest and result.source_time_mapping.source_origin_ms == 0
    with pytest.raises(ApiError) as failure:
        DockerMediaProcessor().process(body[:24], f"video/{extension}")
    assert failure.value.code == "MEDIA_VALIDATION_FAILED"
