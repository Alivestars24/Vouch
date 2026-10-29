from __future__ import annotations

import os
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from test_workflow import (
    MP4,
    NOTICE_ACKNOWLEDGMENT,
    create_campaign,
    create_submission,
    start_check,
)

from vouch_backend import media, service
from vouch_backend.errors import ApiError
from vouch_backend.media import (
    FixtureMediaProcessor,
    PreparedMedia,
    ProcessedMedia,
    SourceTimeMapping,
)
from vouch_backend.models import (
    Campaign,
    DeletionRequest,
    MediaAsset,
    Membership,
    RulePackVersion,
    SubmissionVersion,
    utcnow,
)
from vouch_backend.retention import reconcile_once
from vouch_backend.schemas import CheckCreate, DeletionRequestCreate
from vouch_backend.service import (
    RetentionActor,
    _erase_source,
    _manifest,
    sha256_bytes,
    stable_hash,
)
from vouch_backend.worker import process_next_job


class DecodedDouble(FixtureMediaProcessor):
    mode = "decoded"
    processor_version = "decoded-test-v1"

    def process(
        self, body: bytes, content_type: str, prepared: PreparedMedia | None = None,
    ) -> ProcessedMedia:
        assert content_type == "video/mp4" and body == MP4
        return ProcessedMedia(
            mode="decoded",
            processor_version=self.processor_version,
            duration_ms=250,
            width=160,
            height=90,
            frame_rate=24.0,
            audio_present=False,
            normalized_sha256="a" * 64,
            image_digest="sha256:" + "b" * 64,
            source_time_mapping=SourceTimeMapping(),
        )


def uploaded(
    client: TestClient,
    headers: dict[str, str],
    *,
    body: bytes = MP4,
) -> tuple[dict[str, Any], dict[str, Any]]:
    campaign = create_campaign(client, headers)
    response = client.post(
        "/api/v1/uploads",
        headers=headers,
        json={
            "campaign_id": campaign["id"],
            "filename": "private-original.mp4",
            **NOTICE_ACKNOWLEDGMENT,
            "content_type": "video/mp4",
            "byte_size": len(body),
            "rights_attested": True,
        },
    )
    assert response.status_code == 201, response.text
    intent = response.json()
    response = client.put(
        intent["content_url"],
        headers={
            **headers,
            "Content-Type": "video/mp4",
            "X-Upload-Token": intent["upload_token"],
        },
        content=body,
    )
    assert response.status_code == 200, response.text
    return campaign, intent


def finalize(client: TestClient, headers: dict[str, str], intent: dict[str, Any]) -> Any:
    return client.post(
        f"/api/v1/uploads/{intent['upload_id']}/finalize",
        headers=headers,
        json={"finalize_token": intent["finalize_token"]},
    )


def test_decoded_metadata_and_original_hash_are_persisted_without_changing_provider_mode(
    client: TestClient,
    marketer_headers: dict[str, str],
) -> None:
    client.app.state.media_processor = DecodedDouble()
    campaign, intent = uploaded(client, marketer_headers)
    with client.app.state.database.session_factory() as session:
        asset = session.get(MediaAsset, UUID(intent["upload_id"]))
        assert asset is not None and asset.sha256 == sha256_bytes(MP4)
    result = finalize(client, marketer_headers, intent)
    assert result.status_code == 200, result.text
    asset_json = result.json()
    assert asset_json["sha256"] == sha256_bytes(MP4) and asset_json["duration_ms"] == 250
    assert asset_json["processing_metadata"]["normalized_sha256"] == "a" * 64
    assert asset_json["processing_metadata"]["mode"] == "decoded"
    assert finalize(client, marketer_headers, intent).json() == asset_json
    caps = client.get("/api/v1/capabilities", headers=marketer_headers).json()
    assert caps["invocation_mode"] == "fixture"
    assert caps["media_processing"] == {"mode": "decoded", "processor_version": "decoded-test-v1"}
    response = client.post(
        f"/api/v1/campaigns/{campaign['id']}/submissions",
        headers=marketer_headers,
        json={
            "asset_id": asset_json["id"],
            "creator_id": campaign["creator_ids"][0],
            "caption": "Synthetic",
            "rights_attested": True,
        },
    )
    assert response.status_code == 201, response.text
    version = response.json()["versions"][0]
    assert (
        version["duration_ms"] == 250
        and version["media_processing"] == asset_json["processing_metadata"]
    )
    check = start_check(client, marketer_headers, version["id"], "partial_voice", "decoded-short")
    assert check.status_code == 202 and process_next_job(client.app.state.database)
    result = client.get(f"/api/v1/checks/{check.json()['resource_id']}", headers=marketer_headers)
    assert result.status_code == 200, result.text
    payload = result.json()
    assert payload["analysis_status"] == "partial"
    for evidence in payload["evidence"]:
        if evidence["start_ms"] is not None:
            assert 0 <= evidence["start_ms"] <= evidence["end_ms"] <= 250
    for finding in payload["findings"]:
        if finding["time_range"] is not None:
            assert 0 <= finding["time_range"]["start_ms"] <= finding["time_range"]["end_ms"] <= 250


