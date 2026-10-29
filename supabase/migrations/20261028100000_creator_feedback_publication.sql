-- Explicit creator feedback publication. Drafts remain internal until an authorized
-- member snapshots an allowlisted message against one exact analysis lineage.

alter table vouch.submission_versions
  add constraint uq_submission_version_feedback_lineage
  unique (organization_id, id, submission_id);
alter table vouch.analyses
  add constraint uq_analysis_feedback_lineage
  unique (organization_id, id, submission_version_id, manifest_hash);
alter table vouch.fix_request_drafts
  add constraint uq_fix_request_draft_feedback_lineage
  unique (organization_id, id, analysis_id);

create table vouch.creator_feedback (
  id uuid primary key,
  organization_id uuid not null,
  submission_id uuid not null,
  submission_version_id uuid not null,
  analysis_id uuid not null,
  fix_request_draft_id uuid not null,
  message text not null check (
    message = '' or (message = btrim(message) and length(message) between 1 and 4000)
  ),
  start_ms integer,
  end_ms integer,
  invocation_mode varchar(16) not null
    check (invocation_mode in ('fixture', 'recorded', 'live')),
  analysis_status varchar(32) not null
    check (analysis_status in ('queued', 'running', 'completed', 'partial', 'failed', 'cancelled')),
  manifest_hash varchar(64) not null check (manifest_hash ~ '^[a-f0-9]{64}$'),
  published_by_user_id uuid not null references vouch.users(id) on delete restrict,
  idempotency_key varchar(160) not null check (length(idempotency_key) between 1 and 160),
  request_digest varchar(64) not null check (request_digest ~ '^[a-f0-9]{64}$'),
  published_at timestamptz not null,
  unique (organization_id, id),
  unique (organization_id, published_by_user_id, idempotency_key),
  foreign key (organization_id)
    references vouch.organizations(id) on delete restrict,
  foreign key (organization_id, submission_id)
    references vouch.submissions(organization_id, id) on delete restrict,
  foreign key (organization_id, submission_version_id, submission_id)
    references vouch.submission_versions(organization_id, id, submission_id) on delete restrict,
  foreign key (organization_id, analysis_id, submission_version_id, manifest_hash)
    references vouch.analyses(
      organization_id, id, submission_version_id, manifest_hash
    ) on delete restrict,
  foreign key (organization_id, fix_request_draft_id, analysis_id)
    references vouch.fix_request_drafts(organization_id, id, analysis_id) on delete restrict,
  check (
    (start_ms is null and end_ms is null)
    or (start_ms is not null and end_ms is not null and start_ms >= 0 and end_ms > start_ms)
  )
);
create index ix_creator_feedback_submission_publication
  on vouch.creator_feedback(organization_id, submission_id, published_at, id);
create index ix_creator_feedback_analysis
  on vouch.creator_feedback(organization_id, analysis_id);

alter table vouch.creator_feedback enable row level security;
revoke all on table vouch.creator_feedback
  from public, anon, authenticated, vouch_worker, vouch_guest;

-- Fixed-path owner lookup validates the immutable cross-table snapshot without
-- opening any referenced tenant table to the guest or browser roles.
create function vouch_private.creator_feedback_publishable(
  tenant uuid,
  target_submission uuid,
  target_version uuid,
  target_analysis uuid,
  target_draft uuid,
  snapshot_manifest_hash text,
  snapshot_invocation_mode text,
  snapshot_analysis_status text,
  range_start_ms integer,
  range_end_ms integer
) returns boolean
language sql security definer set search_path = '' as $$
  select exists (
    select 1
    from vouch.submissions s
    join vouch.submission_versions sv
      on sv.organization_id = s.organization_id
      and sv.submission_id = s.id
      and sv.id = target_version
    join vouch.media_assets ma
      on ma.organization_id = sv.organization_id and ma.id = sv.asset_id
    join vouch.analyses a
      on a.organization_id = sv.organization_id
      and a.submission_version_id = sv.id
      and a.id = target_analysis
    join vouch.fix_request_drafts d
      on d.organization_id = a.organization_id
      and d.analysis_id = a.id
      and d.id = target_draft
    where s.organization_id = tenant
      and s.id = target_submission
      and s.deleted_at is null
      and ma.deleted_at is null
      and ma.status = 'validated'
      and ma.retention_deadline > clock_timestamp()
      and d.text <> ''
      and a.manifest_hash = snapshot_manifest_hash
      and a.invocation_mode = snapshot_invocation_mode
      and a.analysis_status = snapshot_analysis_status
      and (
        (range_start_ms is null and range_end_ms is null)
        or (
          range_start_ms is not null and range_end_ms is not null
          and range_start_ms >= 0 and range_end_ms > range_start_ms
          and (ma.duration_ms is null or range_end_ms <= ma.duration_ms)
        )
      )
      and not exists (
        select 1 from vouch.tombstones t
        where t.organization_id = tenant
          and (
            (t.resource_type = 'submission' and t.resource_id = s.id)
            or (t.resource_type = 'media_asset' and t.resource_id = ma.id)
          )
      )
  )
