from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Literal

import httpx

from .config import Settings
from .providers import ProviderError

META_API_BASE_URL = "https://api.meta.ai/v1"
MAX_MODEL_CATALOG_BYTES = 1_000_000
MAX_MODEL_CATALOG_ITEMS = 500
MAX_RESPONSE_BYTES = 2_000_000
SPARK_SMOKE_OUTPUT_TOKENS = 128
SPARK_MODEL_ID = "muse-spark-1.3"
SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,200}$")


@dataclass(frozen=True, slots=True)
class MetaModelDefinition:
    family: str
    model_id: str
    role: str


VOUCH_META_MODELS = (
    MetaModelDefinition(
        family="Spark",
        model_id="muse-spark-1.3",
        role="structured Check reasoning over authorized evidence",
    ),
    MetaModelDefinition(
        family="Voice Transcribe",
        model_id="muse-voice-transcribe-1.0",
        role="time-aligned speech evidence",
    ),
    MetaModelDefinition(
        family="SAM",
        model_id="sam-3.1",
        role="sampled visual and product-concept evidence",
    ),
    MetaModelDefinition(
        family="Wonder",
        model_id="muse-wonder-1.0",
        role="bounded read-only campaign evidence dossier",
    ),
    MetaModelDefinition(
        family="Muse Image",
        model_id="muse-image-1.0",
        role="conditional eyewear preview",
    ),
)


@dataclass(frozen=True, slots=True)
class MetaModelCapability:
    family: str
    model_id: str
    role: str
    catalog_visible: bool
    status: Literal["configured_unverified", "awaiting_access", "policy_restricted"]
    reason: str
    inference_verified: bool = False