def test_decode_failure_never_falls_back_to_a_fixture_success(
    client: TestClient,
    marketer_headers: dict[str, str],
) -> None:
    class Failing(DecodedDouble):
        def process(
            self, body: bytes, content_type: str, prepared: PreparedMedia | None = None,
        ) -> ProcessedMedia:
            raise ApiError(422, "MEDIA_VALIDATION_FAILED", "Media validation failed.")

    client.app.state.media_processor = Failing()
    _, intent = uploaded(client, marketer_headers)
    response = finalize(client, marketer_headers, intent)
    assert (
        response.status_code == 422
        and response.json()["error"]["code"] == "MEDIA_VALIDATION_FAILED"
    )
    with client.app.state.database.session_factory() as session:
        asset = session.get(MediaAsset, UUID(intent["upload_id"]))
        assert asset is not None and asset.status == "content_uploaded"
        assert asset.processing_metadata == {} and asset.duration_ms is None


def test_invalid_signature_is_rejected_before_decoding(
    client: TestClient,
    marketer_headers: dict[str, str],
) -> None:
    class NeverCalled(DecodedDouble):
        def process(
            self, body: bytes, content_type: str, prepared: PreparedMedia | None = None,
        ) -> ProcessedMedia:
            raise AssertionError("Invalid media reached the processor")

    client.app.state.media_processor = NeverCalled()
    _, intent = uploaded(client, marketer_headers, body=b"not an mp4 file")
    assert finalize(client, marketer_headers, intent).status_code == 415


def test_deletion_commits_while_decoder_is_paused_and_wins_late_publication(
    client: TestClient,
    marketer_headers: dict[str, str],
) -> None:
    entered, release = threading.Event(), threading.Event()

    class Paused(DecodedDouble):
        def process(
            self, body: bytes, content_type: str, prepared: PreparedMedia | None = None,
        ) -> ProcessedMedia:
            entered.set()
            assert release.wait(10)
            return super().process(body, content_type)

    client.app.state.media_processor = Paused()
    _, intent = uploaded(client, marketer_headers)
    with ThreadPoolExecutor(max_workers=2) as executor:
        decoding = executor.submit(finalize, client, marketer_headers, intent)
        try:
            assert entered.wait(5)
            deleting = executor.submit(
                client.post,
                "/api/v1/deletion-requests",
                headers=marketer_headers,
                json={"resource_type": "media_asset", "resource_id": intent["upload_id"]},
            )
            deletion = deleting.result(timeout=5)
            assert deletion.status_code == 202 and deletion.json()["status"] == "completed"
        finally:
            release.set()
        assert decoding.result(timeout=5).status_code == 404
    with client.app.state.database.session_factory() as session:
        asset = session.get(MediaAsset, UUID(intent["upload_id"]))
        assert asset is not None and asset.status == "deleted" and asset.object_bytes is None
        assert asset.processing_metadata == {} and asset.duration_ms is None


