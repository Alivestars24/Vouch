from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy.engine import make_url

BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_PATH = (BACKEND_ROOT / "vouch.db").resolve()
DEFAULT_GUEST_RATE_LIMIT_KEY = "vouch-local-guest-rate-limit-key-2026"


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str = field(repr=False)
    database_schema: str = "vouch"
    environment: str = "development"
    cors_origins: tuple[str, ...] = (
        "http://127.0.0.1:3000",
        "http://localhost:3000",
    )
    worker_poll_seconds: float = 1.0
    auth_mode: str = "fixture"
    media_mode: str = "fixture"
    media_image: str = "vouch-media-sandbox:local"
    supabase_url: str | None = None
    supabase_publishable_key: str | None = field(default=None, repr=False)
    supabase_secret_key: str | None = field(default=None, repr=False)
    guest_database_url: str | None = field(default=None, repr=False)
    guest_storage_key: str | None = field(default=None, repr=False)
    guest_public_origin: str = "http://127.0.0.1:3000"
    guest_rate_limit_key: str = field(
        default=DEFAULT_GUEST_RATE_LIMIT_KEY, repr=False
    )
    meta_api_key: str | None = field(default=None, repr=False)
    operator_region: str = "IN"

    def __post_init__(self) -> None:
        if self.media_mode not in {"fixture", "decoded"}:
            raise ValueError("VOUCH_MEDIA_MODE must be fixture or decoded.")
        if not self.media_image or self.media_image.startswith("-"):
            raise ValueError("VOUCH_MEDIA_IMAGE must identify a local sandbox image.")
        if self.auth_mode not in {"fixture", "supabase"}:
            raise ValueError("VOUCH_AUTH_MODE must be fixture or supabase.")
        if self.environment not in {"development", "test", "production"}:
            raise ValueError("VOUCH_ENVIRONMENT must be development, test or production.")
        if self.environment == "production" and self.auth_mode != "supabase":
            raise ValueError(
                "Production requires Supabase authentication; fixture identity cannot be deployed."
            )
        guest_origin = urlsplit(self.guest_public_origin)
        if (
            not guest_origin.hostname
            or guest_origin.username
            or guest_origin.password
            or guest_origin.path
            or guest_origin.query
            or guest_origin.fragment
            or (
                guest_origin.scheme != "https"
                and not (
                    guest_origin.scheme == "http"
                    and guest_origin.hostname in {"127.0.0.1", "localhost", "::1"}
                )
            )
        ):
            raise ValueError(
                "VOUCH_GUEST_PUBLIC_ORIGIN must be an HTTPS origin "
                "(HTTP only for loopback)."
            )
        if self.guest_public_origin not in self.cors_origins:
            raise ValueError("VOUCH_GUEST_PUBLIC_ORIGIN must be in VOUCH_CORS_ORIGINS.")
        if self.environment == "production" and any(
            urlsplit(origin).scheme != "https" for origin in self.cors_origins
        ):
            raise ValueError("Production CORS origins must use HTTPS.")
        if len(self.guest_rate_limit_key.encode("utf-8")) < 32:
            raise ValueError("VOUCH_GUEST_RATE_LIMIT_KEY must contain at least 32 bytes.")
        if self.meta_api_key is not None and (
            self.meta_api_key != self.meta_api_key.strip()
            or not 20 <= len(self.meta_api_key) <= 512
            or any(character.isspace() for character in self.meta_api_key)
        ):
            raise ValueError("VOUCH_META_API_KEY has an invalid format.")
        if not 2 <= len(self.operator_region) <= 8 or not self.operator_region.isalpha():
            raise ValueError("VOUCH_OPERATOR_REGION must contain a 2-8 letter region code.")
        if self.auth_mode == "fixture":
            database = make_url(self.database_url)
            if database.get_backend_name() in {"postgres", "postgresql"} and database.host not in {
                "127.0.0.1",
                "localhost",
                "::1",
            }:
                raise ValueError("Fixture identity requires local persistence, never hosted data.")
        if self.auth_mode == "supabase":
            if (
                self.guest_database_url is not None
                and self.guest_rate_limit_key == DEFAULT_GUEST_RATE_LIMIT_KEY
            ):
                raise ValueError(
                    "Authenticated guest access requires a private rate-limit HMAC key."
                )
            member_database = make_url(self.database_url)
            if member_database.get_backend_name() not in {"postgres", "postgresql"}:
                raise ValueError("Supabase authentication requires PostgreSQL persistence.")
            if not self.supabase_url or not self.supabase_publishable_key:
                raise ValueError(
                    "Supabase authentication requires a trusted URL and publishable key."
                )
            if self.guest_storage_key is not None and self.guest_storage_key in {
                self.supabase_publishable_key,
                self.supabase_secret_key,
            }:
                raise ValueError(
                    "VOUCH_GUEST_STORAGE_KEY must be distinct from member and cleanup keys."
                )
            parsed = urlsplit(self.supabase_url)
            if (
                not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.path not in {"", "/"}
                or parsed.query
                or parsed.fragment
                or (
                    parsed.scheme != "https"
                    and not (
                        parsed.scheme == "http"
                        and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
                    )
                )
            ):
                raise ValueError("Supabase URL must be an HTTPS origin (HTTP only for loopback).")
            if self.guest_database_url is not None:
                guest_database = make_url(self.guest_database_url)
                if guest_database.get_backend_name() not in {"postgres", "postgresql"}:
                    raise ValueError("Guest runtime persistence must use PostgreSQL.")
                if (
                    guest_database.host,
                    guest_database.port,
                    guest_database.database,
                ) != (
                    member_database.host,
                    member_database.port,
                    member_database.database,
                ):
                    raise ValueError(
                        "Guest and member runtime credentials must target the same database."
                    )

    @classmethod
    def from_env(cls) -> Settings:
        raw_origins = os.getenv(
            "VOUCH_CORS_ORIGINS",
            "http://127.0.0.1:3000,http://localhost:3000",
        )
        return cls(
            database_url=os.getenv(
                "VOUCH_DATABASE_URL",
                f"sqlite:///{DEFAULT_DATABASE_PATH.as_posix()}",
            ),
            environment=os.getenv("VOUCH_ENVIRONMENT", "development"),
            database_schema=os.getenv("VOUCH_DATABASE_SCHEMA", "vouch"),
            cors_origins=tuple(
                origin.strip() for origin in raw_origins.split(",") if origin.strip()
            ),
            worker_poll_seconds=float(os.getenv("VOUCH_WORKER_POLL_SECONDS", "1.0")),
            auth_mode=os.getenv("VOUCH_AUTH_MODE", "fixture"),
            media_mode=os.getenv("VOUCH_MEDIA_MODE", "fixture"),
            media_image=os.getenv("VOUCH_MEDIA_IMAGE", "vouch-media-sandbox:local"),
            supabase_url=os.getenv("VOUCH_SUPABASE_URL"),
            supabase_publishable_key=os.getenv("VOUCH_SUPABASE_PUBLISHABLE_KEY"),
            supabase_secret_key=os.getenv("VOUCH_SUPABASE_SECRET_KEY"),
            guest_database_url=os.getenv("VOUCH_GUEST_DATABASE_URL"),
            guest_storage_key=os.getenv("VOUCH_GUEST_STORAGE_KEY"),
            guest_public_origin=os.getenv(
                "VOUCH_GUEST_PUBLIC_ORIGIN", "http://127.0.0.1:3000"
            ),
            guest_rate_limit_key=os.getenv(
                "VOUCH_GUEST_RATE_LIMIT_KEY", DEFAULT_GUEST_RATE_LIMIT_KEY
            ),
            meta_api_key=os.getenv("VOUCH_META_API_KEY"),
            operator_region=os.getenv("VOUCH_OPERATOR_REGION", "IN").upper(),
        )
