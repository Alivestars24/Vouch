-- Durable, tenant-scoped call envelopes for every Check provider stage.
-- Live invocation remains disabled; fixture calls now prove the same accounting lifecycle.

create table vouch.model_calls (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null,
  job_id uuid not null,
  analysis_id uuid not null,
  budget_reservation_id uuid not null,
  logical_operation_key varchar(220) not null,
  capability varchar(40) not null,
  attempt_no integer not null check (attempt_no > 0),
  invocation_mode varchar(16) not null check (invocation_mode in ('fixture','recorded','live')),
  provider varchar(40) not null,
  requested_model varchar(160) not null,
  returned_model varchar(160),
  prompt_version varchar(80) not null,
  schema_version varchar(80) not null,
  adapter_version varchar(80) not null,
  status varchar(32) not null check (
    status in ('requested','in_flight','succeeded','failed','outcome_unknown')
  ),
  provider_request_id varchar(200),
  usage_units jsonb not null default '{}'::jsonb check (jsonb_typeof(usage_units) = 'object'),
  cost_known boolean not null,
  cost_minor integer check (cost_minor is null or cost_minor >= 0),
  currency varchar(3) not null check (currency ~ '^[A-Z]{3}$'),
  error_code varchar(64),
  retryable boolean,
  started_at timestamptz not null default now(),
  completed_at timestamptz,
  unique (organization_id, id),
  constraint uq_model_call_job_attempt_capability
    unique (organization_id, job_id, attempt_no, capability),
  foreign key (organization_id, job_id)
    references vouch.jobs (organization_id, id) on delete cascade,
  foreign key (organization_id, analysis_id)
    references vouch.analyses (organization_id, id) on delete cascade,
  foreign key (organization_id, budget_reservation_id)
    references vouch.budget_reservations (organization_id, id) on delete restrict,
  constraint ck_model_call_cost_known check (
    (cost_known and cost_minor is not null) or (not cost_known and cost_minor is null)
  ),
  check ((status in ('succeeded','failed','outcome_unknown') and completed_at is not null)
    or (status in ('requested','in_flight') and completed_at is null)),
  check (invocation_mode <> 'fixture' or cost_minor = 0)
);

create index ix_model_calls_analysis on vouch.model_calls (organization_id, analysis_id, started_at);
create index ix_model_calls_job on vouch.model_calls (organization_id, job_id, attempt_no);
alter table vouch.model_calls enable row level security;

revoke all on vouch.model_calls from public, anon, authenticated;

grant select on vouch.model_calls to vouch_api;
create policy api_read on vouch.model_calls for select to vouch_api
  using (vouch_private.member_of(organization_id));

grant select, insert on vouch.model_calls to vouch_worker;
grant update (
  returned_model, status, provider_request_id, usage_units, cost_known, cost_minor,
  error_code, retryable, completed_at
) on vouch.model_calls to vouch_worker;
create policy worker_read on vouch.model_calls for select to vouch_worker
  using (organization_id = (select vouch_private.organization_id()));
create policy worker_insert on vouch.model_calls for insert to vouch_worker
  with check (organization_id = (select vouch_private.organization_id()));
create policy worker_update on vouch.model_calls for update to vouch_worker
  using (organization_id = (select vouch_private.organization_id()))
  with check (organization_id = (select vouch_private.organization_id()));