@pytest.mark.parametrize(
    "mutation,expected",
    [
        ("membership", 403),
        ("rights", 422),
        ("retention", 409),
        ("authorization", 401),
        ("bytes", 409),
    ],
)
def test_finalization_rechecks_current_authority_and_source_after_processing(
    client: TestClient,
    marketer_headers: dict[str, str],
    mutation: str,
    expected: int,
) -> None:
    _, intent = uploaded(client, marketer_headers)

    class Mutating(DecodedDouble):
        def process(
            self, body: bytes, content_type: str, prepared: PreparedMedia | None = None,
        ) -> ProcessedMedia:
            with client.app.state.database.session_factory() as session:
                asset = session.get(MediaAsset, UUID(intent["upload_id"]))
                assert asset is not None
                if mutation == "membership":
                    membership = session.scalar(
                        select(Membership).where(
                            Membership.user_id == asset.uploader_user_id,
                            Membership.organization_id == asset.organization_id,
                        )
                    )
                    assert membership is not None
                    membership.active = False
                elif mutation == "rights":
                    asset.rights_attested = False
                elif mutation == "retention":
                    asset.retention_deadline = utcnow() - timedelta(seconds=1)
                elif mutation == "authorization":
                    asset.created_at = utcnow() - timedelta(minutes=6)
                else:
                    asset.object_bytes = MP4 + b"changed"
                session.commit()
            return super().process(body, content_type)

    client.app.state.media_processor = Mutating()
    response = finalize(client, marketer_headers, intent)
    assert response.status_code == expected, response.text
    with client.app.state.database.session_factory() as session:
        asset = session.get(MediaAsset, UUID(intent["upload_id"]))
        assert asset is not None and asset.status != "validated" and asset.processing_metadata == {}


def test_legacy_empty_metadata_keeps_its_original_manifest_binding(
    client: TestClient,
    marketer_headers: dict[str, str],
) -> None:
    campaign = create_campaign(client, marketer_headers)
    submission = create_submission(client, marketer_headers, campaign)
    with client.app.state.database.session_factory() as session:
        version = session.get(SubmissionVersion, UUID(submission["versions"][0]["id"]))
        stored_campaign = session.get(Campaign, UUID(campaign["id"]))
        assert version is not None and stored_campaign is not None
        asset = session.get(MediaAsset, version.asset_id)
        pack = session.get(RulePackVersion, stored_campaign.rule_pack_version_id)
        assert asset is not None and pack is not None
        measured = asset.processing_metadata
        asset.processing_metadata = {}
        old = _manifest(version, asset, stored_campaign, pack, CheckCreate(scenario="clean"))
        assert "media_processing" not in old
        old_hash = stable_hash(old)
        asset.processing_metadata = measured
        new = _manifest(version, asset, stored_campaign, pack, CheckCreate(scenario="clean"))
        assert new["media_processing"] == measured and stable_hash(new) != old_hash
        assert (
            stable_hash({key: value for key, value in new.items() if key != "media_processing"})
            == old_hash
        )


