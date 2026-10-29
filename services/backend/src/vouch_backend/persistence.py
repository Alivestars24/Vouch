"""Emit deterministic PostgreSQL DDL from the same model used by the fixture API."""

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from .models import Base


def schema_sql() -> str:
    metadata = MetaData(schema="vouch")
    for table in Base.metadata.sorted_tables:
        table.to_metadata(metadata)
    dialect = postgresql.dialect()
    statements = [
        "-- Generated from vouch_backend.models; update through an additive migration.",
        "create schema if not exists vouch;",
        "revoke all on schema vouch from public, anon, authenticated;",
        "alter default privileges in schema vouch revoke all on tables from anon, authenticated;",
    ]
    for table in metadata.sorted_tables:
        statements.append(f"{CreateTable(table).compile(dialect=dialect)};")
        statements.append(f'alter table vouch."{table.name}" enable row level security;')
        for index in sorted(table.indexes, key=lambda item: item.name or ""):
            statements.append(f"{CreateIndex(index).compile(dialect=dialect)};")
    statements.extend(
        [
            "revoke all on all tables in schema vouch from public, anon, authenticated;",
            "-- The API/worker use server-only database credentials and explicit tenant scope.",
            "-- This local fixture persistence path must not be deployed with header identity.",
        ]
    )
    return "\n\n".join(statements) + "\n"


def print_schema() -> None:
    print(schema_sql())
