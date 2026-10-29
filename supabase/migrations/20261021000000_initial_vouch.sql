-- Vouch initial schema.
--
-- This migration deliberately exposes no anonymous data. Authenticated access is
-- mediated by RLS and active organization memberships. Background workers still
-- need an explicitly scoped repository: a service credential bypasses RLS and is
-- not, by itself, tenant authorization.

create extension if not exists pgcrypto with schema extensions;

create schema if not exists private;
revoke all on schema private from public, anon, authenticated;

create type public.membership_role as enum ('admin', 'marketer', 'reviewer', 'viewer');
create type public.membership_status as enum ('active', 'revoked');
create type public.record_status as enum ('draft', 'active', 'archived');
create type public.rights_status as enum ('pending', 'authorized', 'revoked');
create type public.upload_status as enum ('issued', 'uploaded', 'validating', 'validated', 'rejected', 'expired');
create type public.asset_validation_state as enum ('quarantined', 'validating', 'validated', 'rejected', 'deleted');
create type public.deletion_state as enum ('active', 'pending', 'deleted', 'failed');
create type public.analysis_status as enum ('queued', 'running', 'completed', 'partial', 'failed', 'cancelled');
create type public.machine_assessment as enum ('no_issues_detected', 'fixes_suggested', 'potentially_blocking', 'human_review_required', 'not_assessed');
create type public.review_status as enum ('unreviewed', 'changes_requested', 'approved', 'rejected', 'superseded', 'revoked');
create type public.invocation_mode as enum ('fixture', 'recorded', 'live');
create type public.evidence_modality as enum ('transcript', 'on_screen_text', 'visual', 'caption', 'coverage_gap');
create type public.evidence_state as enum ('observed', 'missing', 'failed', 'unknown');
create type public.finding_severity as enum ('critical', 'major', 'minor');
create type public.finding_decision_kind as enum ('accepted', 'dismissed', 'incorrect', 'uncertain');
create type public.review_action as enum ('changes_requested', 'approved', 'rejected', 'revoked', 'superseded');
create type public.job_status as enum ('queued', 'running', 'retry_wait', 'succeeded', 'failed', 'cancelled', 'dead_letter');
create type public.job_stage_status as enum ('pending', 'running', 'succeeded', 'failed', 'skipped', 'cancelled', 'outcome_unknown');
create type public.idempotency_status as enum ('started', 'accepted', 'completed', 'failed');
create type public.reservation_status as enum ('held', 'settled', 'released', 'unresolved');
create type public.deletion_request_status as enum ('requested', 'in_progress', 'partial', 'completed', 'failed');
create type public.deletion_item_status as enum ('pending', 'in_progress', 'deleted', 'not_found', 'failed', 'provider_unconfirmed');

