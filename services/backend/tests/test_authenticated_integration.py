"""Opt-in, real local Auth/Storage and restricted-login proofs; never targets hosted."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from contextlib import suppress
from pathlib import Path
from threading import Barrier, Event
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from test_workflow import MP4, create_campaign, create_submission, start_check, upload_asset

from vouch_backend.api import create_app
from vouch_backend.config import Settings
from vouch_backend.db import Database, set_database_scope
from vouch_backend.errors import ApiError
from vouch_backend.models import (
    Campaign,
    CampaignCreator,
    ConsentReceipt,
    CreatorFeedback,
    GuestGrant,
    MediaAsset,
    Membership,
    SubmissionVersion,
    User,
)
from vouch_backend.seed import ACME_ORG_ID, BETA_ORG_ID, MARKETER_USER_ID
from vouch_backend.worker import process_next_job

pytestmark = pytest.mark.skipif(
    os.getenv("VOUCH_TEST_AUTHENTICATED") != "1", reason="Opt-in local Supabase integration."
)
ROOT = Path(__file__).resolve().parents[3]


class LocalRuntime(dict[str, Any]):
    def __repr__(self) -> str:
        return "<local authenticated runtime; credentials redacted>"


class PrivateHeaders(dict[str, str]):
    def __repr__(self) -> str:
        return "<authenticated headers; token redacted>"


class PausedGuestUploadStore:
    """Pause before the exact-key Storage write to expose deletion ordering."""

    def __init__(self, delegate: Any, entered: Event, release: Event) -> None:
        self.delegate = delegate
        self.entered = entered
        self.release = release

    def upload(self, key: str, body: bytes, content_type: str) -> None:
        self.entered.set()
        if not self.release.wait(timeout=10):
            raise RuntimeError("Timed out waiting to resume the guest upload test.")
        self.delegate.upload(key, body, content_type)

    def download(self, key: str) -> bytes:
        return self.delegate.download(key)


def env_file(name: str) -> dict[str, str]:
    result = {}
    for line in (ROOT / f"services/backend/.env.{name}").read_text().splitlines():
        key, separator, value = line.partition("=")
        if separator and not key.startswith("#"):
            result[key] = value.strip().strip('"')
    return result


@pytest.fixture(scope="module")
def runtime() -> Iterator[dict[str, Any]]:
    api = env_file("api")
    worker = env_file("worker")
    assert api["VOUCH_SUPABASE_URL"] == "http://127.0.0.1:54321"
    credentials = json.loads((ROOT / ".local/credentials.json").read_text())
    headers = {}
    for role in ("marketer", "reviewer", "beta", "revoked"):
        response = httpx.post(
            f"{api['VOUCH_SUPABASE_URL']}/auth/v1/token?grant_type=password",
            headers={"apikey": api["VOUCH_SUPABASE_PUBLISHABLE_KEY"]},
            json={"email": f"{role}@vouch.test", "password": credentials["password"]},
            timeout=10,
        )
        assert response.status_code == 200, f"Local {role} sign-in failed."
        headers[role] = PrivateHeaders(
            {
                "Authorization": f"Bearer {response.json()['access_token']}",
                "X-Organization-Id": str(BETA_ORG_ID if role == "beta" else ACME_ORG_ID),
            }
        )
    settings = Settings(
        database_url=api["VOUCH_DATABASE_URL"],
        auth_mode="supabase",
        environment="test",
        supabase_url=api["VOUCH_SUPABASE_URL"],
        supabase_publishable_key=api["VOUCH_SUPABASE_PUBLISHABLE_KEY"],
        supabase_secret_key=api["VOUCH_SUPABASE_SECRET_KEY"],
        guest_database_url=api["VOUCH_GUEST_DATABASE_URL"],
        guest_storage_key=api["VOUCH_GUEST_STORAGE_KEY"],
        guest_rate_limit_key=api["VOUCH_GUEST_RATE_LIMIT_KEY"],
    )
    worker_db = Database(worker["VOUCH_DATABASE_URL"], runtime_role="vouch_worker")
    owner = Database("postgresql+psycopg://postgres:postgres@127.0.0.1:54322/postgres")
    try:
        with TestClient(create_app(settings)) as client:
            yield LocalRuntime(
                {
                    "client": client,
                    "worker": worker_db,
                    "owner": owner,
                    "headers": headers,
                    "settings": settings,
                }
            )
    finally:
        worker_db.dispose()
        owner.dispose()


def test_real_find_links_evidence_under_restricted_api_role(
    runtime: dict[str, Any],
) -> None:
    client = runtime["client"]
    marketer = runtime["headers"]["marketer"]
    reviewer = runtime["headers"]["reviewer"]
    campaign = create_campaign(client, marketer)
    creators = client.get("/api/v1/creators", headers=marketer)
    assert creators.status_code == 200, creators.text
    creator = creators.json()["items"][0]
    evidence = next(
        item
        for item in creator["evidence"]
        if item["match_kind"] == "exact_product"
        and item["product_id"] == campaign["product"]["id"]
    )
    payload = {"creator_id": creator["id"], "evidence_id": evidence["id"]}

    denied = client.post(
        f"/api/v1/campaigns/{campaign['id']}/creators",
        headers=reviewer,
        json=payload,
    )
    linked = client.post(
        f"/api/v1/campaigns/{campaign['id']}/creators",
        headers=marketer,
        json=payload,
    )
    replay = client.post(
        f"/api/v1/campaigns/{campaign['id']}/creators",
        headers=marketer,
        json=payload,
    )

    assert denied.status_code == 403
    assert linked.status_code == 200
    assert linked.json()["created"] is False
    assert linked.json()["evidence_id"] == evidence["id"]
    assert replay.status_code == 200
    assert replay.json() == linked.json()
    with runtime["owner"].session_factory() as session:
        assignment = session.scalar(
            select(CampaignCreator).where(
                CampaignCreator.campaign_id == UUID(campaign["id"]),
                CampaignCreator.creator_id == UUID(creator["id"]),
            )
        )
    assert assignment is not None
    assert assignment.evidence_id == UUID(evidence["id"])
    alternate = next(
        item for item in creator["evidence"] if item["id"] != evidence["id"]
    )
    with client.app.state.database.session_factory() as session:
        set_database_scope(
            session,
            organization_id=ACME_ORG_ID,
            user_id=MARKETER_USER_ID,
        )
        rewritten = session.execute(
            text(
                "update campaign_creators set evidence_id = :alternate "
                "where id = :assignment"
            ),
            {
                "alternate": UUID(alternate["id"]),
                "assignment": assignment.id,
            },
        )
        session.commit()
    assert rewritten.rowcount == 0
    with runtime["owner"].session_factory() as session:
        persisted_evidence_id = session.scalar(
            select(CampaignCreator.evidence_id).where(
                CampaignCreator.id == assignment.id
            )
        )
    assert persisted_evidence_id == UUID(evidence["id"])


def test_real_auth_private_media_review_and_deletion(runtime: dict[str, Any]) -> None:
    client = runtime["client"]
    marketer, reviewer = runtime["headers"]["marketer"], runtime["headers"]["reviewer"]
    discovery = client.get(
        "/api/v1/me/workspaces",
        headers={
            "Authorization": marketer["Authorization"],
        },
    )
    assert discovery.status_code == 200 and len(discovery.json()["items"]) == 1
    assert client.get("/api/v1/campaigns", headers=runtime["headers"]["revoked"]).status_code == 403
    campaign = create_campaign(client, marketer)
    submission = create_submission(client, marketer, campaign)
    version = submission["versions"][0]
    with runtime["owner"].session_factory() as session:
        asset = session.get(MediaAsset, UUID(version["asset_id"]))
        assert asset is not None and asset.object_bytes is None
        assert asset.storage_backend == "supabase" and asset.object_key
        asset_id = str(asset.id)
        object_key = asset.object_key
    content_url = f"/api/v1/uploads/{asset_id}/content"
    assert client.get(content_url, headers=reviewer).status_code == 200
    assert client.get(content_url, headers=runtime["headers"]["beta"]).status_code == 404
    settings = runtime["settings"]
    anonymous = httpx.get(
        f"{settings.supabase_url}/storage/v1/object/authenticated/vouch-media/{object_key}",
        headers={"apikey": settings.supabase_publishable_key},
        timeout=10,
    )
    assert anonymous.status_code != 200
    accepted = start_check(client, marketer, version["id"], "success", uuid4().hex)
    assert accepted.status_code == 202, accepted.text
    assert process_next_job(runtime["worker"])
    check_url = f"/api/v1/checks/{accepted.json()['resource_id']}"
    check_response = client.get(check_url, headers=reviewer)
    assert check_response.status_code == 200, check_response.text
    check = check_response.json()
    assert check["analysis_status"] == "completed", check
    finding = check["findings"][0]
    decision = client.post(
        f"/api/v1/findings/{finding['id']}/decisions",
        headers=reviewer,
        json={
            "decision": "dismissed",
            "rationale": "Synthetic evidence reviewed by a human.",
            "expected_review_version": 1,
        },
    )
    assert decision.status_code == 200, decision.text
    draft = client.post(
        f"{check_url}/fix-request-drafts",
        headers=marketer,
        json={"finding_ids": [finding["id"]]},
    )
    assert draft.status_code == 201, draft.text
    feedback_body = {
        "fix_request_draft_id": draft.json()["id"],
        "message": "Make the sponsorship cue explicit in the opening four seconds.",
        "start_ms": 0,
        "end_ms": 4000,
    }
    feedback_headers = {**marketer, "Idempotency-Key": f"feedback-{check['id']}"}
    published = client.post(
        f"{check_url}/creator-feedback",
        headers=feedback_headers,
        json=feedback_body,
    )
    assert published.status_code == 201, published.text
    replay = client.post(
        f"{check_url}/creator-feedback",
        headers=feedback_headers,
        json=feedback_body,
    )
    assert replay.status_code == 200 and replay.json() == published.json(), replay.text

    origin = runtime["settings"].guest_public_origin
    invitation = client.post(
        f"/api/v1/campaigns/{campaign['id']}/guest-invitations",
        headers=marketer,
        json={
            "creator_id": submission["creator_id"],
            "submission_id": submission["id"],
            "recovery_id": str(uuid4()),
        },
    )
    assert invitation.status_code == 201, invitation.text
    invitation_secret = invitation.json()["invitation_url"].partition("#invite=")[2]
    guest_client = TestClient(client.app, client=("feedback-guest", 50_006))
    try:
        exchanged = guest_client.post(
            "/api/v1/guest/exchange",
            headers={"Origin": origin},
            json={"invitation_secret": invitation_secret},
        )
        assert exchanged.status_code == 200, exchanged.text
        portal = guest_client.get(
            "/api/v1/guest/submission", headers={"Origin": origin}
        )
        assert portal.status_code == 200, portal.text
        assert portal.json()["feedback"] == [
            {
                "version_no": 1,
                "message": feedback_body["message"],
                "start_ms": 0,
                "end_ms": 4000,
                "invocation_mode": "fixture",
                "analysis_status": "completed",
                "manifest_hash": check["manifest_hash"],
                "published_at": published.json()["published_at"],
                "historical": False,
            }
        ]
    finally:
        guest_client.close()
    approval = client.post(
        f"{check_url}/review-decisions",
        headers=reviewer,
        json={
            "action": "approve",
            "expected_review_version": 2,
            "manifest_hash": check["manifest_hash"],
            "rationale": "Human exact-version decision.",
        },
    )
    assert approval.status_code == 200 and approval.json()["review_status"] == "approved", (
        approval.text
    )
    revision_asset = upload_asset(client, marketer, campaign["id"])
    revision = client.post(
        f"/api/v1/submissions/{submission['id']}/versions",
        headers=marketer,
        json={
            "asset_id": revision_asset["id"],
            "caption": "Authorized revision.",
            "rights_attested": True,
        },
    )
    assert revision.status_code == 201, revision.text
    assert client.get(check_url, headers=reviewer).json()["review_status"] == "superseded"
    deleted = client.post(
        "/api/v1/deletion-requests",
        headers=marketer,
        json={
            "resource_type": "submission",
            "resource_id": submission["id"],
        },
    )
    assert deleted.status_code == 202 and deleted.json()["status"] == "completed", deleted.text
    assert client.get(content_url, headers=reviewer).status_code == 404
    missing = httpx.get(
        f"{settings.supabase_url}/storage/v1/object/authenticated/vouch-media/{object_key}",
        headers={
            "apikey": settings.supabase_publishable_key,
            "Authorization": marketer["Authorization"],
        },
        timeout=10,
    )
    assert missing.status_code != 200
    with runtime["owner"].session_factory() as session:
        retained_feedback = session.get(CreatorFeedback, UUID(published.json()["id"]))
        assert retained_feedback is not None
        assert retained_feedback.message == ""
        assert retained_feedback.start_ms is None and retained_feedback.end_ms is None
        assert retained_feedback.manifest_hash == check["manifest_hash"]


def test_restricted_credentials_scope_pooling_and_revocation(runtime: dict[str, Any]) -> None:
    api_db = runtime["client"].app.state.database
    with runtime["owner"].session_factory() as session:
        user = session.get(User, MARKETER_USER_ID)
        assert user and user.auth_subject
        subject = user.auth_subject
    with api_db.session_factory() as session:
        assert not session.scalars(select(Campaign)).all()
        set_database_scope(
            session, auth_subject=subject, user_id=MARKETER_USER_ID, organization_id=ACME_ORG_ID
        )
        campaigns = session.scalars(select(Campaign)).all()
        assert campaigns and all(item.organization_id == ACME_ORG_ID for item in campaigns)
        session.commit()
        assert session.scalars(select(Campaign)).all()  # Scope reapplied after commit.
    with api_db.session_factory() as session:
        assert not session.scalars(select(Campaign)).all()  # No pool context leak.
        assert not session.scalars(select(User)).all()
        with pytest.raises(DBAPIError):
            session.execute(text("update users set auth_subject = null"))
        session.rollback()
    with runtime["worker"].session_factory() as session:
        with pytest.raises(DBAPIError):
            session.execute(text("insert into approvals(id) values (:id)"), {"id": uuid4()})
        session.rollback()
    with runtime["owner"].session_factory() as session:
        membership = session.scalar(
            select(Membership).where(
                Membership.user_id == MARKETER_USER_ID,
                Membership.organization_id == ACME_ORG_ID,
            )
        )
        assert membership
        membership.active = False
        session.commit()
        try:
            denied = runtime["client"].get(
                "/api/v1/campaigns", headers=runtime["headers"]["marketer"]
            )
            assert denied.status_code == 403
        finally:
            membership.active = True
            session.commit()


def test_local_signout_revokes_the_api_session(runtime: dict[str, Any]) -> None:
    credentials = json.loads((ROOT / ".local/credentials.json").read_text())
    settings = runtime["settings"]
    response = httpx.post(
        f"{settings.supabase_url}/auth/v1/token?grant_type=password",
        headers={"apikey": settings.supabase_publishable_key},
        json={"email": "viewer@vouch.test", "password": credentials["password"]},
        timeout=10,
    )
    assert response.status_code == 200
    headers = PrivateHeaders({"Authorization": f"Bearer {response.json()['access_token']}"})
    assert runtime["client"].get("/api/v1/me/workspaces", headers=headers).status_code == 200
    signed_out = httpx.post(
        f"{settings.supabase_url}/auth/v1/logout?scope=local",
        headers={
            **headers,
            "apikey": settings.supabase_publishable_key,
        },
        timeout=10,
    )
    assert signed_out.status_code == 204
    assert runtime["client"].get("/api/v1/me/workspaces", headers=headers).status_code == 401


def test_processing_authorization_withdrawal_under_real_auth_and_private_storage(
    runtime: dict[str, Any],
) -> None:
    client = runtime["client"]
    marketer = runtime["headers"]["marketer"]
    campaign = create_campaign(client, marketer)
    submission = create_submission(client, marketer, campaign)
    version = submission["versions"][0]
    assert version["authorization_status"] == "active"
    authorization = version["consent_receipt"]
    url = f"/api/v1/consent-receipts/{authorization['id']}"
    assert client.get(url, headers=marketer).json() == authorization
    assert client.get(url, headers=runtime["headers"]["beta"]).status_code == 404
    assert client.post(f"{url}/withdraw", headers=runtime["headers"]["reviewer"]).status_code == 403
    withdrawn = client.post(f"{url}/withdraw", headers=marketer)
    assert withdrawn.status_code == 202 and withdrawn.json()["status"] == "completed"
    repeated = client.post(f"{url}/withdraw", headers=marketer)
    assert repeated.status_code == 202 and repeated.json()["id"] == withdrawn.json()["id"]
    receipt = client.get(url, headers=marketer).json()
    assert receipt["revoked_by"] == str(MARKETER_USER_ID) and receipt["revoked_at"]
    assert receipt["revocation_reason"] == "withdrawn"
    assert receipt["revocation_actor_kind"] == "member"
    with runtime["owner"].session_factory() as session:
        stored = session.get(ConsentReceipt, UUID(authorization["id"]))
        assert stored and stored.revoked_at and stored.revocation_reason == "withdrawn"
        assert stored.actor_user_id == MARKETER_USER_ID
    assert client.get(
        f"/api/v1/uploads/{version['asset_id']}/content", headers=marketer
    ).status_code == 404


def test_real_guest_invitation_exchange_cookie_and_immediate_revocation(
    runtime: dict[str, Any],
) -> None:
    client = runtime["client"]
    marketer = runtime["headers"]["marketer"]
    origin = runtime["settings"].guest_public_origin
    campaign = create_campaign(client, marketer)
    submission = create_submission(client, marketer, campaign)
    invitation_payload = {
        "creator_id": campaign["creator_ids"][0],
        "submission_id": submission["id"],
        "recovery_id": str(uuid4()),
    }

    issued = client.post(
        f"/api/v1/campaigns/{campaign['id']}/guest-invitations",
        headers=marketer,
        json=invitation_payload,
    )
    assert issued.status_code == 201, issued.text
    invitation = issued.json()
    invitation_secret = invitation["invitation_url"].partition("#invite=")[2]
    assert invitation_secret

    exchanged = client.post(
        "/api/v1/guest/exchange",
        headers={"Origin": origin},
        json={"invitation_secret": invitation_secret},
    )
    assert exchanged.status_code == 200, exchanged.text
    session_secret = client.cookies.get("vouch_guest_session")
    assert session_secret

    context = client.get("/api/v1/guest/submission")
    assert context.status_code == 200, context.text
    assert context.json() == {
        "session_expires_at": exchanged.json()["expires_at"],
        "campaign": {
            "name": campaign["name"],
            "market": campaign["market"],
            "brand_name": "Acme Eyewear",
        },
        "creator": {"name": "Synthetic Creator", "handle": "@synthetic-creator"},
        "submission": {
            "current_version": {
                "version_no": 1,
                "caption": "New frames. Sponsored fixture draft.",
                "created_at": submission["versions"][0]["created_at"],
            },
            "review_state": "awaiting_brand_review",
            "approved_version_no": None,
        },
        "allowed_actions": [
            "read_submission",
            "upload_source",
            "submit_version",
        ],
        "feedback": [],
    }

    client.cookies.clear()
    replay = client.post(
        "/api/v1/guest/exchange",
        headers={"Origin": origin},
        json={"invitation_secret": invitation_secret},
    )
    assert replay.status_code == 401
    assert replay.json()["error"]["code"] == "GUEST_ACCESS_ENDED"
    client.cookies.set("vouch_guest_session", session_secret, path="/api/v1/guest")

    revoked = client.post(
        f"/api/v1/guest-invitations/{invitation['id']}/revoke",
        headers=marketer,
    )
    assert revoked.status_code == 202, revoked.text
    assert client.get("/api/v1/guest/submission").status_code == 401

    client.cookies.clear()
    issued_again = client.post(
        f"/api/v1/campaigns/{campaign['id']}/guest-invitations",
        headers=marketer,
        json=invitation_payload,
    )
    assert issued_again.status_code == 201, issued_again.text
    second_secret = issued_again.json()["invitation_url"].partition("#invite=")[2]
    exchanged_again = client.post(
        "/api/v1/guest/exchange",
        headers={"Origin": origin},
        json={"invitation_secret": second_secret},
    )
    assert exchanged_again.status_code == 200, exchanged_again.text

    with runtime["owner"].session_factory() as session:
        membership = session.scalar(
            select(Membership).where(
                Membership.user_id == MARKETER_USER_ID,
                Membership.organization_id == ACME_ORG_ID,
            )
        )
        assert membership
        membership.active = False
        session.commit()
        try:
            denied = client.get("/api/v1/guest/submission")
            assert denied.status_code == 401
            assert denied.json()["error"]["code"] == "GUEST_ACCESS_ENDED"
        finally:
            membership.active = True
            session.commit()


def test_real_guest_invitation_exchange_is_single_use_under_concurrency(
    runtime: dict[str, Any],
) -> None:
    client = runtime["client"]
    marketer = runtime["headers"]["marketer"]
    origin = runtime["settings"].guest_public_origin
    campaign = create_campaign(client, marketer)
    submission = create_submission(client, marketer, campaign)
    issued = client.post(
        f"/api/v1/campaigns/{campaign['id']}/guest-invitations",
        headers=marketer,
        json={
            "creator_id": campaign["creator_ids"][0],
            "submission_id": submission["id"],
            "recovery_id": str(uuid4()),
        },
    )
    assert issued.status_code == 201, issued.text
    invitation_secret = issued.json()["invitation_url"].partition("#invite=")[2]
    assert invitation_secret

    request_clients = [
        TestClient(client.app, client=("guest-race-a", 50_001)),
        TestClient(client.app, client=("guest-race-b", 50_002)),
    ]
    start = Barrier(3)

    def attempt_exchange(request_client: TestClient) -> httpx.Response:
        start.wait(timeout=5)
        try:
            return request_client.post(
                "/api/v1/guest/exchange",
                headers={"Origin": origin},
                json={"invitation_secret": invitation_secret},
            )
        finally:
            request_client.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(attempt_exchange, request_client) for request_client in request_clients
        ]
        start.wait(timeout=5)
        responses = [future.result(timeout=10) for future in futures]

    accepted = [response for response in responses if response.status_code == 200]
    denied = [response for response in responses if response.status_code == 401]
    assert len(accepted) == 1
    assert len(denied) == 1

    control_client = TestClient(client.app, client=("guest-race-control", 50_003))
    try:
        invalid = control_client.post(
            "/api/v1/guest/exchange",
            headers={"Origin": origin},
            json={"invitation_secret": "x" * 43},
        )
    finally:
        control_client.close()

    def safe_denial(response: httpx.Response) -> tuple[int, str, str, bool]:
        error = response.json()["error"]
        return response.status_code, error["code"], error["message"], error["retryable"]

    concurrent_denial = safe_denial(denied[0])
    assert concurrent_denial == safe_denial(invalid)
    assert (concurrent_denial[0], concurrent_denial[1], concurrent_denial[3]) == (
        401,
        "GUEST_ACCESS_ENDED",
        False,
    )


def test_real_guest_initial_draft_uses_restricted_database_and_private_storage(
    runtime: dict[str, Any],
) -> None:
    client = runtime["client"]
    marketer = runtime["headers"]["marketer"]
    origin = runtime["settings"].guest_public_origin
    campaign = create_campaign(client, marketer)

    issued = client.post(
        f"/api/v1/campaigns/{campaign['id']}/guest-invitations",
        headers=marketer,
        json={
            "creator_id": campaign["creator_ids"][0],
            "recovery_id": str(uuid4()),
        },
    )
    assert issued.status_code == 201, issued.text
    invitation = issued.json()
    assert invitation["allowed_actions"] == [
        "read_submission",
        "upload_source",
        "submit_version",
    ]
    invitation_secret = invitation["invitation_url"].partition("#invite=")[2]
    assert invitation_secret
    exchanged = client.post(
        "/api/v1/guest/exchange",
        headers={"Origin": origin},
        json={"invitation_secret": invitation_secret},
    )
    assert exchanged.status_code == 200, exchanged.text

    notice_response = client.get("/api/v1/guest/notices/campaign-check")
    assert notice_response.status_code == 200, notice_response.text
    notice = notice_response.json()
    intent = client.post(
        "/api/v1/guest/uploads",
        headers={"Origin": origin, "Idempotency-Key": str(uuid4())},
        json={
            "filename": "authenticated-creator-draft.mp4",
            "content_type": "video/mp4",
            "byte_size": len(MP4),
            "rights_attested": True,
            "notice_version": notice["version"],
            "notice_acknowledged": True,
            "purpose": "campaign_check",
        },
    )
    assert intent.status_code == 201, intent.text
    upload = intent.json()
    stored = client.put(
        upload["content_url"],
        headers={
            "Origin": origin,
            "Content-Type": "video/mp4",
            "X-Upload-Token": upload["upload_token"],
        },
        content=MP4,
    )
    assert stored.status_code == 200, stored.text
    finalized = client.post(
        upload["finalize_url"],
        headers={"Origin": origin},
        json={"finalize_token": upload["finalize_token"]},
    )
    assert finalized.status_code == 200, finalized.text
    replayed_store = client.put(
        upload["content_url"],
        headers={
            "Origin": origin,
            "Content-Type": "video/mp4",
            "X-Upload-Token": upload["upload_token"],
        },
        content=MP4,
    )
    assert replayed_store.status_code == 200, replayed_store.text
    assert replayed_store.json() == stored.json()
    changed_replay = client.put(
        upload["content_url"],
        headers={
            "Origin": origin,
            "Content-Type": "video/mp4",
            "X-Upload-Token": upload["upload_token"],
        },
        content=MP4[:-1] + b"x",
    )
    assert changed_replay.status_code == 409
    assert changed_replay.json()["error"]["code"] == "UPLOAD_CONTENT_CONFLICT"
    version = client.post(
        "/api/v1/guest/submission-versions",
        headers={"Origin": origin, "Idempotency-Key": str(uuid4())},
        json={
            "asset_id": upload["upload_id"],
            "caption": "Authenticated creator-owned first draft.",
            "expected_current_version_id": None,
        },
    )
    assert version.status_code == 201, version.text

    with runtime["owner"].session_factory() as session:
        asset = session.get(MediaAsset, UUID(upload["upload_id"]))
        receipt = session.get(ConsentReceipt, UUID(upload["consent_receipt"]["id"]))
        stored_version = session.get(SubmissionVersion, UUID(version.json()["id"]))
        assert asset and receipt and stored_version
        assert asset.storage_backend == "supabase" and asset.object_bytes is None
        assert asset.status == "validated"
        assert asset.uploader_user_id is None and asset.uploader_guest_session_id
        assert receipt.actor_user_id is None
        assert receipt.actor_guest_session_id == asset.uploader_guest_session_id
        assert stored_version.uploader_user_id is None
        assert stored_version.uploader_guest_session_id == asset.uploader_guest_session_id


def test_real_guest_storage_write_is_fenced_from_member_deletion(
    runtime: dict[str, Any],
) -> None:
    client = runtime["client"]
    marketer = runtime["headers"]["marketer"]
    origin = runtime["settings"].guest_public_origin
    campaign = create_campaign(client, marketer)
    issued = client.post(
        f"/api/v1/campaigns/{campaign['id']}/guest-invitations",
        headers=marketer,
        json={
            "creator_id": campaign["creator_ids"][0],
            "recovery_id": str(uuid4()),
        },
    )
    assert issued.status_code == 201, issued.text
    invitation_secret = issued.json()["invitation_url"].partition("#invite=")[2]
    assert invitation_secret
    exchanged = client.post(
        "/api/v1/guest/exchange",
        headers={"Origin": origin},
        json={"invitation_secret": invitation_secret},
    )
    assert exchanged.status_code == 200, exchanged.text
    guest_cookie = client.cookies.get("vouch_guest_session")
    assert guest_cookie

    notice_response = client.get("/api/v1/guest/notices/campaign-check")
    assert notice_response.status_code == 200, notice_response.text
    notice = notice_response.json()
    intent = client.post(
        "/api/v1/guest/uploads",
        headers={"Origin": origin, "Idempotency-Key": str(uuid4())},
        json={
            "filename": "deletion-race.mp4",
            "content_type": "video/mp4",
            "byte_size": len(MP4),
            "rights_attested": True,
            "notice_version": notice["version"],
            "notice_acknowledged": True,
            "purpose": "campaign_check",
        },
    )
    assert intent.status_code == 201, intent.text
    upload = intent.json()
    asset_id = UUID(upload["upload_id"])
    with runtime["owner"].session_factory() as session:
        asset = session.get(MediaAsset, asset_id)
        assert asset is not None and asset.object_key is not None
        object_key = asset.object_key

    app = client.app
    original_guest_store = app.state.guest_media_store
    cleanup_store = app.state.media_store
    assert original_guest_store is not None and cleanup_store is not None
    entered = Event()
    release = Event()
    app.state.guest_media_store = PausedGuestUploadStore(
        original_guest_store,
        entered,
        release,
    )
    guest_client = TestClient(app, client=("guest-upload-race", 50_004))
    member_client = TestClient(app, client=("member-delete-race", 50_005))
    guest_client.cookies.set("vouch_guest_session", guest_cookie, path="/api/v1/guest")
    deletion_was_blocked = False
    deletion_response: httpx.Response | None = None
    upload_response: httpx.Response | None = None
    remote_present_after_deletion = True
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            upload_future = executor.submit(
                guest_client.put,
                upload["content_url"],
                headers={
                    "Origin": origin,
                    "Content-Type": "video/mp4",
                    "X-Upload-Token": upload["upload_token"],
                },
                content=MP4,
            )
            assert entered.wait(timeout=5), "Guest Storage upload did not reach the race gate."
            deletion_future = executor.submit(
                member_client.post,
                "/api/v1/deletion-requests",
                headers=marketer,
                json={"resource_type": "media_asset", "resource_id": str(asset_id)},
            )
            try:
                deletion_response = deletion_future.result(timeout=0.5)
            except FutureTimeoutError:
                deletion_was_blocked = True
            finally:
                release.set()
            upload_response = upload_future.result(timeout=15)
            deletion_response = deletion_response or deletion_future.result(timeout=15)
        try:
            original_guest_store.download(object_key)
        except ApiError as error:
            assert error.status_code == 404
            remote_present_after_deletion = False
    finally:
        release.set()
        app.state.guest_media_store = original_guest_store
        guest_client.close()
        member_client.close()
        with suppress(ApiError):
            cleanup_store.delete(object_key)

    assert deletion_was_blocked
    assert upload_response is not None and upload_response.status_code == 200
    assert deletion_response is not None and deletion_response.status_code == 202
    assert deletion_response.json()["status"] == "completed"
    assert remote_present_after_deletion is False


def test_real_guest_renewal_preserves_consumed_upload_quota(
    runtime: dict[str, Any],
) -> None:
    client = runtime["client"]
    marketer = runtime["headers"]["marketer"]
    origin = runtime["settings"].guest_public_origin
    campaign = create_campaign(client, marketer)
    issued = client.post(
        f"/api/v1/campaigns/{campaign['id']}/guest-invitations",
        headers=marketer,
        json={
            "creator_id": campaign["creator_ids"][0],
            "recovery_id": str(uuid4()),
        },
    )
    assert issued.status_code == 201, issued.text
    invitation = issued.json()
    invitation_secret = invitation["invitation_url"].partition("#invite=")[2]
    assert invitation_secret
    exchanged = client.post(
        "/api/v1/guest/exchange",
        headers={"Origin": origin},
        json={"invitation_secret": invitation_secret},
    )
    assert exchanged.status_code == 200, exchanged.text
    prior_session_secret = client.cookies.get("vouch_guest_session")
    assert prior_session_secret

    notice_response = client.get("/api/v1/guest/notices/campaign-check")
    assert notice_response.status_code == 200, notice_response.text
    notice = notice_response.json()
    intent = client.post(
        "/api/v1/guest/uploads",
        headers={"Origin": origin, "Idempotency-Key": str(uuid4())},
        json={
            "filename": "renewal-quota.mp4",
            "content_type": "video/mp4",
            "byte_size": len(MP4),
            "rights_attested": True,
            "notice_version": notice["version"],
            "notice_acknowledged": True,
            "purpose": "campaign_check",
        },
    )
    assert intent.status_code == 201, intent.text
    upload = intent.json()
    stored = client.put(
        upload["content_url"],
        headers={
            "Origin": origin,
            "Content-Type": "video/mp4",
            "X-Upload-Token": upload["upload_token"],
        },
        content=MP4,
    )
    assert stored.status_code == 200, stored.text
    finalized = client.post(
        upload["finalize_url"],
        headers={"Origin": origin},
        json={"finalize_token": upload["finalize_token"]},
    )
    assert finalized.status_code == 200, finalized.text

    with runtime["owner"].session_factory() as session:
        prior = session.get(GuestGrant, UUID(invitation["id"]))
        assert prior is not None
        assert prior.source_count == 1
        assert prior.reserved_bytes == len(MP4)

    client.cookies.clear()
    renewed_response = client.post(
        f"/api/v1/guest-invitations/{invitation['id']}/renew",
        headers=marketer,
    )
    assert renewed_response.status_code == 201, renewed_response.text
    renewed = renewed_response.json()
    assert renewed["allowed_actions"] == invitation["allowed_actions"]

    with runtime["owner"].session_factory() as session:
        prior = session.get(GuestGrant, UUID(invitation["id"]))
        replacement = session.get(GuestGrant, UUID(renewed["id"]))
        assert prior is not None and replacement is not None
        assert prior.revoked_at is not None
        assert replacement.source_count == prior.source_count == 1
        assert replacement.reserved_bytes == prior.reserved_bytes == len(MP4)

    client.cookies.set("vouch_guest_session", prior_session_secret, path="/api/v1/guest")
    assert client.get("/api/v1/guest/submission").status_code == 401
    client.cookies.clear()


def test_real_guest_renewal_preserves_legacy_read_only_capability(
    runtime: dict[str, Any],
) -> None:
    client = runtime["client"]
    marketer = runtime["headers"]["marketer"]
    campaign = create_campaign(client, marketer)
    submission = create_submission(client, marketer, campaign)
    issued = client.post(
        f"/api/v1/campaigns/{campaign['id']}/guest-invitations",
        headers=marketer,
        json={
            "creator_id": campaign["creator_ids"][0],
            "submission_id": submission["id"],
            "recovery_id": str(uuid4()),
        },
    )
    assert issued.status_code == 201, issued.text
    invitation = issued.json()

    with runtime["owner"].session_factory() as session:
        legacy = session.get(GuestGrant, UUID(invitation["id"]))
        assert legacy is not None
        legacy.allowed_actions = ["read_submission"]
        session.commit()

    renewed_response = client.post(
        f"/api/v1/guest-invitations/{invitation['id']}/renew",
        headers=marketer,
    )
    assert renewed_response.status_code == 201, renewed_response.text
    renewed = renewed_response.json()
    assert renewed["allowed_actions"] == ["read_submission"]

    with runtime["owner"].session_factory() as session:
        prior = session.get(GuestGrant, UUID(invitation["id"]))
        replacement = session.get(GuestGrant, UUID(renewed["id"]))
        assert prior is not None and replacement is not None
        assert prior.revoked_at is not None
        assert replacement.allowed_actions == ["read_submission"]
        assert replacement.source_count == 0
        assert replacement.reserved_bytes == 0
