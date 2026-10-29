from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from vouch_backend.models import AuditEvent, CampaignCreator, CreatorEvidence


def first_item(client: TestClient, path: str, headers: dict[str, str]) -> dict[str, Any]:
    response = client.get(path, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["items"][0]


def empty_campaign(client: TestClient, headers: dict[str, str]) -> dict[str, Any]:
    product = first_item(client, "/api/v1/products", headers)
    pack = first_item(client, "/api/v1/rule-pack-versions", headers)
    response = client.post(
        "/api/v1/campaigns",
        headers=headers,
        json={
            "name": "Find roster",
            "objective": "Select a creator from curated evidence",
            "market": "IN",
            "product_id": product["id"],
            "rule_pack_version_id": pack["id"],
            "creator_ids": [],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_creator_catalog_is_tenant_scoped_and_labels_fixture_evidence(
    client: TestClient,
    marketer_headers: dict[str, str],
    beta_headers: dict[str, str],
) -> None:
    acme = client.get("/api/v1/creators", headers=marketer_headers)
    beta = client.get("/api/v1/creators", headers=beta_headers)

    assert acme.status_code == 200
    assert acme.json()["collection"] == "curated"
    assert len(acme.json()["items"]) == 1
    creator = acme.json()["items"][0]
    assert creator["handle"] == "@synthetic-creator"
    assert {item["match_kind"] for item in creator["evidence"]} == {
        "exact_product",
        "category_relevance",
    }
    assert {item["source_kind"] for item in creator["evidence"]} == {"fixture"}
    assert {item["source_label"] for item in creator["evidence"]} == {
        "Authorized synthetic fixture"
    }

    assert beta.status_code == 200
    assert [item["handle"] for item in beta.json()["items"]] == ["@beta-creator"]
    assert creator["id"] not in {item["id"] for item in beta.json()["items"]}


def test_creator_catalog_filters_only_matching_curated_evidence(
    client: TestClient,
    marketer_headers: dict[str, str],
    beta_headers: dict[str, str],
) -> None:
    product = first_item(client, "/api/v1/products", marketer_headers)
    response = client.get(
        "/api/v1/creators",
        headers=marketer_headers,
        params={"product_id": product["id"], "match_kind": "exact_product", "q": "Orbit"},
    )
    assert response.status_code == 200
    assert len(response.json()["items"]) == 1
    evidence = response.json()["items"][0]["evidence"]
    assert len(evidence) == 1
    assert evidence[0]["match_kind"] == "exact_product"
    assert evidence[0]["product_id"] == product["id"]

    category = client.get(
        "/api/v1/creators",
        headers=marketer_headers,
        params={"category": "EYEWEAR", "match_kind": "category_relevance"},
    )
    assert category.status_code == 200
    assert [item["match_kind"] for item in category.json()["items"][0]["evidence"]] == [
        "category_relevance"
    ]

    empty = client.get(
        "/api/v1/creators", headers=marketer_headers, params={"category": "accessories"}
    )
    assert empty.status_code == 200
    assert empty.json() == {"collection": "curated", "items": []}

    beta_product = first_item(client, "/api/v1/products", beta_headers)
    foreign_product = client.get(
        "/api/v1/creators",
        headers=marketer_headers,
        params={"product_id": beta_product["id"]},
    )
    assert foreign_product.status_code == 404


def test_add_creator_to_campaign_is_role_gated_tenant_safe_and_idempotent(
    client: TestClient,
    marketer_headers: dict[str, str],
    reviewer_headers: dict[str, str],
    beta_headers: dict[str, str],
) -> None:
    campaign = empty_campaign(client, marketer_headers)
    creator = first_item(client, "/api/v1/creators", marketer_headers)
    evidence = next(
        item for item in creator["evidence"] if item["match_kind"] == "exact_product"
    )
    payload = {"creator_id": creator["id"], "evidence_id": evidence["id"]}

    denied = client.post(
        f"/api/v1/campaigns/{campaign['id']}/creators",
        headers=reviewer_headers,
        json=payload,
    )
    assert denied.status_code == 403

    created = client.post(
        f"/api/v1/campaigns/{campaign['id']}/creators",
        headers=marketer_headers,
        json=payload,
    )
    duplicate = client.post(
        f"/api/v1/campaigns/{campaign['id']}/creators",
        headers=marketer_headers,
        json=payload,
    )
    assert created.status_code == 201
    assert created.json()["created"] is True
    assert created.json()["evidence_id"] == evidence["id"]
    assert duplicate.status_code == 200
    assert duplicate.json() == {**created.json(), "created": False}

    refreshed = client.get(
        f"/api/v1/campaigns/{campaign['id']}", headers=marketer_headers
    )
    assert refreshed.status_code == 200
    assert refreshed.json()["creator_ids"] == [creator["id"]]
    with client.app.state.database.session_factory() as session:
        assignment_count = session.scalar(
            select(func.count(CampaignCreator.id)).where(
                CampaignCreator.campaign_id == UUID(campaign["id"]),
                CampaignCreator.creator_id == UUID(creator["id"]),
            )
        )
        assignment = session.scalar(
            select(CampaignCreator).where(
                CampaignCreator.campaign_id == UUID(campaign["id"]),
                CampaignCreator.creator_id == UUID(creator["id"]),
            )
        )
        audit_count = session.scalar(
            select(func.count(AuditEvent.id)).where(
                AuditEvent.action == "campaign.creator_added",
                AuditEvent.resource_id == UUID(created.json()["id"]),
            )
        )
    assert assignment_count == 1
    assert assignment is not None
    assert assignment.evidence_id == UUID(evidence["id"])
    assert audit_count == 1

    beta_creator = first_item(client, "/api/v1/creators", beta_headers)
    foreign = client.post(
        f"/api/v1/campaigns/{campaign['id']}/creators",
        headers=marketer_headers,
        json={
            "creator_id": beta_creator["id"],
            "evidence_id": beta_creator["evidence"][0]["id"],
        },
    )
    assert foreign.status_code == 404


def test_campaign_roster_rejects_unknown_permission_evidence(
    client: TestClient,
    marketer_headers: dict[str, str],
) -> None:
    campaign = empty_campaign(client, marketer_headers)
    creator = first_item(client, "/api/v1/creators", marketer_headers)
    evidence_id = uuid4()
    with client.app.state.database.session_factory() as session:
        session.add(
            CreatorEvidence(
                id=evidence_id,
                organization_id=UUID("11111111-1111-4111-8111-111111111111"),
                creator_id=UUID(creator["id"]),
                product_id=None,
                category="eyewear",
                match_kind="category_relevance",
                source_kind="fixture",
                source_uri="fixture://creator-evidence/unapproved",
                source_label="Synthetic unapproved fixture",
                permission_status="permission_unknown",
                verification_status="unreviewed",
                evidence_mode="human_curated",
                description="Synthetic evidence with intentionally unknown permission.",
                captured_at=datetime(2026, 10, 20, tzinfo=UTC),
            )
        )
        session.commit()

    response = client.post(
        f"/api/v1/campaigns/{campaign['id']}/creators",
        headers=marketer_headers,
        json={"creator_id": creator["id"], "evidence_id": str(evidence_id)},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CREATOR_EVIDENCE_NOT_ELIGIBLE"


def test_campaign_roster_rejects_evidence_for_another_product_category(
    client: TestClient,
    marketer_headers: dict[str, str],
) -> None:
    campaign = empty_campaign(client, marketer_headers)
    creator = first_item(client, "/api/v1/creators", marketer_headers)
    evidence_id = uuid4()
    with client.app.state.database.session_factory() as session:
        session.add(
            CreatorEvidence(
                id=evidence_id,
                organization_id=UUID("11111111-1111-4111-8111-111111111111"),
                creator_id=UUID(creator["id"]),
                product_id=None,
                category="skincare",
                match_kind="category_relevance",
                source_kind="fixture",
                source_uri="fixture://creator-evidence/wrong-category",
                source_label="Synthetic category mismatch fixture",
                permission_status="permission_recorded",
                verification_status="verified",
                evidence_mode="human_curated",
                description="Rights-cleared evidence for an unrelated synthetic category.",
                captured_at=datetime(2026, 10, 20, tzinfo=UTC),
            )
        )
        session.commit()

    response = client.post(
        f"/api/v1/campaigns/{campaign['id']}/creators",
        headers=marketer_headers,
        json={"creator_id": creator["id"], "evidence_id": str(evidence_id)},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CREATOR_EVIDENCE_CAMPAIGN_MISMATCH"
