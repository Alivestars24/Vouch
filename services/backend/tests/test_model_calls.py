from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import select
from test_workflow import create_campaign, create_submission, start_check

from vouch_backend.models import BudgetReservation, Job, ModelCall, Organization
from vouch_backend.providers import FixtureProviders, ProviderContext, ProviderError
from vouch_backend.worker import process_next_job


class UnknownOutcomeTranscriber:
    def transcribe(self, _context: ProviderContext) -> object:
        raise ProviderError(
            "OUTCOME_UNKNOWN",
            "The provider outcome requires reconciliation.",
            retryable=False,
        )


def test_success_persists_one_zero_cost_call_per_fixture_stage(
    client: TestClient, marketer_headers: dict[str, str]
) -> None:
    campaign = create_campaign(client, marketer_headers)
    submission = create_submission(client, marketer_headers, campaign)
    accepted = start_check(
        client, marketer_headers, submission["versions"][0]["id"], "clean", "model-calls"
    )

    assert accepted.status_code == 202
    assert process_next_job(client.app.state.database)

    analysis_id = UUID(accepted.json()["resource_id"])
    with client.app.state.database.session_factory() as session:
        calls = session.scalars(
            select(ModelCall)
            .where(ModelCall.analysis_id == analysis_id)
            .order_by(ModelCall.capability)
        ).all()
        assert [call.capability for call in calls] == ["reasoner", "segmenter", "transcriber"]
        assert all(call.status == "succeeded" for call in calls)
        assert all(call.provider == "fixture" for call in calls)
        assert all(call.cost_known and call.cost_minor == 0 for call in calls)
        assert all(call.completed_at is not None for call in calls)

    check = client.get(f"/api/v1/checks/{analysis_id}", headers=marketer_headers)
    assert check.status_code == 200
    summaries = check.json()["model_call_summaries"]
    assert len(summaries) == 3
    assert all(summary["status"] == "succeeded" for summary in summaries)
    assert all(summary["live_verified"] is False for summary in summaries)


def test_unknown_provider_outcome_is_not_retried_or_released(
    client: TestClient, marketer_headers: dict[str, str]
) -> None:
    campaign = create_campaign(client, marketer_headers)
    submission = create_submission(client, marketer_headers, campaign)
    accepted = start_check(
        client, marketer_headers, submission["versions"][0]["id"], "clean", "unknown-outcome"
    )
    job_id = UUID(accepted.json()["operation_id"])

    providers = FixtureProviders(transcriber=UnknownOutcomeTranscriber())  # type: ignore[arg-type]
    assert process_next_job(client.app.state.database, providers=providers)
    assert not process_next_job(client.app.state.database, providers=providers)

    with client.app.state.database.session_factory() as session:
        job = session.get(Job, job_id)
        reservation = session.scalar(
            select(BudgetReservation).where(BudgetReservation.job_id == job_id)
        )
        organization = session.get(Organization, UUID(marketer_headers["X-Organization-Id"]))
        calls = session.scalars(select(ModelCall).where(ModelCall.job_id == job_id)).all()

        assert job is not None and job.status == "outcome_unknown"
        assert job.attempt_count == 1
        assert reservation is not None and reservation.status == "held"
        assert organization is not None and organization.budget_held_minor == 25
        assert len(calls) == 1
        assert calls[0].status == "outcome_unknown"
        assert calls[0].cost_known is False and calls[0].cost_minor is None
        assert calls[0].error_code == "OUTCOME_UNKNOWN"
