from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass, field
from typing import Annotated, Any
from uuid import UUID

import httpx
from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .config import Settings
from .db import set_database_scope
from .errors import ApiError, bad_request, forbidden
from .models import Membership, MembershipRole, Organization, User

bearer_scheme = HTTPBearer(
    auto_error=False,
    scheme_name="SupabaseBearer",
    bearerFormat="JWT",
    description=(
        "Required in Supabase mode; verified against the configured Auth server. "
        "Fixture headers are supported only in explicit local development/test mode."
    ),
)
BearerDep = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]


@dataclass(frozen=True, slots=True)
class Principal:
    organization_id: UUID
    organization_name: str
    user_id: UUID
    email: str
    display_name: str
    roles: frozenset[str]
    access_token: str | None = field(default=None, repr=False)


@dataclass(frozen=True, slots=True)
class VerifiedActor:
    user_id: UUID
    email: str
    display_name: str
    auth_subject: UUID
    access_token: str = field(repr=False)


def get_session(request: Request) -> Session:
    return request.state.session


def verify_supabase_token(settings: Settings, token: str) -> UUID:
    """Verify with the configured Auth origin, never user-supplied JWT claims or URLs."""
    if not settings.supabase_url or not settings.supabase_publishable_key:
        raise RuntimeError("Supabase authentication is not configured.")
    try:
        with httpx.Client(timeout=5.0, follow_redirects=False, trust_env=False) as client:
            response = client.get(
                f"{settings.supabase_url.rstrip('/')}/auth/v1/user",
                headers={
                    "apikey": settings.supabase_publishable_key,
                    "Authorization": f"Bearer {token}",
                },
            )
    except httpx.HTTPError as error:
        raise ApiError(
            503, "AUTH_UNAVAILABLE", "Sign-in verification is temporarily unavailable.", True
        ) from error
    if response.status_code in {401, 403}:
        raise ApiError(401, "AUTH_INVALID", "Sign in again to continue.")
    if response.status_code != 200:
        raise ApiError(
            503, "AUTH_UNAVAILABLE", "Sign-in verification is temporarily unavailable.", True
        )
    try:
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("id"), str):
            raise ValueError("Missing authenticated subject")
        return UUID(payload["id"])
    except (ValueError, TypeError) as error:
        raise ApiError(
            503, "AUTH_UNAVAILABLE", "Sign-in verification is temporarily unavailable.", True
        ) from error


def get_actor(request: Request, session: Session) -> VerifiedActor:
    if any(name in request.headers for name in {"X-Fixture-User", "X-Fixture-Roles"}):
        raise bad_request(
            "FIXTURE_HEADERS_REJECTED", "Fixture identity headers are not accepted in this mode."
        )
    authorization = request.headers.get("Authorization", "")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer" or len(parts[1]) > 16_384:
        raise ApiError(401, "AUTH_REQUIRED", "Sign in to continue.")
    token = parts[1]
    subject = verify_supabase_token(request.app.state.settings, token)
    set_database_scope(session, auth_subject=subject)
    user = session.scalar(select(User).where(User.auth_subject == subject))
    if user is None:
        raise forbidden("USER_NOT_PROVISIONED", "This account has no Vouch access.")
    set_database_scope(session, auth_subject=subject, user_id=user.id)
    return VerifiedActor(user.id, user.email, user.display_name, subject, token)


