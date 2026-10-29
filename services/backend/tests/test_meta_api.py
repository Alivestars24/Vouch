from __future__ import annotations

import json

import httpx
import pytest

from vouch_backend.config import Settings
from vouch_backend.meta_api import (
    META_API_BASE_URL,
    SPARK_MODEL_ID,
    SPARK_SMOKE_OUTPUT_TOKENS,
    MetaModelClient,
    probe_meta_capabilities,
)
from vouch_backend.providers import ProviderError

TEST_KEY = "fixture-provider-key-1234567890"


def settings(*, api_key: str | None = TEST_KEY, operator_region: str = "IN") -> Settings:
    return Settings(
        database_url="sqlite:///:memory:",
        environment="test",
        meta_api_key=api_key,
        operator_region=operator_region,
    )


def test_model_catalog_probe_is_server_only_and_normalizes_vouch_capabilities() -> None:
    requested: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(request)
        assert request.method == "GET"
        assert str(request.url) == f"{META_API_BASE_URL}/models"
        assert request.headers["Authorization"] == f"Bearer {TEST_KEY}"
        return httpx.Response(
            200,
            json={
                "object": "list",
                "data": [
                    {"id": "muse-spark-1.3"},
                    {"id": "muse-voice-transcribe-1.0"},
                    {"id": "sam-3.1"},
                    {"id": "muse-wonder-1.0"},
                    {"id": "muse-image-1.0"},
                ],
            },
        )

    result = probe_meta_capabilities(
        settings(), transport=httpx.MockTransport(handler)
    )

    assert len(requested) == 1
    assert result.catalog_verified is True
    assert result.operator_region == "IN"
    by_family = {item.family: item for item in result.capabilities}
    assert by_family["Spark"].status == "configured_unverified"
    assert by_family["Spark"].catalog_visible is True
    assert by_family["Spark"].inference_verified is False
    assert by_family["Muse Image"].status == "policy_restricted"
    assert by_family["Muse Image"].catalog_visible is True


def test_missing_catalog_model_remains_awaiting_access() -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            200,
            json={
                "data": [
                    {"id": "muse-spark-1.3"},
                    {"id": "muse-spark-1.3-contributor"},
                    {"id": "muse-spark-open"},
                    {"id": "muse-wonder-full"},
                    {"id": "muse-glimmer"},
                ]
            },
        )
    )

    result = probe_meta_capabilities(settings(operator_region="US"), transport=transport)

    by_family = {item.family: item for item in result.capabilities}
    assert by_family["Spark"].status == "configured_unverified"
    assert by_family["Voice Transcribe"].status == "awaiting_access"
    assert by_family["Muse Image"].status == "awaiting_access"


def test_oversized_catalog_fails_closed_before_json_parsing() -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(200, content=b"x" * 1_000_001)
    )

    with pytest.raises(ProviderError) as captured:
        MetaModelClient(TEST_KEY, transport=transport).list_model_ids()

    assert captured.value.code == "INVALID_PROVIDER_OUTPUT"


def test_catalog_timeout_is_safe_and_retryable() -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout(f"private transport detail {TEST_KEY}", request=request)

    with pytest.raises(ProviderError) as captured:
        MetaModelClient(TEST_KEY, transport=httpx.MockTransport(timeout)).list_model_ids()

    assert captured.value.code == "TIMEOUT"
    assert captured.value.retryable is True
    assert TEST_KEY not in captured.value.safe_message
    assert captured.value.__cause__ is None


@pytest.mark.parametrize(
    ("status_code", "code", "retryable"),
    [
        (401, "ACCESS_DENIED", False),
        (403, "ACCESS_DENIED", False),
        (429, "RATE_LIMITED", True),
        (503, "PROVIDER_UNAVAILABLE", True),
        (404, "ACCESS_UNVERIFIED", False),
    ],
)
def test_provider_http_errors_are_safe(
    status_code: int, code: str, retryable: bool
) -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            status_code,
            json={"message": f"private body {TEST_KEY}"},
        )
    )

    with pytest.raises(ProviderError) as captured:
        MetaModelClient(TEST_KEY, transport=transport).list_model_ids()

    assert captured.value.code == code
    assert captured.value.retryable is retryable
    assert TEST_KEY not in captured.value.safe_message
    assert "private body" not in captured.value.safe_message


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"data": "not-a-list"},
        {"data": ["not-an-object"]},
        {"data": [{"id": ""}]},
    ],
)
def test_invalid_catalog_payload_fails_closed(payload: object) -> None:
    transport = httpx.MockTransport(lambda _request: httpx.Response(200, json=payload))

    with pytest.raises(ProviderError) as captured:
        MetaModelClient(TEST_KEY, transport=transport).list_model_ids()

    assert captured.value.code == "INVALID_PROVIDER_OUTPUT"
    assert captured.value.retryable is False


def test_missing_configuration_and_repr_do_not_expose_a_secret() -> None:
    with pytest.raises(ProviderError) as captured:
        probe_meta_capabilities(settings(api_key=None))
    assert captured.value.code == "NOT_CONFIGURED"

    configured = settings()
    assert TEST_KEY not in repr(configured)
    assert TEST_KEY not in repr(MetaModelClient(TEST_KEY))


def test_key_validation_does_not_pin_a_provider_prefix() -> None:
    future_format = "provider-format-may-change-1234567890"
    configured = settings(api_key=future_format)
    assert future_format not in repr(configured)


