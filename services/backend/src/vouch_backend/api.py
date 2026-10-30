from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Header, Query, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .auth import (
    Principal,
    VerifiedActor,
    authenticated_workspaces,
    get_principal,
    get_session,
    get_upload_principal,
    get_workspace_identity,
)
from .config import Settings
from .db import Database
from .errors import ApiError, not_found
from .guest_auth import (
    GUEST_COOKIE_NAME,
    GUEST_COOKIE_PATH,
    GuestPrincipal,
    get_guest_principal,
    guest_client_bucket,
    guest_cookie_secure,
    require_guest_origin,
)
from .guest_service import (
    UPLOAD_ACTION,
    create_guest_submission_version,
    create_guest_upload_intent,
    exchange_guest_invitation,
    finalize_guest_upload,
    guest_submission_context,
    issue_guest_invitation,
    put_guest_upload_content,
    renew_guest_invitation,
    require_guest_action,
    revoke_guest_invitation,
    withdraw_guest_source,
)
from .media import create_media_processor
from .models import Job, MediaAsset
from .notices import ProcessingNotice, get_guest_notice, get_notice
from .schemas import (
    ApprovalReportRead,
    CampaignBriefRead,
    CampaignCreate,
    CampaignCreatorCreate,
    CampaignCreatorRead,
    CampaignReadinessRead,
    CampaignRequirementCreate,
    CampaignRequirementRead,
    CampaignTrackRead,
    CheckCreate,
    ConsentReceiptRead,
    CreatorCatalogResponse,
    CreatorFeedbackCreate,
    CreatorFeedbackRead,
    CreatorMatchKind,
    CreatorPermissionStatus,
    CreatorVerificationStatus,
    DeletionRequestCreate,
    FindingDecisionCreate,
    FixRequestCreate,
    GuestExchangeCreate,
    GuestExchangeRead,
    GuestInvitationCreate,
    GuestInvitationRead,
    GuestMediaAssetRead,
    GuestSubmissionRead,
    GuestSubmissionVersionCreate,
    GuestSubmissionVersionRead,
    GuestUploadContentRead,
    GuestUploadFinalize,
    GuestUploadIntentCreate,
    GuestUploadIntentRead,
    OutcomeEventRead,
    ProductClaimCreate,
    ProductClaimRead,
    ReviewDecisionCreate,
    StorageUsageResponse,
    SubmissionCreate,
    SubmissionVersionCreate,
    TestOutcomeEventCreate,
    UploadFinalize,
    UploadIntentCreate,
)
from .seed import seed_fixture_data
from .service import (
    add_campaign_creator,
    approval_report,
    campaign_brief,
    campaign_dict,
    campaign_readiness,
    campaign_track_report,
    capabilities,
    catalog_creators,
    catalog_products,
    catalog_rule_packs,
    check_dict,
    comparison,
    consent_receipt_dict,
    create_campaign,
    create_campaign_requirement,
    create_check,
    create_deletion_request,
    create_fix_request,
    create_product_claim,
    create_submission,
    create_submission_version,
    finalize_upload,
    get_analysis,
    get_campaign,
    get_consent_receipt,
    get_deletion_request,
    get_submission,
    job_dict,
    list_audit,
    list_campaign_submissions,
    list_campaigns,
    list_deletion_requests,
    list_product_claims,
    publish_creator_feedback,
    read_media,
    record_finding_decision,
    record_test_outcome_event,
    review_decision,
    submission_dict,
    upload_content,
    upload_intent,
    usage,
    withdraw_processing_authorization,
    workspace_list,
)
from .storage import MAX_MEDIA_BYTES, SupabaseGuestMediaStore, SupabaseMediaStore
from .storage_quota import workspace_storage_usage

