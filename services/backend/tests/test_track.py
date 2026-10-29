from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient
from test_workflow import create_campaign


def _event(
    client: TestClient,
    headers: dict[str, str],
    campaign_id: str,
    creator_id: str,
    *,
    event_kind: str,
    external_event_id: str,
    order_external_id: str | None = None,
    amount_minor: int = 0,
) -> object:
    return client.post(
        f"/api/v1/campaigns/{campaign_id}/track/test-events",
        headers=headers,
        json={
            "creator_id": creator_id,
            "event_kind": event_kind,
            "external_event_id": external_event_id,
            "order_external_id": order_external_id,
            "amount_minor": amount_minor,
            "currency": "INR",
            "occurred_at": datetime(2026, 10, 29, 9, 0, tzinfo=UTC).isoformat(),
        },
    )


def test_track_test_events_are_idempotent_refund_aware_and_separate_from_live(
    client: TestClient, marketer_headers: dict[str, str]
) -> None:
    campaign = create_campaign(client, marketer_headers)
    creator_id = campaign["creator_ids"][0]
    click = _event(
        client,
        marketer_headers,
        campaign["id"],
        creator_id,
        event_kind="click",
        external_event_id="click-1",
    )
    assert click.status_code == 201, click.text
    duplicate = _event(
        client,
        marketer_headers,
        campaign["id"],
        creator_id,
        event_kind="click",
        external_event_id="click-1",
    )
    assert duplicate.status_code == 200
    assert duplicate.json() == click.json()

    order = _event(
        client,
        marketer_headers,
        campaign["id"],
        creator_id,
        event_kind="order",
        external_event_id="order-event-1",
        order_external_id="order-1",
        amount_minor=12_500,
    )
    assert order.status_code == 201, order.text
    refund = _event(
        client,
        marketer_headers,
        campaign["id"],
        creator_id,
        event_kind="refund",
        external_event_id="refund-event-1",
        order_external_id="order-1",
        amount_minor=2_500,
    )
    assert refund.status_code == 201, refund.text

    report = client.get(
        f"/api/v1/campaigns/{campaign['id']}/track", headers=marketer_headers
    )
    assert report.status_code == 200, report.text
    payload = report.json()
    assert payload["test"] == {
        "clicks": 1,
        "orders": 1,
        "refunds": 1,
        "conversion_rate": 1.0,
        "totals_by_currency": {
            "INR": {
                "gross_minor": 12_500,
                "refunded_minor": 2_500,
                "net_minor": 10_000,
            }
        },
    }
    assert payload["live"] == {
        "clicks": 0,
        "orders": 0,
        "refunds": 0,
        "conversion_rate": None,
        "totals_by_currency": {},
    }
    assert len(payload["events"]) == 3
    assert all(event["environment"] == "test" for event in payload["events"])


def test_track_rejects_conflicts_unknown_orders_and_read_only_mutation(
    client: TestClient,
    marketer_headers: dict[str, str],
    reviewer_headers: dict[str, str],
) -> None:
    campaign = create_campaign(client, marketer_headers)
    creator_id = campaign["creator_ids"][0]
    first = _event(
        client,
        marketer_headers,
        campaign["id"],
        creator_id,
        event_kind="click",
        external_event_id="stable-id",
    )
    assert first.status_code == 201
    conflict = _event(
        client,
        marketer_headers,
        campaign["id"],
        creator_id,
        event_kind="order",
        external_event_id="stable-id",
        order_external_id="order-2",
        amount_minor=100,
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "TRACK_EVENT_CONFLICT"
    missing = _event(
        client,
        marketer_headers,
        campaign["id"],
        creator_id,
        event_kind="refund",
        external_event_id="refund-missing",
        order_external_id="missing-order",
        amount_minor=100,
    )
    assert missing.status_code == 422
    assert missing.json()["error"]["code"] == "TRACK_ORDER_NOT_FOUND"
    denied = _event(
        client,
        reviewer_headers,
        campaign["id"],
        creator_id,
        event_kind="click",
        external_event_id="reviewer-click",
    )
    assert denied.status_code == 403
