"""Provision restricted runtime credentials for an explicitly selected hosted project."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import sys
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy.engine import URL

from .local_setup import PROJECT_ROOT, RUNTIME_KINDS, _atomic_write, _cli_command, _merge_env

ROLE_NAMES = {kind: f"vouch_runtime_{kind}" for kind in RUNTIME_KINDS}
EXPECTED_PROJECT_REF_LENGTH = 20


class HostedSetupError(Exception):
    """A safe hosted-setup failure that never includes credentials or remote bodies."""


def _run_cli(*args: str, timeout: int = 90) -> str:
    try:
        result = subprocess.run(
            [*_cli_command(), *args, "--workdir", str(PROJECT_ROOT)],
            cwd=PROJECT_ROOT,
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise HostedSetupError("The authenticated Supabase CLI could not complete.") from error
    if result.returncode:
        raise HostedSetupError(
            "The hosted Supabase operation failed safely. Confirm CLI login, project link, "
            "and project health."
        )
    return result.stdout


def _validate_project_ref(project_ref: str) -> None:
    if (
        len(project_ref) != EXPECTED_PROJECT_REF_LENGTH
        or not project_ref.isascii()
        or not project_ref.isalnum()
        or project_ref.lower() != project_ref
    ):
        raise HostedSetupError("The hosted Supabase project ref has an invalid format.")
    linked_path = PROJECT_ROOT / "supabase/.temp/project-ref"
    if not linked_path.is_file() or linked_path.read_text(encoding="utf-8").strip() != project_ref:
        raise HostedSetupError("Refusing setup: the repository is linked to a different project.")


def _credentials(project_ref: str) -> dict[str, Any]:
    ignored = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    if ".local/" not in {line.strip() for line in ignored}:
        raise HostedSetupError("Refusing to save credentials until .local/ is ignored.")
    path = PROJECT_ROOT / f".local/hosted-credentials-{project_ref}.json"
    if path.exists():
        try:
            saved = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise HostedSetupError(
                "Existing hosted credentials are unreadable; not overwritten."
            ) from error
        passwords = saved.get("database_passwords") if isinstance(saved, dict) else None
        if (
            saved.get("project_ref") != project_ref
            or not isinstance(passwords, dict)
            or any(
                not isinstance(passwords.get(kind), str) or len(passwords[kind]) < 32
                for kind in RUNTIME_KINDS
            )
            or not isinstance(saved.get("guest_rate_limit_key"), str)
            or len(saved["guest_rate_limit_key"]) < 32
        ):
            raise HostedSetupError("Existing hosted credentials are incomplete; not overwritten.")
        return saved
    saved = {
        "project_ref": project_ref,
        "database_passwords": {
            kind: secrets.token_urlsafe(36) for kind in RUNTIME_KINDS
        },
        "guest_rate_limit_key": secrets.token_urlsafe(36),
    }
    _atomic_write(path, json.dumps(saved, indent=2) + "\n")
    return saved


def _api_keys(project_ref: str) -> dict[str, str]:
    try:
        payload = json.loads(
            _run_cli(
                "projects",
                "api-keys",
                "--project-ref",
                project_ref,
                "--reveal",
                "--output",
                "json",
            )
        )
    except json.JSONDecodeError as error:
        raise HostedSetupError("Supabase returned an unexpected API-key contract.") from error
    if not isinstance(payload, list):
        raise HostedSetupError("Supabase returned an unexpected API-key contract.")

    def select_key(key_type: str, name: str = "default") -> str:
        matches = [
            item.get("api_key")
            for item in payload
            if isinstance(item, dict)
            and item.get("type") == key_type
            and item.get("name") == name
            and not item.get("disabled", False)
            and isinstance(item.get("api_key"), str)
        ]
        if len(matches) != 1 or not matches[0]:
            raise HostedSetupError(f"Exactly one active {key_type} API key is required.")
        return matches[0]

    publishable = select_key("publishable")
    secret = select_key("secret")
    service_role = select_key("legacy", "service_role")
    if len({publishable, secret, service_role}) != 3:
        raise HostedSetupError("Hosted member, cleanup, and guest Storage keys must be distinct.")
    return {"publishable": publishable, "secret": secret, "guest_storage": service_role}


def _pooler(project_ref: str) -> tuple[str, int, str]:
    path = PROJECT_ROOT / "supabase/.temp/pooler-url"
    if not path.is_file():
        raise HostedSetupError("Link the hosted project before provisioning runtime credentials.")
    parsed = urlsplit(path.read_text(encoding="utf-8").strip())
    if (
        parsed.scheme not in {"postgres", "postgresql"}
        or not parsed.hostname
        or not parsed.hostname.endswith(".pooler.supabase.com")
        or parsed.port != 5432
        or parsed.username != f"postgres.{project_ref}"
        or parsed.password
        or parsed.path != "/postgres"
        or parsed.query
        or parsed.fragment
    ):
        raise HostedSetupError(
            "The linked project pooler metadata did not match its safe contract."
        )
    return parsed.hostname, parsed.port, parsed.path.removeprefix("/")


def _role_sql(credentials: dict[str, Any]) -> str:
    statements = [
        "begin;",
        "set local statement_timeout = '30s';",
        "set local lock_timeout = '5s';",
    ]
    for kind in RUNTIME_KINDS:
        role = ROLE_NAMES[kind]
        group = f"vouch_{kind}"
        password = credentials["database_passwords"][kind]
        statements.append(
            f"""