$$;
revoke all on function vouch_private.creator_feedback_publishable(
  uuid, uuid, uuid, uuid, uuid, text, text, text, integer, integer
) from public, anon, authenticated, vouch_worker, vouch_guest, vouch_retention;
grant execute on function vouch_private.creator_feedback_publishable(
  uuid, uuid, uuid, uuid, uuid, text, text, text, integer, integer
) to vouch_api;

create function vouch_private.guard_creator_feedback_insert() returns trigger
language plpgsql set search_path = '' as $$
begin
  if new.message = '' or length(btrim(new.message)) not between 1 and 4000
    or new.message <> btrim(new.message)
    or not vouch_private.creator_feedback_publishable(
      new.organization_id,
      new.submission_id,
      new.submission_version_id,
      new.analysis_id,
      new.fix_request_draft_id,
      new.manifest_hash,
      new.invocation_mode,
      new.analysis_status,
      new.start_ms,
      new.end_ms
    ) then
    raise check_violation using
      message = 'Creator feedback must bind an active exact analysis snapshot';
  end if;
  return new;
end
$$;
revoke all on function vouch_private.guard_creator_feedback_insert()
  from public, anon, authenticated, vouch_api, vouch_worker, vouch_guest, vouch_retention;
create trigger guard_creator_feedback_insert
  before insert on vouch.creator_feedback
  for each row execute function vouch_private.guard_creator_feedback_insert();

grant select, insert on vouch.creator_feedback to vouch_api;
create policy api_creator_feedback_read on vouch.creator_feedback for select to vouch_api
  using (
    vouch_private.has_role(
      organization_id, array['admin', 'marketer', 'reviewer']
    )
  );
create policy api_creator_feedback_insert on vouch.creator_feedback for insert to vouch_api
  with check (
    vouch_private.has_role(
      organization_id, array['admin', 'marketer', 'reviewer']
    )
    and published_by_user_id = vouch_private.user_id()
    and message <> ''
    and published_at between clock_timestamp() - interval '1 minute'
      and clock_timestamp() + interval '1 minute'
    and vouch_private.creator_feedback_publishable(
      organization_id,
      submission_id,
      submission_version_id,
      analysis_id,
      fix_request_draft_id,
      manifest_hash,
      invocation_mode,
      analysis_status,
      start_ms,
      end_ms
    )
  );

-- Retention can follow only an already authorized expired-source lineage and can
-- erase only the shared message snapshot. Identifiers and provenance remain for
-- bounded audit/retry accounting.
grant select on vouch.creator_feedback to vouch_retention;
grant update(message) on vouch.creator_feedback to vouch_retention;
create policy retention_creator_feedback_read
  on vouch.creator_feedback for select to vouch_retention
  using (vouch_private.retention_analysis_allowed(analysis_id, organization_id));
create policy retention_creator_feedback_scrub
  on vouch.creator_feedback for update to vouch_retention
  using (vouch_private.retention_analysis_allowed(analysis_id, organization_id))
  with check (vouch_private.retention_analysis_allowed(analysis_id, organization_id));