def get_principal(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    organization: Annotated[str | None, Header(alias="X-Organization-Id")] = None,
    fixture_user: Annotated[str | None, Header(alias="X-Fixture-User")] = None,
    caller_roles: Annotated[str | None, Header(alias="X-Fixture-Roles")] = None,
    _bearer: BearerDep = None,
) -> Principal:
    if request.app.state.settings.auth_mode == "supabase":
        actor = get_actor(request, session)
        try:
            org_id = UUID(organization or "")
        except ValueError as error:
            raise bad_request(
                "ORGANIZATION_REQUIRED", "Select an organization to continue."
            ) from error
        set_database_scope(
            session, auth_subject=actor.auth_subject, user_id=actor.user_id, organization_id=org_id
        )
        membership = session.scalar(
            select(Membership).where(
                Membership.organization_id == org_id,
                Membership.user_id == actor.user_id,
                Membership.active.is_(True),
            )
        )
        if membership is None:
            raise forbidden("MEMBERSHIP_INACTIVE", "No active membership was found.")
        org = session.scalar(select(Organization).where(Organization.id == org_id))
        if org is None:
            raise forbidden("MEMBERSHIP_INACTIVE", "No active membership was found.")
        roles = frozenset(
            session.scalars(
                select(MembershipRole.role).where(
                    MembershipRole.membership_id == membership.id,
                    MembershipRole.organization_id == org_id,
                )
            ).all()
        )
        return Principal(
            org.id,
            org.name,
            actor.user_id,
            actor.email,
            actor.display_name,
            roles,
            actor.access_token,
        )
    if caller_roles is not None:
        raise bad_request(
            "CALLER_ROLES_REJECTED",
            "Roles are resolved server-side and must not be supplied by the caller.",
        )
    if not organization or not fixture_user:
        raise ApiError(
            401,
            "FIXTURE_AUTH_REQUIRED",
            "X-Organization-Id and X-Fixture-User are required in fixture mode.",
        )
    org_terms = [Organization.slug == organization]
    with suppress(ValueError):
        org_terms.append(Organization.id == UUID(organization))
    org = session.scalar(select(Organization).where(or_(*org_terms)))
    if org is None:
        raise ApiError(401, "FIXTURE_AUTH_INVALID", "Fixture identity is invalid.")
    user_terms = [User.email == fixture_user.lower()]
    with suppress(ValueError):
        user_terms.append(User.id == UUID(fixture_user))
    user = session.scalar(select(User).where(or_(*user_terms)))
    if user is None:
        raise ApiError(401, "FIXTURE_AUTH_INVALID", "Fixture identity is invalid.")
    membership = session.scalar(
        select(Membership).where(
            Membership.organization_id == org.id,
            Membership.user_id == user.id,
            Membership.active.is_(True),
        )
    )
    if membership is None:
        raise ApiError(401, "MEMBERSHIP_INACTIVE", "No active membership was found.")
    roles = frozenset(
        session.scalars(
            select(MembershipRole.role).where(MembershipRole.membership_id == membership.id)
        ).all()
    )
    return Principal(
        organization_id=org.id,
        organization_name=org.name,
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        roles=roles,
    )


def get_workspace_identity(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    organization: Annotated[str | None, Header(alias="X-Organization-Id")] = None,
    fixture_user: Annotated[str | None, Header(alias="X-Fixture-User")] = None,
    caller_roles: Annotated[str | None, Header(alias="X-Fixture-Roles")] = None,
    _bearer: BearerDep = None,
) -> Principal | VerifiedActor:
    if request.app.state.settings.auth_mode == "supabase":
        return get_actor(request, session)
    return get_principal(request, session, organization, fixture_user, caller_roles)


def authenticated_workspaces(session: Session, actor: VerifiedActor) -> dict[str, Any]:
    memberships = session.scalars(
        select(Membership).where(Membership.user_id == actor.user_id, Membership.active.is_(True))
    ).all()
    items = []
    for membership in memberships:
        org = session.scalar(
            select(Organization).where(Organization.id == membership.organization_id)
        )
        if org is None:
            continue
        roles = session.scalars(
            select(MembershipRole.role).where(
                MembershipRole.membership_id == membership.id,
                MembershipRole.organization_id == membership.organization_id,
            )
        ).all()
        items.append(
            {
                "id": str(org.id),
                "name": org.name,
                "roles": sorted(roles),
                "user": {
                    "id": str(actor.user_id),
                    "email": actor.email,
                    "display_name": actor.display_name,
                },
            }
        )
    return {
        "items": sorted(items, key=lambda item: (item["name"], item["id"])),
        "user": {
            "id": str(actor.user_id),
            "email": actor.email,
            "display_name": actor.display_name,
        },
    }


def get_upload_principal(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    organization: Annotated[str | None, Header(alias="X-Organization-Id")] = None,
    fixture_user: Annotated[str | None, Header(alias="X-Fixture-User")] = None,
    caller_roles: Annotated[str | None, Header(alias="X-Fixture-Roles")] = None,
    _bearer: BearerDep = None,
) -> Principal | None:
    if request.app.state.settings.auth_mode == "fixture":
        return None
    return get_principal(request, session, organization, fixture_user, caller_roles)


def require_roles(principal: Principal, *allowed: str) -> None:
    if principal.roles.isdisjoint(allowed):
        raise forbidden()
