"""Trusted wrapper; untrusted media and normalized bytes exist only in bounded container tmpfs."""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Any

ROOT = Path("/work")
MAX_BYTES = 5_000_000
MAX_NORMALIZED_BYTES = 32 * 1024 * 1024
TIME_TOLERANCE = Decimal("0.0011")  # Matroska's millisecond time base may alternate frame steps.


def run(*arguments: str) -> bytes:
    result = subprocess.run(
        arguments, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, check=True, timeout=24,
    )
    if len(result.stdout) > 2_000_000:
        raise ValueError("metadata limit")
    return result.stdout


def probe(path: Path) -> dict[str, Any]:
    return json.loads(run(
        "ffprobe", "-v", "error", "-protocol_whitelist", "file,pipe",
        "-show_entries",
        "format=format_name,duration:stream=codec_type,codec_name,width,height,"
        "avg_frame_rate,r_frame_rate,start_time,sample_rate",
        "-of", "json", str(path),
    ))


def frames(path: Path, selector: str) -> list[dict[str, Any]]:
    payload = json.loads(run(
        "ffprobe", "-v", "error", "-threads", "1", "-protocol_whitelist", "file,pipe",
        "-select_streams", selector, "-show_frames", "-show_entries",
        "frame=best_effort_timestamp_time,pkt_duration_time,nb_samples,width,height",
        "-of", "json", str(path),
    ))
    result = payload["frames"]
    if not isinstance(result, list) or not result or len(result) > 4000:
        raise ValueError("frame limit")
    return result


def video_timeline(
    values: list[dict[str, Any]], rate: Fraction, width: int, height: int
) -> tuple[list[Decimal], Decimal]:
    step = Decimal(rate.denominator) / Decimal(rate.numerator)
    timestamps = [Decimal(item["best_effort_timestamp_time"]) for item in values]
    if timestamps[0] != 0:
        raise ValueError("unsupported presentation offset")
    for index, item in enumerate(values):
        if int(item["width"]) != width or int(item["height"]) != height:
            raise ValueError("changing dimensions")
        if index and (
            timestamps[index] <= timestamps[index - 1]
            or abs(timestamps[index] - timestamps[index - 1] - step) > TIME_TOLERANCE
        ):
            raise ValueError("non-monotonic or discontinuous presentation clock")
    duration = timestamps[-1] + step
    if not 0 < duration <= 30:
        raise ValueError("duration limit")
    return timestamps, duration


def audio_timeline(values: list[dict[str, Any]], sample_rate: int) -> Decimal:
    if sample_rate <= 0 or sample_rate > 192_000:
        raise ValueError("sample rate limit")
    end = Decimal(0)
    for item in values:
        start = Decimal(item["best_effort_timestamp_time"])
        if abs(start - end) > TIME_TOLERANCE:
            raise ValueError("unsupported audio offset or discontinuity")
        count = int(item["nb_samples"])
        if not 0 < count <= 65536:
            raise ValueError("audio frame limit")
        end = start + Decimal(count) / Decimal(sample_rate)
    if not 0 < end <= Decimal("30.1"):
        raise ValueError("audio duration limit")
    return end


