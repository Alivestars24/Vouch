from __future__ import annotations

import re
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import cast
from uuid import UUID

from sqlalchemy import Connection, Engine, create_engine, event, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.schema import CreateIndex, CreateTable

from .models import Base


def set_database_scope(
    session: Session,
    *,
    auth_subject: UUID | None = None,
    user_id: UUID | None = None,
    organization_id: UUID | None = None,
    guest_grant_id: UUID | None = None,
    guest_session_id: UUID | None = None,
    retention_asset_id: UUID | None = None,
    retention_request_id: UUID | None = None,
) -> None:
    """Merge verified context; SET LOCAL never survives a returned pool connection."""
    scope = session.info.setdefault("vouch_scope", {})
    for key, value in (
        ("auth_subject", auth_subject),
        ("user_id", user_id),
        ("organization_id", organization_id),
        ("guest_grant_id", guest_grant_id),
        ("guest_session_id", guest_session_id),
        ("retention_asset_id", retention_asset_id),
        ("retention_request_id", retention_request_id),
    ):
        if value is not None:
            scope[key] = str(value)
    if session.get_bind().dialect.name == "postgresql":
        _write_scope(session.connection(), scope)


def _write_scope(connection: Connection, scope: dict[str, str]) -> None:
    for key in (
        "auth_subject",
        "user_id",
        "organization_id",
        "guest_grant_id",
        "guest_session_id",
        "retention_asset_id",
        "retention_request_id",
    ):
        connection.execute(
            text("select set_config(:key, :value, true)"),
            {"key": f"vouch.{key}", "value": scope.get(key, "")},
        )


