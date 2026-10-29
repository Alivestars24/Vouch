from __future__ import annotations

from typing import Any
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient
from test_workflow import MP4, create_campaign

from vouch_backend.auth import Principal, get_principal, get_upload_principal
from vouch_backend.config import Settings
from vouch_backend.errors import ApiError
from vouch_backend.models import MediaAsset
from vouch_backend.seed import ACME_ORG_ID, MARKETER_USER_ID
from vouch_backend.storage import SupabaseMediaStore

KEY = (
    "11111111-1111-4111-8111-111111111111/"
    "10000000-0000-4000-8000-000000000001/"
    "10000000-0000-4000-8000-000000000002/source"
)


def store_with(handler: Any) -> SupabaseMediaStore:
    return SupabaseMediaStore(
        Settings(
            database_url="sqlite:///:memory:",
            supabase_url="http://127.0.0.1:54321",
            supabase_publishable_key="public-test-key",
            supabase_secret_key="secret-test-key",
        ),
        httpx.MockTransport(handler),
    )


def test_upload_retry_reconciles_identical_bytes_and_rejects_overwrite() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        assert request.headers["apikey"] == "public-test-key"
        assert request.headers["authorization"] == "Bearer user-token"
        if request.method == "POST":
            assert request.headers["x-upsert"] == "false"
            return httpx.Response(400, json={"statusCode": "409"})
        return httpx.Response(200, content=MP4)

    store = store_with(handler)
    store.upload(KEY, MP4, "video/mp4", "user-token")
    with pytest.raises(ApiError, match="UPLOAD_CONTENT_CONFLICT"):
        store.upload(KEY, MP4 + b"changed", "video/mp4", "user-token")
    assert len(seen) == 4


def test_deletion_confirms_absence_and_uses_server_key_only() -> None:
    remaining = True

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["apikey"] == "secret-test-key"
        assert "user-token" not in str(request.headers)
        if request.method == "DELETE":
            assert request.content == ('{"prefixes":["' + KEY + '"]}').encode()
            return httpx.Response(200, json=[])
        return (
            httpx.Response(200, content=MP4)
            if remaining
            else httpx.Response(400, json={"statusCode": "404"})
        )

    store = store_with(handler)
    with pytest.raises(ApiError) as error:
        store.delete(KEY)
    assert error.value.code == "STORAGE_UNAVAILABLE"
    remaining = False
    store.delete(KEY)


def test_storage_timeout_is_safe_retryable_and_arbitrary_keys_are_rejected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("sensitive provider body", request=request)

    store = store_with(handler)
    with pytest.raises(ApiError) as error:
        store.upload(KEY, MP4, "video/mp4", "user-token")
    assert error.value.retryable and "sensitive" not in str(error.value)
    with pytest.raises(ValueError):
        store.delete("../../other-bucket/private")


class MemoryStore:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.fail_delete = True

    def upload(self, key: str, body: bytes, content_type: str, access_token: str) -> None:
        self.objects[key] = body

    def download(self, key: str, access_token: str) -> bytes:
        return self.objects[key]

    def delete(self, key: str) -> None:
        if self.fail_delete:
            raise ApiError(503, "STORAGE_UNAVAILABLE", "Retry cleanup.", True)
        self.objects.pop(key, None)


def test_private_storage_lifecycle_and_partial_deletion_retry(client: TestClient) -> None:
    from test_workflow import NOTICE_ACKNOWLEDGMENT

    principal = Principal(
        organization_id=ACME_ORG_ID,
        organization_name="Acme",
        user_id=MARKETER_USER_ID,
        email="marketer@vouch.test",
        display_name="Marketer",
        roles=frozenset({"marketer"}),
        access_token="verified-test-token",
    )
    client.app.dependency_overrides[get_principal] = lambda: principal
    client.app.dependency_overrides[get_upload_principal] = lambda: principal
    store = MemoryStore()
    client.app.state.media_store = store
    campaign = create_campaign(client, {})
    intent_response = client.post(
        "/api/v1/uploads",
        json={
            "campaign_id": campaign["id"],
            "filename": "authorized.mp4",
            **NOTICE_ACKNOWLEDGMENT,
            "content_type": "video/mp4",
            "byte_size": len(MP4),
            "rights_attested": True,
        },
    )
    assert intent_response.status_code == 201, intent_response.text
    intent = intent_response.json()
    response = client.put(
        intent["content_url"],
        content=MP4,
        headers={
            "Content-Type": "video/mp4",
            "X-Upload-Token": intent["upload_token"],
        },
    )
    assert response.status_code == 200, response.text
    retried_upload = client.put(
        intent["content_url"],
        content=MP4,
        headers={
            "Content-Type": "video/mp4",
            "X-Upload-Token": intent["upload_token"],
        },
    )
    assert retried_upload.status_code == 200, retried_upload.text
    finalized = client.post(
        f"/api/v1/uploads/{intent['upload_id']}/finalize",
        json={
            "finalize_token": intent["finalize_token"],
        },
    )
    assert finalized.status_code == 200, finalized.text
    assert finalized.json()["storage_backend"] == "supabase"
    with client.app.state.database.session_factory() as session:
        asset = session.get(MediaAsset, UUID(intent["upload_id"]))
        assert (
            asset is not None and asset.object_bytes is None and asset.object_key in store.objects
        )
    download = client.get(intent["content_url"])
    assert download.status_code == 200 and download.content == MP4
    assert download.headers["cache-control"] == "no-store"
    payload = {"resource_type": "media_asset", "resource_id": intent["upload_id"]}
    partial = client.post("/api/v1/deletion-requests", json=payload)
    assert partial.status_code == 202, partial.text
    assert partial.json()["status"] == "partial"
    assert partial.json()["completed_at"] is None
    assert client.get(intent["content_url"]).status_code == 404
    store.fail_delete = False
    retried = client.post("/api/v1/deletion-requests", json=payload)
    assert retried.status_code == 202 and retried.json()["status"] == "completed", retried.text
    assert retried.json()["id"] == partial.json()["id"] and not store.objects
