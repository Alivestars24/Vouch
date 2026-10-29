from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .models import (
    Brand,
    Creator,
    CreatorEvidence,
    Membership,
    MembershipRole,
    Organization,
    Product,
    RulePackVersion,
    User,
)

ACME_ORG_ID = UUID("11111111-1111-4111-8111-111111111111")
BETA_ORG_ID = UUID("22222222-2222-4222-8222-222222222222")

ADMIN_USER_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1")
MARKETER_USER_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa2")
REVIEWER_USER_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa3")
VIEWER_USER_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa4")
REVOKED_USER_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa5")
BETA_USER_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb1")

ACME_BRAND_ID = UUID("10000000-0000-4000-8000-000000000001")
ACME_PRODUCT_ID = UUID("10000000-0000-4000-8000-000000000002")
ACME_CREATOR_ID = UUID("10000000-0000-4000-8000-000000000003")
ACME_RULE_PACK_ID = UUID("10000000-0000-4000-8000-000000000004")
ACME_EXACT_EVIDENCE_ID = UUID("10000000-0000-4000-8000-000000000005")
ACME_CATEGORY_EVIDENCE_ID = UUID("10000000-0000-4000-8000-000000000006")

BETA_BRAND_ID = UUID("20000000-0000-4000-8000-000000000001")
BETA_PRODUCT_ID = UUID("20000000-0000-4000-8000-000000000002")
BETA_CREATOR_ID = UUID("20000000-0000-4000-8000-000000000003")
BETA_RULE_PACK_ID = UUID("20000000-0000-4000-8000-000000000004")
BETA_EXACT_EVIDENCE_ID = UUID("20000000-0000-4000-8000-000000000005")

RULES: list[dict[str, object]] = [
    {
        "id": "DISCLOSURE_AUDIO",
        "version": "1.0",
        "title": "Spoken disclosure clarity",
        "kind": "brand_policy",
        "severity": "major",
        "source": "fixture://draft-brand-policy/disclosure-audio",
    },
    {
        "id": "PRODUCT_VISIBILITY",
        "version": "1.0",
        "title": "Product should be identifiable",
        "kind": "brand_policy",
        "severity": "minor",
        "source": "fixture://draft-brand-policy/product-visibility",
    },
]


def _membership(
    session: Session,
    membership_id: UUID,
    organization_id: UUID,
    user_id: UUID,
    roles: tuple[str, ...],
    *,
    active: bool = True,
) -> None:
    membership = Membership(
        id=membership_id,
        organization_id=organization_id,
        user_id=user_id,
        active=active,
    )
    session.add(membership)
    for role in roles:
        session.add(
            MembershipRole(
                organization_id=organization_id,
                membership_id=membership.id,
                role=role,
            )
        )


def _seed_creator_evidence(session: Session) -> None:
    fixture_time = datetime(2026, 10, 20, 12, tzinfo=UTC)
    records = [
        CreatorEvidence(
            id=ACME_EXACT_EVIDENCE_ID,
            organization_id=ACME_ORG_ID,
            creator_id=ACME_CREATOR_ID,
            product_id=ACME_PRODUCT_ID,
            category="eyewear",
            match_kind="exact_product",
            source_kind="fixture",
            source_uri="fixture://creator-evidence/acme-orbit-frames",
            source_label="Authorized synthetic fixture",
            permission_status="permission_recorded",
            verification_status="verified",
            evidence_mode="human_curated",
            description="Synthetic creator shown with the fixture Orbit Frames product.",
            captured_at=fixture_time,
        ),
        CreatorEvidence(
            id=ACME_CATEGORY_EVIDENCE_ID,
            organization_id=ACME_ORG_ID,
            creator_id=ACME_CREATOR_ID,
            product_id=None,
            category="eyewear",
            match_kind="category_relevance",
            source_kind="fixture",
            source_uri="fixture://creator-evidence/acme-eyewear-category",
            source_label="Authorized synthetic fixture",
            permission_status="permission_recorded",
            verification_status="unreviewed",
            evidence_mode="human_curated",
            description="Rights-cleared synthetic eyewear category evidence; not an SKU match.",
            captured_at=fixture_time,
        ),
        CreatorEvidence(
            id=BETA_EXACT_EVIDENCE_ID,
            organization_id=BETA_ORG_ID,
            creator_id=BETA_CREATOR_ID,
            product_id=BETA_PRODUCT_ID,
            category="accessories",
            match_kind="exact_product",
            source_kind="fixture",
            source_uri="fixture://creator-evidence/beta-sample",
            source_label="Authorized synthetic fixture",
            permission_status="permission_recorded",
            verification_status="verified",
            evidence_mode="human_curated",
            description="Beta creator shown with the synthetic Beta Sample fixture product.",
            captured_at=fixture_time,
        ),
    ]
    existing = set(
        session.scalars(
            select(CreatorEvidence.id).where(
                CreatorEvidence.id.in_([record.id for record in records])
            )
        ).all()
    )
    for record in records:
        if record.id not in existing and session.get(Creator, record.creator_id) is not None:
            session.add(record)