create or replace function vouch_private.guard_retention_scrub() returns trigger
language plpgsql set search_path = '' as $$
declare valid boolean := false;
begin
  if not (current_user='vouch_retention' or (pg_has_role(current_user,'vouch_retention','member')
    and not exists (select 1 from pg_catalog.pg_roles where rolname=current_user
      and (rolsuper or rolbypassrls)))) then return new; end if;
  if to_jsonb(new)=to_jsonb(old) then return new; end if;
  case tg_table_name
    when 'media_assets' then valid := new.filename='' and new.object_bytes is null
      and new.status='deleted' and new.deleted_at is not null
      and to_jsonb(new)-array['filename','object_bytes','status','deleted_at']
        =to_jsonb(old)-array['filename','object_bytes','status','deleted_at'];
    when 'submissions' then valid := false;
    when 'submission_versions' then valid := new.caption='';
    when 'analyses' then valid := new.machine_assessment='not_assessed'
      and new.observed_coverage::jsonb='[]'::jsonb and new.missing_intervals::jsonb='[]'::jsonb
      and (new.analysis_status=old.analysis_status
        or (old.analysis_status in ('queued','running') and new.analysis_status='cancelled'));
    when 'review_contexts' then valid := new.review_status='revoked' and new.revision=old.revision+1;
    when 'jobs' then valid := old.status in ('queued','running','retry_wait')
      and new.status='cancelled' and new.fence=old.fence+1
      and new.lease_owner is null and new.lease_until is null and new.retry_after is null;
    when 'budget_reservations' then valid := old.status='held' and new.status='released'
      and new.reconciled_at is not null and exists (select 1 from vouch.jobs j
        where j.id=new.job_id and j.organization_id=new.organization_id and j.status='cancelled');
    when 'organizations' then valid := new.budget_held_minor<=old.budget_held_minor
      and new.budget_held_minor>=0
      and new.budget_held_minor=vouch_private.retention_held_total(new.id);
    when 'evidence_items' then valid := new.description='';
    when 'findings' then valid := new.evidence_text='' and new.uncertainty='' and new.suggested_action='';
    when 'finding_decisions','review_events' then valid := new.rationale='';
    when 'fix_request_drafts' then valid := new.text='';
    when 'creator_feedback' then valid := new.message=''
      and to_jsonb(new)-'message'=to_jsonb(old)-'message';
    else valid := false;
  end case;
  if not coalesce(valid,false) then
    raise insufficient_privilege using message='Retention may only scrub anchored expired content';
  end if;
  return new;
end
$$;
create trigger guard_retention_scrub
  before update on vouch.creator_feedback
  for each row execute function vouch_private.guard_retention_scrub();

-- Replace the allowlisted guest DTO so it exposes only explicitly published
-- snapshots for this assignment. Scrubbed or unavailable source lineage is hidden
-- immediately, including while durable cleanup is still reconciling.
create or replace function vouch_private.guest_submission_context() returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  checked_at timestamptz := clock_timestamp();
  scoped_session vouch.guest_sessions%rowtype;
  scoped_grant vouch.guest_grants%rowtype;
  result jsonb;
