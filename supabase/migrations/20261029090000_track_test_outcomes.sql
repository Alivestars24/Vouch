-- Deterministic, tenant-scoped Track events for the MVP. This API role can
-- insert only explicitly labeled test events; live ingestion requires a later
-- verified connector/webhook boundary and is not inferred from fixture data.

create table vouch.outcome_events (
  id uuid primary key,
  organization_id uuid not null references vouch.organizations(id) on delete cascade,
  campaign_id uuid not null references vouch.campaigns(id) on delete cascade,
  creator_id uuid not null references vouch.creators(id),
  event_kind varchar(16) not null check (event_kind in ('click', 'order', 'refund')),
  environment varchar(8) not null check (environment in ('test', 'live')),
  external_event_id varchar(160) not null,
  order_external_id varchar(160),
  amount_minor integer not null check (amount_minor >= 0),
  currency varchar(3) not null check (length(currency) = 3),
  attribution_status varchar(24) not null
    check (attribution_status in ('attributed', 'ambiguous', 'unattributed')),
  attribution_method varchar(40) not null,
  payload_hash varchar(64) not null check (length(payload_hash) = 64),
  occurred_at timestamptz not null,
  received_at timestamptz not null,
  unique (organization_id, id),
  unique (organization_id, environment, external_event_id),
  foreign key (organization_id, campaign_id)
    references vouch.campaigns(organization_id, id),
  foreign key (organization_id, creator_id)
    references vouch.creators(organization_id, id)
);

create index ix_outcome_campaign_received
  on vouch.outcome_events(organization_id, campaign_id, received_at desc);
create index ix_outcome_order_lookup
  on vouch.outcome_events(organization_id, environment, order_external_id)
  where order_external_id is not null;

alter table vouch.outcome_events enable row level security;
revoke all on vouch.outcome_events from public, anon, authenticated,
  vouch_worker, vouch_guest, vouch_retention;
grant select, insert on vouch.outcome_events to vouch_api;

create policy api_track_read on vouch.outcome_events for select to vouch_api
using (
  organization_id = vouch_private.organization_id()
  and vouch_private.member_of(organization_id)
);

create policy api_track_test_insert on vouch.outcome_events for insert to vouch_api
with check (
  organization_id = vouch_private.organization_id()
  and environment = 'test'
  and attribution_status = 'attributed'
  and attribution_method = 'test_roster'
  and received_at between clock_timestamp() - interval '1 minute'
    and clock_timestamp() + interval '1 minute'
  and vouch_private.has_role(organization_id, array['admin', 'marketer'])
  and exists (
    select 1 from vouch.campaign_creators roster
    where roster.organization_id = outcome_events.organization_id
      and roster.campaign_id = outcome_events.campaign_id
      and roster.creator_id = outcome_events.creator_id
  )
);
