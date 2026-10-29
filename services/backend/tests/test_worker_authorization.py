from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from test_workflow import create_campaign, create_submission, start_check

from vouch_backend.models import Analysis, ConsentReceipt, EvidenceItem, Job, Organization, utcnow
from vouch_backend.providers import FixtureProviders
from vouch_backend.worker import _job_inputs, _publish_success, claim_next_job, process_next_job


@pytest.mark.parametrize("phase", ["before_input", "before_publication"])
@pytest.mark.parametrize("authorization", ["missing", "revoked"])
def test_missing_or_revoked_authorization_cancels_without_publishing(
    client: TestClient, marketer_headers: dict[str, str], phase: str, authorization: str,
) -> None:
    campaign = create_campaign(client, marketer_headers)
    submission = create_submission(client, marketer_headers, campaign)
    version = submission["versions"][0]
    accepted = start_check(client, marketer_headers, version["id"], "clean", f"consent-{phase}")
    assert accepted.status_code == 202, accepted.text
    database = client.app.state.database
    if phase == "before_publication":
        claim = claim_next_job(database, "consent-race")
        assert claim is not None
        context, _ = _job_inputs(database, claim)
        providers = FixtureProviders()
        evidence = [providers.transcriber.transcribe(context), providers.segmenter.segment(context)]
    # Owner-only fixtures model legacy/mid-flight authorization loss. Runtime credentials
    # cannot delete receipts or revoke without atomic source erasure.
    with database.session_factory() as session:
        receipt = session.scalar(select(ConsentReceipt).where(
            ConsentReceipt.asset_id == UUID(version["asset_id"]),
        ))
        assert receipt is not None
        if authorization == "missing":
            session.delete(receipt)
        else:
            receipt.revoked_at = utcnow()
            receipt.revoked_by = receipt.actor_user_id
            receipt.revocation_actor_kind = "member"
            receipt.revocation_reason = "withdrawn"
        session.commit()
    if phase == "before_publication":
        assert not _publish_success(database, claim, evidence, [])
    else:
        assert process_next_job(database)
    with database.session_factory() as session:
        job = session.get(Job, UUID(accepted.json()["operation_id"]))
        analysis = session.get(Analysis, UUID(accepted.json()["resource_id"]))
        org = session.get(Organization, UUID(marketer_headers["X-Organization-Id"]))
        assert job is not None and job.status == "cancelled"
        assert analysis is not None and analysis.analysis_status == "cancelled"
        assert org is not None and org.budget_held_minor == 0
        assert not session.scalars(select(EvidenceItem)).all()
