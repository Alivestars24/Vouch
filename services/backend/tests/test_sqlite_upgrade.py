from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from vouch_backend.db import Database, set_database_scope
from vouch_backend.models import (
    AuditEvent,
    Campaign,
    CampaignCreator,
    ConsentReceipt,
    DeletionRequest,
    GuestCommand,
    GuestGrant,
    GuestSession,
    MediaAsset,
    Submission,
    SubmissionVersion,
)
from vouch_backend.seed import (
    ACME_CREATOR_ID,
    ACME_ORG_ID,
    ACME_PRODUCT_ID,
    ACME_RULE_PACK_ID,
    ADMIN_USER_ID,
    seed_fixture_data,
)


def _legacy_database(tmp_path: Path) -> Database:
    database = Database(f"sqlite:///{(tmp_path / 'legacy.db').as_posix()}")
    database.create_all()
    with database.session_factory() as session:
        seed_fixture_data(session)
    with database.engine.begin() as connection:
        connection.execute(text("DROP TABLE deletion_requests"))
        connection.execute(
            text(
                "CREATE TABLE deletion_requests (\n"
                "id CHAR(32) NOT NULL PRIMARY KEY,\n"
                "organization_id CHAR(32) NOT NULL REFERENCES organizations(id),\n"
                "resource_type VARCHAR(50) NOT NULL,\n"
                "resource_id CHAR(32) NOT NULL,\n"
                "status VARCHAR(24) NOT NULL,\n"
                "destinations JSON NOT NULL,\n"
                "requested_by CHAR(32) NOT NULL REFERENCES users(id),\n"
                "created_at DATETIME NOT NULL,\n"
                "completed_at DATETIME,\n"
                "legacy_note TEXT DEFAULT 'preserve me',\n"
                "UNIQUE (organization_id, id)\n"
                ")"
            )
        )
        connection.execute(text("CREATE INDEX legacy_receipt_index ON deletion_requests(status)"))
        connection.execute(text("CREATE TABLE legacy_update_markers (receipt_id CHAR(32))"))
        connection.execute(
            text(
                "CREATE TRIGGER legacy_receipt_updated AFTER UPDATE ON deletion_requests "
                "BEGIN INSERT INTO legacy_update_markers VALUES (NEW.id); END"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE legacy_receipt_child ("
                "receipt_id CHAR(32) REFERENCES deletion_requests(id) ON DELETE CASCADE)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO deletion_requests VALUES "
                "(:id,:org,'submission',:resource,'completed',:destinations,:actor,"
                "'2026-10-21 12:00:00','2026-10-21 12:01:00','retained original note')"
            ),
            {
                "id": uuid4().hex,
                "org": ACME_ORG_ID.hex,
                "resource": uuid4().hex,
                "destinations": '[{"destination":"local_fixture_database","status":"completed"}]',
                "actor": ADMIN_USER_ID.hex,
            },
        )
        connection.execute(
            text("INSERT INTO legacy_receipt_child SELECT id FROM deletion_requests")
        )
    return database


def _legacy_tenant_parent_database(tmp_path: Path) -> Database:
    database = Database(f"sqlite:///{(tmp_path / 'legacy-tenant-parent.db').as_posix()}")
    with database.engine.begin() as connection:
        connection.execute(text("CREATE TABLE organizations (id CHAR(32) PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE users (id CHAR(32) PRIMARY KEY)"))
        connection.execute(
            text(
                "CREATE TABLE campaigns ("
                "id CHAR(32) PRIMARY KEY, "
                "organization_id CHAR(32) NOT NULL REFERENCES organizations(id))"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE media_assets ("
                "id CHAR(32) PRIMARY KEY, "
                "organization_id CHAR(32) NOT NULL REFERENCES organizations(id), "
                "campaign_id CHAR(32) NOT NULL REFERENCES campaigns(id))"
            )
        )
    return database


def _legacy_guest_parent_database(tmp_path: Path) -> Database:
    database = Database(f"sqlite:///{(tmp_path / 'legacy-guest-parent.db').as_posix()}")
    with database.engine.begin() as connection:
        connection.execute(text("CREATE TABLE organizations (id CHAR(32) PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE users (id CHAR(32) PRIMARY KEY)"))
        connection.execute(
            text(
                "CREATE TABLE creators ("
                "id CHAR(32) PRIMARY KEY, organization_id CHAR(32) NOT NULL)"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE campaigns ("
                "id CHAR(32) PRIMARY KEY, organization_id CHAR(32) NOT NULL)"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE campaign_creators ("
                "id CHAR(32) PRIMARY KEY, organization_id CHAR(32) NOT NULL, "
                "campaign_id CHAR(32) NOT NULL, creator_id CHAR(32) NOT NULL, "
                "UNIQUE (campaign_id, creator_id))"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE submissions ("
                "id CHAR(32) PRIMARY KEY, organization_id CHAR(32) NOT NULL, "
                "campaign_id CHAR(32) NOT NULL, creator_id CHAR(32) NOT NULL, "
                "current_version_id CHAR(32), created_at DATETIME NOT NULL, "
                "deleted_at DATETIME)"
            )
        )
    return database


def test_sqlite_upgrade_adds_tenant_parent_keys_before_new_children(tmp_path: Path) -> None:
    database = _legacy_tenant_parent_database(tmp_path)
    try:
        database.create_all()
        database.create_all()  # Restart/provisioning is idempotent.
        with database.engine.begin() as connection:
            assert connection.execute(text("PRAGMA foreign_key_check")).first() is None
            for table in ("campaigns", "media_assets"):
                indexes = inspect(connection).get_indexes(table)
                assert any(
                    item["unique"]
                    and item["column_names"] == ["organization_id", "id"]
                    for item in indexes
                )

            organization_id, other_organization_id = uuid4(), uuid4()
            campaign_id, asset_id, actor_id = uuid4(), uuid4(), uuid4()
            connection.execute(
                text("INSERT INTO organizations (id) VALUES (:first), (:second)"),
                {"first": organization_id.hex, "second": other_organization_id.hex},
            )
            connection.execute(
                text("INSERT INTO users (id) VALUES (:actor)"), {"actor": actor_id.hex}
            )
            connection.execute(
                text(
                    "INSERT INTO campaigns (id, organization_id) VALUES (:campaign, :org)"
                ),
                {"campaign": campaign_id.hex, "org": organization_id.hex},
            )
            connection.execute(
                text(
                    "INSERT INTO media_assets (id, organization_id, campaign_id, "
                    "uploader_user_id, filename, proposed_content_type, expected_bytes, "
                    "status, upload_token_hash, finalize_token_hash, storage_backend, "
                    "processing_metadata, rights_attested, retention_deadline, created_at) "
                    "VALUES (:asset, :org, :campaign, :actor, 'legacy.mp4', 'video/mp4', "
                    "1, 'intent_created', :upload_hash, :finalize_hash, 'database', '{}', "
                    "1, '2026-11-24 00:00:00', '2026-10-24 00:00:00')"
                ),
                {
                    "asset": asset_id.hex,
                    "org": organization_id.hex,
                    "campaign": campaign_id.hex,
                    "actor": actor_id.hex,
                    "upload_hash": "a" * 64,
                    "finalize_hash": "b" * 64,
                },
            )
            with pytest.raises(IntegrityError):
                connection.execute(
                    text(
                        "INSERT INTO consent_receipts ("
                        "id, organization_id, asset_id, campaign_id, actor_user_id, purpose, "
                        "notice_version, notice_hash, accepted_at) VALUES ("
                        ":id, :org, :asset, :campaign, :actor, 'campaign_check', "
                        "'test-notice', :hash, '2026-10-24 00:00:00')"
                    ),
                    {
                        "id": uuid4().hex,
                        "org": other_organization_id.hex,
                        "asset": asset_id.hex,
                        "campaign": campaign_id.hex,
                        "actor": actor_id.hex,
                        "hash": "0" * 64,
                    },
                )
    finally:
        database.dispose()


def test_sqlite_upgrade_adds_guest_lineage_keys_before_guest_tables(tmp_path: Path) -> None:
    database = _legacy_guest_parent_database(tmp_path)
    try:
        database.create_all()
        database.create_all()
        with database.engine.begin() as connection:
            assert connection.execute(text("PRAGMA foreign_key_check")).first() is None
            assert "evidence_id" in {
                column["name"]
                for column in inspect(connection).get_columns("campaign_creators")
            }
            expected = {
                "campaign_creators": (
                    "organization_id",
                    "campaign_id",
                    "creator_id",
                ),
                "submissions": (
                    "organization_id",
                    "id",
                    "campaign_id",
                    "creator_id",
                ),
            }
            for table_name, columns in expected.items():
                indexes = inspect(connection).get_indexes(table_name)
                constraints = inspect(connection).get_unique_constraints(table_name)
                keys = {
                    tuple(item["column_names"])
                    for item in [*indexes, *constraints]
                    if item.get("unique", True)
                }
                assert columns in keys

            organization_id = uuid4()
            user_id = uuid4()
            creator_id = uuid4()
            campaign_id = uuid4()
            submission_id = uuid4()
            connection.execute(
                text("INSERT INTO organizations (id) VALUES (:id)"),
                {"id": organization_id.hex},
            )
            connection.execute(
                text("INSERT INTO users (id) VALUES (:id)"), {"id": user_id.hex}
            )
            connection.execute(
                text("INSERT INTO creators (id, organization_id) VALUES (:id, :org)"),
                {"id": creator_id.hex, "org": organization_id.hex},
            )
            connection.execute(
                text("INSERT INTO campaigns (id, organization_id) VALUES (:id, :org)"),
                {"id": campaign_id.hex, "org": organization_id.hex},
            )
            connection.execute(
                text(
                    "INSERT INTO campaign_creators "
                    "(id, organization_id, campaign_id, creator_id) "
                    "VALUES (:id, :org, :campaign, :creator)"
                ),
                {
                    "id": uuid4().hex,
                    "org": organization_id.hex,
                    "campaign": campaign_id.hex,
                    "creator": creator_id.hex,
                },
            )
            connection.execute(
                text(
                    "INSERT INTO submissions "
                    "(id, organization_id, campaign_id, creator_id, created_at) "
                    "VALUES (:id, :org, :campaign, :creator, '2026-10-25 00:00:00')"
                ),
                {
                    "id": submission_id.hex,
                    "org": organization_id.hex,
                    "campaign": campaign_id.hex,
                    "creator": creator_id.hex,
                },
            )
            connection.execute(
                text(
                    "INSERT INTO guest_grants ("
                    "id, organization_id, campaign_id, creator_id, submission_id, "
                    "issued_by_user_id, issuance_recovery_id, renewal_root_id, "
                    "scope_kind, invitation_secret_hash, allowed_actions, "
                    "expires_at, source_count, reserved_bytes, created_at) VALUES ("
                    ":id, :org, :campaign, :creator, :submission, :user, :id, :id, "
                    "'existing_submission', :digest, '[\"read_submission\"]', "
                    "'2026-10-27 00:00:00', 0, 0, '2026-10-25 00:00:00')"
                ),
                {
                    "id": uuid4().hex,
                    "org": organization_id.hex,
                    "campaign": campaign_id.hex,
                    "creator": creator_id.hex,
                    "submission": submission_id.hex,
                    "user": user_id.hex,
                    "digest": "a" * 64,
                },
            )
            assert connection.scalar(text("SELECT count(*) FROM guest_grants")) == 1
            assert connection.execute(text("PRAGMA foreign_key_check")).first() is None
    finally:
        database.dispose()


def test_sqlite_receipt_upgrade_preserves_data_constraints_and_dependents(tmp_path: Path) -> None:
    database = _legacy_database(tmp_path)
    try:
        with database.engine.connect() as connection:
            original = dict(
                connection.execute(text("SELECT * FROM deletion_requests")).mappings().one()
            )
        database.create_all()
        database.create_all()  # Restart/provisioning is idempotent.
        with database.engine.begin() as connection:
            upgraded = dict(
                connection.execute(text("SELECT * FROM deletion_requests")).mappings().one()
            )
            assert {key: upgraded[key] for key in original} == original
            assert upgraded["requested_by_kind"] == "member"
            assert upgraded["attempt_count"] == 0
            assert upgraded["max_attempts"] == 3
            assert upgraded["fence"] == 0
            assert connection.scalar(text("SELECT count(*) FROM legacy_receipt_child")) == 1
            assert connection.execute(text("PRAGMA foreign_key_check")).first() is None
            assert connection.scalar(text("PRAGMA foreign_keys")) == 1
            connection.execute(text("UPDATE deletion_requests SET status='completed'"))
            assert connection.scalar(text("SELECT count(*) FROM legacy_update_markers")) == 1
        columns = {
            column["name"]: column
            for column in inspect(database.engine).get_columns("deletion_requests")
        }
        assert columns["requested_by"]["nullable"]
        indexes = {
            item["name"] for item in inspect(database.engine).get_indexes("deletion_requests")
        }
        assert {"legacy_receipt_index", "ix_deletion_request_claim"} <= indexes
        with database.session_factory() as session:
            session.add(
                DeletionRequest(
                    organization_id=ACME_ORG_ID,
                    resource_type="media_asset",
                    resource_id=uuid4(),
                    requested_by=None,
                    requested_by_kind="retention",
                )
            )
            session.commit()
            session.add(
                DeletionRequest(
                    organization_id=uuid4(), resource_type="media_asset", resource_id=uuid4()
                )
            )
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()
    finally:
        database.dispose()


def test_sqlite_upgrade_rolls_back_if_table_rebuild_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _legacy_database(tmp_path)
    try:
        with database.engine.connect() as connection:
            original_schema = connection.scalar(
                text("SELECT sql FROM sqlite_schema WHERE name='deletion_requests'")
            )
        original_rebuild = database._rebuild_sqlite_deletion_requests

        def fail_rebuild(connection: object) -> None:
            original_rebuild(connection)  # type: ignore[arg-type]
            raise RuntimeError("controlled upgrade failure")

        monkeypatch.setattr(database, "_rebuild_sqlite_deletion_requests", fail_rebuild)
        with pytest.raises(RuntimeError, match="controlled upgrade failure"):
            database.create_all()
        with database.engine.connect() as connection:
            assert connection.scalar(
                text("SELECT sql FROM sqlite_schema WHERE name='deletion_requests'")
            ) == original_schema
            assert connection.scalar(text("SELECT count(*) FROM deletion_requests")) == 1
            assert connection.scalar(text("SELECT count(*) FROM legacy_receipt_child")) == 1
            assert connection.scalar(text("PRAGMA foreign_keys")) == 1
    finally:
        database.dispose()


def _guest_attribution_scope(database: Database) -> dict[str, object]:
    now = datetime.now(UTC)
    ids = {
        "campaign": uuid4(),
        "submission": uuid4(),
        "other_submission": uuid4(),
        "grant": uuid4(),
        "session": uuid4(),
    }
    with database.session_factory() as session:
        seed_fixture_data(session)
        session.add(
            Campaign(
                id=ids["campaign"],
                organization_id=ACME_ORG_ID,
                name="Guest attribution",
                objective="Test additive attribution",
                market="IN",
                product_id=ACME_PRODUCT_ID,
                rule_pack_version_id=ACME_RULE_PACK_ID,
                created_by=ADMIN_USER_ID,
            )
        )
        session.add(
            CampaignCreator(
                organization_id=ACME_ORG_ID,
                campaign_id=ids["campaign"],
                creator_id=ACME_CREATOR_ID,
            )
        )
        session.add_all(
            [
                Submission(
                    id=ids["submission"],
                    organization_id=ACME_ORG_ID,
                    campaign_id=ids["campaign"],
                    creator_id=ACME_CREATOR_ID,
                ),
                Submission(
                    id=ids["other_submission"],
                    organization_id=ACME_ORG_ID,
                    campaign_id=ids["campaign"],
                    creator_id=ACME_CREATOR_ID,
                ),
            ]
        )
        session.flush()
        session.add(
            GuestGrant(
                id=ids["grant"],
                organization_id=ACME_ORG_ID,
                campaign_id=ids["campaign"],
                creator_id=ACME_CREATOR_ID,
                submission_id=ids["submission"],
                issued_by_user_id=ADMIN_USER_ID,
                issuance_recovery_id=ids["grant"],
                renewal_root_id=ids["grant"],
                scope_kind="created_submission",
                invitation_secret_hash="a" * 64,
                allowed_actions=["read_submission", "upload_source", "submit_version"],
                expires_at=now + timedelta(hours=1),
                consumed_at=now,
            )
        )
        session.flush()
        session.add(
            GuestSession(
                id=ids["session"],
                organization_id=ACME_ORG_ID,
                grant_id=ids["grant"],
                session_secret_hash="b" * 64,
                expires_at=now + timedelta(minutes=30),
            )
        )
        session.commit()
    return ids


def _downgrade_guest_attribution_tables(database: Database) -> None:
    """Build the exact pre-milestone shape from current metadata for upgrade proof."""
    pooled = database.engine.raw_connection()
    connection = pooled.driver_connection
    try:
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute("BEGIN IMMEDIATE")
        for table_name in (
            "consent_receipts",
            "submission_versions",
            "media_assets",
            "audit_events",
        ):
            (current_sql,) = connection.execute(
                "SELECT sql FROM sqlite_schema WHERE type='table' AND name=?",
                (table_name,),
            ).fetchone()
            legacy_lines = [
                line
                for line in current_sql.splitlines()
                if "uploader_guest_session_id" not in line
                and "actor_guest_session_id" not in line
                and "ck_audit_event_guest_actor" not in line
            ]
            legacy_sql = "\n".join(legacy_lines)
            legacy_sql = legacy_sql.replace(
                "uploader_user_id CHAR(32),", "uploader_user_id CHAR(32) NOT NULL,"
            ).replace("actor_user_id CHAR(32),", "actor_user_id CHAR(32) NOT NULL,")
            temporary = f"_legacy_{table_name}"
            legacy_sql = legacy_sql.replace(
                f"CREATE TABLE {table_name}", f'CREATE TABLE "{temporary}"', 1
            )
            connection.execute(legacy_sql)
            source_columns = [
                row[1] for row in connection.execute(f'PRAGMA table_info("{table_name}")')
            ]
            target_columns = {
                row[1] for row in connection.execute(f'PRAGMA table_info("{temporary}")')
            }
            copied = [name for name in source_columns if name in target_columns]
            quoted = ", ".join(f'"{name}"' for name in copied)
            connection.execute(
                f'INSERT INTO "{temporary}" ({quoted}) '
                f'SELECT {quoted} FROM "{table_name}"'
            )
            connection.execute(f'DROP TABLE "{table_name}"')
            connection.execute(f'ALTER TABLE "{temporary}" RENAME TO "{table_name}"')
        connection.execute(
            "CREATE INDEX legacy_guest_asset_status ON media_assets(status)"
        )
        connection.execute(
            "CREATE TRIGGER legacy_guest_audit_marker AFTER UPDATE ON audit_events "
            "BEGIN SELECT 1; END"
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.execute("PRAGMA foreign_keys=ON")
        pooled.close()


def test_sqlite_guest_attribution_upgrade_preserves_member_history(tmp_path: Path) -> None:
    database = Database(f"sqlite:///{(tmp_path / 'legacy-guest-actors.db').as_posix()}")
    try:
        database.create_all()
        ids = _guest_attribution_scope(database)
        now = datetime.now(UTC)
        asset_with_receipt, legacy_without_receipt, version_id, receipt_id, audit_id = (
            uuid4(),
            uuid4(),
            uuid4(),
            uuid4(),
            uuid4(),
        )
        with database.session_factory() as session:
            for asset_id in (asset_with_receipt, legacy_without_receipt):
                session.add(
                    MediaAsset(
                        id=asset_id,
                        organization_id=ACME_ORG_ID,
                        campaign_id=ids["campaign"],
                        uploader_user_id=ADMIN_USER_ID,
                        filename=f"{asset_id}.mp4",
                        proposed_content_type="video/mp4",
                        validated_content_type="video/mp4",
                        expected_bytes=16,
                        actual_bytes=16,
                        sha256="c" * 64,
                        duration_ms=1000,
                        status="validated",
                        upload_token_hash="d" * 64,
                        finalize_token_hash="e" * 64,
                        object_bytes=b"fixture",
                        rights_attested=True,
                        retention_deadline=now + timedelta(days=30),
                    )
                )
            session.flush()
            session.add(
                SubmissionVersion(
                    id=version_id,
                    organization_id=ACME_ORG_ID,
                    submission_id=ids["submission"],
                    version_no=1,
                    asset_id=asset_with_receipt,
                    media_hash="c" * 64,
                    caption="member history",
                    caption_hash="f" * 64,
                    uploader_user_id=ADMIN_USER_ID,
                    rights_attested=True,
                )
            )
            session.add(
                ConsentReceipt(
                    id=receipt_id,
                    organization_id=ACME_ORG_ID,
                    asset_id=asset_with_receipt,
                    campaign_id=ids["campaign"],
                    actor_user_id=ADMIN_USER_ID,
                    purpose="campaign_check",
                    notice_version="member-v1",
                    notice_hash="1" * 64,
                )
            )
            session.add(
                AuditEvent(
                    id=audit_id,
                    organization_id=ACME_ORG_ID,
                    actor_user_id=ADMIN_USER_ID,
                    actor_kind="member",
                    action="legacy.member_event",
                    resource_type="media_asset",
                    resource_id=asset_with_receipt,
                    safe_metadata={},
                )
            )
            session.commit()
        _downgrade_guest_attribution_tables(database)

        database.create_all()
        database.create_all()

        inspector = inspect(database.engine)
        for table_name, member_column, guest_column in (
            ("media_assets", "uploader_user_id", "uploader_guest_session_id"),
            ("submission_versions", "uploader_user_id", "uploader_guest_session_id"),
            ("consent_receipts", "actor_user_id", "actor_guest_session_id"),
        ):
            columns = {column["name"]: column for column in inspector.get_columns(table_name)}
            assert columns[member_column]["nullable"]
            assert columns[guest_column]["nullable"]
        assert "actor_guest_session_id" in {
            column["name"] for column in inspector.get_columns("audit_events")
        }
        with database.engine.connect() as connection:
            assert connection.scalar(
                text("SELECT uploader_user_id FROM media_assets WHERE id=:id"),
                {"id": asset_with_receipt.hex},
            ) == ADMIN_USER_ID.hex
            assert connection.scalar(
                text("SELECT uploader_user_id FROM submission_versions WHERE id=:id"),
                {"id": version_id.hex},
            ) == ADMIN_USER_ID.hex
            assert connection.scalar(
                text("SELECT actor_user_id FROM consent_receipts WHERE id=:id"),
                {"id": receipt_id.hex},
            ) == ADMIN_USER_ID.hex
            assert connection.scalar(text("SELECT count(*) FROM consent_receipts")) == 1
            assert connection.scalar(
                text("SELECT count(*) FROM consent_receipts WHERE asset_id=:id"),
                {"id": legacy_without_receipt.hex},
            ) == 0
            assert connection.execute(text("PRAGMA foreign_key_check")).first() is None
            objects = {
                row[0]
                for row in connection.execute(
                    text(
                        "SELECT name FROM sqlite_schema WHERE name IN "
                        "('legacy_guest_asset_status','legacy_guest_audit_marker')"
                    )
                )
            }
            assert objects == {"legacy_guest_asset_status", "legacy_guest_audit_marker"}
    finally:
        database.dispose()


def test_sqlite_guest_attribution_and_command_guards(tmp_path: Path) -> None:
    database = Database(f"sqlite:///{(tmp_path / 'guest-actor-guards.db').as_posix()}")
    try:
        database.create_all()
        ids = _guest_attribution_scope(database)
        now = datetime.now(UTC)
        asset_id, version_id = uuid4(), uuid4()
        with database.session_factory() as session:
            session.add(
                MediaAsset(
                    id=asset_id,
                    organization_id=ACME_ORG_ID,
                    campaign_id=ids["campaign"],
                    uploader_guest_session_id=ids["session"],
                    filename="creator.mp4",
                    proposed_content_type="video/mp4",
                    validated_content_type="video/mp4",
                    expected_bytes=32,
                    actual_bytes=32,
                    sha256="2" * 64,
                    duration_ms=1000,
                    status="validated",
                    upload_token_hash="3" * 64,
                    finalize_token_hash="4" * 64,
                    object_bytes=b"guest fixture",
                    rights_attested=True,
                    retention_deadline=now + timedelta(days=30),
                )
            )
            session.flush()
            session.add_all(
                [
                    ConsentReceipt(
                        organization_id=ACME_ORG_ID,
                        asset_id=asset_id,
                        campaign_id=ids["campaign"],
                        actor_guest_session_id=ids["session"],
                        purpose="campaign_check",
                        notice_version="creator-v1",
                        notice_hash="5" * 64,
                    ),
                    SubmissionVersion(
                        id=version_id,
                        organization_id=ACME_ORG_ID,
                        submission_id=ids["submission"],
                        version_no=1,
                        asset_id=asset_id,
                        media_hash="2" * 64,
                        caption="creator draft",
                        caption_hash="6" * 64,
                        uploader_guest_session_id=ids["session"],
                        rights_attested=True,
                    ),
                    AuditEvent(
                        organization_id=ACME_ORG_ID,
                        actor_guest_session_id=ids["session"],
                        actor_kind="guest",
                        action="guest.version_submitted",
                        resource_type="submission_version",
                        resource_id=version_id,
                        safe_metadata={},
                    ),
                ]
            )
            session.flush()
            session.add(
                GuestCommand(
                    organization_id=ACME_ORG_ID,
                    guest_session_id=ids["session"],
                    operation="guest_submission_version",
                    idempotency_key="version-1",
                    request_digest="7" * 64,
                    result_resource_type="submission_version",
                    result_resource_id=version_id,
                )
            )
            session.commit()

            session.add(
                GuestCommand(
                    organization_id=ACME_ORG_ID,
                    guest_session_id=ids["session"],
                    operation="guest_submission_version",
                    idempotency_key="version-1",
                    request_digest="8" * 64,
                    result_resource_type="submission_version",
                    result_resource_id=version_id,
                )
            )
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()

            session.add(
                ConsentReceipt(
                    organization_id=ACME_ORG_ID,
                    asset_id=asset_id,
                    campaign_id=ids["campaign"],
                    actor_user_id=ADMIN_USER_ID,
                    purpose="campaign_check",
                    notice_version="wrong-actor",
                    notice_hash="9" * 64,
                )
            )
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()

            session.add(
                SubmissionVersion(
                    organization_id=ACME_ORG_ID,
                    submission_id=ids["other_submission"],
                    version_no=1,
                    asset_id=asset_id,
                    media_hash="2" * 64,
                    caption="wrong submission",
                    caption_hash="a" * 64,
                    uploader_guest_session_id=ids["session"],
                    rights_attested=True,
                )
            )
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()

            session.add(
                AuditEvent(
                    organization_id=ACME_ORG_ID,
                    actor_kind="guest",
                    action="guest.missing_actor",
                    resource_type="submission",
                    resource_id=ids["submission"],
                    safe_metadata={},
                )
            )
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()
    finally:
        database.dispose()


def test_database_scope_merges_retention_scope_across_transactions(tmp_path: Path) -> None:
    database = Database(f"sqlite:///{(tmp_path / 'scope.db').as_posix()}")
    try:
        with database.session_factory() as session:
            asset, receipt = uuid4(), uuid4()
            set_database_scope(session, organization_id=ACME_ORG_ID, retention_asset_id=asset)
            session.commit()
            set_database_scope(session, retention_request_id=receipt)
            assert session.info["vouch_scope"] == {
                "organization_id": str(ACME_ORG_ID),
                "retention_asset_id": str(asset),
                "retention_request_id": str(receipt),
            }
    finally:
        database.dispose()
