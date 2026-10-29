from uuid import uuid4

import pytest

from vouch_backend.providers import FixtureProviders, ProviderContext
from vouch_backend.worker import _validate_evidence, _validate_finding


@pytest.mark.parametrize("duration_ms", [1, 250, 1500, 1501, 2000, 10_000])
@pytest.mark.parametrize("scenario", ["success", "partial_voice"])
def test_synthetic_evidence_respects_measured_source_time(
    duration_ms: int, scenario: str,
) -> None:
    providers = FixtureProviders()
    context = ProviderContext(uuid4(), uuid4(), duration_ms, "", scenario, 1)
    evidence = [providers.transcriber.transcribe(context), providers.segmenter.segment(context)]
    for item in evidence:
        _validate_evidence(item, duration_ms)
    findings = providers.reasoner.evaluate(context, evidence)
    for finding in findings:
        _validate_finding(finding, evidence, duration_ms, {("DISCLOSURE_AUDIO", "1.0")})
        assert evidence[0].start_ms is not None and evidence[0].end_ms is not None
        assert finding.start_ms is not None and finding.end_ms is not None
        assert evidence[0].start_ms <= finding.start_ms < finding.end_ms <= evidence[0].end_ms
    if scenario == "partial_voice" and duration_ms <= 1500:
        assert not findings and not evidence[0].complete
        assert evidence[0].missing_intervals == [(0, duration_ms)]