SessionDep = Annotated[Session, Depends(get_session)]
PrincipalDep = Annotated[Principal, Depends(get_principal)]
WorkspaceIdentityDep = Annotated[Principal | VerifiedActor, Depends(get_workspace_identity)]
UploadPrincipalDep = Annotated[Principal | None, Depends(get_upload_principal)]
GuestPrincipalDep = Annotated[GuestPrincipal, Depends(get_guest_principal)]


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or Settings.from_env()
    database = Database(
        app_settings.database_url,
        app_settings.database_schema,
        runtime_role="vouch_api" if app_settings.auth_mode == "supabase" else None,
    )
    guest_database = (
        Database(
            app_settings.guest_database_url,
            app_settings.database_schema,
            runtime_role="vouch_guest",
        )
        if app_settings.auth_mode == "supabase" and app_settings.guest_database_url
        else None
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        database.create_all()
        if guest_database is not None:
            guest_database.create_all()
        if app_settings.auth_mode == "fixture":
            with database.session_factory() as session:
                seed_fixture_data(session)
        yield
        if guest_database is not None:
            guest_database.dispose()
        database.dispose()

    app = FastAPI(
        title="Vouch API",
        version="0.1.0",
        description=(
            "Fixture-first API for workspace, campaign, evidence-backed Check, revision, "
            "and exact-version human approval."
        ),
        lifespan=lifespan,
    )
    app.state.database = database
    app.state.guest_database = guest_database
    app.state.settings = app_settings
    app.state.media_processor = create_media_processor(app_settings)
    app.state.media_store = (
        SupabaseMediaStore(app_settings) if app_settings.auth_mode == "supabase" else None
    )
    app.state.guest_media_store = (
        SupabaseGuestMediaStore(app_settings)
        if app_settings.auth_mode == "supabase" and app_settings.guest_storage_key
        else None
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(app_settings.cors_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=[
            "Accept",
            "Authorization",
            "Content-Type",
            "Idempotency-Key",
            "X-Fixture-User",
            "X-Organization-Id",
            "X-Upload-Token",
        ],
    )

    @app.middleware("http")
    async def attach_database_session(request: Request, call_next: Any) -> Response:
        request_database = (
            guest_database
            if request.url.path.startswith("/api/v1/guest/") and guest_database is not None
            else database
        )
        with request_database.session_factory() as session:
            request.state.session = session
            session.info["media_processor"] = app.state.media_processor
            if app.state.media_store is not None:
                session.info["media_store"] = app.state.media_store
            if app.state.guest_media_store is not None:
                session.info["guest_media_store"] = app.state.guest_media_store
            try:
                response = await call_next(request)
                if request.url.path.startswith("/api/v1/guest") or (
                    "/guest-invitations" in request.url.path
                ):
                    response.headers["Cache-Control"] = "no-store"
                    response.headers["Pragma"] = "no-cache"
                    response.headers["Referrer-Policy"] = "no-referrer"
                return response
            except Exception:
                session.rollback()
                raise

    @app.exception_handler(ApiError)
    async def api_error_handler(request: Request, error: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code,
            content={
                "error": {
                    "code": error.code,
                    "message": error.message,
                    "retryable": error.retryable,
                    "request_id": request.headers.get("X-Request-Id") or str(uuid4()),
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _request: Request, error: RequestValidationError
    ) -> JSONResponse:
        fields = [
            ".".join(str(part) for part in item["loc"] if part != "body") for item in error.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": "The request did not match the API contract.",
                    "retryable": False,
                    "fields": fields,
                }
            },
        )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "execution_mode": "fixture"}

    @app.get("/ready")
    def ready(session: SessionDep) -> dict[str, str]:
        session.execute(text("select 1"))
        return {"status": "ready", "database": "reachable", "execution_mode": "fixture"}

    @app.get("/api/v1/me/workspaces")
    def workspaces(session: SessionDep, identity: WorkspaceIdentityDep) -> dict[str, Any]:
        if isinstance(identity, VerifiedActor):
            return authenticated_workspaces(session, identity)
        return workspace_list(session, identity)

    @app.get("/api/v1/capabilities")
    def capability_list(
        principal: PrincipalDep,
        market: str = Query(default="IN", min_length=2, max_length=8),
    ) -> dict[str, Any]:
        _ = principal
        processor = app.state.media_processor
        return capabilities(
            market,
            {
                "mode": processor.mode,
                "processor_version": processor.processor_version,
            },
        )

    @app.get("/api/v1/products")
    def products(session: SessionDep, principal: PrincipalDep) -> dict[str, Any]:
        return catalog_products(session, principal)

    @app.get(
        "/api/v1/products/{product_id}/claims",
        response_model=list[ProductClaimRead],
    )
    def product_claims(
        product_id: UUID, session: SessionDep, principal: PrincipalDep
    ) -> list[dict[str, Any]]:
        return list_product_claims(session, principal, product_id)

    @app.post(
        "/api/v1/products/{product_id}/claims",
        response_model=ProductClaimRead,
        status_code=status.HTTP_201_CREATED,
    )
    def product_claim_create(
        product_id: UUID,
        payload: ProductClaimCreate,
        session: SessionDep,
        principal: PrincipalDep,
    ) -> dict[str, Any]:
        return create_product_claim(session, principal, product_id, payload)

    @app.get("/api/v1/creators", response_model=CreatorCatalogResponse)
    def creators(
        session: SessionDep,
        principal: PrincipalDep,
        q: str | None = Query(default=None, min_length=1, max_length=160),
        category: str | None = Query(default=None, min_length=1, max_length=80),
        match_kind: CreatorMatchKind | None = None,
        permission_status: CreatorPermissionStatus | None = None,
        verification_status: CreatorVerificationStatus | None = None,
        product_id: UUID | None = None,
    ) -> dict[str, Any]:
        return catalog_creators(
            session,
            principal,
            query=q,
            category=category,
            match_kind=match_kind,
            permission_status=permission_status,
            verification_status=verification_status,
            product_id=product_id,
        )

    @app.get("/api/v1/rule-pack-versions")
    def rule_packs(session: SessionDep, principal: PrincipalDep) -> dict[str, Any]:
        return catalog_rule_packs(session, principal)

    @app.get("/api/v1/campaigns")
    def campaigns(session: SessionDep, principal: PrincipalDep) -> dict[str, Any]:
        return list_campaigns(session, principal)

    @app.post("/api/v1/campaigns", status_code=status.HTTP_201_CREATED)
    def campaign_create(
        payload: CampaignCreate, session: SessionDep, principal: PrincipalDep
    ) -> dict[str, Any]:
        return create_campaign(session, principal, payload)

    @app.get("/api/v1/campaigns/{campaign_id}")
    def campaign_get(
        campaign_id: UUID, session: SessionDep, principal: PrincipalDep
    ) -> dict[str, Any]:
        return campaign_dict(session, get_campaign(session, principal, campaign_id))

    @app.get(
        "/api/v1/campaigns/{campaign_id}/readiness",
        response_model=CampaignReadinessRead,
    )
    def campaign_readiness_get(
        campaign_id: UUID,
        response: Response,
        session: SessionDep,
        principal: PrincipalDep,
    ) -> CampaignReadinessRead:
        response.headers["Cache-Control"] = "no-store"
        return CampaignReadinessRead.model_validate(
            campaign_readiness(session, principal, campaign_id)
        )

    @app.get(
        "/api/v1/campaigns/{campaign_id}/brief",
        response_model=CampaignBriefRead,
    )
    def campaign_brief_get(
        campaign_id: UUID,
        response: Response,
        session: SessionDep,
        principal: PrincipalDep,
    ) -> CampaignBriefRead:
        response.headers["Cache-Control"] = "no-store"
        return CampaignBriefRead.model_validate(campaign_brief(session, principal, campaign_id))

    @app.post(
        "/api/v1/campaigns/{campaign_id}/requirements",
        response_model=CampaignRequirementRead,
        status_code=status.HTTP_201_CREATED,
    )
    def campaign_requirement_create(
        campaign_id: UUID,
        payload: CampaignRequirementCreate,
        session: SessionDep,
        principal: PrincipalDep,
    ) -> dict[str, Any]:
        return create_campaign_requirement(session, principal, campaign_id, payload)

    @app.get(
        "/api/v1/campaigns/{campaign_id}/track",
        response_model=CampaignTrackRead,
    )
    def campaign_track(
        campaign_id: UUID, session: SessionDep, principal: PrincipalDep
    ) -> dict[str, Any]:
        return campaign_track_report(session, principal, campaign_id)

    @app.post(
        "/api/v1/campaigns/{campaign_id}/track/test-events",
        response_model=OutcomeEventRead,
        status_code=status.HTTP_201_CREATED,
    )
    def campaign_track_test_event(
        campaign_id: UUID,
        payload: TestOutcomeEventCreate,
        response: Response,
        session: SessionDep,
        principal: PrincipalDep,
    ) -> dict[str, Any]:
        event, created = record_test_outcome_event(
            session, principal, campaign_id, payload
        )
        if not created:
            response.status_code = status.HTTP_200_OK
        return event

    @app.post(
        "/api/v1/campaigns/{campaign_id}/creators",
        status_code=status.HTTP_201_CREATED,
        response_model=CampaignCreatorRead,
    )
    def campaign_creator_create(
        campaign_id: UUID,
        payload: CampaignCreatorCreate,
        response: Response,
        session: SessionDep,
        principal: PrincipalDep,
    ) -> dict[str, Any]:
        result, created = add_campaign_creator(session, principal, campaign_id, payload)
        if not created:
            response.status_code = status.HTTP_200_OK
        return result

    @app.get("/api/v1/campaigns/{campaign_id}/submissions")
    def campaign_submissions(
        campaign_id: UUID, session: SessionDep, principal: PrincipalDep
    ) -> dict[str, Any]:
        return list_campaign_submissions(session, principal, campaign_id)

    @app.post(
        "/api/v1/campaigns/{campaign_id}/guest-invitations",
        status_code=status.HTTP_201_CREATED,
        response_model=GuestInvitationRead,
    )
    def guest_invitation_create(
        campaign_id: UUID,
        payload: GuestInvitationCreate,
        session: SessionDep,
        principal: PrincipalDep,
    ) -> dict[str, Any]:
        return issue_guest_invitation(session, principal, app_settings, campaign_id, payload)

    @app.post("/api/v1/guest-invitations/{grant_id}/revoke", status_code=202)
    def guest_invitation_revoke(
        grant_id: UUID,
        session: SessionDep,
        principal: PrincipalDep,
    ) -> dict[str, str]:
        return revoke_guest_invitation(session, principal, app_settings, grant_id)

    @app.post(
        "/api/v1/guest-invitations/{grant_id}/renew",
        status_code=status.HTTP_201_CREATED,
        response_model=GuestInvitationRead,
    )
    def guest_invitation_renew(
        grant_id: UUID,
        session: SessionDep,
        principal: PrincipalDep,
    ) -> dict[str, Any]:
        return renew_guest_invitation(session, principal, app_settings, grant_id)

    @app.post("/api/v1/guest/exchange", response_model=GuestExchangeRead)
    def guest_exchange(
        payload: GuestExchangeCreate,
        request: Request,
        response: Response,
        session: SessionDep,
    ) -> dict[str, Any]:
        require_guest_origin(request)
        session_secret, expires_at = exchange_guest_invitation(
            session,
            app_settings,
            payload.invitation_secret,
            guest_client_bucket(request),
        )
        max_age = max(0, int((expires_at - datetime.now(UTC)).total_seconds()))
        response.set_cookie(
            GUEST_COOKIE_NAME,
            session_secret,
            max_age=max_age,
            expires=expires_at,
            path=GUEST_COOKIE_PATH,
            secure=guest_cookie_secure(app_settings.guest_public_origin),
            httponly=True,
            samesite="strict",
        )
        return {"status": "active", "expires_at": expires_at}

    @app.get("/api/v1/guest/submission", response_model=GuestSubmissionRead)
    def guest_submission(
        session: SessionDep,
        principal: GuestPrincipalDep,
    ) -> dict[str, Any]:
        return guest_submission_context(session, principal)

    @app.get(
        "/api/v1/guest/notices/campaign-check",
        response_model=ProcessingNotice,
    )
    def guest_processing_notice(principal: GuestPrincipalDep) -> dict[str, Any]:
        require_guest_action(principal, UPLOAD_ACTION)
        return get_guest_notice().model_dump(mode="json")

    @app.post(
        "/api/v1/guest/uploads",
        status_code=status.HTTP_201_CREATED,
        response_model=GuestUploadIntentRead,
    )
    def guest_upload_create(
        payload: GuestUploadIntentCreate,
        request: Request,
        session: SessionDep,
        principal: GuestPrincipalDep,
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    ) -> dict[str, Any]:
        require_guest_origin(request)
        return create_guest_upload_intent(
            session,
            principal,
            app_settings,
            payload,
            idempotency_key,
        )

    @app.put(
        "/api/v1/guest/uploads/{upload_id}/content",
        response_model=GuestUploadContentRead,
    )
    async def guest_upload_put(
        upload_id: UUID,
        request: Request,
        session: SessionDep,
        principal: GuestPrincipalDep,
        upload_token: Annotated[str | None, Header(alias="X-Upload-Token")] = None,
        content_type: Annotated[str | None, Header(alias="Content-Type")] = None,
    ) -> dict[str, Any]:
        require_guest_origin(request)
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > MAX_MEDIA_BYTES:
                raise ApiError(413, "UPLOAD_TOO_LARGE", "The upload exceeds the 5 MB limit.")
            body.extend(chunk)
        return put_guest_upload_content(
            session,
            principal,
            app_settings,
            upload_id,
            upload_token,
            content_type,
            bytes(body),
        )

    @app.post(
        "/api/v1/guest/uploads/{upload_id}/finalize",
        response_model=GuestMediaAssetRead,
    )
    def guest_upload_finalize(
        upload_id: UUID,
        payload: GuestUploadFinalize,
        request: Request,
        session: SessionDep,
        principal: GuestPrincipalDep,
    ) -> dict[str, Any]:
        require_guest_origin(request)
        return finalize_guest_upload(
            session,
            principal,
            app_settings,
            upload_id,
            payload.finalize_token,
        )

    @app.post(
        "/api/v1/guest/submission-versions",
        status_code=status.HTTP_201_CREATED,
        response_model=GuestSubmissionVersionRead,
    )
    def guest_submission_version_create(
        payload: GuestSubmissionVersionCreate,
        request: Request,
        session: SessionDep,
        principal: GuestPrincipalDep,
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    ) -> dict[str, Any]:
        require_guest_origin(request)
        return create_guest_submission_version(
            session,
            principal,
            payload,
            idempotency_key,
        )

    @app.post("/api/v1/guest/consent-receipts/{receipt_id}/withdraw", status_code=202)
    def guest_consent_withdraw(
        receipt_id: UUID,
        request: Request,
        session: SessionDep,
        principal: GuestPrincipalDep,
    ) -> dict[str, Any]:
        require_guest_origin(request)
        return withdraw_guest_source(session, principal, receipt_id)

    @app.post("/api/v1/uploads", status_code=status.HTTP_201_CREATED)
    def upload_create(
        payload: UploadIntentCreate, session: SessionDep, principal: PrincipalDep
    ) -> dict[str, Any]:
        return upload_intent(session, principal, payload)

    @app.get("/api/v1/notices/campaign-check", response_model=ProcessingNotice)
    def current_processing_notice() -> dict[str, Any]:
        return get_notice().model_dump(mode="json")

    @app.get("/api/v1/notices/campaign-check/{version}", response_model=ProcessingNotice)
    def versioned_processing_notice(version: str) -> dict[str, Any]:
        return get_notice(version).model_dump(mode="json")

    @app.get("/api/v1/consent-receipts/{receipt_id}", response_model=ConsentReceiptRead)
    def consent_get(
        receipt_id: UUID, session: SessionDep, principal: PrincipalDep
    ) -> dict[str, Any]:
        return consent_receipt_dict(get_consent_receipt(session, principal, receipt_id))

    @app.post("/api/v1/consent-receipts/{receipt_id}/withdraw", status_code=202)
    def consent_withdraw(
        receipt_id: UUID, session: SessionDep, principal: PrincipalDep
    ) -> dict[str, Any]:
        return withdraw_processing_authorization(session, principal, receipt_id)

    @app.put("/api/v1/uploads/{upload_id}/content")
    async def upload_put(
        upload_id: UUID,
        request: Request,
        session: SessionDep,
        principal: UploadPrincipalDep,
        upload_token: Annotated[str | None, Header(alias="X-Upload-Token")] = None,
        content_type: Annotated[str | None, Header(alias="Content-Type")] = None,
    ) -> dict[str, Any]:
        if principal is not None:
            asset = session.scalar(
                select(MediaAsset).where(
                    MediaAsset.id == upload_id,
                    MediaAsset.organization_id == principal.organization_id,
                    MediaAsset.uploader_user_id == principal.user_id,
                )
            )
            if asset is None:
                raise not_found()
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > 5_000_000:
                raise ApiError(413, "UPLOAD_TOO_LARGE", "The upload exceeds the 5 MB limit.")
            body.extend(chunk)
        return upload_content(
            session, upload_id, upload_token, content_type, bytes(body), principal
        )

    @app.get("/api/v1/uploads/{upload_id}/content")
    def upload_get(upload_id: UUID, session: SessionDep, principal: PrincipalDep) -> Response:
        body, content_type = read_media(session, principal, upload_id)
        return Response(
            content=body,
            media_type=content_type,
            headers={
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "Content-Disposition": "attachment; filename=draft-media",
            },
        )

    @app.post("/api/v1/uploads/{upload_id}/finalize")
    def upload_finalize(
        upload_id: UUID,
        payload: UploadFinalize,
        session: SessionDep,
        principal: PrincipalDep,
    ) -> dict[str, Any]:
        return finalize_upload(session, principal, upload_id, payload.finalize_token)

    @app.post("/api/v1/campaigns/{campaign_id}/submissions", status_code=201)
    def submission_create(
        campaign_id: UUID,
        payload: SubmissionCreate,
        session: SessionDep,
        principal: PrincipalDep,
    ) -> dict[str, Any]:
        return create_submission(session, principal, campaign_id, payload)

    @app.get("/api/v1/submissions/{submission_id}")
    def submission_get(
        submission_id: UUID, session: SessionDep, principal: PrincipalDep
    ) -> dict[str, Any]:
        return submission_dict(session, get_submission(session, principal, submission_id))

    @app.post("/api/v1/submissions/{submission_id}/versions", status_code=201)
    def submission_version_create(
        submission_id: UUID,
        payload: SubmissionVersionCreate,
        session: SessionDep,
        principal: PrincipalDep,
    ) -> dict[str, Any]:
        return create_submission_version(session, principal, submission_id, payload)

    @app.post("/api/v1/submission-versions/{version_id}/checks", status_code=202)
    def check_create(
        version_id: UUID,
        payload: CheckCreate,
        session: SessionDep,
        principal: PrincipalDep,
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    ) -> Response:
        result, created = create_check(session, principal, version_id, payload, idempotency_key)
        return JSONResponse(status_code=202 if created else 200, content=result)

    @app.get("/api/v1/jobs/{job_id}")
    def job_get(job_id: UUID, session: SessionDep, principal: PrincipalDep) -> dict[str, Any]:
        job = session.scalar(
            select(Job).where(
                Job.id == job_id,
                Job.organization_id == principal.organization_id,
            )
        )
        if job is None:
            raise not_found()
        return job_dict(job)

    @app.get("/api/v1/checks/{analysis_id}")
    def check_get(
        analysis_id: UUID, session: SessionDep, principal: PrincipalDep
    ) -> dict[str, Any]:
        return check_dict(session, get_analysis(session, principal, analysis_id))

    @app.get("/api/v1/checks/{analysis_id}/comparison")
    def check_comparison(
        analysis_id: UUID,
        previous_check_id: UUID,
        session: SessionDep,
        principal: PrincipalDep,
    ) -> dict[str, Any]:
        return comparison(session, principal, analysis_id, previous_check_id)

    @app.post("/api/v1/findings/{finding_id}/decisions")
    def finding_decide(
        finding_id: UUID,
        payload: FindingDecisionCreate,
        session: SessionDep,
        principal: PrincipalDep,
    ) -> dict[str, Any]:
        return record_finding_decision(session, principal, finding_id, payload)

    @app.post("/api/v1/checks/{analysis_id}/fix-request-drafts", status_code=201)
    def fix_request_create(
        analysis_id: UUID,
        payload: FixRequestCreate,
        session: SessionDep,
        principal: PrincipalDep,
    ) -> dict[str, Any]:
        return create_fix_request(session, principal, analysis_id, payload)

    @app.post(
        "/api/v1/checks/{analysis_id}/creator-feedback",
        response_model=CreatorFeedbackRead,
        status_code=201,
    )
    def creator_feedback_create(
        analysis_id: UUID,
        payload: CreatorFeedbackCreate,
        response: Response,
        session: SessionDep,
        principal: PrincipalDep,
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    ) -> dict[str, Any]:
        result, created = publish_creator_feedback(
            session, principal, analysis_id, payload, idempotency_key
        )
        response.status_code = 201 if created else 200
        return result

    @app.post("/api/v1/checks/{analysis_id}/review-decisions")
    def review_decide(
        analysis_id: UUID,
        payload: ReviewDecisionCreate,
        session: SessionDep,
        principal: PrincipalDep,
    ) -> dict[str, Any]:
        return review_decision(session, principal, analysis_id, payload)

    @app.get(
        "/api/v1/checks/{analysis_id}/approval-report",
        response_model=ApprovalReportRead,
    )
    def approval_report_get(
        analysis_id: UUID,
        response: Response,
        session: SessionDep,
        principal: PrincipalDep,
    ) -> ApprovalReportRead:
        response.headers["Cache-Control"] = "no-store"
        return ApprovalReportRead.model_validate(
            approval_report(session, principal, analysis_id)
        )

    @app.get("/api/v1/usage")
    def usage_get(session: SessionDep, principal: PrincipalDep) -> dict[str, Any]:
        return usage(session, principal)

    @app.get("/api/v1/storage/usage", response_model=StorageUsageResponse)
    def storage_usage_get(
        session: SessionDep, principal: PrincipalDep, response: Response
    ) -> StorageUsageResponse:
        response.headers["Cache-Control"] = "no-store"
        return workspace_storage_usage(session, principal)

    @app.get("/api/v1/audit")
    def audit_get(session: SessionDep, principal: PrincipalDep) -> dict[str, Any]:
        return list_audit(session, principal)

    @app.post("/api/v1/deletion-requests", status_code=202)
    def deletion_create(
        payload: DeletionRequestCreate,
        session: SessionDep,
        principal: PrincipalDep,
    ) -> dict[str, Any]:
        return create_deletion_request(session, principal, payload)

    @app.get("/api/v1/deletion-requests/{deletion_id}")
    def deletion_get(
        deletion_id: UUID, session: SessionDep, principal: PrincipalDep
    ) -> dict[str, Any]:
        return get_deletion_request(session, principal, deletion_id)

    @app.get("/api/v1/deletion-requests")
    def deletion_list(
        session: SessionDep,
        principal: PrincipalDep,
        campaign_id: UUID | None = None,
    ) -> dict[str, Any]:
        return list_deletion_requests(session, principal, campaign_id)

    return app


app = create_app()