@pytest.mark.parametrize(
    "api_key",
    ["short", " fixture-provider-key-1234567890", "fixture-provider-key bad value"],
)
def test_invalid_key_format_is_rejected_before_network(api_key: str) -> None:
    with pytest.raises(ValueError, match="VOUCH_META_API_KEY"):
        settings(api_key=api_key)
    with pytest.raises(ValueError, match="valid Meta Model API key"):
        MetaModelClient(api_key)


def spark_response(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": "resp_vouch_smoke",
        "object": "response",
        "status": "completed",
        "model": SPARK_MODEL_ID,
        "store": False,
        "error": None,
        "output_text": '{"status":"ok"}',
        "usage": {
            "input_tokens": 30,
            "input_tokens_details": {"cached_tokens": 5},
            "output_tokens": 20,
            "output_tokens_details": {"reasoning_tokens": 12},
            "total_tokens": 50,
        },
    }
    payload.update(overrides)
    return payload


def test_spark_smoke_uses_bounded_stateless_strict_responses_request() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert str(request.url) == f"{META_API_BASE_URL}/responses"
        assert request.headers["Authorization"] == f"Bearer {TEST_KEY}"
        body = json.loads(request.content)
        assert body["model"] == SPARK_MODEL_ID
        assert body["store"] is False
        assert body["max_output_tokens"] == SPARK_SMOKE_OUTPUT_TOKENS == 128
        assert body["reasoning"] == {"effort": "minimal"}
        assert "tools" not in body
        output_format = body["text"]["format"]
        assert output_format["type"] == "json_schema"
        assert output_format["strict"] is True
        assert output_format["schema"]["additionalProperties"] is False
        assert output_format["schema"]["required"] == ["status"]
        return httpx.Response(
            200,
            headers={"x-request-id": "req_safe-123"},
            json=spark_response(),
        )

    result = MetaModelClient(
        TEST_KEY, transport=httpx.MockTransport(handler)
    ).run_spark_smoke()

    assert result.requested_model == SPARK_MODEL_ID
    assert result.returned_model == SPARK_MODEL_ID
    assert result.provider_request_id == "req_safe-123"
    assert result.store is False
    assert result.structured_output_verified is True
    assert result.usage is not None
    assert result.usage.total_tokens == 50
    assert result.usage.cached_input_tokens == 5
    assert result.usage.reasoning_tokens == 12


def test_spark_smoke_accepts_documented_output_array_without_helper() -> None:
    output = [
        {"type": "reasoning", "id": "reasoning_1", "summary": []},
        {
            "type": "message",
            "role": "assistant",
            "status": "completed",
            "content": [
                {
                    "type": "output_text",
                    "text": '{"status":"ok"}',
                    "annotations": [],
                }
            ],
        },
    ]
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            200,
            headers={"x-request-id": "unsafe request id"},
            json=spark_response(output_text=None, output=output),
        )
    )

    result = MetaModelClient(TEST_KEY, transport=transport).run_spark_smoke()

    assert result.structured_output_verified is True
    assert result.provider_request_id is None


def test_spark_smoke_preserves_unknown_usage_instead_of_inventing_zeroes() -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(200, json=spark_response(usage=None))
    )

    result = MetaModelClient(TEST_KEY, transport=transport).run_spark_smoke()

    assert result.structured_output_verified is True
    assert result.usage is None


@pytest.mark.parametrize(
    ("status_code", "code", "retryable"),
    [
        (400, "ACCESS_UNVERIFIED", False),
        (401, "ACCESS_DENIED", False),
        (403, "ACCESS_DENIED", False),
        (429, "RATE_LIMITED", True),
        (500, "OUTCOME_UNKNOWN", False),
        (503, "OUTCOME_UNKNOWN", False),
    ],
)
def test_spark_smoke_http_errors_preserve_paid_outcome_semantics(
    status_code: int, code: str, retryable: bool
) -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            status_code,
            json={"error": {"message": f"private body {TEST_KEY}"}},
        )
    )

    with pytest.raises(ProviderError) as captured:
        MetaModelClient(TEST_KEY, transport=transport).run_spark_smoke()

    assert captured.value.code == code
    assert captured.value.retryable is retryable
    assert TEST_KEY not in captured.value.safe_message
    assert "private body" not in captured.value.safe_message


def test_spark_smoke_timeout_is_outcome_unknown_and_never_auto_retryable() -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout(f"private timeout {TEST_KEY}", request=request)

    with pytest.raises(ProviderError) as captured:
        MetaModelClient(TEST_KEY, transport=httpx.MockTransport(timeout)).run_spark_smoke()

    assert captured.value.code == "OUTCOME_UNKNOWN"
    assert captured.value.retryable is False
    assert TEST_KEY not in captured.value.safe_message
    assert captured.value.__cause__ is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"status": "incomplete"},
        {"model": "muse-spark-1.3-contributor"},
        {"store": True},
        {"object": "not-a-response"},
        {"error": {"type": "provider_error"}},
        {"output_text": '{"status":"wrong"}'},
        {"output_text": '{"status":"ok","extra":true}'},
        {"usage": {"input_tokens": 30, "output_tokens": 20, "total_tokens": 10}},
    ],
)
def test_spark_smoke_invalid_result_fails_closed(overrides: dict[str, object]) -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(200, json=spark_response(**overrides))
    )

    with pytest.raises(ProviderError) as captured:
        MetaModelClient(TEST_KEY, transport=transport).run_spark_smoke()

    assert captured.value.code == "INVALID_PROVIDER_OUTPUT"
    assert captured.value.retryable is False