create table public.organizations (
  id uuid primary key default gen_random_uuid(),
  name text not null check (length(btrim(name)) between 1 and 120),
  slug text not null unique check (slug ~ '^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$'),
  created_by uuid not null references auth.users(id) on delete restrict,
  check_media_retention_days integer not null default 30 check (check_media_retention_days between 1 and 365),
  review_metadata_retention_days integer not null default 90 check (review_metadata_retention_days between 1 and 730),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.memberships (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete restrict,
  user_id uuid not null references auth.users(id) on delete restrict,
  status public.membership_status not null default 'active',
  invited_by uuid references auth.users(id) on delete set null,
  joined_at timestamptz not null default now(),
  revoked_at timestamptz,
  updated_at timestamptz not null default now(),
  unique (organization_id, id),
  unique (organization_id, user_id),
  check ((status = 'active' and revoked_at is null) or (status = 'revoked' and revoked_at is not null))
);

create table public.membership_roles (
  organization_id uuid not null,
  membership_id uuid not null,
  role public.membership_role not null,
  granted_by uuid not null references auth.users(id) on delete restrict,
  granted_at timestamptz not null default now(),
  primary key (organization_id, membership_id, role),
  foreign key (organization_id, membership_id)
    references public.memberships (organization_id, id) on delete restrict
);

create table public.brands (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete restrict,
  name text not null check (length(btrim(name)) between 1 and 120),
  status public.record_status not null default 'active',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (organization_id, id),
  unique (organization_id, name)
);

create table public.products (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null,
  brand_id uuid not null,
  external_id text,
  name text not null check (length(btrim(name)) between 1 and 160),
  category text not null check (length(btrim(category)) between 1 and 80),
  status public.record_status not null default 'active',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (organization_id, id),
  unique (organization_id, brand_id, external_id),
  foreign key (organization_id, brand_id)
    references public.brands (organization_id, id) on delete restrict
);

create table public.product_versions (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null,
  product_id uuid not null,
  version_no integer not null check (version_no > 0),
  snapshot jsonb not null check (jsonb_typeof(snapshot) = 'object'),
  content_hash text not null check (content_hash ~ '^[0-9a-f]{64}$'),
  created_by uuid not null references auth.users(id) on delete restrict,
  created_at timestamptz not null default now(),
  unique (organization_id, id),
  unique (organization_id, product_id, version_no),
  foreign key (organization_id, product_id)
    references public.products (organization_id, id) on delete restrict
);

create table public.creators (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete restrict,
  display_name text not null check (length(btrim(display_name)) between 1 and 120),
  handle text,
  market_code text check (market_code is null or market_code ~ '^[A-Z]{2}$'),
  status public.record_status not null default 'active',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (organization_id, id)
);

create table public.creator_evidence (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null,
  creator_id uuid not null,
  source_uri text not null,
  source_label text not null,
  rights_status public.rights_status not null,
  rights_basis text not null,
  observed_at timestamptz not null,
  verified_at timestamptz,
  verification_state text not null check (verification_state in ('unreviewed', 'reviewed', 'rejected')),
  created_by uuid not null references auth.users(id) on delete restrict,
  created_at timestamptz not null default now(),
  unique (organization_id, id),
  foreign key (organization_id, creator_id)
    references public.creators (organization_id, id) on delete restrict
);

create table public.rule_packs (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete restrict,
  name text not null check (length(btrim(name)) between 1 and 160),
  kind text not null check (kind in ('brand_policy', 'legal_rulebook')),
  status public.record_status not null default 'draft',
  created_by uuid not null references auth.users(id) on delete restrict,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (organization_id, id),
  unique (organization_id, name)
);

create table public.rule_pack_versions (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null,
  rule_pack_id uuid not null,
  version_no integer not null check (version_no > 0),
  status text not null check (status in ('draft', 'reviewed', 'active', 'retired')),
  applicability jsonb not null default '{}'::jsonb check (jsonb_typeof(applicability) = 'object'),
  content_hash text not null check (content_hash ~ '^[0-9a-f]{64}$'),
  provenance_label text not null,
  source_checked_at timestamptz,
  reviewed_by uuid references auth.users(id) on delete restrict,
  created_by uuid not null references auth.users(id) on delete restrict,
  created_at timestamptz not null default now(),
  unique (organization_id, id),
  unique (organization_id, rule_pack_id, version_no),
  foreign key (organization_id, rule_pack_id)
    references public.rule_packs (organization_id, id) on delete restrict,
  check ((status in ('reviewed', 'active', 'retired') and reviewed_by is not null) or status = 'draft')
);

create table public.rules (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null,
  rule_pack_version_id uuid not null,
  code text not null check (code ~ '^[A-Z0-9][A-Z0-9._-]{1,63}$'),
  title text not null,
  description text not null,
  severity public.finding_severity not null,
  required_modalities public.evidence_modality[] not null default '{}'::public.evidence_modality[],
  source_title text not null,
  source_uri text not null,
  source_excerpt text,
  applicability jsonb not null default '{}'::jsonb check (jsonb_typeof(applicability) = 'object'),
  status public.record_status not null default 'active',
  created_at timestamptz not null default now(),
  unique (organization_id, id),
  unique (organization_id, rule_pack_version_id, code),
  foreign key (organization_id, rule_pack_version_id)
    references public.rule_pack_versions (organization_id, id) on delete restrict
);

create table public.campaigns (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null,
  brand_id uuid not null,
  product_version_id uuid not null,
  name text not null check (length(btrim(name)) between 1 and 160),
  objective text not null check (length(btrim(objective)) between 1 and 1000),
  market_code text not null check (market_code ~ '^[A-Z]{2}$'),
  status public.record_status not null default 'draft',
  created_by uuid not null references auth.users(id) on delete restrict,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (organization_id, id),
  foreign key (organization_id, brand_id)
    references public.brands (organization_id, id) on delete restrict,
  foreign key (organization_id, product_version_id)
    references public.product_versions (organization_id, id) on delete restrict
);

create table public.campaign_rule_pins (
  organization_id uuid not null,
  campaign_id uuid not null,
  rule_pack_version_id uuid not null,
  pinned_by uuid not null references auth.users(id) on delete restrict,
  pinned_at timestamptz not null default now(),
  primary key (organization_id, campaign_id, rule_pack_version_id),
  foreign key (organization_id, campaign_id)
    references public.campaigns (organization_id, id) on delete restrict,
  foreign key (organization_id, rule_pack_version_id)
    references public.rule_pack_versions (organization_id, id) on delete restrict
);

create table public.campaign_creators (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null,
  campaign_id uuid not null,
  creator_id uuid not null,
  creator_evidence_id uuid,
  status text not null default 'invited' check (status in ('shortlisted', 'invited', 'active', 'completed', 'removed')),
  added_by uuid not null references auth.users(id) on delete restrict,
  added_at timestamptz not null default now(),
  unique (organization_id, id),
  unique (organization_id, campaign_id, creator_id),
  foreign key (organization_id, campaign_id)
    references public.campaigns (organization_id, id) on delete restrict,
  foreign key (organization_id, creator_id)
    references public.creators (organization_id, id) on delete restrict,
  foreign key (organization_id, creator_evidence_id)
    references public.creator_evidence (organization_id, id) on delete restrict
);

create table public.consent_receipts (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete restrict,
  subject_type text not null check (subject_type in ('member', 'creator', 'shopper')),
  subject_ref uuid not null,
  purpose text not null,
  notice_version text not null,
  status text not null check (status in ('granted', 'declined', 'revoked')),
  actor_user_id uuid references auth.users(id) on delete restrict,
  actor_attestation jsonb not null default '{}'::jsonb check (jsonb_typeof(actor_attestation) = 'object'),
  consented_at timestamptz,
  revoked_at timestamptz,
  created_at timestamptz not null default now(),
  unique (organization_id, id),
  check ((status = 'granted' and consented_at is not null and revoked_at is null)
      or (status = 'declined' and consented_at is null and revoked_at is null)
      or (status = 'revoked' and consented_at is not null and revoked_at is not null))
);

create table public.upload_intents (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null,
  campaign_id uuid not null,
  purpose text not null check (purpose in ('check_source', 'check_revision', 'creator_evidence')),
  bucket_id text not null,
  object_key text not null,
  expected_mime text not null,
  max_bytes bigint not null check (max_bytes > 0),
  uploaded_by uuid not null references auth.users(id) on delete restrict,
  status public.upload_status not null default 'issued',
  expires_at timestamptz not null,
  finalized_at timestamptz,
  created_at timestamptz not null default now(),
  unique (organization_id, id),
  unique (bucket_id, object_key),
  foreign key (organization_id, campaign_id)
    references public.campaigns (organization_id, id) on delete restrict,
  check (expires_at > created_at),
  check ((status = 'validated' and finalized_at is not null) or status <> 'validated')
);

create table public.media_assets (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null,
  campaign_id uuid not null,
  upload_intent_id uuid,
  parent_asset_id uuid,
  bucket_id text not null,
  object_key text not null,
  kind text not null check (kind in ('source_video', 'normalized_video', 'audio', 'frame', 'thumbnail', 'transcript', 'report')),
  sha256 text not null check (sha256 ~ '^[0-9a-f]{64}$'),
  byte_size bigint not null check (byte_size >= 0),
  validated_mime text not null,
  duration_ms integer check (duration_ms is null or duration_ms > 0),
  validation_state public.asset_validation_state not null,
  retention_deadline timestamptz not null,
  deletion_state public.deletion_state not null default 'active',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (organization_id, id),
  unique (bucket_id, object_key),
  foreign key (organization_id, campaign_id)
    references public.campaigns (organization_id, id) on delete restrict,
  foreign key (organization_id, upload_intent_id)
    references public.upload_intents (organization_id, id) on delete restrict,
  foreign key (organization_id, parent_asset_id)
    references public.media_assets (organization_id, id) on delete restrict
);

create table public.submissions (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null,
  campaign_id uuid not null,
  campaign_creator_id uuid,
  title text not null check (length(btrim(title)) between 1 and 160),
  rights_status public.rights_status not null,
  state text not null default 'draft' check (state in ('draft', 'in_review', 'changes_requested', 'approved', 'rejected', 'archived')),
  created_by uuid not null references auth.users(id) on delete restrict,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (organization_id, id),
  foreign key (organization_id, campaign_id)
    references public.campaigns (organization_id, id) on delete restrict,
  foreign key (organization_id, campaign_creator_id)
    references public.campaign_creators (organization_id, id) on delete restrict
);

create table public.submission_versions (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null,
  submission_id uuid not null,
  asset_id uuid not null,
  version_no integer not null check (version_no > 0),
  media_sha256 text not null check (media_sha256 ~ '^[0-9a-f]{64}$'),
  caption_text text not null default '',
  caption_sha256 text not null check (caption_sha256 ~ '^[0-9a-f]{64}$'),
  uploaded_by uuid not null references auth.users(id) on delete restrict,
  source_created_at timestamptz,
  created_at timestamptz not null default now(),
  unique (organization_id, id),
  unique (organization_id, submission_id, version_no),
  foreign key (organization_id, submission_id)
    references public.submissions (organization_id, id) on delete restrict,
  foreign key (organization_id, asset_id)
    references public.media_assets (organization_id, id) on delete restrict
);

create table public.analyses (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null,
  campaign_id uuid not null,
  submission_version_id uuid not null,
  manifest_hash text not null check (manifest_hash ~ '^[0-9a-f]{64}$'),
  rule_manifest_hash text not null check (rule_manifest_hash ~ '^[0-9a-f]{64}$'),
  prompt_version text not null,
  model_manifest_hash text not null check (model_manifest_hash ~ '^[0-9a-f]{64}$'),
  transform_version text not null,
  invocation_mode public.invocation_mode not null,
  provider_models jsonb not null default '[]'::jsonb check (jsonb_typeof(provider_models) = 'array'),
  analysis_status public.analysis_status not null default 'queued',
  machine_assessment public.machine_assessment not null default 'not_assessed',
  required_coverage jsonb not null default '{}'::jsonb check (jsonb_typeof(required_coverage) = 'object'),
  observed_coverage jsonb not null default '{}'::jsonb check (jsonb_typeof(observed_coverage) = 'object'),
  coverage_gaps jsonb not null default '[]'::jsonb check (jsonb_typeof(coverage_gaps) = 'array'),
  coverage_complete boolean not null default false,
  requested_by uuid not null references auth.users(id) on delete restrict,
  created_at timestamptz not null default now(),
  started_at timestamptz,
  completed_at timestamptz,
  unique (organization_id, id),
  unique (organization_id, submission_version_id, manifest_hash),
  foreign key (organization_id, campaign_id)
    references public.campaigns (organization_id, id) on delete restrict,
  foreign key (organization_id, submission_version_id)
    references public.submission_versions (organization_id, id) on delete restrict,
  check ((analysis_status in ('completed', 'partial', 'failed', 'cancelled') and completed_at is not null)
      or (analysis_status in ('queued', 'running') and completed_at is null)),
  check (machine_assessment <> 'no_issues_detected' or (analysis_status = 'completed' and coverage_complete))
);

create table public.evidence_items (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null,
  analysis_id uuid not null,
  source_asset_id uuid,
  modality public.evidence_modality not null,
  state public.evidence_state not null,
  start_ms integer,
  end_ms integer,
  start_char integer,
  end_char integer,
  precision_ms integer check (precision_ms is null or precision_ms >= 0),
  excerpt text check (excerpt is null or length(excerpt) <= 1000),
  missing_intervals jsonb not null default '[]'::jsonb check (jsonb_typeof(missing_intervals) = 'array'),
  provenance jsonb not null default '{}'::jsonb check (jsonb_typeof(provenance) = 'object'),
  created_at timestamptz not null default now(),
  unique (organization_id, id),
  unique (organization_id, analysis_id, id),
  foreign key (organization_id, analysis_id)
    references public.analyses (organization_id, id) on delete restrict,
  foreign key (organization_id, source_asset_id)
    references public.media_assets (organization_id, id) on delete restrict,
  check ((start_ms is null and end_ms is null) or (start_ms >= 0 and end_ms > start_ms)),
  check ((start_char is null and end_char is null) or (start_char >= 0 and end_char > start_char)),
  check (start_ms is not null or start_char is not null or state <> 'observed' or modality = 'visual')
);

create table public.findings (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null,
  analysis_id uuid not null,
  rule_id uuid not null,
  severity public.finding_severity not null,
  title text not null,
  evidence_summary text not null check (length(evidence_summary) <= 1000),
  start_ms integer,
  end_ms integer,
  start_char integer,
  end_char integer,
  uncertainty text,
  confidence_provenance text not null,
  suggested_action text not null,
  requires_resolution boolean not null default true,
  created_at timestamptz not null default now(),
  unique (organization_id, id),
  unique (organization_id, analysis_id, id),
  foreign key (organization_id, analysis_id)
    references public.analyses (organization_id, id) on delete restrict,
  foreign key (organization_id, rule_id)
    references public.rules (organization_id, id) on delete restrict,
  check ((start_ms is null and end_ms is null) or (start_ms >= 0 and end_ms > start_ms)),
  check ((start_char is null and end_char is null) or (start_char >= 0 and end_char > start_char))
);

create table public.finding_evidence (
  organization_id uuid not null,
  analysis_id uuid not null,
  finding_id uuid not null,
  evidence_item_id uuid not null,
  primary key (organization_id, finding_id, evidence_item_id),
  foreign key (organization_id, analysis_id, finding_id)
    references public.findings (organization_id, analysis_id, id) on delete restrict,
  foreign key (organization_id, analysis_id, evidence_item_id)
    references public.evidence_items (organization_id, analysis_id, id) on delete restrict
);

create table public.finding_decisions (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null,
  finding_id uuid not null,
  decision public.finding_decision_kind not null,
  rationale text not null check (length(btrim(rationale)) between 1 and 2000),
  actor_user_id uuid not null references auth.users(id) on delete restrict,
  created_at timestamptz not null default now(),
  unique (organization_id, id),
  foreign key (organization_id, finding_id)
    references public.findings (organization_id, id) on delete restrict
);

create table public.review_contexts (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null,
  analysis_id uuid not null,
  submission_version_id uuid not null,
  manifest_hash text not null check (manifest_hash ~ '^[0-9a-f]{64}$'),
  review_status public.review_status not null default 'unreviewed',
  review_version integer not null default 1 check (review_version > 0),
  decisions_revision integer not null default 0 check (decisions_revision >= 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (organization_id, id),
  unique (organization_id, analysis_id),
  foreign key (organization_id, analysis_id)
    references public.analyses (organization_id, id) on delete restrict,
  foreign key (organization_id, submission_version_id)
    references public.submission_versions (organization_id, id) on delete restrict
);

create table public.review_events (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null,
  review_context_id uuid not null,
  action public.review_action not null,
  expected_review_version integer not null check (expected_review_version > 0),
  rationale text not null check (length(btrim(rationale)) between 1 and 2000),
  actor_user_id uuid not null references auth.users(id) on delete restrict,
  approval_id uuid,
  created_at timestamptz not null default now(),
  unique (organization_id, id),
  foreign key (organization_id, review_context_id)
    references public.review_contexts (organization_id, id) on delete restrict
);

create table public.approvals (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null,
  review_context_id uuid not null,
  analysis_id uuid not null,
  submission_version_id uuid not null,
  expected_review_version integer not null check (expected_review_version > 0),
  decisions_revision integer not null check (decisions_revision >= 0),
  manifest_hash text not null check (manifest_hash ~ '^[0-9a-f]{64}$'),
  asset_sha256 text not null check (asset_sha256 ~ '^[0-9a-f]{64}$'),
  caption_sha256 text not null check (caption_sha256 ~ '^[0-9a-f]{64}$'),
  rule_manifest_hash text not null check (rule_manifest_hash ~ '^[0-9a-f]{64}$'),
  prompt_version text not null,
  model_manifest_hash text not null check (model_manifest_hash ~ '^[0-9a-f]{64}$'),
  reviewer_user_id uuid not null references auth.users(id) on delete restrict,
  rationale text not null check (length(btrim(rationale)) between 1 and 2000),
  approved_at timestamptz not null default now(),
  unique (organization_id, id),
  unique (organization_id, review_context_id),
  foreign key (organization_id, review_context_id)
    references public.review_contexts (organization_id, id) on delete restrict,
  foreign key (organization_id, analysis_id)
    references public.analyses (organization_id, id) on delete restrict,
  foreign key (organization_id, submission_version_id)
    references public.submission_versions (organization_id, id) on delete restrict
);

alter table public.review_events
  add constraint review_events_approval_fk
  foreign key (organization_id, approval_id)
  references public.approvals (organization_id, id) on delete restrict;

create table public.jobs (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete restrict,
  analysis_id uuid,
  job_type text not null,
  resource_type text not null,
  resource_id uuid not null,
  logical_operation_key text not null,
  status public.job_status not null default 'queued',
  invocation_mode public.invocation_mode not null,
  attempt_count integer not null default 0 check (attempt_count >= 0),
  max_attempts integer not null default 3 check (max_attempts between 1 and 10),
  retry_after timestamptz,
  lease_owner text,
  lease_until timestamptz,
  fencing_token bigint not null default 0 check (fencing_token >= 0),
  deadline_at timestamptz,
  requested_by uuid references auth.users(id) on delete restrict,
  safe_error_code text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (organization_id, id),
  unique (organization_id, logical_operation_key),
  foreign key (organization_id, analysis_id)
    references public.analyses (organization_id, id) on delete restrict,
  check ((status = 'running' and lease_owner is not null and lease_until is not null) or status <> 'running')
);

create table public.job_stages (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null,
  job_id uuid not null,
  stage_name text not null,
  attempt_no integer not null check (attempt_no > 0),
  status public.job_stage_status not null default 'pending',
  operation_key text not null,
  provider_request_id text,
  input_snapshot_hash text not null check (input_snapshot_hash ~ '^[0-9a-f]{64}$'),
  output_ref uuid,
  retryable boolean not null default false,
  safe_error_code text,
  started_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz not null default now(),
  unique (organization_id, id),
  unique (organization_id, job_id, stage_name, attempt_no),
  unique (organization_id, operation_key),
  foreign key (organization_id, job_id)
    references public.jobs (organization_id, id) on delete restrict,
  check ((status in ('succeeded', 'failed', 'skipped', 'cancelled', 'outcome_unknown') and completed_at is not null)
      or status in ('pending', 'running'))
);

create table public.idempotency_records (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete restrict,
  actor_user_id uuid not null references auth.users(id) on delete restrict,
  operation text not null,
  idempotency_key text not null,
  body_digest text not null check (body_digest ~ '^[0-9a-f]{64}$'),
  status public.idempotency_status not null default 'started',
  response_status integer,
  response_resource_type text,
  response_resource_id uuid,
  expires_at timestamptz not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (organization_id, id),
  unique (organization_id, actor_user_id, operation, idempotency_key)
);

create table public.budget_accounts (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete restrict,
  currency text not null check (currency ~ '^[A-Z]{3}$'),
  authorized_cap_minor bigint not null check (authorized_cap_minor >= 0),
  settled_minor bigint not null default 0 check (settled_minor >= 0),
  reserved_minor bigint not null default 0 check (reserved_minor >= 0),
  unresolved_minor bigint not null default 0 check (unresolved_minor >= 0),
  period_starts_at timestamptz not null,
  period_ends_at timestamptz not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (organization_id, id),
  unique (organization_id, currency, period_starts_at),
  check (period_ends_at > period_starts_at),
  check (settled_minor + reserved_minor + unresolved_minor <= authorized_cap_minor)
);

create table public.budget_reservations (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null,
  budget_account_id uuid not null,
  job_id uuid not null,
  operation_key text not null,
  amount_minor bigint not null check (amount_minor > 0),
  settled_minor bigint not null default 0 check (settled_minor >= 0),
  status public.reservation_status not null default 'held',
  expires_at timestamptz not null,
  created_by uuid not null references auth.users(id) on delete restrict,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (organization_id, id),
  unique (organization_id, operation_key),
  foreign key (organization_id, budget_account_id)
    references public.budget_accounts (organization_id, id) on delete restrict,
  foreign key (organization_id, job_id)
    references public.jobs (organization_id, id) on delete restrict,
  check (settled_minor <= amount_minor)
);

create table public.usage_ledger (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null,
  budget_reservation_id uuid,
  job_id uuid not null,
  job_stage_id uuid,
  invocation_mode public.invocation_mode not null,
  provider text not null,
  model text not null,
  units jsonb not null check (jsonb_typeof(units) = 'object'),
  price_version text,
  cost_known boolean not null,
  cost_minor bigint check (cost_minor is null or cost_minor >= 0),
  currency text not null check (currency ~ '^[A-Z]{3}$'),
  occurred_at timestamptz not null default now(),
  unique (organization_id, id),
  foreign key (organization_id, budget_reservation_id)
    references public.budget_reservations (organization_id, id) on delete restrict,
  foreign key (organization_id, job_id)
    references public.jobs (organization_id, id) on delete restrict,
  foreign key (organization_id, job_stage_id)
    references public.job_stages (organization_id, id) on delete restrict,
  check ((cost_known and cost_minor is not null) or (not cost_known and cost_minor is null)),
  check (invocation_mode <> 'fixture' or cost_minor = 0)
);

create table public.provider_artifacts (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete restrict,
  media_asset_id uuid,
  job_id uuid,
  provider text not null,
  remote_artifact_id text not null,
  region text,
  retention_deadline timestamptz not null,
  deletion_status public.deletion_item_status not null default 'pending',
  deletion_confirmed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (organization_id, id),
  unique (organization_id, provider, remote_artifact_id),
  foreign key (organization_id, media_asset_id)
    references public.media_assets (organization_id, id) on delete restrict,
  foreign key (organization_id, job_id)
    references public.jobs (organization_id, id) on delete restrict
);

create table public.deletion_requests (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete restrict,
  requested_by uuid not null references auth.users(id) on delete restrict,
  target_type text not null,
  target_id uuid not null,
  reason text not null,
  status public.deletion_request_status not null default 'requested',
  scope_snapshot jsonb not null default '{}'::jsonb check (jsonb_typeof(scope_snapshot) = 'object'),
  requested_at timestamptz not null default now(),
  completed_at timestamptz,
  updated_at timestamptz not null default now(),
  unique (organization_id, id),
  check ((status = 'completed' and completed_at is not null) or status <> 'completed')
);

create table public.deletion_items (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null,
  deletion_request_id uuid not null,
  destination text not null,
  artifact_type text not null,
  artifact_ref text not null,
  status public.deletion_item_status not null default 'pending',
  attempts integer not null default 0 check (attempts >= 0),
  next_retry_at timestamptz,
  safe_error_code text,
  confirmed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (organization_id, id),
  unique (organization_id, deletion_request_id, destination, artifact_type, artifact_ref),
  foreign key (organization_id, deletion_request_id)
    references public.deletion_requests (organization_id, id) on delete restrict
);

create table public.deletion_tombstones (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null,
  deletion_request_id uuid not null,
  target_type text not null,
  target_id uuid not null,
  created_at timestamptz not null default now(),
  unique (organization_id, id),
  unique (organization_id, target_type, target_id),
  foreign key (organization_id, deletion_request_id)
    references public.deletion_requests (organization_id, id) on delete restrict
);

create table public.audit_events (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete restrict,
  actor_user_id uuid references auth.users(id) on delete restrict,
  actor_type text not null check (actor_type in ('member', 'worker', 'system')),
  actor_role text,
  action text not null,
  resource_type text not null,
  resource_id uuid,
  resource_version text,
  outcome text not null check (outcome in ('succeeded', 'denied', 'failed')),
  request_id text,
  safe_metadata jsonb not null default '{}'::jsonb check (jsonb_typeof(safe_metadata) = 'object'),
  previous_event_hash text check (previous_event_hash is null or previous_event_hash ~ '^[0-9a-f]{64}$'),
  event_hash text not null check (event_hash ~ '^[0-9a-f]{64}$'),
  occurred_at timestamptz not null default now(),
  unique (organization_id, id),
  unique (organization_id, event_hash)
);

create index memberships_user_active_idx on public.memberships (user_id, organization_id) where status = 'active';
create index campaigns_org_updated_idx on public.campaigns (organization_id, updated_at desc);
create index media_assets_retention_idx on public.media_assets (retention_deadline) where deletion_state in ('active', 'failed');
create index submissions_campaign_idx on public.submissions (organization_id, campaign_id, updated_at desc);
create index submission_versions_submission_idx on public.submission_versions (organization_id, submission_id, version_no desc);
create index analyses_submission_idx on public.analyses (organization_id, submission_version_id, created_at desc);
create index evidence_analysis_time_idx on public.evidence_items (organization_id, analysis_id, start_ms);
create index findings_analysis_idx on public.findings (organization_id, analysis_id, severity);
create index finding_decisions_latest_idx on public.finding_decisions (organization_id, finding_id, created_at desc, id desc);
create index jobs_ready_idx on public.jobs (retry_after, created_at) where status in ('queued', 'retry_wait');
create index jobs_lease_idx on public.jobs (lease_until) where status = 'running';
create index budget_reservations_expiry_idx on public.budget_reservations (expires_at) where status in ('held', 'unresolved');
create index provider_artifacts_retention_idx on public.provider_artifacts (retention_deadline) where deletion_status not in ('deleted', 'not_found');
create index deletion_items_retry_idx on public.deletion_items (next_retry_at, created_at) where status in ('pending', 'failed', 'provider_unconfirmed');
create index audit_events_org_time_idx on public.audit_events (organization_id, occurred_at desc, id desc);

-- RLS is defense in depth for direct authenticated access. API and worker service
-- credentials must still pass an explicit organization scope to their repositories.
create or replace function private.is_active_member(target_organization_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select exists (
    select 1
    from public.memberships membership
    where membership.organization_id = target_organization_id
      and membership.user_id = auth.uid()
      and membership.status = 'active'
  );
$$;

create or replace function private.has_org_role(
  target_organization_id uuid,
  allowed_roles text[]
)
returns boolean
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select exists (
    select 1
    from public.memberships membership
    join public.membership_roles membership_role
      on membership_role.organization_id = membership.organization_id
     and membership_role.membership_id = membership.id
    where membership.organization_id = target_organization_id
      and membership.user_id = auth.uid()
      and membership.status = 'active'
      and membership_role.role::text = any(allowed_roles)
  );
$$;

revoke all on function private.is_active_member(uuid) from public;
revoke all on function private.has_org_role(uuid, text[]) from public;
grant execute on function private.is_active_member(uuid) to authenticated;
grant execute on function private.has_org_role(uuid, text[]) to authenticated;

alter table public.organizations enable row level security;
create policy organizations_active_member_read on public.organizations
  for select to authenticated
  using (private.is_active_member(id));
create policy organizations_admin_update on public.organizations
  for update to authenticated
  using (private.has_org_role(id, array['admin']))
  with check (private.has_org_role(id, array['admin']));

do $rls$
declare
  table_name text;
  read_tables text[] := array[
    'memberships', 'membership_roles', 'brands', 'products', 'product_versions',
    'creators', 'creator_evidence', 'rule_packs', 'rule_pack_versions', 'rules',
    'campaigns', 'campaign_rule_pins', 'campaign_creators', 'consent_receipts',
    'upload_intents', 'media_assets', 'submissions', 'submission_versions',
    'analyses', 'evidence_items', 'findings', 'finding_evidence',
    'finding_decisions', 'review_contexts', 'review_events', 'approvals', 'jobs',
    'job_stages', 'idempotency_records', 'budget_accounts', 'budget_reservations',
    'usage_ledger', 'provider_artifacts', 'deletion_requests', 'deletion_items',
    'deletion_tombstones', 'audit_events'
  ];
begin
  foreach table_name in array read_tables loop
    execute format('alter table public.%I enable row level security', table_name);
    execute format(
      'create policy active_member_read on public.%I for select to authenticated using (private.is_active_member(organization_id))',
      table_name
    );
  end loop;
end
$rls$;

do $rls$
declare
  table_name text;
  marketer_tables text[] := array[
    'brands', 'products', 'product_versions', 'creators', 'creator_evidence',
    'rule_packs', 'rule_pack_versions', 'rules', 'campaigns',
    'campaign_rule_pins', 'campaign_creators', 'consent_receipts',
    'upload_intents', 'media_assets', 'submissions', 'submission_versions',
    'analyses', 'evidence_items', 'findings', 'finding_evidence', 'jobs',
    'job_stages', 'idempotency_records', 'budget_reservations', 'usage_ledger',
    'provider_artifacts', 'deletion_requests', 'deletion_items', 'deletion_tombstones'
  ];
begin
  foreach table_name in array marketer_tables loop
    execute format(
      'create policy marketer_insert on public.%I for insert to authenticated with check (private.has_org_role(organization_id, array[''admin'', ''marketer'']))',
      table_name
    );
    execute format(
      'create policy marketer_update on public.%I for update to authenticated using (private.has_org_role(organization_id, array[''admin'', ''marketer''])) with check (private.has_org_role(organization_id, array[''admin'', ''marketer'']))',
      table_name
    );
  end loop;
end
$rls$;

do $rls$
declare
  table_name text;
  reviewer_tables text[] := array['finding_decisions', 'review_contexts', 'review_events', 'approvals'];
begin
  foreach table_name in array reviewer_tables loop
    execute format(
      'create policy reviewer_insert on public.%I for insert to authenticated with check (private.has_org_role(organization_id, array[''reviewer'']))',
      table_name
    );
    execute format(
      'create policy reviewer_update on public.%I for update to authenticated using (private.has_org_role(organization_id, array[''reviewer''])) with check (private.has_org_role(organization_id, array[''reviewer'']))',
      table_name
    );
  end loop;
end
$rls$;

create policy membership_admin_insert on public.memberships
  for insert to authenticated
  with check (private.has_org_role(organization_id, array['admin']));
create policy membership_admin_update on public.memberships
  for update to authenticated
  using (private.has_org_role(organization_id, array['admin']))
  with check (private.has_org_role(organization_id, array['admin']));
create policy membership_role_admin_insert on public.membership_roles
  for insert to authenticated
  with check (private.has_org_role(organization_id, array['admin']));
create policy membership_role_admin_update on public.membership_roles
  for update to authenticated
  using (private.has_org_role(organization_id, array['admin']))
  with check (private.has_org_role(organization_id, array['admin']));

-- Budget caps and immutable audit records are service-owned in this slice.
-- No authenticated delete policies exist: erasure flows through deletion requests
-- and tombstones so source assets, derivatives, and remote artifacts stay traceable.