@dataclass(frozen=True, slots=True)
class MetaCapabilityProbe:
    provider: str
    checked_at: str
    catalog_verified: bool
    operator_region: str
    capabilities: tuple[MetaModelCapability, ...]

    def model_dump(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class MetaUsage:
    input_tokens: int
    cached_input_tokens: int | None
    output_tokens: int
    reasoning_tokens: int | None
    total_tokens: int


@dataclass(frozen=True, slots=True)
class MetaSparkSmokeResult:
    provider: str
    requested_model: str
    returned_model: str
    response_id: str
    provider_request_id: str | None
    store: bool
    structured_output_verified: bool
    usage: MetaUsage | None

    def model_dump(self) -> dict[str, object]:
        return asdict(self)


class MetaModelClient:
    """Minimal server-only Meta Model API client.

    The first integration slice deliberately probes only the model catalog. Product inference
    remains disabled until each media adapter can preserve authorization, provenance, cost and
    remote-cleanup invariants end to end.
    """

    def __init__(
        self,
        api_key: str,
        *,
        transport: httpx.BaseTransport | None = None,
        timeout_seconds: float = 8.0,
    ) -> None:
        if (
            api_key != api_key.strip()
            or not 20 <= len(api_key) <= 512
            or any(character.isspace() for character in api_key)
        ):
            raise ValueError("A valid Meta Model API key is required.")
        self._api_key = api_key
        self._transport = transport
        self._timeout_seconds = timeout_seconds

    def __repr__(self) -> str:
        return "MetaModelClient(configured=True)"

    def list_model_ids(self) -> frozenset[str]:
        try:
            with (
                httpx.Client(
                timeout=self._timeout_seconds,
                follow_redirects=False,
                trust_env=False,
                transport=self._transport,
                ) as client,
                client.stream(
                    "GET",
                    f"{META_API_BASE_URL}/models",
                    headers={
                        "Accept": "application/json",
                        "Authorization": f"Bearer {self._api_key}",
                    },
                ) as response,
            ):
                self._raise_for_status(response.status_code)
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_MODEL_CATALOG_BYTES:
                        raise ProviderError(
                            "INVALID_PROVIDER_OUTPUT",
                            "Meta returned a model catalog larger than the accepted limit.",
                            retryable=False,
                        )
        except httpx.TimeoutException:
            raise ProviderError(
                "TIMEOUT",
                "Meta model access verification timed out safely.",
                retryable=True,
            ) from None
        except httpx.HTTPError:
            raise ProviderError(
                "PROVIDER_UNAVAILABLE",
                "Meta model access verification is temporarily unavailable.",
                retryable=True,
            ) from None
        return self._parse_model_ids(bytes(body))

    def run_spark_smoke(self) -> MetaSparkSmokeResult:
        """Run one explicit, synthetic, bounded paid inference.

        This proves the account/model/Responses structured-output path only. It is not a customer
        Check and accepts no caller-supplied text or media.
        """
        request_body = {
            "model": SPARK_MODEL_ID,
            "input": (
                "Return the fixed readiness result. Set status to ok. "
                "Do not add any other fields."
            ),
            "store": False,
            # Meta counts private reasoning and visible JSON against this shared limit. A
            # 64-token budget intermittently ended before the 15-character result was emitted.
            "max_output_tokens": SPARK_SMOKE_OUTPUT_TOKENS,
            "reasoning": {"effort": "minimal"},
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "vouch_meta_smoke",
                    "description": "A bounded Vouch Meta Responses API readiness result.",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "status": {"type": "string", "enum": ["ok"]},
                        },
                        "required": ["status"],
                        "additionalProperties": False,
                    },
                }
            },
        }
        try:
            with (
                httpx.Client(
                    timeout=self._timeout_seconds,
                    follow_redirects=False,
                    trust_env=False,
                    transport=self._transport,
                ) as client,
                client.stream(
                    "POST",
                    f"{META_API_BASE_URL}/responses",
                    headers={
                        "Accept": "application/json",
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json=request_body,
                ) as response,
            ):
                self._raise_for_inference_status(response.status_code)
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_RESPONSE_BYTES:
                        raise ProviderError(
                            "INVALID_PROVIDER_OUTPUT",
                            "Meta returned a response larger than the accepted limit.",
                            retryable=False,
                        )
                request_id = self._safe_request_id(response.headers.get("x-request-id"))
        except httpx.ConnectError:
            raise ProviderError(
                "PROVIDER_UNAVAILABLE",
                "The Meta inference service could not be reached.",
                retryable=True,
            ) from None
        except httpx.TimeoutException:
            raise ProviderError(
                "OUTCOME_UNKNOWN",
                "The Meta inference timed out after submission; do not retry it blindly.",
                retryable=False,
            ) from None
        except httpx.HTTPError:
            raise ProviderError(
                "OUTCOME_UNKNOWN",
                "The Meta inference ended with an unknown remote outcome.",
                retryable=False,
            ) from None
        return self._parse_spark_smoke(bytes(body), request_id)

    @staticmethod
    def _raise_for_status(status_code: int) -> None:
        if status_code == 200:
            return
        if status_code in {401, 403}:
            raise ProviderError(
                "ACCESS_DENIED",
                "Meta rejected the configured Model API credential or account access.",
                retryable=False,
            )
        if status_code == 429:
            raise ProviderError(
                "RATE_LIMITED",
                "Meta model access verification is rate limited.",
                retryable=True,
            )
        if 500 <= status_code <= 599:
            raise ProviderError(
                "PROVIDER_UNAVAILABLE",
                "Meta model access verification is temporarily unavailable.",
                retryable=True,
            )
        raise ProviderError(
            "ACCESS_UNVERIFIED",
            "Meta model access could not be verified with the documented catalog endpoint.",
            retryable=False,
        )

    @staticmethod
    def _raise_for_inference_status(status_code: int) -> None:
        if status_code == 200:
            return
        if status_code in {401, 403}:
            raise ProviderError(
                "ACCESS_DENIED",
                "Meta rejected the configured Model API credential or model access.",
                retryable=False,
            )
        if status_code == 429:
            raise ProviderError(
                "RATE_LIMITED",
                "Meta rejected the inference before completion because it was rate limited.",
                retryable=True,
            )
        if status_code in {400, 404, 405, 422}:
            raise ProviderError(
                "ACCESS_UNVERIFIED",
                "Meta did not accept the documented Spark Responses request.",
                retryable=False,
            )
        raise ProviderError(
            "OUTCOME_UNKNOWN",
            "The Meta inference ended with an unknown remote outcome.",
            retryable=False,
        )

    @staticmethod
    def _parse_model_ids(body: bytes) -> frozenset[str]:
        try:
            payload = json.loads(body)
            data = payload["data"]
            if not isinstance(data, list) or len(data) > MAX_MODEL_CATALOG_ITEMS:
                raise ValueError("invalid model collection")
            model_ids: set[str] = set()
            for item in data:
                if not isinstance(item, dict):
                    raise ValueError("invalid model entry")
                model_id = item.get("id")
                if not isinstance(model_id, str) or not model_id or len(model_id) > 200:
                    raise ValueError("invalid model id")
                model_ids.add(model_id)
            return frozenset(model_ids)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise ProviderError(
                "INVALID_PROVIDER_OUTPUT",
                "Meta returned a model catalog that failed runtime validation.",
                retryable=False,
            ) from error

    @staticmethod
    def _safe_request_id(value: str | None) -> str | None:
        return value if value is not None and SAFE_REQUEST_ID.fullmatch(value) else None

    @classmethod
    def _parse_spark_smoke(
        cls, body: bytes, provider_request_id: str | None
    ) -> MetaSparkSmokeResult:
        try:
            payload = json.loads(body)
            if not isinstance(payload, dict):
                raise ValueError("invalid response")
            response_id = payload["id"]
            returned_model = payload["model"]
            if (
                not isinstance(response_id, str)
                or not 1 <= len(response_id) <= 200
                or payload.get("object") != "response"
                or returned_model != SPARK_MODEL_ID
                or payload.get("status") != "completed"
                or payload.get("store") is not False
                or payload.get("error") is not None
            ):
                raise ValueError("invalid response identity")
            output = json.loads(cls._output_text(payload))
            if output != {"status": "ok"}:
                raise ValueError("invalid structured output")
            usage = cls._parse_usage(payload.get("usage"))
            return MetaSparkSmokeResult(
                provider="meta_model_api",
                requested_model=SPARK_MODEL_ID,
                returned_model=returned_model,
                response_id=response_id,
                provider_request_id=provider_request_id,
                store=False,
                structured_output_verified=True,
                usage=usage,
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise ProviderError(
                "INVALID_PROVIDER_OUTPUT",
                "Meta returned a Spark response that failed runtime validation.",
                retryable=False,
            ) from error

    @staticmethod
    def _output_text(payload: dict[str, object]) -> str:
        direct = payload.get("output_text")
        if isinstance(direct, str) and 0 < len(direct) <= 10_000:
            return direct
        output = payload.get("output")
        if not isinstance(output, list):
            raise ValueError("missing output")
        candidates: list[str] = []
        for item in output:
            if not isinstance(item, dict) or item.get("type") != "message":
                continue
            if item.get("status") != "completed":
                raise ValueError("incomplete output message")
            content = item.get("content")
            if not isinstance(content, list):
                raise ValueError("invalid message content")
            for part in content:
                if not isinstance(part, dict):
                    raise ValueError("invalid output part")
                if part.get("type") == "refusal":
                    raise ValueError("provider refusal")
                if part.get("type") == "output_text" and isinstance(part.get("text"), str):
                    candidates.append(part["text"])
        if len(candidates) != 1 or not 0 < len(candidates[0]) <= 10_000:
            raise ValueError("invalid output text")
        return candidates[0]

    @staticmethod
    def _parse_usage(value: object) -> MetaUsage | None:
        if value is None:
            return None
        if not isinstance(value, dict):
            raise ValueError("invalid usage")

        def required_nonnegative_int(field_name: str) -> int:
            item = value.get(field_name)
            if not isinstance(item, int) or isinstance(item, bool) or item < 0:
                raise ValueError("invalid usage")
            return item

        input_tokens = required_nonnegative_int("input_tokens")
        output_tokens = required_nonnegative_int("output_tokens")
        total_tokens = required_nonnegative_int("total_tokens")
        if total_tokens < input_tokens + output_tokens:
            raise ValueError("invalid usage")

        def optional_detail(container_name: str, field_name: str) -> int | None:
            container = value.get(container_name)
            if container is None:
                return None
            if not isinstance(container, dict):
                raise ValueError("invalid usage details")
            detail = container.get(field_name)
            if detail is None:
                return None
            if not isinstance(detail, int) or isinstance(detail, bool) or detail < 0:
                raise ValueError("invalid usage detail")
            return detail

        return MetaUsage(
            input_tokens=input_tokens,
            cached_input_tokens=optional_detail("input_tokens_details", "cached_tokens"),
            output_tokens=output_tokens,
            reasoning_tokens=optional_detail("output_tokens_details", "reasoning_tokens"),
            total_tokens=total_tokens,
        )


def probe_meta_capabilities(
    settings: Settings,
    *,
    transport: httpx.BaseTransport | None = None,
) -> MetaCapabilityProbe:
    if settings.meta_api_key is None:
        raise ProviderError(
            "NOT_CONFIGURED",
            "Meta Model API is not configured on this server.",
            retryable=False,
        )
    available = MetaModelClient(settings.meta_api_key, transport=transport).list_model_ids()
    operator_region = settings.operator_region.upper()
    capabilities: list[MetaModelCapability] = []
    for definition in VOUCH_META_MODELS:
        visible = definition.model_id in available
        if definition.family == "Muse Image" and operator_region == "IN":
            status: Literal[
                "configured_unverified", "awaiting_access", "policy_restricted"
            ] = "policy_restricted"
            reason = (
                "Muse Image calls remain disabled for an India operator under the current "
                "Meta geographic policy. Catalog visibility does not override that restriction."
            )
        elif visible:
            status = "configured_unverified"
            reason = (
                "The account catalog lists this model; a bounded synthetic inference and output "
                "validation are still required before product enablement."
            )
        else:
            status = "awaiting_access"
            reason = "The account catalog did not list the required model ID."
        capabilities.append(
            MetaModelCapability(
                family=definition.family,
                model_id=definition.model_id,
                role=definition.role,
                catalog_visible=visible,
                status=status,
                reason=reason,
            )
        )
    return MetaCapabilityProbe(
        provider="meta_model_api",
        checked_at=datetime.now(UTC).isoformat(),
        catalog_verified=True,
        operator_region=operator_region,
        capabilities=tuple(capabilities),
    )
