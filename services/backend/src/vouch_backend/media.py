"""Independent media validation modes; decoded media never implies live model evidence."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import time
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Protocol, Self
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from .errors import ApiError

if TYPE_CHECKING:
    from .config import Settings

MAX_INPUT_BYTES = 5_000_000
MAX_OUTPUT_BYTES = 16_384


@dataclass(frozen=True, slots=True)
class PreparedMedia:
    name: str
    image_digest: str


class SourceTimeMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["identity"] = "identity"
    source_origin_ms: Literal[0] = 0
    normalized_origin_ms: Literal[0] = 0
    precision_ms: Literal[1] = 1


class ProcessedMedia(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    mode: Literal["fixture", "decoded"]
    processor_version: str = Field(min_length=1, max_length=80)
    duration_ms: int = Field(gt=0, le=30_000)
    width: int | None = Field(default=None, gt=0, le=1920)
    height: int | None = Field(default=None, gt=0, le=1920)
    frame_rate: float | None = Field(default=None, gt=0, le=60)
    audio_present: bool | None = None
    normalized_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    source_time_mapping: SourceTimeMapping = Field(default_factory=SourceTimeMapping)
    image_digest: str | None = Field(default=None, pattern=r"^sha256:[a-f0-9]{64}$")

    @model_validator(mode="after")
    def complete_decoded_metadata(self) -> Self:
        if self.mode == "decoded" and (
            self.width is None or self.height is None or self.frame_rate is None
            or self.audio_present is None or self.normalized_sha256 is None
            or self.image_digest is None
            or self.width * self.height > 1920 * 1080
        ):
            raise ValueError("Decoded metadata must have complete, bounded provenance.")
        return self


class MediaProcessor(Protocol):
    @property
    def mode(self) -> str: ...

    @property
    def processor_version(self) -> str: ...

    def prepare(
        self, content_type: str, organization_id: UUID, asset_id: UUID,
    ) -> PreparedMedia | None: ...

    def process(
        self, body: bytes, content_type: str, prepared: PreparedMedia | None = None,
    ) -> ProcessedMedia: ...


class FixtureMediaProcessor:
    mode = "fixture"
    processor_version = "fixture-media-v1"

    def prepare(
        self, content_type: str, organization_id: UUID, asset_id: UUID,
    ) -> None:
        return None

    def process(
        self, body: bytes, content_type: str, prepared: PreparedMedia | None = None,
    ) -> ProcessedMedia:
        return ProcessedMedia(
            mode="fixture", processor_version=self.processor_version, duration_ms=10_000
        )


def _failure(code: str = "MEDIA_VALIDATION_FAILED") -> ApiError:
    return ApiError(422, code, "Media could not be safely decoded within the supported limits.")


def _unavailable() -> ApiError:
    return ApiError(
        503, "MEDIA_PROCESSOR_UNAVAILABLE", "The local media processor is unavailable.", True
    )


def _docker_command() -> list[str]:
    docker = shutil.which("docker")
    if not docker and os.name == "nt":
        candidate = Path("C:/Program Files/Docker/Docker/resources/bin/docker.exe")
        docker = str(candidate) if candidate.is_file() else None
    if docker is None:
        raise _unavailable()
    try:
        context = subprocess.run(
            [docker, "context", "inspect", "--format", "{{.Endpoints.docker.Host}}"],
            capture_output=True, timeout=5, check=True,
        ).stdout.decode("utf-8").strip()
    except (OSError, subprocess.SubprocessError, UnicodeError):
        raise _unavailable() from None
    if not (
        context == "unix:///var/run/docker.sock"
        or context in {
            "npipe:////./pipe/dockerDesktopLinuxEngine", "npipe:////./pipe/docker_engine"
        }
    ):
        # Never ship private bytes to a remote DOCKER_HOST/context selected in the environment.
        raise _unavailable()
    return [docker, "--host", context]


def _run_bounded(
    command: list[str], body: bytes, timeout: float, cleanup: Callable[[], None]
) -> bytes:
    """Bound untrusted stdout and input; the caller owns exact-container cleanup."""
    process = subprocess.Popen(
        command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
    )
    assert process.stdin is not None and process.stdout is not None
    output: list[bytes] = []
    overflow = threading.Event()

    def write_input() -> None:
        try:
            assert process.stdin is not None
            process.stdin.write(body)
            process.stdin.close()
        except (OSError, ValueError):
            pass

    def read_output() -> None:
        assert process.stdout is not None
        captured = process.stdout.read(MAX_OUTPUT_BYTES + 1)
        output.append(captured)
        if len(captured) > MAX_OUTPUT_BYTES:
            overflow.set()

    writer = threading.Thread(target=write_input, daemon=True)
    reader = threading.Thread(target=read_output, daemon=True)
    writer.start()
    reader.start()
    deadline = time.monotonic() + timeout
    try:
        while process.poll() is None:
            if overflow.is_set():
                raise _failure()
            if time.monotonic() >= deadline:
                raise _failure("MEDIA_VALIDATION_TIMEOUT")
            time.sleep(0.02)
        reader.join(timeout=1)
        if reader.is_alive() or overflow.is_set() or not output:
            raise _failure()
        if process.returncode in {125, 126, 127}:
            raise _unavailable()
        if process.returncode != 0:
            if output[0].strip() == b'{"error":"MEDIA_VALIDATION_TIMEOUT"}':
                raise _failure("MEDIA_VALIDATION_TIMEOUT")
            raise _failure()
        return output[0]
    finally:
        if process.poll() is None:
            with suppress(ApiError):
                cleanup()
            process.kill()
            process.wait(timeout=5)
        writer.join(timeout=1)
        reader.join(timeout=1)
        process.stdin.close()
        process.stdout.close()


def remove_sandbox_container(name: str, organization_id: UUID) -> None:
    """Confirm exact tenant-scoped absence; elapsed time never substitutes for erasure."""
    if not re.fullmatch(
        rf"vouch-media-{organization_id.hex}-[a-f0-9]{{32}}-[a-f0-9]{{32}}", name,
    ):
        raise _unavailable()
    docker = _docker_command()

    def exists() -> bool:
        result = subprocess.run(
            [*docker, "ps", "--all", "--filter", f"name=^/{name}$", "--format", "{{.ID}}"],
            capture_output=True, timeout=5, check=True,
        )
        return bool(result.stdout.strip())

    try:
        if exists():
            subprocess.run(
                [*docker, "rm", "--force", name],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5, check=True,
            )
        if exists():
            raise _unavailable()
    except (OSError, subprocess.SubprocessError):
        raise _unavailable() from None


class DockerMediaProcessor:
    mode = "decoded"
    processor_version = "ffmpeg-sandbox-v1"

    def __init__(
        self, image: str = "vouch-media-sandbox:local", timeout_seconds: float = 30
    ) -> None:
        if not re.fullmatch(r"[a-z0-9][a-zA-Z0-9_./:@-]{0,250}", image):
            raise ValueError("Use an explicit local media image reference.")
        if not 0 < timeout_seconds <= 30:
            raise ValueError("Media validation timeout must be positive and at most 30 seconds.")
        self.image = image
        self.timeout_seconds = timeout_seconds

    def prepare(
        self, content_type: str, organization_id: UUID, asset_id: UUID,
    ) -> PreparedMedia:
        if content_type not in {"video/mp4", "video/webm"}:
            raise _failure()
        docker = _docker_command()
        try:
            digest = subprocess.run(
                [*docker, "image", "inspect", "--format", "{{.Id}}", self.image],
                capture_output=True, timeout=5, check=True,
            ).stdout.decode("ascii").strip()
        except (OSError, subprocess.SubprocessError, UnicodeError):
            raise _unavailable() from None
        if not re.fullmatch(r"sha256:[a-f0-9]{64}", digest):
            raise _unavailable()
        name = f"vouch-media-{organization_id.hex}-{asset_id.hex}-{uuid4().hex}"
        command = [
            *docker, "create", "--interactive", "--pull", "never", "--name", name,
            "--network", "none", "--read-only", "--user", "65532:65532",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges=true",
            "--cpus", "1", "--memory", "512m", "--memory-swap", "512m", "--pids-limit", "32",
            "--tmpfs", "/work:rw,noexec,nosuid,nodev,size=64m,uid=65532,gid=65532,mode=0700",
            "--log-driver", "none", "--ulimit", "fsize=33554432:33554432", digest, content_type,
        ]
        try:
            subprocess.run(command, capture_output=True, timeout=5, check=True)
        except (OSError, subprocess.SubprocessError):
            with suppress(ApiError):
                remove_sandbox_container(name, organization_id)
            raise _unavailable() from None
        return PreparedMedia(name, digest)

    def process(
        self, body: bytes, content_type: str, prepared: PreparedMedia | None = None,
    ) -> ProcessedMedia:
        if not 0 < len(body) <= MAX_INPUT_BYTES or content_type not in {"video/mp4", "video/webm"}:
            raise _failure()
        # The API always supplies a durably registered empty container. Direct smoke tests
        # may prepare their own synthetic, zero-tenant container through this convenience path.
        plan = prepared or self.prepare(content_type, UUID(int=0), uuid4())
        organization_id = UUID(plan.name.split("-")[2])
        docker = _docker_command()

        def cleanup() -> None:
            remove_sandbox_container(plan.name, organization_id)

        try:
            raw = _run_bounded(
                [*docker, "start", "--attach", "--interactive", plan.name], body,
                self.timeout_seconds, cleanup,
            )
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                raise _failure()
            payload["image_digest"] = plan.image_digest
            result = ProcessedMedia.model_validate(payload)
            if result.mode != "decoded" or result.processor_version != self.processor_version:
                raise _failure()
            return result
        except (OSError, subprocess.SubprocessError):
            raise _unavailable() from None
        except (ValueError, ValidationError):
            raise _failure() from None
        finally:
            cleanup()


def create_media_processor(settings: Settings) -> MediaProcessor:
    if settings.media_mode == "fixture":
        return FixtureMediaProcessor()
    return DockerMediaProcessor(settings.media_image)
