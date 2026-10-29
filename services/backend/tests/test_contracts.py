from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from test_workflow import MP4, NOTICE_ACKNOWLEDGMENT, create_campaign

from vouch_backend.schemas import ConsentReceiptRead


def test_notices_and_receipt_gets_declare_explicit_response_schemas(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    for path in ("/api/v1/notices/campaign-check", "/api/v1/notices/campaign-check/{version}"):
        operation = schema["paths"][path]["get"]
        assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
            "$ref": "#/components/schemas/ProcessingNotice"
        }
        assert "security" not in operation
    receipt = schema["paths"]["/api/v1/consent-receipts/{receipt_id}"]["get"]
    assert receipt["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ConsentReceiptRead"
    }
    assert receipt["security"] == [{"SupabaseBearer": []}]
    model = schema["components"]["schemas"]["ConsentReceiptRead"]
    assert set(model["required"]) == set(ConsentReceiptRead.model_fields)
    assert model["properties"]["id"]["format"] == "uuid"
    assert model["properties"]["accepted_at"]["format"] == "date-time"
    assert model["properties"]["purpose"]["const"] == "campaign_check"
    assert model["properties"]["revoked_at"]["anyOf"][1] == {"type": "null"}
    upload = schema["components"]["schemas"]["UploadIntentCreate"]
    assert upload["properties"]["notice_acknowledged"]["const"] is True
    assert {"notice_acknowledged", "notice_version", "purpose"} <= set(upload["required"])
    # This slice deliberately leaves unrelated dictionary responses generic.
    withdrawal = schema["paths"]["/api/v1/consent-receipts/{receipt_id}/withdraw"]["post"]
    assert "$ref" not in withdrawal["responses"]["202"]["content"]["application/json"]["schema"]


def test_typed_receipt_response_preserves_existing_runtime_keys_and_values(
    client: TestClient, marketer_headers: dict[str, str]
) -> None:
    campaign = create_campaign(client, marketer_headers)
    intent = client.post(
        "/api/v1/uploads", headers=marketer_headers,
        json={
            **NOTICE_ACKNOWLEDGMENT, "campaign_id": campaign["id"], "filename": "synthetic.mp4",
            "content_type": "video/mp4", "byte_size": len(MP4), "rights_attested": True,
        },
    )
    assert intent.status_code == 201
    original = intent.json()["consent_receipt"]
    response = client.get(
        f"/api/v1/consent-receipts/{original['id']}", headers=marketer_headers
    )
    assert response.status_code == 200 and response.json() == original
    assert ConsentReceiptRead.model_validate(response.json()).model_dump(mode="json") == original


@pytest.mark.parametrize(
    "changed",
    [
        {"accepted_at": "2026-10-23T10:30:00"},
        {"accepted_at": "2026-10-23T10:30:00+05:30"},
        {"revocation_actor_kind": "worker"},
        {"purpose": "try_preview"},
        {"id": "not-a-uuid"},
    ],
)
def test_receipt_wire_schema_rejects_invalid_shape_or_non_utc_timestamps(
    changed: dict[str, Any],
) -> None:
    values = {
        "id": "11111111-1111-4111-8111-111111111111",
        "asset_id": "11111111-1111-4111-8111-111111111112",
        "campaign_id": "11111111-1111-4111-8111-111111111113",
        "actor_user_id": "11111111-1111-4111-8111-111111111114",
        "purpose": "campaign_check", "notice_version": "synthetic-notice-v1",
        "notice_hash": "a" * 64, "accepted_at": "2026-10-23T00:00:00Z",
        "revoked_at": None, "revoked_by": None, "revocation_actor_kind": None,
        "revocation_reason": None,
    }
    with pytest.raises(ValidationError):
        ConsentReceiptRead.model_validate({**values, **changed})