do $vouch$
declare
  flags record;
begin
  select rolsuper, rolbypassrls, rolcreatedb, rolcreaterole, rolreplication
    into flags from pg_roles where rolname = '{role}';
  if found and (flags.rolsuper or flags.rolbypassrls or flags.rolcreatedb
    or flags.rolcreaterole or flags.rolreplication) then
    raise exception 'Existing Vouch runtime role is privileged';
  end if;
  if not exists (select 1 from pg_roles where rolname = '{group}' and not rolcanlogin) then
    raise exception 'Expected Vouch runtime group is missing or can login';
  end if;
  if exists (
    select 1 from pg_auth_members m
    join pg_roles child on child.oid = m.member
    join pg_roles parent on parent.oid = m.roleid
    where child.rolname = '{role}' and parent.rolname <> '{group}'
  ) then
    raise exception 'Existing Vouch runtime role has unexpected membership';
  end if;
  if exists (select 1 from pg_roles where rolname = '{role}') then
    alter role {role} login inherit password '{password}' valid until 'infinity';
  else
    create role {role} login inherit nosuperuser nobypassrls nocreatedb nocreaterole
      noreplication password '{password}' valid until 'infinity';
  end if;
  grant {group} to {role};
end
$vouch$;
""".strip()
        )
    statements.extend(
        [
            "commit;",
            "select count(*) as verified_runtime_roles from pg_roles "
            "where rolname in ('vouch_runtime_api','vouch_runtime_worker',"
            "'vouch_runtime_retention','vouch_runtime_guest') and rolcanlogin "
            "and not rolsuper and not rolbypassrls and not rolcreatedb "
            "and not rolcreaterole and not rolreplication;",
        ]
    )
    return "\n\n".join(statements) + "\n"


def _provision_roles(project_ref: str, credentials: dict[str, Any]) -> None:
    temporary = PROJECT_ROOT / f".local/.hosted-roles-{project_ref}.sql"
    _atomic_write(temporary, _role_sql(credentials))
    try:
        output = _run_cli(
            "db",
            "query",
            "--linked",
            "--project-ref",
            project_ref,
            "--file",
            str(temporary),
            timeout=120,
        )
        if "verified_runtime_roles" not in output or "4" not in output:
            raise HostedSetupError("Hosted runtime-role verification did not complete.")
    finally:
        temporary.unlink(missing_ok=True)


def _database_urls(
    project_ref: str, credentials: dict[str, Any], host: str, port: int, database: str
) -> dict[str, str]:
    return {
        kind: URL.create(
            "postgresql+psycopg",
            username=f"{ROLE_NAMES[kind]}.{project_ref}",
            password=credentials["database_passwords"][kind],
            host=host,
            port=port,
            database=database,
            query={"sslmode": "require"},
        ).render_as_string(hide_password=False)
        for kind in RUNTIME_KINDS
    }


def _read_existing_meta_key() -> str | None:
    for path in (
        PROJECT_ROOT / "services/backend/.env.worker",
        PROJECT_ROOT / "services/backend/.env.hosted.worker",
    ):
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("VOUCH_META_API_KEY="):
                raw = line.split("=", 1)[1].strip()
                try:
                    value = json.loads(raw)
                except json.JSONDecodeError:
                    value = raw
                if isinstance(value, str) and value:
                    return value
    return None


def setup_hosted(project_ref: str) -> None:
    _validate_project_ref(project_ref)
    credentials = _credentials(project_ref)
    keys = _api_keys(project_ref)
    host, port, database = _pooler(project_ref)
    _provision_roles(project_ref, credentials)
    urls = _database_urls(project_ref, credentials, host, port, database)
    api_url = f"https://{project_ref}.supabase.co"
    meta_api_key = _read_existing_meta_key()
    for kind in RUNTIME_KINDS:
        values = {
            "VOUCH_AUTH_MODE": "supabase",
            "VOUCH_ENVIRONMENT": "development",
            "VOUCH_DATABASE_SCHEMA": "vouch",
            "VOUCH_DATABASE_URL": urls[kind],
            "VOUCH_SUPABASE_URL": api_url,
            "VOUCH_SUPABASE_PUBLISHABLE_KEY": keys["publishable"],
            "VOUCH_OPERATOR_REGION": "IN",
        }
        if kind in {"api", "retention"}:
            values["VOUCH_SUPABASE_SECRET_KEY"] = keys["secret"]
        if kind == "api":
            values["VOUCH_API_PORT"] = "8011"
            values["VOUCH_GUEST_DATABASE_URL"] = urls["guest"]
            values["VOUCH_GUEST_RATE_LIMIT_KEY"] = credentials["guest_rate_limit_key"]
            values["VOUCH_GUEST_STORAGE_KEY"] = keys["guest_storage"]
        if kind == "worker" and meta_api_key:
            values["VOUCH_META_API_KEY"] = meta_api_key
        _merge_env(PROJECT_ROOT / f"services/backend/.env.hosted.{kind}", values)
    _merge_env(
        PROJECT_ROOT / "apps/web/.env.local",
        {
            "NEXT_PUBLIC_AUTH_MODE": "supabase",
            "NEXT_PUBLIC_SUPABASE_URL": api_url,
            "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY": keys["publishable"],
            "NEXT_PUBLIC_GOOGLE_OAUTH_ENABLED": "true",
            "NEXT_PUBLIC_API_BASE_URL": "http://127.0.0.1:8011/api/v1",
        },
    )
    print("Hosted Vouch runtime setup complete for the explicitly linked project.")
    print("No fixture users or fixture domain data were created.")
    print("Runtime credentials were saved only to ignored local environment files.")
    print("Run: npm.cmd run dev:hosted")


def main() -> None:
    parser = argparse.ArgumentParser(description="Provision a linked hosted Vouch runtime.")
    parser.add_argument("--project-ref", required=True)
    args = parser.parse_args()
    try:
        setup_hosted(args.project_ref)
    except HostedSetupError as error:
        print(f"Hosted setup stopped: {error}", file=sys.stderr)
        raise SystemExit(1) from None
    except Exception:
        print(
            "Hosted setup failed safely; no credential or remote payload was printed.",
            file=sys.stderr,
        )
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
