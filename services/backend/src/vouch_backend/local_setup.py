"""Provision synthetic accounts and restricted credentials on this repository's local stack."""

from __future__ import annotations

import json
import os
import platform
import secrets
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

import httpx
import psycopg
from psycopg import sql
from sqlalchemy import select
from sqlalchemy.engine import make_url

from .db import Database
from .models import User
from .seed import (
    ADMIN_USER_ID,
    BETA_USER_ID,
    MARKETER_USER_ID,
    REVIEWER_USER_ID,
    REVOKED_USER_ID,
    VIEWER_USER_ID,
    seed_fixture_data,
)

PROJECT_ROOT = Path(__file__).resolve().parents[4]
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
SYNTHETIC_USERS = (
    (ADMIN_USER_ID, "admin@vouch.test", "admin"),
    (MARKETER_USER_ID, "marketer@vouch.test", "marketer"),
    (REVIEWER_USER_ID, "reviewer@vouch.test", "reviewer"),
    (VIEWER_USER_ID, "viewer@vouch.test", "viewer"),
    (REVOKED_USER_ID, "revoked@vouch.test", "revoked"),
    (BETA_USER_ID, "beta@vouch.test", "marketer (Beta)"),
)
RUNTIME_KINDS = ("api", "worker", "retention", "guest")


class LocalSetupError(Exception):
    """A safe, actionable setup failure without remote bodies or credentials."""


def _cli_command() -> list[str]:
    suffix = {
        ("Windows", "AMD64"): "windows-x64",
        ("Windows", "ARM64"): "windows-arm64",
        ("Darwin", "arm64"): "darwin-arm64",
        ("Darwin", "x86_64"): "darwin-x64",
        ("Linux", "x86_64"): "linux-x64",
        ("Linux", "aarch64"): "linux-arm64",
    }.get((platform.system(), platform.machine()))
    if suffix:
        binary = (
            PROJECT_ROOT
            / "node_modules"
            / "@supabase"
            / f"cli-{suffix}"
            / "bin"
            / ("supabase.exe" if os.name == "nt" else "supabase")
        )
        if binary.is_file():
            return [str(binary)]
    node = shutil.which("node")
    wrapper = PROJECT_ROOT / "node_modules/supabase/dist/supabase.js"
    if node and wrapper.is_file():
        return [node, str(wrapper)]
    raise LocalSetupError("Install repository dependencies with npm.cmd install first.")