def process(body: bytes, content_type: str) -> dict[str, Any]:
    if not body or len(body) > MAX_BYTES or content_type not in {"video/mp4", "video/webm"}:
        raise ValueError("input limit")
    source = ROOT / "source"
    source.write_bytes(body)
    information = probe(source)
    format_name = str(information["format"]["format_name"])
    if (content_type == "video/mp4" and "mp4" not in format_name) or (
        content_type == "video/webm" and "webm" not in format_name
    ):
        raise ValueError("container mismatch")
    streams = information["streams"]
    videos = [item for item in streams if item.get("codec_type") == "video"]
    audio = [item for item in streams if item.get("codec_type") == "audio"]
    if len(videos) != 1 or len(audio) > 1 or len(videos) + len(audio) != len(streams):
        raise ValueError("unsupported streams")
    video = videos[0]
    if video["codec_name"] not in {"h264", "mpeg4", "vp8", "vp9", "av1"}:
        raise ValueError("unsupported video codec")
    if audio and audio[0]["codec_name"] not in {"aac", "opus", "vorbis", "mp3"}:
        raise ValueError("unsupported audio codec")
    width, height = int(video["width"]), int(video["height"])
    rate = Fraction(video["avg_frame_rate"])
    if not (
        0 < width <= 1920 and 0 < height <= 1920 and width * height <= 1920 * 1080
        and 0 < rate <= 60 and rate == Fraction(video["r_frame_rate"])
        and width % 2 == 0 and height % 2 == 0
    ):
        raise ValueError("video envelope")
    original_frames, duration = video_timeline(frames(source, "v:0"), rate, width, height)
    reported = Decimal(information["format"]["duration"])
    if not 0 < reported <= Decimal("30.1") or abs(reported - duration) > Decimal("0.1"):
        raise ValueError("ambiguous duration")
    audio_duration = (
        audio_timeline(frames(source, "a:0"), int(audio[0]["sample_rate"])) if audio else None
    )
    if audio_duration is not None and abs(audio_duration - duration) > Decimal("0.1"):
        raise ValueError("unaligned audio and video")
    normalized = ROOT / "normalized.nut"
    run(
        "ffmpeg", "-nostdin", "-v", "error", "-xerror", "-err_detect", "explode",
        "-threads", "1", "-protocol_whitelist", "file,pipe", "-copyts", "-start_at_zero",
        "-i", str(source), "-map", "0:v:0", "-map", "0:a:0?", "-sn", "-dn",
        "-map_metadata", "-1", "-map_chapters", "-1", "-threads", "1",
        "-filter_threads", "1", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
        "-pix_fmt", "yuv420p", "-fps_mode", "passthrough", "-c:a", "pcm_s16le",
        "-fflags", "+bitexact", "-flags:v", "+bitexact", "-flags:a", "+bitexact",
        "-f", "nut", str(normalized),
    )
    if not 0 < normalized.stat().st_size <= MAX_NORMALIZED_BYTES:
        raise ValueError("normalization size limit")
    mapped_frames, mapped_duration = video_timeline(
        frames(normalized, "v:0"), rate, width, height
    )
    if len(mapped_frames) != len(original_frames) or abs(mapped_duration - duration) > TIME_TOLERANCE:
        raise ValueError("normalization changed clock")
    if any(abs(before - after) > TIME_TOLERANCE for before, after in zip(
        original_frames, mapped_frames, strict=True
    )):
        raise ValueError("normalization changed presentation timestamps")
    if audio_duration is not None:
        mapped_audio = audio_timeline(
            frames(normalized, "a:0"), int(audio[0]["sample_rate"])
        )
        if abs(mapped_audio - audio_duration) > TIME_TOLERANCE:
            raise ValueError("normalization changed audio timing")
    digest = hashlib.file_digest(normalized.open("rb"), "sha256").hexdigest()
    return {
        "mode": "decoded", "processor_version": "ffmpeg-sandbox-v1",
        "duration_ms": math.ceil(duration * 1000), "width": width, "height": height,
        "frame_rate": float(rate), "audio_present": bool(audio), "normalized_sha256": digest,
        "source_time_mapping": {
            "kind": "identity", "source_origin_ms": 0, "normalized_origin_ms": 0,
            "precision_ms": 1,
        },
    }


def main() -> None:
    try:
        result = process(sys.stdin.buffer.read(MAX_BYTES + 1), sys.argv[1])
    except subprocess.TimeoutExpired:
        print('{"error":"MEDIA_VALIDATION_TIMEOUT"}')
        raise SystemExit(3) from None
    except Exception:
        print('{"error":"MEDIA_VALIDATION_FAILED"}')
        raise SystemExit(2) from None
    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()
