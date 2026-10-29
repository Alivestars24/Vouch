from __future__ import annotations

import logging
import socket
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from sqlalchemy import and_, or_, select

from .config import Settings
from .db import Database, set_database_scope
from .models import (
    Analysis,
    BudgetReservation,
    Campaign,
    EvidenceItem,
    Finding,
    Job,
    MediaAsset,
    ModelCall,
    ReviewContext,
    RulePackVersion,
    Submission,
    SubmissionVersion,
    Tombstone,
    utcnow,
)
from .providers import (
    EvidenceResult,
    FindingResult,
    FixtureProviders,
    ProviderContext,
    ProviderError,
)
from .schemas import CheckCreate
from .seed import seed_fixture_data
from .service import (
    _manifest,
    audit,
    release_reservation,
    source_authorization_active,
    source_authorization_receipt,
    source_expired,
    stable_hash,
)

LOGGER = logging.getLogger("vouch.worker")
LEASE_SECONDS = 30
FIXTURE_ADAPTER_VERSION = "fixture-adapter.v1"


@dataclass(frozen=True, slots=True)
class ClaimedJob:
    job_id: UUID
    fence: int
    attempt: int


def _start_model_call(database: Database, claim: ClaimedJob, capability: str) -> UUID:
    with database.session_factory() as session:
        job = session.get(Job, claim.job_id)
        if job is None or job.status != "running" or job.fence != claim.fence:
            raise ProviderError("CANCELLED", "The job lease is no longer current.", retryable=False)
        set_database_scope(session, organization_id=job.organization_id)
        analysis = session.get(Analysis, job.resource_id)
        reservation = session.scalar(
            select(BudgetReservation).where(BudgetReservation.job_id == job.id)
        )
        if analysis is None or reservation is None:
            raise ProviderError(
                "INVALID_INPUT", "The model-call envelope is incomplete.", retryable=False
            )
        requested_model = analysis.model_versions.get(capability)
        if not isinstance(requested_model, str) or not requested_model:
            raise ProviderError(
                "INVALID_INPUT", "The pinned model version is missing.", retryable=False
            )
        existing = session.scalar(
            select(ModelCall).where(
                ModelCall.organization_id == job.organization_id,
                ModelCall.job_id == job.id,
                ModelCall.attempt_no == claim.attempt,
                ModelCall.capability == capability,
            )
        )
        if existing is not None:
            return existing.id
        model_call = ModelCall(
            organization_id=job.organization_id,
            job_id=job.id,
            analysis_id=analysis.id,
            budget_reservation_id=reservation.id,
            logical_operation_key=f"{job.logical_key}:{capability}:{claim.attempt}",
            capability=capability,
            attempt_no=claim.attempt,
            invocation_mode=analysis.invocation_mode,
            provider="fixture",
            requested_model=requested_model,
            prompt_version=analysis.prompt_version,
            schema_version=analysis.schema_version,
            adapter_version=FIXTURE_ADAPTER_VERSION,
            status="in_flight",
            usage_units={},
            cost_known=True,
            cost_minor=0,
            currency=reservation.currency,
        )
        session.add(model_call)
        session.commit()
        return model_call.id


def _finish_model_call(
    database: Database,
    claim: ClaimedJob,
    model_call_id: UUID,
    *,
    error: ProviderError | None = None,
) -> None:
    with database.session_factory() as session:
        job = session.get(Job, claim.job_id)
        if job is None:
            return
        set_database_scope(session, organization_id=job.organization_id)
        model_call = session.scalar(
            select(ModelCall)
            .where(
                ModelCall.id == model_call_id,
                ModelCall.organization_id == job.organization_id,
                ModelCall.job_id == job.id,
                ModelCall.attempt_no == claim.attempt,
            )
            .with_for_update()
        )
        if model_call is None or model_call.status != "in_flight":
            return
        model_call.completed_at = utcnow()
        if error is None:
            model_call.status = "succeeded"
            model_call.returned_model = model_call.requested_model
        else:
            model_call.status = "outcome_unknown" if error.code == "OUTCOME_UNKNOWN" else "failed"
            model_call.error_code = error.code
            model_call.retryable = error.retryable
            if error.code == "OUTCOME_UNKNOWN":
                model_call.cost_known = False
                model_call.cost_minor = None
        session.commit()


