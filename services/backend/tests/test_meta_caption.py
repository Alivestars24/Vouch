from __future__ import annotations

import json

import httpx
import pytest

from vouch_backend.meta_caption import review_caption
from vouch_backend.providers import ProviderError

KEY = "test-provider-credential-123456"


def response(quote: str | None, requirement: str = "Identify sponsorship") -> dict[str, object]:
    return {
        "object": "response",
        "model": "muse-spark-1.3",
        "status": "completed",
        "store": False,
        "error": None,
        "output_text": json.dumps(
            {
                "findings": [
                    {
                        "quote": quote,
                        "kind": "quoted_concern" if quote is not None else "missing_requirement",
                        "requirement": requirement,
                        "concern": "Disclosure is unclear",
                        "suggested_action": "Clarify it",
                    }
                ]
            }
        ),
        "usage": {"input_tokens": 20, "output_tokens": 10, "total_tokens": 30},
    }


def test_caption_request_is_bounded_stateless_and_requires_source_quote() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["store"] is False
        assert body["max_output_tokens"] == 600
        assert body["text"]["format"]["strict"] is True
        return httpx.Response(200, json=response("amazing glasses"))

    result = review_caption(
        KEY,
        caption="These are amazing glasses",
        requirements="Identify sponsorship",
        transport=httpx.MockTransport(handler),
    )
    assert result.review.findings[0].quote == "amazing glasses"
    assert (result.input_tokens, result.output_tokens) == (20, 10)


def test_fabricated_quote_is_rejected() -> None:
    transport = httpx.MockTransport(
        lambda _: httpx.Response(200, json=response("invented quote", "Disclose"))
    )
    with pytest.raises(ProviderError) as error:
        review_caption(KEY, caption="Real caption", requirements="Disclose", transport=transport)
    assert error.value.code == "INVALID_PROVIDER_OUTPUT"


def test_missing_requirement_is_grounded_in_exact_brief_without_invented_quote() -> None:
    transport = httpx.MockTransport(lambda _: httpx.Response(200, json=response(None, "Disclose")))
    result = review_caption(
        KEY, caption="Real caption", requirements="Disclose", transport=transport
    )
    assert result.review.findings[0].kind == "missing_requirement"
    assert result.review.findings[0].quote is None


def test_timeout_never_blindly_retries_paid_request() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("private details", request=request)

    with pytest.raises(ProviderError) as error:
        review_caption(
            KEY,
            caption="Real caption",
            requirements="Disclose",
            transport=httpx.MockTransport(handler),
        )
    assert error.value.code == "OUTCOME_UNKNOWN"
    assert error.value.retryable is False