class Database:
    def __init__(self, url: str, schema: str = "vouch", runtime_role: str | None = None) -> None:
        parsed = make_url(url)
        if not re.fullmatch(r"vouch(?:_test_[a-f0-9]+)?", schema):
            raise ValueError("Only the vouch runtime or an isolated test schema is allowed.")
        self.schema = schema
        if runtime_role not in {
            None,
            "vouch_api",
            "vouch_worker",
            "vouch_retention",
            "vouch_guest",
        }:
            raise ValueError("Unknown runtime database role.")
        self.runtime_role = runtime_role
        self.is_sqlite = parsed.drivername.startswith("sqlite")
        if self.is_sqlite and runtime_role is not None:
            raise ValueError("Authenticated runtime roles require PostgreSQL.")
        if parsed.drivername in {"postgres", "postgresql"}:
            parsed = parsed.set(drivername="postgresql+psycopg")
        connect_args: dict[str, object] = {}
        engine_kwargs: dict[str, object] = {"pool_pre_ping": True}
        if self.is_sqlite:
            connect_args["check_same_thread"] = False
            if parsed.database in (None, "", ":memory:"):
                engine_kwargs["poolclass"] = StaticPool
            elif parsed.database:
                Path(parsed.database).parent.mkdir(parents=True, exist_ok=True)
        self.engine: Engine = create_engine(
            parsed,
            connect_args=connect_args,
            **engine_kwargs,
        )
        if self.is_sqlite:
            event.listen(self.engine, "connect", self._enable_sqlite_foreign_keys)
            event.listen(self.engine, "begin", self._serialize_sqlite_transaction)
        else:
            event.listen(self.engine, "connect", self._set_postgres_search_path)
        self.session_factory = sessionmaker(
            bind=self.engine,
            class_=Session,
            expire_on_commit=False,
            autoflush=False,
        )
        if not self.is_sqlite:
            event.listen(self.session_factory, "after_begin", self._transaction_scope)
        if runtime_role is not None:
            with self.engine.connect() as connection:
                flags = connection.execute(
                    text(
                        "select rolsuper, rolbypassrls, "
                        "pg_has_role(session_user, :role, 'member') "
                        "from pg_roles where rolname = session_user"
                    ),
                    {"role": runtime_role},
                ).one()
                if flags[0] or flags[1] or not flags[2]:
                    raise ValueError("Use the separate non-bypass runtime login credential.")

    def _transaction_scope(
        self, session: Session, _transaction: object, connection: Connection
    ) -> None:
        if self.runtime_role is not None:
            # Role is an allowlisted constant, never request input.
            connection.exec_driver_sql(f'SET LOCAL ROLE "{self.runtime_role}"')
        _write_scope(connection, session.info.get("vouch_scope", {}))

    @staticmethod
    def _enable_sqlite_foreign_keys(dbapi_connection: object, _record: object) -> None:
        dbapi_connection.isolation_level = None  # type: ignore[attr-defined]
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=15000")
        cursor.close()

    @staticmethod
    def _serialize_sqlite_transaction(connection: object) -> None:
        connection.exec_driver_sql("BEGIN IMMEDIATE")  # type: ignore[attr-defined]

    def _set_postgres_search_path(self, dbapi_connection: object, _record: object) -> None:
        # This is connection-local; never interpolate an unchecked user-provided schema.
        previous_autocommit = dbapi_connection.autocommit  # type: ignore[attr-defined]
        dbapi_connection.autocommit = True  # type: ignore[attr-defined]
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute(f'SET search_path TO "{self.schema}"')
        cursor.close()
        dbapi_connection.autocommit = previous_autocommit  # type: ignore[attr-defined]

    def create_all(self) -> None:
        if not self.is_sqlite:
            with self.engine.connect() as connection:
                if not connection.scalar(text("select to_regclass('organizations')")):
                    raise RuntimeError(
                        "Apply the Supabase runtime migration before starting Vouch."
                    )
            return
        # New tables (including consent_receipts) are additive. Never backfill receipts:
        # an existing source without a notice remains explicitly legacy_no_notice.
        self._ensure_sqlite_tenant_parent_keys()
        self._ensure_sqlite_guest_parent_keys()
        Base.metadata.create_all(self.engine)
        self._upgrade_sqlite_find()
        self._upgrade_sqlite_guest_grants()
        # Preserve existing local fixture databases while adding explicit role scope.
        if "organization_id" not in {
            column["name"] for column in inspect(self.engine).get_columns("membership_roles")
        }:
            with self.engine.begin() as connection:
                connection.execute(
                    text(
                        "ALTER TABLE membership_roles ADD COLUMN organization_id CHAR(32) "
                        "REFERENCES organizations(id)"
                    )
                )
                connection.execute(
                    text(
                        "UPDATE membership_roles SET organization_id = "
                        "(SELECT organization_id FROM memberships "
                        "WHERE memberships.id = membership_roles.membership_id)"
                    )
                )
        with self.engine.begin() as connection:
            if "auth_subject" not in {
                column["name"] for column in inspect(connection).get_columns("users")
            }:
                connection.execute(text("ALTER TABLE users ADD COLUMN auth_subject CHAR(32)"))
                connection.execute(
                    text(
                        "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_auth_subject "
                        "ON users(auth_subject)"
                    )
                )
            media_columns = {
                column["name"] for column in inspect(connection).get_columns("media_assets")
            }
            if "storage_backend" not in media_columns:
                connection.execute(
                    text(
                        "ALTER TABLE media_assets ADD COLUMN storage_backend VARCHAR(32) "
                        "NOT NULL DEFAULT 'database'"
                    )
                )
            if "object_key" not in media_columns:
                connection.execute(
                    text("ALTER TABLE media_assets ADD COLUMN object_key VARCHAR(500)")
                )
            if "processing_container" not in media_columns:
                connection.execute(
                    text("ALTER TABLE media_assets ADD COLUMN processing_container VARCHAR(160)")
                )
            if "processing_lease_until" not in media_columns:
                connection.execute(
                    text("ALTER TABLE media_assets ADD COLUMN processing_lease_until DATETIME")
                )
            if "processing_metadata" not in media_columns:
                connection.execute(
                    text(
                        "ALTER TABLE media_assets ADD COLUMN processing_metadata JSON "
                        "NOT NULL DEFAULT '{}'"
                    )
                )
        self._ensure_sqlite_tenant_parent_keys()
        self._ensure_sqlite_guest_parent_keys()
        self._upgrade_sqlite_guest_attribution()
        self._ensure_sqlite_guest_attribution_guards()
        self._upgrade_sqlite_deletion_requests()

    def _upgrade_sqlite_find(self) -> None:
        """Keep existing fixture databases compatible with evidence-linked rosters."""
        with self.engine.begin() as connection:
            inspector = inspect(connection)
            if "campaign_creators" not in inspector.get_table_names():
                return
            columns = {
                column["name"] for column in inspector.get_columns("campaign_creators")
            }
            if "evidence_id" not in columns:
                connection.execute(
                    text("ALTER TABLE campaign_creators ADD COLUMN evidence_id CHAR(32)")
                )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_campaign_creators_evidence_id "
                    "ON campaign_creators(evidence_id)"
                )
            )

    def _ensure_sqlite_guest_attribution_guards(self) -> None:
        """Keep a guest source/version inside the session grant's fixed scope."""
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE TRIGGER IF NOT EXISTS guest_grant_actions_insert_guard "
                    "BEFORE INSERT ON guest_grants WHEN "
                    "json(NEW.allowed_actions) NOT IN ("
                    "json('[\"read_submission\"]'), "
                    "json('[\"read_submission\",\"upload_source\",\"submit_version\"]')) "
                    "BEGIN SELECT RAISE(ABORT, 'invalid guest action vocabulary'); END"
                )
            )
            connection.execute(
                text(
                    "CREATE TRIGGER IF NOT EXISTS guest_grant_quota_update_guard "
                    "BEFORE UPDATE OF source_count, reserved_bytes ON guest_grants WHEN "
                    "NEW.source_count <> OLD.source_count + 1 "
                    "OR NEW.reserved_bytes <= OLD.reserved_bytes "
                    "OR NEW.reserved_bytes - OLD.reserved_bytes > 5000000 "
                    "OR NEW.source_count > 5 OR NEW.reserved_bytes > 25000000 "
                    "BEGIN SELECT RAISE(ABORT, 'invalid guest source reservation'); END"
                )
            )
            for timing in ("INSERT", "UPDATE"):
                suffix = timing.lower()
                connection.execute(
                    text(
                        f"CREATE TRIGGER IF NOT EXISTS guest_media_scope_{suffix}_guard "
                        f"BEFORE {timing} ON media_assets "
                        "WHEN NEW.uploader_guest_session_id IS NOT NULL AND NOT EXISTS ("
                        "SELECT 1 FROM guest_sessions gs JOIN guest_grants g "
                        "ON g.id = gs.grant_id AND g.organization_id = gs.organization_id "
                        "WHERE gs.id = NEW.uploader_guest_session_id "
                        "AND gs.organization_id = NEW.organization_id "
                        "AND g.campaign_id = NEW.campaign_id) "
                        "BEGIN SELECT RAISE(ABORT, 'guest media outside grant scope'); END"
                    )
                )
                connection.execute(
                    text(
                        f"CREATE TRIGGER IF NOT EXISTS guest_version_scope_{suffix}_guard "
                        f"BEFORE {timing} ON submission_versions "
                        "WHEN NEW.uploader_guest_session_id IS NOT NULL AND NOT EXISTS ("
                        "SELECT 1 FROM guest_sessions gs JOIN guest_grants g "
                        "ON g.id = gs.grant_id AND g.organization_id = gs.organization_id "
                        "WHERE gs.id = NEW.uploader_guest_session_id "
                        "AND gs.organization_id = NEW.organization_id "
                        "AND g.submission_id = NEW.submission_id) "
                        "BEGIN SELECT RAISE(ABORT, 'guest version outside grant scope'); END"
                    )
                )

    def _upgrade_sqlite_guest_attribution(self) -> None:
        """Add guest actors without rewriting or re-attributing existing member rows."""
        targets = {
            "consent_receipts": ("actor_guest_session_id", "actor_user_id"),
            "submission_versions": ("uploader_guest_session_id", "uploader_user_id"),
            "media_assets": ("uploader_guest_session_id", "uploader_user_id"),
            "audit_events": ("actor_guest_session_id", None),
        }
        with self.engine.connect() as probe:
            inspector = inspect(probe)
            existing_tables = set(inspector.get_table_names())
            needs_upgrade = False
            for table_name, (guest_column, member_column) in targets.items():
                if table_name not in existing_tables:
                    continue
                columns = {
                    column["name"]: column for column in inspector.get_columns(table_name)
                }
                if guest_column not in columns or (
                    member_column is not None and not columns[member_column]["nullable"]
                ):
                    needs_upgrade = True
                    break
            if not needs_upgrade:
                return

        pooled = self.engine.raw_connection()
        connection = cast(sqlite3.Connection, pooled.driver_connection)
        try:
            # SQLite cannot relax NOT NULL or add the required table constraints
            # in place. Disable FK enforcement outside the transaction, rebuild all
            # related tables, then validate the complete graph before commit.
            connection.execute("PRAGMA foreign_keys=OFF")
            connection.execute("BEGIN IMMEDIATE")
            existing_tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_schema WHERE type='table'"
                )
            }
            for table_name in targets:
                if table_name in existing_tables:
                    self._rebuild_sqlite_guest_attribution_table(connection, table_name)
            for table_name in targets:
                if table_name not in existing_tables:
                    continue
                for index in Base.metadata.tables[table_name].indexes:
                    connection.execute(
                        str(
                            CreateIndex(index, if_not_exists=True).compile(
                                dialect=self.engine.dialect
                            )
                        )
                    )
            violation = connection.execute("PRAGMA foreign_key_check").fetchone()
            if violation is not None:
                raise RuntimeError(
                    "SQLite guest-attribution upgrade failed its foreign-key check."
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.execute("PRAGMA foreign_keys=ON")
            pooled.close()

    def _rebuild_sqlite_guest_attribution_table(
        self, connection: sqlite3.Connection, table_name: str
    ) -> None:
        temporary = f"_vouch_{table_name}_guest_attribution_upgrade"
        if connection.execute(
            "SELECT 1 FROM sqlite_schema WHERE name = ?", (temporary,)
        ).fetchone():
            raise RuntimeError(
                "SQLite guest-attribution upgrade found an unexpected temporary table."
            )
        dependents = connection.execute(
            "SELECT sql FROM sqlite_schema WHERE tbl_name = ? "
            "AND type IN ('index', 'trigger') AND sql IS NOT NULL",
            (table_name,),
        ).fetchall()
        create_sql = str(
            CreateTable(Base.metadata.tables[table_name]).compile(dialect=self.engine.dialect)
        ).strip()
        create_sql, changed = re.subn(
            rf'(?i)^(CREATE\s+TABLE\s+)(?:"{re.escape(table_name)}"|{re.escape(table_name)})',
            rf'\1"{temporary}"',
            create_sql,
            count=1,
        )
        if changed != 1:
            raise RuntimeError(f"SQLite table {table_name} could not be safely upgraded.")
        old_columns = [
            row[1] for row in connection.execute(f'PRAGMA table_info("{table_name}")')
        ]
        connection.execute(create_sql)
        new_columns = {
            row[1] for row in connection.execute(f'PRAGMA table_info("{temporary}")')
        }
        copied_columns = [name for name in old_columns if name in new_columns]
        quoted = ", ".join('"' + name.replace('"', '""') + '"' for name in copied_columns)
        connection.execute(
            f'INSERT INTO "{temporary}" ({quoted}) SELECT {quoted} FROM "{table_name}"'
        )
        connection.execute(f'DROP TABLE "{table_name}"')
        connection.execute(f'ALTER TABLE "{temporary}" RENAME TO "{table_name}"')
        for (statement,) in dependents:
            connection.execute(statement)

    def _upgrade_sqlite_guest_grants(self) -> None:
        """Preserve first-slice grants while adding non-secret recovery lineage."""
        with self.engine.begin() as connection:
            inspector = inspect(connection)
            if "guest_grants" not in set(inspector.get_table_names()):
                return
            columns = {
                column["name"] for column in inspector.get_columns("guest_grants")
            }
            if "issuance_recovery_id" not in columns:
                connection.execute(
                    text(
                        "ALTER TABLE guest_grants "
                        "ADD COLUMN issuance_recovery_id CHAR(32)"
                    )
                )
            if "renewal_root_id" not in columns:
                connection.execute(
                    text("ALTER TABLE guest_grants ADD COLUMN renewal_root_id CHAR(32)")
                )
            connection.execute(
                text(
                    "UPDATE guest_grants SET "
                    "issuance_recovery_id = COALESCE(issuance_recovery_id, id), "
                    "renewal_root_id = COALESCE(renewal_root_id, id)"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_guest_grant_recovery ON guest_grants "
                    "(organization_id, issued_by_user_id, issuance_recovery_id, created_at)"
                )
            )
            connection.execute(
                text(
                    "CREATE TRIGGER IF NOT EXISTS guest_grant_family_insert_guard "
                    "BEFORE INSERT ON guest_grants WHEN "
                    "NEW.issuance_recovery_id IS NULL OR NEW.renewal_root_id IS NULL OR "
                    "(NEW.renewal_root_id <> NEW.id AND NOT EXISTS ("
                    "SELECT 1 FROM guest_grants root WHERE root.id = NEW.renewal_root_id "
                    "AND root.organization_id = NEW.organization_id "
                    "AND root.campaign_id = NEW.campaign_id "
                    "AND root.creator_id = NEW.creator_id "
                    "AND root.submission_id = NEW.submission_id "
                    "AND root.issued_by_user_id = NEW.issued_by_user_id "
                    "AND root.issuance_recovery_id = NEW.issuance_recovery_id)) "
                    "BEGIN SELECT RAISE(ABORT, 'invalid guest grant renewal family'); END"
                )
            )
            connection.execute(
                text(
                    "CREATE TRIGGER IF NOT EXISTS guest_grant_family_update_guard "
                    "BEFORE UPDATE OF organization_id, campaign_id, creator_id, submission_id, "
                    "issued_by_user_id, issuance_recovery_id, renewal_root_id ON guest_grants "
                    "WHEN NEW.organization_id <> OLD.organization_id "
                    "OR NEW.campaign_id <> OLD.campaign_id "
                    "OR NEW.creator_id <> OLD.creator_id "
                    "OR NEW.submission_id <> OLD.submission_id "
                    "OR NEW.issued_by_user_id <> OLD.issued_by_user_id "
                    "OR NEW.issuance_recovery_id <> OLD.issuance_recovery_id "
                    "OR NEW.renewal_root_id <> OLD.renewal_root_id "
                    "BEGIN SELECT RAISE(ABORT, 'guest grant renewal scope is immutable'); END"
                )
            )

    def _ensure_sqlite_tenant_parent_keys(self) -> None:
        """Make legacy tenant rows valid parents before adding composite foreign keys."""
        with self.engine.begin() as connection:
            inspector = inspect(connection)
            existing_tables = set(inspector.get_table_names())
            quote = connection.dialect.identifier_preparer.quote
            target_columns = ("organization_id", "id")
            for table in Base.metadata.tables.values():
                if table.name not in existing_tables or not set(target_columns) <= {
                    column["name"] for column in inspector.get_columns(table.name)
                }:
                    continue
                unique_keys = {
                    tuple(
                        name
                        for name in constraint.get("column_names") or ()
                        if name is not None
                    )
                    for constraint in inspector.get_unique_constraints(table.name)
                }
                unique_keys.update(
                    tuple(
                        name for name in index.get("column_names") or () if name is not None
                    )
                    for index in inspector.get_indexes(table.name)
                    if index.get("unique")
                )
                if target_columns in unique_keys:
                    continue
                index_name = f"ux_{table.name}_organization_id_id"
                connection.exec_driver_sql(
                    f"CREATE UNIQUE INDEX {quote(index_name)} ON {quote(table.name)} "
                    f"({quote('organization_id')}, {quote('id')})"
                )

    def _ensure_sqlite_guest_parent_keys(self) -> None:
        """Add lineage parent keys before additive guest child tables are created."""
        targets = {
            "campaign_creators": ("organization_id", "campaign_id", "creator_id"),
            "submissions": (
                "organization_id",
                "id",
                "campaign_id",
                "creator_id",
            ),
        }
        with self.engine.begin() as connection:
            inspector = inspect(connection)
            existing_tables = set(inspector.get_table_names())
            quote = connection.dialect.identifier_preparer.quote
            for table_name, columns in targets.items():
                if table_name not in existing_tables or not set(columns) <= {
                    column["name"] for column in inspector.get_columns(table_name)
                }:
                    continue
                unique_keys = {
                    tuple(name for name in item.get("column_names") or () if name is not None)
                    for item in inspector.get_unique_constraints(table_name)
                }
                unique_keys.update(
                    tuple(name for name in item.get("column_names") or () if name is not None)
                    for item in inspector.get_indexes(table_name)
                    if item.get("unique")
                )
                if columns in unique_keys:
                    continue
                index_name = f"ux_{table_name}_{'_'.join(columns)}"
                quoted_columns = ", ".join(quote(column) for column in columns)
                connection.exec_driver_sql(
                    f"CREATE UNIQUE INDEX {quote(index_name)} ON {quote(table_name)} "
                    f"({quoted_columns})"
                )

    def _upgrade_sqlite_deletion_requests(self) -> None:
        """Preserve legacy receipts while permitting a genuinely actorless system request."""
        additions = {
            "requested_by_kind": "VARCHAR(24) NOT NULL DEFAULT 'member'",
            "attempt_count": "INTEGER NOT NULL DEFAULT 0",
            "max_attempts": "INTEGER NOT NULL DEFAULT 3",
            "retry_after": "DATETIME",
            "lease_owner": "VARCHAR(100)",
            "lease_until": "DATETIME",
            "fence": "INTEGER NOT NULL DEFAULT 0",
            "last_error_code": "VARCHAR(64)",
        }
        pooled = self.engine.raw_connection()
        connection = cast(sqlite3.Connection, pooled.driver_connection)
        try:
            # SQLite <3.53 cannot remove NOT NULL in-place. Disable FKs outside the
            # transaction, then follow its documented create/copy/drop/rename sequence.
            connection.execute("PRAGMA foreign_keys=OFF")
            connection.execute("BEGIN IMMEDIATE")
            columns = {
                row[1]: row for row in connection.execute("PRAGMA table_info(deletion_requests)")
            }
            for name, declaration in additions.items():
                if name not in columns:
                    connection.execute(
                        f'ALTER TABLE deletion_requests ADD COLUMN "{name}" {declaration}'
                    )
            if columns["requested_by"][3]:
                self._rebuild_sqlite_deletion_requests(connection)
            connection.execute(
                "CREATE INDEX IF NOT EXISTS ix_deletion_request_claim "
                "ON deletion_requests(status, retry_after, lease_until)"
            )
            if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise RuntimeError("SQLite retention upgrade failed its foreign-key check.")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.execute("PRAGMA foreign_keys=ON")
            pooled.close()

    @staticmethod
    def _rebuild_sqlite_deletion_requests(connection: sqlite3.Connection) -> None:
        temporary = "_vouch_deletion_requests_retention_upgrade"
        if connection.execute(
            "SELECT 1 FROM sqlite_schema WHERE name = ?", (temporary,)
        ).fetchone():
            raise RuntimeError("SQLite retention upgrade found an unexpected temporary table.")
        row = connection.execute(
            "SELECT sql FROM sqlite_schema WHERE type='table' AND name='deletion_requests'"
        ).fetchone()
        assert row is not None
        create_sql, changed = re.subn(
            r"(?im)^(\s*requested_by\s+\w+(?:\(\d+\))?)\s+NOT\s+NULL\b",
            r"\1",
            row[0],
            count=1,
        )
        if changed != 1:
            raise RuntimeError("SQLite receipt schema differs; no existing data was changed.")
        create_sql, renamed = re.subn(
            r'(?i)^(CREATE\s+TABLE\s+)(?:"deletion_requests"|deletion_requests)(?=\s*\()',
            rf'\1"{temporary}"',
            create_sql,
            count=1,
        )
        if renamed != 1:
            raise RuntimeError("SQLite receipt table could not be safely upgraded.")
        dependents = connection.execute(
            "SELECT sql FROM sqlite_schema WHERE tbl_name='deletion_requests' "
            "AND type IN ('index', 'trigger') AND sql IS NOT NULL"
        ).fetchall()
        names = [row[1] for row in connection.execute("PRAGMA table_info(deletion_requests)")]
        quoted = ", ".join('"' + name.replace('"', '""') + '"' for name in names)
        connection.execute(create_sql)
        connection.execute(
            f'INSERT INTO "{temporary}" ({quoted}) SELECT {quoted} FROM deletion_requests'
        )
        connection.execute("DROP TABLE deletion_requests")
        connection.execute(f'ALTER TABLE "{temporary}" RENAME TO deletion_requests')
        for (statement,) in dependents:
            connection.execute(statement)

    def session(self) -> Iterator[Session]:
        with self.session_factory() as session:
            try:
                yield session
            except Exception:
                session.rollback()
                raise

    def dispose(self) -> None:
        self.engine.dispose()
