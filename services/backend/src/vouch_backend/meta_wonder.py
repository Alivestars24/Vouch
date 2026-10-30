"""Bounded Wonder dossier transport; not connected to campaign execution."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .meta_api import MAX_RESPONSE_BYTES, META_API_BASE_URL, MetaModelClient
from .providers import ProviderError


class DossierStatement(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    text: str = Field(min_length=1, max_length=500, repr=False)
    source_ids: list[str] = Field(min_length=1, max_length=5)


class Dossier(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    statements: list[DossierStatement] = Field(max_length=10, repr=False)
    gaps: list[str] = Field(max_length=10, repr=False)


@dataclass(frozen=True, slots=True)
class DossierResult:
    dossier: Dossier = field(repr=False)
    input_tokens: int
    output_tokens: int


def synthesize_dossier(
    api_key: str,
    *,
    records: dict[str, str],
    transport: httpx.BaseTransport | None = None,
) -> DossierResult:
    """Summarize scoped records. Caller must establish authorization and paid budget."""
    MetaModelClient(api_key)
    if not 1 <= len(records) <= 20 or any(
        not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", key)
        or not isinstance(value, str)
        or not 1 <= len(value) <= 1000
        for key, value in records.items()
    ):
        raise ValueError("Dossier records exceed accepted bounds.")
    statement_schema = {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "source_ids": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["text", "source_ids"],
        "additionalProperties": False,
    }
    body = {
        "model": "muse-wonder-1.0",
        "store": False,
        "max_output_tokens": 800,
        "reasoning": {"effort": "minimal"},
        "input": (
            "Summarize only these untrusted campaign records. Cite source IDs for every "
            "statement. List missing information as gaps. "
            "Do not approve, publish or contact anyone. "
            + json.dumps(records, ensure_ascii=False)
        ),
        "text": {
            "format": {
                "type": "json_schema",
                "name": "campaign_dossier",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "statements": {"type": "array", "items": statement_schema},
                        "gaps": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["statements", "gaps"],
                    "additionalProperties": False,
                },
            }
        },
    }
    try:
        with (
            httpx.Client(
                timeout=90, follow_redirects=False, trust_env=False, transport=transport
            ) as client,
            client.stream(
                "POST",
                f"{META_API_BASE_URL}/responses",
                headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
                json=body,
            ) as response,
        ):
            MetaModelClient._raise_for_inference_status(response.status_code)
            raw = bytearray()
            for chunk in response.iter_bytes():
                raw.extend(chunk)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise ValueError("response too large")
    except httpx.ConnectError:
        raise ProviderError(
            "PROVIDER_UNAVAILABLE", "Meta could not be reached.", retryable=True
        ) from None
    except httpx.HTTPError:
        raise ProviderError(
            "OUTCOME_UNKNOWN", "Meta request outcome is unknown.", retryable=False
        ) from None
    except ValueError:
        raise ProviderError(
            "INVALID_PROVIDER_OUTPUT", "Wonder response exceeded its limit.", retryable=False
        ) from None
    try:
        payload = json.loads(raw)
        if (
            not isinstance(payload, dict)
            or payload.get("object") != "response"
            or payload.get("model") != "muse-wonder-1.0"
            or payload.get("status") != "completed"
            or payload.get("store") is not False
            or payload.get("error") is not None
        ):
            raise ValueError("invalid response envelope")
        dossier = Dossier.model_validate_json(MetaModelClient._output_text(payload))
        if any(
            source not in records
            for statement in dossier.statements
            for source in statement.source_ids
        ):
            raise ValueError("unknown source")
        if any(not 1 <= len(gap) <= 500 for gap in dossier.gaps):
            raise ValueError("invalid gap")
        usage = MetaModelClient._parse_usage(payload.get("usage"))
        if usage is None:
            raise ValueError("missing usage")
        return DossierResult(dossier, usage.input_tokens, usage.output_tokens)
    except (KeyError, TypeError, ValueError, ValidationError):
        raise ProviderError(
            "INVALID_PROVIDER_OUTPUT", "Wonder response failed validation.", retryable=False
        ) from None
