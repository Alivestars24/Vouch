from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import make_url

from vouch_backend.api import create_app
from vouch_backend.config import Settings
from vouch_backend.db import Database
from vouch_backend.models import Base


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    postgres_url = os.getenv("VOUCH_TEST_POSTGRES_URL")
    schema = f"vouch_test_{uuid4().hex}" if postgres_url else "vouch"
    database_url = postgres_url or f"sqlite:///{(tmp_path / 'vouch-test.db').as_posix()}"
    if postgres_url:
        if make_url(postgres_url).host not in {"127.0.0.1", "localhost"}:
            raise ValueError("Postgres fixture tests may only target a local database.")
        setup = Database(database_url, schema)
        with setup.engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        Base.metadata.create_all(setup.engine)
    settings = Settings(database_url=database_url, database_schema=schema, environment="test")
    app = create_app(settings)
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        if postgres_url:
            with setup.engine.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            setup.dispose()


@pytest.fixture
def marketer_headers() -> dict[str, str]:
    return {
        "X-Organization-Id": "11111111-1111-4111-8111-111111111111",
        "X-Fixture-User": "marketer@vouch.test",
    }


@pytest.fixture
def reviewer_headers() -> dict[str, str]:
    return {
        "X-Organization-Id": "11111111-1111-4111-8111-111111111111",
        "X-Fixture-User": "reviewer@vouch.test",
    }


@pytest.fixture
def admin_headers() -> dict[str, str]:
    return {
        "X-Organization-Id": "11111111-1111-4111-8111-111111111111",
        "X-Fixture-User": "admin@vouch.test",
    }


@pytest.fixture
def beta_headers() -> dict[str, str]:
    return {
        "X-Organization-Id": "22222222-2222-4222-8222-222222222222",
        "X-Fixture-User": "beta@vouch.test",
    }