def _invoke_model_call[T](
    database: Database,
    claim: ClaimedJob,
    capability: str,
    operation: Callable[[], T],
) -> T:
    model_call_id = _start_model_call(database, claim, capability)
    try:
        result = operation()
    except ProviderError as error:
        _finish_model_call(database, claim, model_call_id, error=error)
        raise
    except Exception:
        internal_error = ProviderError(
            "WORKER_INTERNAL_ERROR",
            "The fixture worker failed safely. See the local worker log.",
            retryable=False,
        )
        _finish_model_call(database, claim, model_call_id, error=internal_error)
        raise
    _finish_model_call(database, claim, model_call_id)
    return result


def claim_next_job(database: Database, worker_id: str) -> ClaimedJob | None:
    now = utcnow()
    with database.session_factory() as session:
        eligible = or_(
            Job.status == "queued",
            and_(Job.status == "retry_wait", Job.retry_after <= now),
            and_(Job.status == "running", Job.lease_until < now),
        )
        candidate = session.scalar(select(Job).where(eligible).order_by(Job.created_at).limit(1))
        if candidate is None:
            return None
        set_database_scope(session, organization_id=candidate.organization_id)
        analysis = session.get(Analysis, candidate.resource_id)
        version = (
            session.get(SubmissionVersion, analysis.submission_version_id) if analysis else None
        )
        if version is not None:
            session.scalar(
                select(Submission)
                .where(
                    Submission.id == version.submission_id,
                    Submission.organization_id == candidate.organization_id,
                )
                .with_for_update()
            )
        job = session.scalar(
            select(Job)
            .where(Job.id == candidate.id, eligible)
            .with_for_update(skip_locked=True)
            .execution_options(populate_existing=True)
        )
        if job is None:
            return None
        job.status = "running"
        job.attempt_count += 1
        job.fence += 1
        job.lease_owner = worker_id
        job.lease_until = now + timedelta(seconds=LEASE_SECONDS)
        job.retry_after = None
        job.updated_at = now
        if analysis is not None:
            analysis.analysis_status = "running"
        session.commit()
        return ClaimedJob(job.id, job.fence, job.attempt_count)


def _validate_evidence(item: EvidenceResult, duration_ms: int) -> None:
    if item.start_ms is not None or item.end_ms is not None:
        if item.start_ms is None or item.end_ms is None:
            raise ProviderError(
                "INVALID_PROVIDER_OUTPUT",
                "Fixture evidence returned an incomplete time range.",
                retryable=False,
            )
        if not 0 <= item.start_ms < item.end_ms <= duration_ms:
            raise ProviderError(
                "INVALID_PROVIDER_OUTPUT",
                "Fixture evidence returned a time range outside the source.",
                retryable=False,
            )
    for start_ms, end_ms in item.missing_intervals:
        if not 0 <= start_ms < end_ms <= duration_ms:
            raise ProviderError(
                "INVALID_PROVIDER_OUTPUT",
                "Fixture evidence returned an invalid missing interval.",
                retryable=False,
            )


def _validate_finding(
    item: FindingResult,
    evidence: list[EvidenceResult],
    duration_ms: int,
    allowed_rules: set[tuple[str, str]],
) -> None:
    if (item.rule_id, item.rule_version) not in allowed_rules:
        raise ProviderError(
            "INVALID_PROVIDER_OUTPUT",
            "Fixture reasoning referenced a rule outside the pinned pack.",
            retryable=False,
        )
    if not item.evidence_indexes or any(
        index < 0 or index >= len(evidence) for index in item.evidence_indexes
    ):
        raise ProviderError(
            "INVALID_PROVIDER_OUTPUT",
            "Fixture reasoning referenced unavailable evidence.",
            retryable=False,
        )
    if item.start_ms is not None or item.end_ms is not None:
        if item.start_ms is None or item.end_ms is None:
            raise ProviderError(
                "INVALID_PROVIDER_OUTPUT",
                "Fixture finding returned an incomplete time range.",
                retryable=False,
            )
        if not 0 <= item.start_ms < item.end_ms <= duration_ms:
            raise ProviderError(
                "INVALID_PROVIDER_OUTPUT",
                "Fixture finding returned a time range outside the source.",
                retryable=False,
            )


