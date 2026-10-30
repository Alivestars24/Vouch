from __future__ import annotations

import json

import httpx
import pytest

from vouch_backend.meta_wonder import synthesize_dossier
from vouch_backend.providers import ProviderError

KEY = "test-provider-credential-123456"


def response(source: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "object": "response",
            "model": "muse-wonder-1.0",
            "status": "completed",
            "store": False,
            "error": None,
            "output_text": json.dumps(
                {
                    "statements": [{"text": "One draft is pending.", "source_ids": [source]}],
                    "gaps": [],
                }
            ),
            "usage": {"input_tokens": 20, "output_tokens": 10, "total_tokens": 30},
        },
    )


def test_wonder_checks_source_ids_and_stateless_request() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content)["store"] is False
        return response("draft_1")

    result = synthesize_dossier(
        KEY, records={"draft_1": "One draft is pending."}, transport=httpx.MockTransport(handler)
    )
    assert result.dossier.statements[0].source_ids == ["draft_1"]


def test_wonder_rejects_citations_outside_supplied_records() -> None:
    with pytest.raises(ProviderError) as error:
        synthesize_dossier(
            KEY,
            records={"draft_1": "One draft is pending."},
            transport=httpx.MockTransport(lambda _: response("invented")),
        )
    assert error.value.code == "INVALID_PROVIDER_OUTPUT"