def test_sandbox_cleanup_failure_stays_partial_and_retryable(
    client: TestClient, marketer_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, intent = uploaded(client, marketer_headers)
    database = client.app.state.database
    with database.session_factory() as session:
        asset = session.get(MediaAsset, UUID(intent["upload_id"]))
        assert asset is not None
        name = f"vouch-media-{asset.organization_id.hex}-{asset.id.hex}-{uuid4().hex}"
        asset.processing_container = name
        session.commit()
    unavailable = True

    def cleanup(container: str, organization_id: UUID) -> None:
        assert container == name and str(organization_id) == marketer_headers["X-Organization-Id"]
        if unavailable:
            raise ApiError(503, "MEDIA_PROCESSOR_UNAVAILABLE", "Cleanup remains unconfirmed.", True)

    monkeypatch.setattr(service, "remove_sandbox_container", cleanup)
    payload = {"resource_type": "media_asset", "resource_id": intent["upload_id"]}
    partial = client.post("/api/v1/deletion-requests", headers=marketer_headers, json=payload)
    assert partial.status_code == 202 and partial.json()["status"] == "partial"
    assert partial.json()["completed_at"] is None
    assert partial.json()["last_error_code"] == "MEDIA_CLEANUP_PENDING"
    unavailable = False
    completed = client.post("/api/v1/deletion-requests", headers=marketer_headers, json=payload)
    assert completed.json()["id"] == partial.json()["id"]
    assert completed.json()["status"] == "completed"
    assert completed.json()["destinations"][-1]["destination"] == "local_media_sandbox"
    assert completed.json()["destinations"][-1]["status"] == "completed"


@pytest.mark.parametrize("tamper", ["name", "active_asset"])
def test_receipt_json_cannot_cancel_a_different_live_assets_sandbox(
    client: TestClient, marketer_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch,
    tamper: str,
) -> None:
    _, old_intent = uploaded(client, marketer_headers)
    _, live_intent = uploaded(client, marketer_headers)
    database = client.app.state.database
    org_id = UUID(marketer_headers["X-Organization-Id"])
    with database.session_factory() as session:
        expired = session.get(MediaAsset, UUID(old_intent["upload_id"]))
        live = session.get(MediaAsset, UUID(live_intent["upload_id"]))
        assert expired is not None and live is not None
        expired.retention_deadline = utcnow() - timedelta(seconds=1)
        expired.processing_container = f"vouch-media-{org_id.hex}-{expired.id.hex}-{uuid4().hex}"
        live.processing_container = f"vouch-media-{org_id.hex}-{live.id.hex}-{uuid4().hex}"
        live_name = live.processing_container
        session.commit()
        receipt = _erase_source(session, RetentionActor(org_id), DeletionRequestCreate(
            resource_type="media_asset", resource_id=expired.id,
        ))
        targets = [dict(item) for item in receipt.destinations]
        targets[-1]["container_names"] = [live_name]
        if tamper == "active_asset":
            targets[-1]["asset_ids"] = [str(live.id)]
        receipt.destinations = targets
        session.commit()
    calls: list[str] = []
    monkeypatch.setattr(service, "remove_sandbox_container", lambda name, org: calls.append(name))
    assert reconcile_once(database)
    assert not calls
    with database.session_factory() as session:
        current = session.get(DeletionRequest, receipt.id)
        live = session.get(MediaAsset, UUID(live_intent["upload_id"]))
        assert current is not None and current.status == "partial" and current.completed_at is None
        assert live is not None and live.status == "content_uploaded" and live.object_bytes == MP4


@pytest.mark.skipif(os.getenv("VOUCH_TEST_MEDIA") != "1", reason="Opt-in real Docker cancellation.")
@pytest.mark.parametrize("phase", ["before_start", "with_input_copy"])
def test_real_container_deletion_blocks_late_start_and_erases_inflight_copy(
    client: TestClient, marketer_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch,
    phase: str,
) -> None:
    entered, release = threading.Event(), threading.Event()

    class PausedDocker(media.DockerMediaProcessor):
        def process(
            self, body: bytes, content_type: str, prepared: PreparedMedia | None = None,
        ) -> ProcessedMedia:
            if phase == "before_start":
                entered.set()
                assert release.wait(15)
            return super().process(body, content_type, prepared)

    def paused_input(
        command: list[str], body: bytes, timeout: float, cleanup: Any,
    ) -> bytes:
        # The real wrapper waits for EOF. Its running container holds the input copy until
        # deletion force-removes it; no untrusted host decoder or real personal video is used.
        process = subprocess.Popen(
            command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        )
        try:
            assert process.stdin is not None
            process.stdin.write(body)
            process.stdin.flush()
            entered.set()
            assert release.wait(15)
            process.wait(timeout=5)
            return b"{}"  # Cancelled work cannot publish a validated result.
        finally:
            if process.poll() is None:
                cleanup()
                process.kill()
                process.wait(timeout=5)
            if process.stdin is not None:
                process.stdin.close()
            if process.stdout is not None:
                process.stdout.close()

    client.app.state.media_processor = PausedDocker()
    if phase == "with_input_copy":
        monkeypatch.setattr(media, "_run_bounded", paused_input)
    _, intent = uploaded(client, marketer_headers)
    with ThreadPoolExecutor(max_workers=2) as executor:
        decoding = executor.submit(finalize, client, marketer_headers, intent)
        try:
            assert entered.wait(15)
            deleted = client.post("/api/v1/deletion-requests", headers=marketer_headers, json={
                "resource_type": "media_asset", "resource_id": intent["upload_id"],
            })
            assert deleted.status_code == 202 and deleted.json()["status"] == "completed"
            assert deleted.json()["destinations"][-1]["status"] == "completed"
        finally:
            release.set()
        response = decoding.result(timeout=15)
        assert response.status_code in {404, 422}, response.text
    with client.app.state.database.session_factory() as session:
        asset = session.get(MediaAsset, UUID(intent["upload_id"]))
        assert asset is not None and asset.status == "deleted" and asset.processing_metadata == {}
        assert asset.processing_container is not None
        media.remove_sandbox_container(asset.processing_container, asset.organization_id)