begin
  select gs.* into scoped_session
    from vouch.guest_sessions gs
    where gs.id = vouch_private.guest_session_id()
      and gs.grant_id = vouch_private.guest_grant_id()
      and gs.organization_id = vouch_private.organization_id()
      and gs.revoked_at is null
      and gs.expires_at > checked_at;
  if scoped_session.id is null then return null; end if;
  select g.* into scoped_grant
    from vouch.guest_grants g
    where g.id = scoped_session.grant_id
      and g.organization_id = scoped_session.organization_id;
  if scoped_grant.id is null or not vouch_private.guest_grant_issuer_active(
    scoped_grant.id, true, checked_at
  ) then return null; end if;
  if exists (
    select 1 from vouch.submissions s
    join vouch.submission_versions sv on sv.id = s.current_version_id
      and sv.organization_id = s.organization_id and sv.submission_id = s.id
    left join vouch.media_assets ma on ma.id = sv.asset_id
      and ma.organization_id = sv.organization_id
    where s.id = scoped_grant.submission_id
      and (ma.id is null or ma.deleted_at is not null
        or ma.retention_deadline <= checked_at or exists (
          select 1 from vouch.tombstones t
          where t.organization_id = s.organization_id
            and t.resource_type = 'media_asset' and t.resource_id = sv.asset_id
        ))
  ) then return null; end if;
  select jsonb_build_object(
    'session_expires_at', scoped_session.expires_at,
    'campaign', jsonb_build_object(
      'name', c.name, 'market', c.market, 'brand_name', b.name
    ),
    'creator', jsonb_build_object('name', cr.name, 'handle', cr.handle),
    'submission', jsonb_build_object(
      'current_version', case when sv.id is null then null else jsonb_build_object(
        'version_no', sv.version_no, 'caption', sv.caption, 'created_at', sv.created_at
      ) end,
      'review_state', case
        when exists (
          select 1 from vouch.review_contexts rc
          join vouch.approvals a on a.review_context_id = rc.id
            and a.organization_id = rc.organization_id
            and a.submission_version_id = rc.submission_version_id
          where rc.organization_id = scoped_grant.organization_id
            and rc.submission_id = scoped_grant.submission_id
            and rc.submission_version_id = s.current_version_id
            and rc.review_status = 'approved'
        ) then 'approved'
        when exists (
          select 1 from vouch.review_contexts rc
          where rc.organization_id = scoped_grant.organization_id
            and rc.submission_id = scoped_grant.submission_id
            and rc.submission_version_id = s.current_version_id
            and rc.review_status = 'changes_requested'
        ) then 'changes_requested'
        else 'awaiting_brand_review'
      end,
      'approved_version_no', case when exists (
        select 1 from vouch.review_contexts rc
        join vouch.approvals a on a.review_context_id = rc.id
          and a.organization_id = rc.organization_id
          and a.submission_version_id = rc.submission_version_id
        where rc.organization_id = scoped_grant.organization_id
          and rc.submission_id = scoped_grant.submission_id
          and rc.submission_version_id = s.current_version_id
          and rc.review_status = 'approved'
      ) then sv.version_no else null end
    ),
    'allowed_actions', scoped_grant.allowed_actions::jsonb,
    'feedback', coalesce((
      select jsonb_agg(
        jsonb_build_object(
          'version_no', feedback_version.version_no,
          'message', cf.message,
          'start_ms', cf.start_ms,
          'end_ms', cf.end_ms,
          'invocation_mode', cf.invocation_mode,
          'analysis_status', cf.analysis_status,
          'manifest_hash', cf.manifest_hash,
          'published_at', cf.published_at,
          'historical', s.current_version_id is null
            or cf.submission_version_id <> s.current_version_id
        ) order by cf.published_at, cf.id
      )
      from vouch.creator_feedback cf
      join vouch.submission_versions feedback_version
        on feedback_version.organization_id = cf.organization_id
        and feedback_version.id = cf.submission_version_id
        and feedback_version.submission_id = cf.submission_id
      join vouch.media_assets feedback_asset
        on feedback_asset.organization_id = feedback_version.organization_id
        and feedback_asset.id = feedback_version.asset_id
      where cf.organization_id = scoped_grant.organization_id
        and cf.submission_id = scoped_grant.submission_id
        and cf.message <> ''
        and feedback_asset.deleted_at is null
        and feedback_asset.retention_deadline > checked_at
        and not exists (
          select 1 from vouch.tombstones feedback_tombstone
          where feedback_tombstone.organization_id = cf.organization_id
            and (
              (feedback_tombstone.resource_type = 'submission'
                and feedback_tombstone.resource_id = cf.submission_id)
              or (feedback_tombstone.resource_type = 'media_asset'
                and feedback_tombstone.resource_id = feedback_asset.id)
            )
        )
    ), '[]'::jsonb)
  ) into result
  from vouch.submissions s
  join vouch.campaigns c on c.id = s.campaign_id and c.organization_id = s.organization_id
  join vouch.products p on p.id = c.product_id and p.organization_id = c.organization_id
  join vouch.brands b on b.id = p.brand_id and b.organization_id = p.organization_id
  join vouch.creators cr on cr.id = s.creator_id and cr.organization_id = s.organization_id
  left join vouch.submission_versions sv on sv.id = s.current_version_id
    and sv.organization_id = s.organization_id and sv.submission_id = s.id
  where s.organization_id = scoped_grant.organization_id
    and s.id = scoped_grant.submission_id
    and s.campaign_id = scoped_grant.campaign_id
    and s.creator_id = scoped_grant.creator_id
    and s.deleted_at is null
    and (s.current_version_id is null or sv.id is not null);
  return result;
end
$$;
