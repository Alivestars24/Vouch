from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from threading import Event
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from test_workflow import create_campaign, create_submission, start_check, upload_asset

from vouch_backend import service
from vouch_backend.config import Settings
from vouch_backend.models import Base, CampaignCreator, Organization, SubmissionVersion
from vouch_backend.seed import ACME_CREATOR_ID, BETA_ORG_ID
from vouch_backend.worker import claim_next_job


def test_concurrent_workers_cannot_claim_the_same_job(
    client: TestClient, marketer_headers: dict[str, str]
) -> None:
    campaign = create_campaign(client, marketer_headers)
    submission = create_submission(client, marketer_headers, campaign)
    accepted = start_check(
        client, marketer_headers, submission["versions"][0]["id"], "success", "concurrent-claim"
    )
    assert accepted.status_code == 202

    def claim(index: int) -> object:
        return claim_next_job(client.app.state.database, f"concurrent-worker-{index}")

    with ThreadPoolExecutor(max_workers=4) as pool:
        claims = list(pool.map(claim, range(4)))
    assert sum(item is not None for item in claims) == 1
    job = client.get(accepted.json()["status_url"], headers=marketer_headers).json()
    assert job["attempt_count"] == 1


def test_concurrent_budget_reservations_do_not_overspend(
    client: TestClient, marketer_headers: dict[str, str]
) -> None:
    campaign = create_campaign(client, marketer_headers)
    submission = create_submission(client, marketer_headers, campaign)
    with client.app.state.database.session_factory() as session:
        organization = session.get(Organization, UUID(marketer_headers["X-Organization-Id"]))
        assert organization is not None
        organization.budget_cap_minor = 25
        session.commit()

    def enqueue(scenario: str) -> int:
        return start_check(
            client, marketer_headers, submission["versions"][0]["id"], scenario, uuid4().hex
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(enqueue, ["success", "partial_voice"]))
    assert sorted(statuses) == [202, 429]
    with client.app.state.database.session_factory() as session:
        organization = session.get(Organization, UUID(marketer_headers["X-Organization-Id"]))
        assert organization is not None
        assert organization.budget_held_minor == 25


def test_composite_foreign_keys_reject_cross_tenant_parent(
    client: TestClient, marketer_headers: dict[str, str]
) -> None:
    campaign = create_campaign(client, marketer_headers)
    with client.app.state.database.session_factory() as session:
        session.add(
            CampaignCreator(
                organization_id=BETA_ORG_ID,
                campaign_id=UUID(campaign["id"]),
                creator_id=ACME_CREATOR_ID,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_fixture_identity_fails_closed_in_deployed_environments() -> None:
    with pytest.raises(ValueError, match="fixture identity"):
        Settings(database_url="sqlite:///:memory:", environment="production")


def test_production_requires_https_supabase_runtime() -> None:
    with pytest.raises(ValueError, match="Production CORS origins"):
        Settings(
            auth_mode="supabase",
            environment="production",
            database_url="postgresql://api:secret@db.example.test/postgres",
            supabase_url="https://project.supabase.co",
            supabase_publishable_key="publishable-test-key",
            cors_origins=("https://app.example.test", "http://preview.example.test"),
            guest_public_origin="https://app.example.test",
        )

    settings = Settings(
        auth_mode="supabase",
        environment="production",
        database_url="postgresql://api:secret@db.example.test/postgres",
        supabase_url="https://project.supabase.co",
        supabase_publishable_key="publishable-test-key",
        cors_origins=("https://app.example.test",),
        guest_public_origin="https://app.example.test",
    )
    assert settings.environment == "production"


def test_postgres_migration_matches_runtime_columns(client: TestClient) -> None:
    database = client.app.state.database
    if database.is_sqlite:
        pytest.skip("Requires the opt-in local Supabase PostgreSQL test run.")
    inspector = inspect(database.engine)
    for table in Base.metadata.sorted_tables:
        actual_columns = {
            column["name"] for column in inspector.get_columns(table.name, schema="vouch")
        }
        assert actual_columns == {column.name for column in table.columns}, table.name


def test_deletion_waits_for_inflight_attachment_and_erases_its_caption(
    client: TestClient, marketer_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    if client.app.state.database.is_sqlite:
        pytest.skip("PostgreSQL advisory-lock concurrency proof; SQLite serializes writes.")
    campaign = create_campaign(client, marketer_headers)
    asset = upload_asset(client, marketer_headers, campaign["id"])
    validated, release_writer, deletion_started = Event(), Event(), Event()
    original = service._validated_asset

    def pause_after_validation(*args: object, **kwargs: object) -> object:
        result = original(*args, **kwargs)  # type: ignore[arg-type]
        validated.set()
        assert release_writer.wait(10)
        return result

    monkeypatch.setattr(service, "_validated_asset", pause_after_validation)

    def attach() -> object:
        return client.post(
            f"/api/v1/campaigns/{campaign['id']}/submissions",
            headers=marketer_headers,
            json={
                "asset_id": asset["id"],
                "creator_id": campaign["creator_ids"][0],
                "caption": "Concurrent private caption",
                "rights_attested": True,
            },
        )

    def delete() -> object:
        deletion_started.set()
        return client.post(
            "/api/v1/deletion-requests",
            headers=marketer_headers,
            json={"resource_type": "media_asset", "resource_id": asset["id"]},
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        attachment = pool.submit(attach)
        try:
            assert validated.wait(10)
            deletion = pool.submit(delete)
            assert deletion_started.wait(10)
            with pytest.raises(FutureTimeout):
                deletion.result(timeout=0.25)
        finally:
            release_writer.set()
        created = attachment.result(timeout=10)
        deleted = deletion.result(timeout=10)
    assert created.status_code == 201, created.text  # type: ignore[attr-defined]
    assert deleted.status_code == 202, deleted.text  # type: ignore[attr-defined]
    assert deleted.json()["status"] == "completed"  # type: ignore[attr-defined]
    with client.app.state.database.session_factory() as session:
        versions = session.query(SubmissionVersion).filter_by(asset_id=UUID(asset["id"])).all()
        assert versions and all(version.caption == "" for version in versions)