def _job_inputs(
    database: Database, claim: ClaimedJob
) -> tuple[ProviderContext, set[tuple[str, str]]]:
    with database.session_factory() as session:
        job = session.get(Job, claim.job_id)
        if job is None or job.status != "running" or job.fence != claim.fence:
            raise ProviderError("CANCELLED", "The job lease is no longer current.", retryable=False)
        set_database_scope(session, organization_id=job.organization_id)
        analysis = session.get(Analysis, job.resource_id)
        if analysis is None or analysis.organization_id != job.organization_id:
            raise ProviderError("INVALID_INPUT", "The analysis record is missing.", retryable=False)
        version = session.get(SubmissionVersion, analysis.submission_version_id)
        if version is None or version.organization_id != job.organization_id:
            raise ProviderError(
                "INVALID_INPUT", "The submission version is missing.", retryable=False
            )
        submission = session.scalar(
            select(Submission)
            .where(
                Submission.id == version.submission_id,
                Submission.organization_id == job.organization_id,
            )
            .with_for_update()
        )
        asset = session.scalar(
            select(MediaAsset).where(
                MediaAsset.id == version.asset_id,
                MediaAsset.organization_id == job.organization_id,
            )
        )
        if submission is None or asset is None or asset.duration_ms is None:
            raise ProviderError(
                "INVALID_INPUT", "Validated source input is missing.", retryable=False
            )
        tombstone = session.scalar(
            select(Tombstone.id).where(
                Tombstone.organization_id == job.organization_id,
                or_(
                    (Tombstone.resource_type == "submission")
                    & (Tombstone.resource_id == submission.id),
                    (Tombstone.resource_type == "media_asset")
                    & (Tombstone.resource_id == asset.id),
                ),
            )
        )
        if (
            tombstone
            or submission.deleted_at is not None
            or asset.deleted_at is not None
            or source_expired(asset)
            or not source_authorization_active(session, asset, job.organization_id)
        ):
            raise ProviderError(
                "CANCELLED", "Source authorization is unavailable, deleted or expired.",
                retryable=False,
            )
        campaign = session.scalar(
            select(Campaign).where(
                Campaign.id == submission.campaign_id,
                Campaign.organization_id == job.organization_id,
            )
        )
        pack = (
            session.scalar(
                select(RulePackVersion).where(
                    RulePackVersion.id == campaign.rule_pack_version_id,
                    RulePackVersion.organization_id == job.organization_id,
                )
            )
            if campaign is not None
            else None
        )
        if pack is None:
            raise ProviderError(
                "INVALID_INPUT", "The pinned rule pack is missing.", retryable=False
            )
        if (
            campaign is None
            or stable_hash(
                _manifest(
                    version,
                    asset,
                    campaign,
                    pack,
                    CheckCreate.model_validate(
                        {
                            "scenario": job.scenario,
                            "invocation_mode": analysis.invocation_mode,
                            "schema_version": analysis.schema_version,
                        }
                    ),
                    source_authorization_receipt(session, asset, job.organization_id),
                )
            )
            != analysis.manifest_hash
        ):
            raise ProviderError(
                "INPUT_SNAPSHOT_CHANGED",
                "The pinned input snapshot changed; a new Check is required.",
                retryable=False,
            )
        allowed_rules = {(str(rule["id"]), str(rule["version"])) for rule in pack.rules}
        context = ProviderContext(
            organization_id=job.organization_id,
            analysis_id=analysis.id,
            duration_ms=asset.duration_ms,
            caption=version.caption,
            scenario=job.scenario,
            attempt=claim.attempt,
        )
        return context, allowed_rules