def _run_cli(*args: str) -> str:
    child_env = os.environ.copy()
    docker_bin = Path("C:/Program Files/Docker/Docker/resources/bin")
    if os.name == "nt" and docker_bin.is_dir():
        child_env["PATH"] = str(docker_bin) + os.pathsep + child_env.get("PATH", "")
    try:
        result = subprocess.run(
            [*_cli_command(), *args, "--workdir", str(PROJECT_ROOT)],
            cwd=PROJECT_ROOT,
            env=child_env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise LocalSetupError(
            "The local Supabase CLI could not complete. Check Docker Desktop."
        ) from error
    if result.returncode:
        raise LocalSetupError(
            "The local Supabase command failed. Start Docker Desktop, then run "
            "npm.cmd run supabase:start."
        )
    return result.stdout


def _validate_targets(api_url: str, database_url: str) -> None:
    api = urlsplit(api_url)
    if (
        api.scheme != "http"
        or api.hostname not in LOOPBACK_HOSTS
        or api.port != 54321
        or api.username
        or api.password
        or api.path not in {"", "/"}
        or api.query
        or api.fragment
    ):
        raise LocalSetupError("Refusing setup: Auth must be the loopback API on port 54321.")
    db = make_url(database_url)
    if (
        db.get_backend_name() not in {"postgres", "postgresql"}
        or db.host not in LOOPBACK_HOSTS
        or db.port != 54322
        or db.database != "postgres"
        or db.username != "postgres"
        or db.query
    ):
        raise LocalSetupError("Refusing setup: database must be local postgres on port 54322.")


def _local_status() -> dict[str, Any]:
    config_path = PROJECT_ROOT / "supabase/config.toml"
    with config_path.open("rb") as handle:
        config = tomllib.load(handle)
    if (
        config.get("project_id") != "vouch-local"
        or config.get("api", {}).get("port") != 54321
        or config.get("db", {}).get("port") != 54322
    ):
        raise LocalSetupError("Refusing setup: unexpected local project configuration.")
    status = json.loads(_run_cli("status", "--output", "json"))
    if not isinstance(status, dict):
        raise LocalSetupError("Local Supabase status did not match its contract.")
    _validate_targets(str(status.get("API_URL", "")), str(status.get("DB_URL", "")))
    required = ("PUBLISHABLE_KEY", "SERVICE_ROLE_KEY")
    if any(not isinstance(status.get(key), str) or not status[key] for key in required):
        raise LocalSetupError("Local Supabase did not provide the required Auth keys.")
    return status


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        os.chmod(temporary_path, 0o600)
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _merge_env(path: Path, values: dict[str, str]) -> None:
    existing = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    emitted: set[str] = set()
    lines = []
    for line in existing:
        key = line.split("=", 1)[0].strip().removeprefix("export ").strip()
        if key not in values:
            lines.append(line)
        elif key not in emitted:
            lines.append(f"{key}={json.dumps(values[key])}")
            emitted.add(key)
    lines.extend(
        f"{key}={json.dumps(value)}" for key, value in values.items() if key not in emitted
    )
    _atomic_write(path, "\n".join(lines) + "\n")


def _credentials(*, rotate_guest: bool = False) -> dict[str, Any]:
    ignored = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    if ".local/" not in {line.strip() for line in ignored}:
        raise LocalSetupError("Refusing to save secrets: add .local/ to .gitignore first.")
    path = PROJECT_ROOT / ".local/credentials.json"
    if path.exists():
        saved = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(saved, dict):
            raise LocalSetupError(
                "Existing local credentials are not valid; preserve and inspect them."
            )
        passwords = saved.get("database_passwords", {})
        if (
            not isinstance(saved.get("password"), str)
            or len(saved["password"]) < 32
            or not isinstance(passwords, dict)
            or any(
                not isinstance(passwords.get(key), str) or len(passwords[key]) < 32
                for key in ("api", "worker")
            )
        ):
            raise LocalSetupError(
                "Existing local credentials are incomplete; they were not overwritten."
            )
        credentials_added = False
        for kind in ("retention", "guest"):
            if kind not in passwords:
                passwords[kind] = secrets.token_urlsafe(32)
                credentials_added = True
            elif not isinstance(passwords[kind], str) or len(passwords[kind]) < 32:
                raise LocalSetupError(
                    f"Existing {kind} credentials are invalid; they were not overwritten."
                )
        rate_limit_key = saved.get("guest_rate_limit_key")
        if rate_limit_key is None:
            saved["guest_rate_limit_key"] = secrets.token_urlsafe(32)
            credentials_added = True
        elif not isinstance(rate_limit_key, str) or len(rate_limit_key) < 32:
            raise LocalSetupError(
                "Existing guest rate-limit credentials are invalid; they were not overwritten."
            )
        if rotate_guest:
            passwords["guest"] = secrets.token_urlsafe(32)
            saved["guest_rate_limit_key"] = secrets.token_urlsafe(32)
            credentials_added = True
        if credentials_added:
            # Persist additive credentials before provisioning; an interrupted
            # upgrade must never rotate existing user/API/Check-worker passwords.
            _atomic_write(path, json.dumps(saved, indent=2) + "\n")
        return saved
    saved = {
        "password": secrets.token_urlsafe(32),
        "users": [{"email": email, "role": role} for _id, email, role in SYNTHETIC_USERS],
        "database_passwords": {kind: secrets.token_urlsafe(32) for kind in RUNTIME_KINDS},
        "guest_rate_limit_key": secrets.token_urlsafe(32),
    }
    # Save before provisioning so an interrupted command never loses a generated password.
    _atomic_write(path, json.dumps(saved, indent=2) + "\n")
    return saved


def _auth_request(client: httpx.Client, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
    response = client.request(method, path, **kwargs)
    if response.status_code not in {200, 201}:
        raise LocalSetupError(
            f"Local synthetic Auth provisioning returned HTTP {response.status_code}."
        )
    payload = response.json()
    if not isinstance(payload, dict):
        raise LocalSetupError("Local Auth returned an unexpected response.")
    return payload


def _provision_users(
    database: Database, status: dict[str, Any], credentials: dict[str, Any]
) -> None:
    with database.session_factory() as session:
        seed_fixture_data(session)
        users: dict[str, User] = {}
        for user_id, email, _role in SYNTHETIC_USERS:
            user = session.scalar(select(User).where(User.id == user_id, User.email == email))
            if user is None:
                raise LocalSetupError(
                    "Expected synthetic domain users are missing; no accounts changed."
                )
            users[email] = user
        with httpx.Client(
            base_url=f"{status['API_URL'].rstrip('/')}/auth/v1/",
            headers={
                "apikey": status["SERVICE_ROLE_KEY"],
                "Authorization": f"Bearer {status['SERVICE_ROLE_KEY']}",
            },
            timeout=10.0,
            follow_redirects=False,
            trust_env=False,
        ) as client:
            existing: dict[str, dict[str, Any]] = {}
            for page in range(1, 101):
                payload = _auth_request(
                    client, "GET", "admin/users", params={"page": page, "per_page": 200}
                )
                listed = payload.get("users")
                if not isinstance(listed, list):
                    raise LocalSetupError("Local Auth user listing did not match its contract.")
                for candidate in listed:
                    email = candidate.get("email", "")
                    if email in users:
                        if email in existing:
                            raise LocalSetupError(
                                "Duplicate synthetic Auth email; setup stopped safely."
                            )
                        existing[email] = candidate
                if len(listed) < 200:
                    break
            else:
                raise LocalSetupError("Local Auth user listing exceeded the safe setup bound.")
            for email, user in users.items():
                previous = existing.get(email)
                subject = UUID(previous["id"]) if previous else None
                if user.auth_subject is not None and user.auth_subject != subject:
                    raise LocalSetupError("An Auth subject mapping differs; it was not reassigned.")
            for email, user in users.items():
                body = {"email": email, "password": credentials["password"], "email_confirm": True}
                previous = existing.get(email)
                payload = _auth_request(
                    client,
                    "PUT" if previous else "POST",
                    f"admin/users/{UUID(previous['id'])}" if previous else "admin/users",
                    json=body,
                )
                subject = UUID(payload["id"])
                if previous and subject != UUID(previous["id"]):
                    raise LocalSetupError("Local Auth changed a synthetic subject unexpectedly.")
                user.auth_subject = subject
        session.commit()


def _provision_logins(database_url: str, credentials: dict[str, Any]) -> dict[str, str]:
    owner = make_url(database_url).set(drivername="postgresql")
    urls: dict[str, str] = {}
    with (
        psycopg.connect(owner.render_as_string(hide_password=False)) as connection,
        connection.cursor() as cursor,
    ):
        for kind in RUNTIME_KINDS:
            name = f"vouch_local_{kind}"
            group = f"vouch_{kind}"
            cursor.execute(
                "select rolsuper, rolbypassrls, rolcreatedb, rolcreaterole, rolreplication "
                "from pg_roles where rolname = %s",
                (name,),
            )
            flags = cursor.fetchone()
            if flags and any(flags):
                raise LocalSetupError(
                    "An existing local runtime role is privileged; setup refused."
                )
            cursor.execute(
                "select parent.rolname from pg_auth_members m "
                "join pg_roles child on child.oid=m.member "
                "join pg_roles parent on parent.oid=m.roleid where child.rolname=%s",
                (name,),
            )
            if any(row[0] != group for row in cursor.fetchall()):
                raise LocalSetupError("An existing local runtime role has unexpected membership.")
            password = credentials["database_passwords"][kind]
            # PostgreSQL disallows even redundant ALTER ... NOBYPASSRLS for a
            # non-superuser owner. Existing roles were verified non-privileged above.
            statement = (
                "ALTER ROLE {} LOGIN INHERIT PASSWORD {}"
                if flags
                else "CREATE ROLE {} LOGIN INHERIT NOSUPERUSER NOBYPASSRLS NOCREATEDB "
                "NOCREATEROLE NOREPLICATION PASSWORD {}"
            )
            cursor.execute(sql.SQL(statement).format(sql.Identifier(name), sql.Literal(password)))
            cursor.execute(
                sql.SQL("GRANT {} TO {}").format(sql.Identifier(group), sql.Identifier(name))
            )
            urls[kind] = owner.set(
                drivername="postgresql+psycopg", username=name, password=password
            ).render_as_string(hide_password=False)
    return urls


def setup_local(*, rotate_guest: bool = False) -> None:
    status = _local_status()
    cleanup_storage_key = status.get("SECRET_KEY")
    guest_storage_key = status.get("SERVICE_ROLE_KEY")
    if (
        not isinstance(cleanup_storage_key, str)
        or not isinstance(guest_storage_key, str)
        or cleanup_storage_key == guest_storage_key
    ):
        raise LocalSetupError(
            "Local Supabase must expose distinct secret and service-role Storage keys."
        )
    _run_cli("migration", "up", "--local", "--yes")
    credentials = _credentials(rotate_guest=rotate_guest)
    database = Database(status["DB_URL"], "vouch")
    try:
        database.create_all()
        _provision_users(database, status, credentials)
    finally:
        database.dispose()
    runtime_urls = _provision_logins(status["DB_URL"], credentials)
    for kind in RUNTIME_KINDS:
        verification = Database(runtime_urls[kind], "vouch", runtime_role=f"vouch_{kind}")
        verification.dispose()
        values = {
            "VOUCH_AUTH_MODE": "supabase",
            "VOUCH_ENVIRONMENT": "development",
            "VOUCH_DATABASE_SCHEMA": "vouch",
            "VOUCH_DATABASE_URL": runtime_urls[kind],
            "VOUCH_SUPABASE_URL": status["API_URL"],
            "VOUCH_SUPABASE_PUBLISHABLE_KEY": status["PUBLISHABLE_KEY"],
        }
        if kind in {"api", "retention"}:
            values["VOUCH_SUPABASE_SECRET_KEY"] = cleanup_storage_key
        if kind == "api":
            values["VOUCH_GUEST_DATABASE_URL"] = runtime_urls["guest"]
            values["VOUCH_GUEST_RATE_LIMIT_KEY"] = credentials["guest_rate_limit_key"]
            values["VOUCH_GUEST_STORAGE_KEY"] = guest_storage_key
        _merge_env(PROJECT_ROOT / f"services/backend/.env.{kind}", values)
    _merge_env(
        PROJECT_ROOT / "apps/web/.env.local",
        {
            "NEXT_PUBLIC_AUTH_MODE": "supabase",
            "NEXT_PUBLIC_SUPABASE_URL": status["API_URL"],
            "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY": status["PUBLISHABLE_KEY"],
            "NEXT_PUBLIC_API_BASE_URL": "http://127.0.0.1:8010/api/v1",
        },
    )
    print("Local authenticated Vouch setup complete. No hosted resources changed.")
    print("Secrets/login password: .local/credentials.json (ignored; keep private).")
    print(
        "Runtime configuration: services/backend/.env.api, .env.worker, .env.retention, "
        ".env.guest; "
        "apps/web/.env.local."
    )
    print("Synthetic login: marketer@vouch.test; review: reviewer@vouch.test.")
    print("Run: npm.cmd run dev:authenticated")


def main() -> None:
    try:
        setup_local(
            rotate_guest=os.getenv("VOUCH_ROTATE_LOCAL_GUEST_CREDENTIALS") == "1"
        )
    except LocalSetupError as error:
        print(f"Local setup stopped: {error}", file=sys.stderr)
        raise SystemExit(1) from None
    except Exception:
        # SQL/HTTP exception reprs can contain credentials or remote payloads.
        print(
            "Local setup failed safely; no private diagnostic payload was printed.", file=sys.stderr
        )
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
