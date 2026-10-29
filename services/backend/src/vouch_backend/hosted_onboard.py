"""Bind an exact hosted Auth subject to an explicitly provisioned Vouch membership."""

from __future__ import annotations

import argparse
import re
import sys
from uuid import UUID

from psycopg import sql

from .hosted_setup import HostedSetupError, _run_cli, _validate_project_ref
from .local_setup import PROJECT_ROOT, _atomic_write

ALLOWED_ROLES = ("admin", "marketer", "reviewer", "viewer")
SLUG_PATTERN = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?")


def _literal(value: str) -> str:
    return sql.Literal(value).as_string()


def _validate_text(name: str, value: str, maximum: int) -> str:
    stripped = value.strip()
    if (
        not stripped
        or len(stripped) > maximum
        or any(ord(character) < 32 for character in stripped)
    ):
        raise HostedSetupError(f"{name} must contain 1-{maximum} printable characters.")
    return stripped


def _onboarding_sql(
    auth_subject: UUID,
    organization_slug: str,
    organization_name: str,
    roles: tuple[str, ...],
) -> str:
    role_values = ", ".join(f"({_literal(role)})" for role in roles)
    audit_roles = ", ".join(_literal(role) for role in roles)
    return f"""
begin;
set local statement_timeout = '30s';
set local lock_timeout = '5s';

do $vouch$
declare
  requested_subject uuid := {_literal(str(auth_subject))}::uuid;
  auth_email text;
  auth_display_name text;
  domain_user_id uuid;
  target_organization_id uuid;
  target_membership_id uuid;
  existing_subject uuid;
begin
  select lower(email),
         coalesce(
           nullif(raw_user_meta_data->>'full_name', ''),
           split_part(email, '@', 1)
         )
    into auth_email, auth_display_name
    from auth.users
   where id = requested_subject
     and deleted_at is null
     and email_confirmed_at is not null;
  if not found or auth_email is null then
    raise exception 'Exact confirmed Auth subject was not found';
  end if;

  select organization.id into target_organization_id
    from vouch.organizations organization
   where organization.slug = {_literal(organization_slug)};
  if target_organization_id is null then
    target_organization_id := gen_random_uuid();
    insert into vouch.organizations (
      id, slug, name, budget_cap_minor, budget_held_minor, budget_settled_minor, budget_currency
    ) values (
      target_organization_id, {_literal(organization_slug)}, {_literal(organization_name)},
      0, 0, 0, 'USD'
    );
  elsif (select name from vouch.organizations where id = target_organization_id)
      <> {_literal(organization_name)} then
    raise exception 'Organization slug already belongs to a different name';
  end if;

  select id into domain_user_id from vouch.users where auth_subject = requested_subject;
  if domain_user_id is null then
    select id, auth_subject into domain_user_id, existing_subject
      from vouch.users where lower(email) = auth_email;
    if domain_user_id is not null and existing_subject is not null
       and existing_subject <> requested_subject then
      raise exception 'Email is already bound to a different Auth subject';
    end if;
  end if;
  if domain_user_id is null then
    domain_user_id := gen_random_uuid();
    insert into vouch.users (id, email, display_name, auth_subject)
    values (domain_user_id, auth_email, left(auth_display_name, 160), requested_subject);
  else
    update vouch.users set auth_subject = requested_subject
     where id = domain_user_id and auth_subject is null;
  end if;

  select membership.id into target_membership_id from vouch.memberships membership
   where membership.organization_id = target_organization_id
     and membership.user_id = domain_user_id;
  if target_membership_id is null then
    target_membership_id := gen_random_uuid();
    insert into vouch.memberships (id, organization_id, user_id, active)
    values (target_membership_id, target_organization_id, domain_user_id, true);
  elsif not (select active from vouch.memberships where id = target_membership_id) then
    raise exception 'Existing membership is revoked and was not reactivated';
  end if;

  insert into vouch.membership_roles (id, organization_id, membership_id, role)
  select gen_random_uuid(), target_organization_id, target_membership_id, requested.role
    from (values {role_values}) as requested(role)
  on conflict (membership_id, role) do nothing;

  insert into vouch.audit_events (
    id, organization_id, actor_user_id, actor_kind, action,
    resource_type, resource_id, safe_metadata, created_at
  ) values (
    gen_random_uuid(), target_organization_id, domain_user_id, 'member', 'membership.provisioned',
    'membership', target_membership_id,
    json_build_object(
      'source', 'hosted_operator_cli',
      'roles', array[{audit_roles}]
    ),
    now()
  );
end
$vouch$;

commit;
select 1 as onboarded_membership;
""".strip() + "\n"


def onboard(
    project_ref: str,
    auth_subject: UUID,
    organization_slug: str,
    organization_name: str,
    roles: tuple[str, ...],
) -> None:
    _validate_project_ref(project_ref)
    if not SLUG_PATTERN.fullmatch(organization_slug):
        raise HostedSetupError("Organization slug must be lowercase letters, digits, or hyphens.")
    organization_name = _validate_text("Organization name", organization_name, 160)
    normalized_roles = tuple(dict.fromkeys(roles))
    if not normalized_roles or any(role not in ALLOWED_ROLES for role in normalized_roles):
        raise HostedSetupError("At least one supported membership role is required.")
    temporary = PROJECT_ROOT / f".local/.hosted-onboard-{project_ref}.sql"
    _atomic_write(
        temporary,
        _onboarding_sql(
            auth_subject,
            organization_slug,
            organization_name,
            normalized_roles,
        ),
    )
    try:
        output = _run_cli(
            "db",
            "query",
            "--linked",
            "--project-ref",
            project_ref,
            "--file",
            str(temporary),
            timeout=90,
        )
        if "onboarded_membership" not in output:
            raise HostedSetupError("Hosted membership verification did not complete.")
    finally:
        temporary.unlink(missing_ok=True)
    print("Hosted Auth subject was bound to the requested Vouch membership.")
    print("No password, token, or broad tenant session was created.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Onboard an exact hosted Auth subject.")
    parser.add_argument("--project-ref", required=True)
    parser.add_argument("--auth-subject", required=True, type=UUID)
    parser.add_argument("--organization-slug", required=True)
    parser.add_argument("--organization-name", required=True)
    parser.add_argument("--role", action="append", choices=ALLOWED_ROLES, required=True)
    args = parser.parse_args()
    try:
        onboard(
            args.project_ref,
            args.auth_subject,
            args.organization_slug,
            args.organization_name,
            tuple(args.role),
        )
    except HostedSetupError as error:
        print(f"Hosted onboarding stopped: {error}", file=sys.stderr)
        raise SystemExit(1) from None
    except Exception:
        print(
            "Hosted onboarding failed safely; no credential or remote payload was printed.",
            file=sys.stderr,
        )
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