def _publish_success(
    database: Database,
    claim: ClaimedJob,
    evidence: list[EvidenceResult],
    findings: list[FindingResult],
) -> bool:
    with database.session_factory() as session:
        job = session.get(Job, claim.job_id)
        if job is None or job.status != "running" or job.fence != claim.fence:
            return False
        set_database_scope(session, organization_id=job.organization_id)
        analysis = session.get(Analysis, job.resource_id)
        if analysis is None:
            return False
        version = session.get(SubmissionVersion, analysis.submission_version_id)
        submission = (
            session.scalar(
                select(Submission)
                .where(
                    Submission.id == version.submission_id,
                    Submission.organization_id == job.organization_id,
                )
                .with_for_update()
            )
            if version
            else None
        )
        if version is None or submission is None:
            return False
        job = session.scalar(
            select(Job)
            .where(Job.id == claim.job_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if job is None or job.status != "running" or job.fence != claim.fence:
            return False
        asset = session.scalar(
            select(MediaAsset).where(
                MediaAsset.id == version.asset_id,
                MediaAsset.organization_id == job.organization_id,
            )
        )
        deleted = session.scalar(
            select(Tombstone.id).where(
                Tombstone.organization_id == job.organization_id,
                or_(
                    (Tombstone.resource_type == "submission")
                    & (Tombstone.resource_id == submission.id),
                    (Tombstone.resource_type == "media_asset")
                    & (Tombstone.resource_id == version.asset_id),
                ),
            )
        )
        if (
            deleted
            or submission.deleted_at is not None
            or asset is None
            or asset.deleted_at is not None
            or source_expired(asset)
            or not source_authorization_active(session, asset, job.organization_id)
        ):
            job.status = "cancelled"
            job.last_error_code = "CANCELLED"
            job.last_error_message = "Source authorization is unavailable, deleted or expired."
            analysis.analysis_status = "cancelled"
            analysis.machine_assessment = "not_assessed"
            release_reservation(session, job.id, "released")
            session.commit()
            return False

        stored_evidence: list[EvidenceItem] = []
        missing_intervals: list[dict[str, object]] = []
        for evidence_item in evidence:
            row = EvidenceItem(
                organization_id=job.organization_id,
                analysis_id=analysis.id,
                modality=evidence_item.modality,
                start_ms=evidence_item.start_ms,
                end_ms=evidence_item.end_ms,
                precision=evidence_item.precision,
                description=evidence_item.description,
            )
            session.add(row)
            session.flush()
            stored_evidence.append(row)
            missing_intervals.extend(
                {
                    "modality": evidence_item.modality,
                    "start_ms": start_ms,
                    "end_ms": end_ms,
                    "reason": evidence_item.description,
                }
                for start_ms, end_ms in evidence_item.missing_intervals
            )

        for finding_item in findings:
            evidence_ids = [
                str(stored_evidence[index].id) for index in finding_item.evidence_indexes
            ]
            session.add(
                Finding(
                    organization_id=job.organization_id,
                    analysis_id=analysis.id,
                    rule_id=finding_item.rule_id,
                    rule_version=finding_item.rule_version,
                    severity=finding_item.severity,
                    evidence_ids=evidence_ids,
                    start_ms=finding_item.start_ms,
                    end_ms=finding_item.end_ms,
                    evidence_text=finding_item.evidence_text,
                    uncertainty=finding_item.uncertainty,
                    suggested_action=finding_item.suggested_action,
                    fingerprint=stable_hash(
                        {
                            "rule_id": finding_item.rule_id,
                            "rule_version": finding_item.rule_version,
                            "evidence_text": finding_item.evidence_text,
                        }
                    ),
                )
            )

        complete_modalities = {item.modality for item in evidence if item.complete}
        required_complete = set(analysis.required_coverage).issubset(complete_modalities)
        analysis.observed_coverage = sorted(complete_modalities)
        analysis.missing_intervals = missing_intervals
        analysis.analysis_status = "completed" if required_complete else "partial"
        if not required_complete:
            analysis.machine_assessment = "human_review_required"
        elif findings:
            analysis.machine_assessment = "fixes_suggested"
        else:
            analysis.machine_assessment = "no_issues_detected"
        analysis.completed_at = utcnow()
        current_version = submission.current_version_id == version.id
        session.add(
            ReviewContext(
                organization_id=job.organization_id,
                analysis_id=analysis.id,
                submission_id=submission.id,
                submission_version_id=version.id,
                review_status="unreviewed" if current_version else "superseded",
                revision=1,
                manifest_hash=analysis.manifest_hash,
                superseded_at=None if current_version else utcnow(),
            )
        )
        job.status = "succeeded"
        job.result_id = analysis.id
        job.lease_owner = None
        job.lease_until = None
        job.last_error_code = None
        job.last_error_message = None
        job.updated_at = utcnow()
        release_reservation(session, job.id, "settled")
        audit(
            session,
            None,
            "check.completed" if required_complete else "check.partial",
            "analysis",
            analysis.id,
            {"attempt": claim.attempt, "invocation_mode": "fixture"},
            organization_id=job.organization_id,
        )
        session.commit()
        return True


def _publish_failure(database: Database, claim: ClaimedJob, error: ProviderError) -> None:
    with database.session_factory() as session:
        job = session.scalar(select(Job).where(Job.id == claim.job_id).with_for_update())
        if job is None or job.status != "running" or job.fence != claim.fence:
            return
        set_database_scope(session, organization_id=job.organization_id)
        analysis = session.get(Analysis, job.resource_id)
        now = utcnow()
        job.last_error_code = error.code
        job.last_error_message = error.safe_message
        job.lease_owner = None
        job.lease_until = None
        job.updated_at = now
        if error.code == "OUTCOME_UNKNOWN":
            job.status = "outcome_unknown"
            job.retry_after = None
            if analysis is not None:
                analysis.analysis_status = "failed"
                analysis.machine_assessment = "not_assessed"
                analysis.completed_at = now
            # The provider may still charge this attempt. Keep the reservation held until a
            # separate reconciliation proves the final usage and cost.
        elif error.retryable and job.attempt_count < job.max_attempts:
            job.status = "retry_wait"
            job.retry_after = now + timedelta(milliseconds=150)
            if analysis is not None:
                analysis.analysis_status = "queued"
        else:
            job.status = (
                "cancelled" if error.code == "CANCELLED"
                else "dead_letter" if error.retryable else "failed"
            )
            job.retry_after = None
            if analysis is not None:
                analysis.analysis_status = "cancelled" if error.code == "CANCELLED" else "failed"
                analysis.machine_assessment = "not_assessed"
                analysis.completed_at = now
            release_reservation(
                session, job.id,
                "released" if error.code == "CANCELLED" else "released_after_failure",
            )
        audit(
            session,
            None,
            "check.outcome_unknown" if job.status == "outcome_unknown"
            else "check.retry_wait" if job.status == "retry_wait"
            else "check.cancelled" if job.status == "cancelled" else "check.failed",
            "job",
            job.id,
            {"attempt": job.attempt_count, "error_code": error.code},
            organization_id=job.organization_id,
        )
        session.commit()


def process_claimed_job(
    database: Database,
    claim: ClaimedJob,
    providers: FixtureProviders | None = None,
) -> bool:
    provider_set = providers or FixtureProviders()
    try:
        context, allowed_rules = _job_inputs(database, claim)

        def transcribe() -> EvidenceResult:
            item = provider_set.transcriber.transcribe(context)
            _validate_evidence(item, context.duration_ms)
            return item

        def segment() -> EvidenceResult:
            item = provider_set.segmenter.segment(context)
            _validate_evidence(item, context.duration_ms)
            return item

        evidence = [
            _invoke_model_call(database, claim, "transcriber", transcribe),
            _invoke_model_call(database, claim, "segmenter", segment),
        ]

        def reason() -> list[FindingResult]:
            items = provider_set.reasoner.evaluate(context, evidence)
            for item in items:
                _validate_finding(item, evidence, context.duration_ms, allowed_rules)
            return items

        findings = _invoke_model_call(database, claim, "reasoner", reason)
        return _publish_success(database, claim, evidence, findings)
    except ProviderError as error:
        _publish_failure(database, claim, error)
        return False
    except Exception:
        LOGGER.error("Unexpected fixture worker failure for job %s", claim.job_id)
        _publish_failure(
            database,
            claim,
            ProviderError(
                "WORKER_INTERNAL_ERROR",
                "The fixture worker failed safely. See the local worker log.",
                retryable=False,
            ),
        )
        return False


def process_next_job(
    database: Database,
    worker_id: str = "fixture-worker",
    providers: FixtureProviders | None = None,
) -> bool:
    claim = claim_next_job(database, worker_id)
    if claim is None:
        return False
    process_claimed_job(database, claim, providers)
    return True


def run_until_idle(database: Database, *, max_cycles: int = 20) -> int:
    processed = 0
    for _ in range(max_cycles):
        if not process_next_job(database):
            break
        processed += 1
        time.sleep(0.16)
    return processed


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = Settings.from_env()
    database = Database(
        settings.database_url,
        settings.database_schema,
        runtime_role="vouch_worker" if settings.auth_mode == "supabase" else None,
    )
    database.create_all()
    if settings.auth_mode == "fixture":
        with database.session_factory() as session:
            seed_fixture_data(session)
    worker_id = f"{socket.gethostname()}-{id(database)}"
    LOGGER.info("Vouch fixture worker started as %s", worker_id)
    try:
        while True:
            processed = process_next_job(database, worker_id)
            if not processed:
                time.sleep(settings.worker_poll_seconds)
    except KeyboardInterrupt:
        LOGGER.info("Vouch fixture worker stopped")
    finally:
        database.dispose()


if __name__ == "__main__":
    main()