def seed_fixture_data(session: Session) -> None:
    if session.get_bind().dialect.name == "postgresql":
        # API and worker may start together. Seed once per runtime schema.
        session.execute(text("select pg_advisory_xact_lock(hashtext(current_schema()))"))
    if session.scalar(select(Organization.id).limit(1)) is not None:
        _seed_creator_evidence(session)
        session.commit()
        return

    acme = Organization(id=ACME_ORG_ID, slug="acme", name="Acme Eyewear")
    beta = Organization(id=BETA_ORG_ID, slug="beta", name="Beta Goods")
    session.add_all([acme, beta])

    users = [
        User(id=ADMIN_USER_ID, email="admin@vouch.test", display_name="Asha Admin"),
        User(id=MARKETER_USER_ID, email="marketer@vouch.test", display_name="Mira Marketer"),
        User(id=REVIEWER_USER_ID, email="reviewer@vouch.test", display_name="Ravi Reviewer"),
        User(id=VIEWER_USER_ID, email="viewer@vouch.test", display_name="Vina Viewer"),
        User(id=REVOKED_USER_ID, email="revoked@vouch.test", display_name="Former Member"),
        User(id=BETA_USER_ID, email="beta@vouch.test", display_name="Ben Beta"),
    ]
    session.add_all(users)
    session.flush()

    _membership(
        session,
        UUID("30000000-0000-4000-8000-000000000001"),
        ACME_ORG_ID,
        ADMIN_USER_ID,
        ("admin",),
    )
    _membership(
        session,
        UUID("30000000-0000-4000-8000-000000000002"),
        ACME_ORG_ID,
        MARKETER_USER_ID,
        ("marketer",),
    )
    _membership(
        session,
        UUID("30000000-0000-4000-8000-000000000003"),
        ACME_ORG_ID,
        REVIEWER_USER_ID,
        ("reviewer",),
    )
    _membership(
        session,
        UUID("30000000-0000-4000-8000-000000000004"),
        ACME_ORG_ID,
        VIEWER_USER_ID,
        ("viewer",),
    )
    _membership(
        session,
        UUID("30000000-0000-4000-8000-000000000005"),
        ACME_ORG_ID,
        REVOKED_USER_ID,
        ("marketer",),
        active=False,
    )
    _membership(
        session,
        UUID("30000000-0000-4000-8000-000000000006"),
        BETA_ORG_ID,
        BETA_USER_ID,
        ("marketer",),
    )

    session.add_all(
        [
            Brand(id=ACME_BRAND_ID, organization_id=ACME_ORG_ID, name="Acme Eyewear"),
            Product(
                id=ACME_PRODUCT_ID,
                organization_id=ACME_ORG_ID,
                brand_id=ACME_BRAND_ID,
                name="Orbit Frames",
                category="eyewear",
                sku="ORBIT-BLK",
            ),
            Creator(
                id=ACME_CREATOR_ID,
                organization_id=ACME_ORG_ID,
                name="Synthetic Creator",
                handle="@synthetic-creator",
            ),
            Brand(id=BETA_BRAND_ID, organization_id=BETA_ORG_ID, name="Beta Goods"),
            Product(
                id=BETA_PRODUCT_ID,
                organization_id=BETA_ORG_ID,
                brand_id=BETA_BRAND_ID,
                name="Beta Sample",
                category="accessories",
                sku="BETA-001",
            ),
            Creator(
                id=BETA_CREATOR_ID,
                organization_id=BETA_ORG_ID,
                name="Beta Creator",
                handle="@beta-creator",
            ),
        ]
    )
    rule_bytes = json.dumps(RULES, sort_keys=True, separators=(",", ":")).encode()
    rule_hash = hashlib.sha256(rule_bytes).hexdigest()
    session.add_all(
        [
            RulePackVersion(
                id=ACME_RULE_PACK_ID,
                organization_id=ACME_ORG_ID,
                name="Acme draft creator policy",
                version="2026.10-fixture",
                status="draft_not_legally_reviewed",
                source_uri="fixture://draft-brand-policy",
                content_hash=rule_hash,
                rules=RULES,
            ),
            RulePackVersion(
                id=BETA_RULE_PACK_ID,
                organization_id=BETA_ORG_ID,
                name="Beta draft creator policy",
                version="2026.10-fixture",
                status="draft_not_legally_reviewed",
                source_uri="fixture://draft-brand-policy",
                content_hash=rule_hash,
                rules=RULES,
            ),
        ]
    )
    session.flush()
    _seed_creator_evidence(session)
    session.commit()
