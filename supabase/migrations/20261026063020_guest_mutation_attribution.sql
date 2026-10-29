-- First creator mutation milestone: preserve member history while adding true,
-- stable guest-session attribution. No historical processing receipt is created.

alter table vouch.guest_grants
  drop constraint if exists guest_grants_allowed_actions_check;
alter table vouch.guest_grants
  add constraint guest_grants_allowed_actions_check check (
    allowed_actions::jsonb in (
      '["read_submission"]'::jsonb,
      '["read_submission", "upload_source", "submit_version"]'::jsonb
    )
  );

alter policy api_guest_grant_insert on vouch.guest_grants
with check (
  organization_id = (select vouch_private.organization_id())
  and issued_by_user_id = (select vouch_private.user_id())
  and invitation_secret_hash ~ '^[a-f0-9]{64}$'
  and allowed_actions::jsonb =
    '["read_submission", "upload_source", "submit_version"]'::jsonb
  and consumed_at is null and revoked_at is null
  and source_count = 0 and reserved_bytes = 0
  and created_at >= clock_timestamp() - interval '1 minute'
  and created_at <= clock_timestamp() + interval '1 minute'
  and expires_at > clock_timestamp()
  and expires_at <= created_at + interval '48 hours'
  and ((scope_kind = 'created_submission'
      and vouch_private.has_role(organization_id, array['admin', 'marketer']))
    or (scope_kind = 'existing_submission'
      and vouch_private.has_role(
        organization_id, array['admin', 'marketer', 'reviewer']
      )))
);

alter table vouch.media_assets
  alter column uploader_user_id drop not null,
  add column uploader_guest_session_id uuid,
  add constraint ck_media_asset_uploader_xor check (
    (uploader_user_id is not null and uploader_guest_session_id is null)
    or (uploader_user_id is null and uploader_guest_session_id is not null)
  ) not valid,
  add constraint uq_media_asset_member_uploader
    unique (organization_id, id, uploader_user_id),
  add constraint uq_media_asset_guest_uploader
    unique (organization_id, id, uploader_guest_session_id),
  add constraint fk_media_asset_guest_session foreign key (
    organization_id, uploader_guest_session_id
  ) references vouch.guest_sessions(organization_id, id) not valid;

alter table vouch.submission_versions
  alter column uploader_user_id drop not null,
  add column uploader_guest_session_id uuid,
  add constraint ck_submission_version_uploader_xor check (
    (uploader_user_id is not null and uploader_guest_session_id is null)
    or (uploader_user_id is null and uploader_guest_session_id is not null)
  ) not valid,
  add constraint fk_submission_version_guest_session foreign key (
    organization_id, uploader_guest_session_id
  ) references vouch.guest_sessions(organization_id, id) not valid,
  add constraint fk_submission_version_member_uploader foreign key (
    organization_id, asset_id, uploader_user_id
  ) references vouch.media_assets(organization_id, id, uploader_user_id) not valid,
  add constraint fk_submission_version_guest_uploader foreign key (
    organization_id, asset_id, uploader_guest_session_id
  ) references vouch.media_assets(
    organization_id, id, uploader_guest_session_id
  ) not valid;

alter table vouch.consent_receipts
  alter column actor_user_id drop not null,
  add column actor_guest_session_id uuid,
  add constraint ck_consent_receipt_actor_xor check (
    (actor_user_id is not null and actor_guest_session_id is null)
    or (actor_user_id is null and actor_guest_session_id is not null)
  ) not valid,
  add constraint fk_consent_receipt_guest_session foreign key (
    organization_id, actor_guest_session_id
  ) references vouch.guest_sessions(organization_id, id) not valid,
  add constraint fk_consent_receipt_member_uploader foreign key (
    organization_id, asset_id, actor_user_id
  ) references vouch.media_assets(organization_id, id, uploader_user_id) not valid,
  add constraint fk_consent_receipt_guest_uploader foreign key (
    organization_id, asset_id, actor_guest_session_id
  ) references vouch.media_assets(
    organization_id, id, uploader_guest_session_id
  ) not valid;

alter table vouch.audit_events
  add column actor_guest_session_id uuid,
  add constraint ck_audit_event_guest_actor check (
    (actor_kind = 'guest' and actor_user_id is null
      and actor_guest_session_id is not null)
    or (actor_kind <> 'guest' and actor_guest_session_id is null)
  ) not valid,
  add constraint fk_audit_event_guest_session foreign key (
    organization_id, actor_guest_session_id
  ) references vouch.guest_sessions(organization_id, id) not valid;

alter table vouch.media_assets validate constraint ck_media_asset_uploader_xor;
alter table vouch.media_assets validate constraint fk_media_asset_guest_session;
alter table vouch.submission_versions
  validate constraint ck_submission_version_uploader_xor;
alter table vouch.submission_versions
  validate constraint fk_submission_version_guest_session;
alter table vouch.submission_versions
  validate constraint fk_submission_version_member_uploader;
alter table vouch.submission_versions
  validate constraint fk_submission_version_guest_uploader;
alter table vouch.consent_receipts validate constraint ck_consent_receipt_actor_xor;
alter table vouch.consent_receipts validate constraint fk_consent_receipt_guest_session;
alter table vouch.consent_receipts
  validate constraint fk_consent_receipt_member_uploader;
alter table vouch.consent_receipts
  validate constraint fk_consent_receipt_guest_uploader;
alter table vouch.audit_events validate constraint ck_audit_event_guest_actor;
alter table vouch.audit_events validate constraint fk_audit_event_guest_session;

create index ix_media_asset_guest_uploader
  on vouch.media_assets(organization_id, uploader_guest_session_id);
create index ix_submission_version_guest_uploader
  on vouch.submission_versions(organization_id, uploader_guest_session_id);
create index ix_consent_receipt_guest_actor
  on vouch.consent_receipts(organization_id, actor_guest_session_id);
create index ix_audit_event_guest_actor
  on vouch.audit_events(organization_id, actor_guest_session_id);

create table vouch.guest_commands (
  id uuid primary key,
  organization_id uuid not null,
  guest_session_id uuid not null,
  operation varchar(80) not null check (
    operation in ('guest_upload_intent', 'guest_submission_version')
  ),
  idempotency_key varchar(160) not null check (length(idempotency_key) between 1 and 160),
  request_digest varchar(64) not null check (request_digest ~ '^[a-f0-9]{64}$'),
  result_resource_type varchar(40) not null,
  result_resource_id uuid not null,
  created_at timestamptz not null,
  constraint uq_guest_command_scope unique (
    organization_id, guest_session_id, operation, idempotency_key
  ),
  constraint ck_guest_command_result_mapping check (
    (operation = 'guest_upload_intent' and result_resource_type = 'media_asset')
    or (operation = 'guest_submission_version'
      and result_resource_type = 'submission_version')
  ),
  unique (organization_id, id),
  foreign key (organization_id)
    references vouch.organizations(id) on delete cascade,
  foreign key (organization_id, guest_session_id)
    references vouch.guest_sessions(organization_id, id) on delete cascade
);
create index ix_guest_command_session_created
  on vouch.guest_commands(guest_session_id, created_at);
alter table vouch.guest_commands enable row level security;
revoke all on vouch.guest_commands from public, anon, authenticated;

create function vouch_private.guest_scope_active() returns boolean
language sql security definer set search_path = '' as $$
  select exists (
    select 1
    from vouch.guest_sessions gs
    join vouch.guest_grants g
      on g.organization_id = gs.organization_id and g.id = gs.grant_id
    where gs.organization_id = vouch_private.organization_id()
      and gs.id = vouch_private.guest_session_id()
      and gs.grant_id = vouch_private.guest_grant_id()
      and gs.revoked_at is null
      and gs.expires_at > clock_timestamp()
      and vouch_private.guest_grant_issuer_active(
        g.id, true, clock_timestamp()
      )
  )
$$;
revoke all on function vouch_private.guest_scope_active()
  from public, anon, authenticated, vouch_api, vouch_worker, vouch_retention;
grant execute on function vouch_private.guest_scope_active() to vouch_guest;
grant execute on function vouch_private.organization_id() to vouch_guest;

create function vouch_private.guest_workspace_storage_available() returns bigint
language sql security definer set search_path = '' as $$
  with scoped as (
    select vouch_private.organization_id() as organization_id
    where vouch_private.guest_scope_active()
  ),
  accounted as (
    select coalesce(sum(
      case
        when ma.deleted_at is not null or ma.status = 'deleted' then
          case
            when ma.storage_backend = 'supabase' and not exists (
              select 1
              from vouch.deletion_requests dr
              cross join lateral jsonb_array_elements(
                case when jsonb_typeof(dr.destinations::jsonb) = 'array'
                  then dr.destinations::jsonb else '[]'::jsonb end
              ) destination
              where dr.organization_id = ma.organization_id
                and dr.status in ('completed', 'partial', 'failed', 'in_progress')
                and destination->>'destination' = 'supabase_storage'
                and destination->>'status' = 'completed'
                and jsonb_typeof(destination->'asset_ids') = 'array'
                and (destination->'asset_ids') @> to_jsonb(array[ma.id::text])
                and (
                  (dr.resource_type = 'media_asset' and dr.resource_id = ma.id)
                  or (dr.resource_type = 'submission' and exists (
                    select 1 from vouch.submission_versions sv
                    where sv.organization_id = ma.organization_id
                      and sv.submission_id = dr.resource_id
                      and sv.asset_id = ma.id
                  ))
                )
            ) then coalesce(nullif(ma.actual_bytes, 0), 5000000)
            when ma.storage_backend <> 'database' or ma.object_bytes is not null
              then coalesce(nullif(ma.actual_bytes, 0), 5000000)
            else 0
          end
        when ma.actual_bytes is not null and ma.actual_bytes > 0
          and ma.status <> 'intent_created' then ma.actual_bytes
        else 5000000
      end
    ), 0)::bigint as bytes
    from scoped s
    join vouch.media_assets ma on ma.organization_id = s.organization_id
  )
  select case when exists (select 1 from scoped)
    then greatest(0::bigint, 500000000::bigint - coalesce((select bytes from accounted), 0))
    else 0::bigint end
$$;
revoke all on function vouch_private.guest_workspace_storage_available()
  from public, anon, authenticated, vouch_api, vouch_worker, vouch_retention;
grant execute on function vouch_private.guest_workspace_storage_available()
  to vouch_guest;

create function vouch_private.guard_guest_mutation_scope() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if tg_table_name = 'media_assets' and new.uploader_guest_session_id is not null then
    if not exists (
      select 1 from vouch.guest_sessions gs
      join vouch.guest_grants g
        on g.organization_id = gs.organization_id and g.id = gs.grant_id
      where gs.organization_id = new.organization_id
        and gs.id = new.uploader_guest_session_id
        and g.campaign_id = new.campaign_id
    ) then
      raise foreign_key_violation using message = 'Guest media is outside its grant scope';
    end if;
  elsif tg_table_name = 'submission_versions'
    and new.uploader_guest_session_id is not null then
    if not exists (
      select 1 from vouch.guest_sessions gs
      join vouch.guest_grants g
        on g.organization_id = gs.organization_id and g.id = gs.grant_id
      where gs.organization_id = new.organization_id
        and gs.id = new.uploader_guest_session_id
        and g.submission_id = new.submission_id
    ) then
      raise foreign_key_violation using message = 'Guest version is outside its grant scope';
    end if;
  end if;
  return new;
end
$$;
revoke all on function vouch_private.guard_guest_mutation_scope()
  from public, anon, authenticated;
create trigger guard_guest_media_scope
  before insert or update on vouch.media_assets
  for each row execute function vouch_private.guard_guest_mutation_scope();
create trigger guard_guest_version_scope
  before insert or update on vouch.submission_versions
  for each row execute function vouch_private.guard_guest_mutation_scope();

create function vouch_private.guard_guest_grant_quota() returns trigger
language plpgsql set search_path = '' as $$
begin
  if current_user = 'vouch_guest'
    and (new.source_count <> old.source_count
      or new.reserved_bytes <> old.reserved_bytes) then
    if new.source_count <> old.source_count + 1
      or new.reserved_bytes <= old.reserved_bytes
      or new.reserved_bytes - old.reserved_bytes > 5000000
      or new.source_count > 5 or new.reserved_bytes > 25000000
      or to_jsonb(new) - array['source_count', 'reserved_bytes']
        <> to_jsonb(old) - array['source_count', 'reserved_bytes'] then
      raise insufficient_privilege using message = 'Invalid guest source reservation';
    end if;
  end if;
  return new;
end
$$;
revoke all on function vouch_private.guard_guest_grant_quota()
  from public, anon, authenticated;
create trigger guard_guest_grant_quota
  before update on vouch.guest_grants
  for each row execute function vouch_private.guard_guest_grant_quota();

create function vouch_private.guard_guest_submission_publication() returns trigger
language plpgsql set search_path = '' as $$
begin
  if current_user = 'vouch_guest' and new.current_version_id is distinct from old.current_version_id
  then
    if old.current_version_id is not null or new.current_version_id is null
      or not exists (
        select 1 from vouch.submission_versions sv
        where sv.organization_id = new.organization_id
          and sv.submission_id = new.id
          and sv.id = new.current_version_id
          and sv.uploader_guest_session_id = vouch_private.guest_session_id()
      ) then
      raise insufficient_privilege using message = 'Invalid guest submission publication';
    end if;
  end if;
  return new;
end
$$;
revoke all on function vouch_private.guard_guest_submission_publication()
  from public, anon, authenticated;
create trigger guard_guest_submission_publication
  before update on vouch.submissions
  for each row execute function vouch_private.guard_guest_submission_publication();

grant select on vouch.guest_grants, vouch.guest_sessions, vouch.submissions,
  vouch.media_assets, vouch.consent_receipts, vouch.submission_versions,
  vouch.guest_commands to vouch_guest;
grant insert on vouch.media_assets, vouch.consent_receipts,
  vouch.submission_versions, vouch.guest_commands, vouch.audit_events to vouch_guest;
grant update(source_count, reserved_bytes) on vouch.guest_grants to vouch_guest;
grant update(filename, validated_content_type, actual_bytes, sha256, duration_ms,
  processing_metadata, status, object_bytes, processing_container,
  processing_lease_until) on vouch.media_assets to vouch_guest;
grant update(current_version_id) on vouch.submissions to vouch_guest;

create policy guest_grant_read on vouch.guest_grants for select to vouch_guest
using (
  organization_id = vouch_private.organization_id()
  and id = vouch_private.guest_grant_id()
  and vouch_private.guest_scope_active()
);
create policy guest_grant_quota on vouch.guest_grants for update to vouch_guest
using (
  organization_id = vouch_private.organization_id()
  and id = vouch_private.guest_grant_id()
  and vouch_private.guest_scope_active()
)
with check (
  organization_id = vouch_private.organization_id()
  and id = vouch_private.guest_grant_id()
  and source_count between 0 and 5
  and reserved_bytes between 0 and 25000000
  and vouch_private.guest_scope_active()
);
create policy guest_session_read on vouch.guest_sessions for select to vouch_guest
using (
  organization_id = vouch_private.organization_id()
  and id = vouch_private.guest_session_id()
  and grant_id = vouch_private.guest_grant_id()
  and vouch_private.guest_scope_active()
);
create policy guest_submission_read on vouch.submissions for select to vouch_guest
using (
  organization_id = vouch_private.organization_id()
  and vouch_private.guest_scope_active()
  and exists (
    select 1 from vouch.guest_grants g
    where g.id = vouch_private.guest_grant_id()
      and g.organization_id = submissions.organization_id
      and g.submission_id = submissions.id
      and g.campaign_id = submissions.campaign_id
      and g.creator_id = submissions.creator_id
  )
);
create policy guest_submission_publish on vouch.submissions for update to vouch_guest
using (
  organization_id = vouch_private.organization_id()
  and current_version_id is null
  and vouch_private.guest_scope_active()
  and exists (
    select 1 from vouch.guest_grants g
    where g.id = vouch_private.guest_grant_id()
      and g.organization_id = submissions.organization_id
      and g.submission_id = submissions.id
      and g.allowed_actions::jsonb @> '["submit_version"]'::jsonb
  )
)
with check (
  organization_id = vouch_private.organization_id()
  and vouch_private.guest_scope_active()
);
create policy guest_media_read on vouch.media_assets for select to vouch_guest
using (
  organization_id = vouch_private.organization_id()
  and uploader_guest_session_id = vouch_private.guest_session_id()
  and vouch_private.guest_scope_active()
);
create policy guest_media_insert on vouch.media_assets for insert to vouch_guest
with check (
  organization_id = vouch_private.organization_id()
  and uploader_user_id is null
  and uploader_guest_session_id = vouch_private.guest_session_id()
  and status = 'intent_created' and object_bytes is null
  and actual_bytes is null and sha256 is null and duration_ms is null
  and validated_content_type is null and deleted_at is null
  and rights_attested
  and created_at between clock_timestamp() - interval '1 minute'
    and clock_timestamp() + interval '1 minute'
  and retention_deadline > clock_timestamp()
  and vouch_private.guest_scope_active()
  and exists (
    select 1 from vouch.guest_grants g
    where g.id = vouch_private.guest_grant_id()
      and g.organization_id = media_assets.organization_id
      and g.campaign_id = media_assets.campaign_id
      and g.allowed_actions::jsonb @> '["upload_source"]'::jsonb
  )
);
create policy guest_media_update on vouch.media_assets for update to vouch_guest
using (
  organization_id = vouch_private.organization_id()
  and uploader_guest_session_id = vouch_private.guest_session_id()
  and status in ('intent_created', 'content_uploaded')
  and deleted_at is null
  and vouch_private.guest_scope_active()
)
with check (
  organization_id = vouch_private.organization_id()
  and uploader_user_id is null
  and uploader_guest_session_id = vouch_private.guest_session_id()
  and status in ('intent_created', 'content_uploaded', 'validated')
  and deleted_at is null and rights_attested
  and vouch_private.guest_scope_active()
);
create policy guest_consent_read on vouch.consent_receipts for select to vouch_guest
using (
  organization_id = vouch_private.organization_id()
  and actor_guest_session_id = vouch_private.guest_session_id()
  and vouch_private.guest_scope_active()
);
create policy guest_consent_insert on vouch.consent_receipts for insert to vouch_guest
with check (
  organization_id = vouch_private.organization_id()
  and actor_user_id is null
  and actor_guest_session_id = vouch_private.guest_session_id()
  and purpose = 'campaign_check'
  and revoked_at is null and revoked_by is null
  and revocation_actor_kind is null and revocation_reason is null
  and vouch_private.guest_scope_active()
  and exists (
    select 1 from vouch.media_assets ma
    where ma.id = consent_receipts.asset_id
      and ma.organization_id = consent_receipts.organization_id
      and ma.campaign_id = consent_receipts.campaign_id
      and ma.uploader_user_id is null
      and ma.uploader_guest_session_id = actor_guest_session_id
      and ma.rights_attested and ma.status = 'intent_created'
      and ma.deleted_at is null
      and ma.created_at > clock_timestamp() - interval '5 minutes'
      and ma.retention_deadline > clock_timestamp()
  )
);
create policy guest_version_read on vouch.submission_versions for select to vouch_guest
using (
  organization_id = vouch_private.organization_id()
  and uploader_guest_session_id = vouch_private.guest_session_id()
  and vouch_private.guest_scope_active()
);
create policy guest_version_insert on vouch.submission_versions for insert to vouch_guest
with check (
  organization_id = vouch_private.organization_id()
  and uploader_user_id is null
  and uploader_guest_session_id = vouch_private.guest_session_id()
  and version_no = 1 and rights_attested
  and vouch_private.guest_scope_active()
  and exists (
    select 1 from vouch.guest_grants g
    join vouch.submissions s
      on s.organization_id = g.organization_id and s.id = g.submission_id
    where g.id = vouch_private.guest_grant_id()
      and g.organization_id = submission_versions.organization_id
      and g.submission_id = submission_versions.submission_id
      and g.allowed_actions::jsonb @> '["submit_version"]'::jsonb
      and s.current_version_id is null and s.deleted_at is null
  )
  and exists (
    select 1 from vouch.media_assets ma
    join vouch.consent_receipts cr
      on cr.organization_id = ma.organization_id and cr.asset_id = ma.id
    where ma.organization_id = submission_versions.organization_id
      and ma.id = submission_versions.asset_id
      and ma.uploader_guest_session_id = uploader_guest_session_id
      and ma.status = 'validated' and ma.deleted_at is null
      and ma.rights_attested and cr.revoked_at is null
      and cr.actor_guest_session_id = uploader_guest_session_id
  )
);
create policy guest_command_read on vouch.guest_commands for select to vouch_guest
using (
  organization_id = vouch_private.organization_id()
  and guest_session_id = vouch_private.guest_session_id()
  and vouch_private.guest_scope_active()
);
create policy guest_command_insert on vouch.guest_commands for insert to vouch_guest
with check (
  organization_id = vouch_private.organization_id()
  and guest_session_id = vouch_private.guest_session_id()
  and created_at between clock_timestamp() - interval '1 minute'
    and clock_timestamp() + interval '1 minute'
  and vouch_private.guest_scope_active()
  and (
    (operation = 'guest_upload_intent' and result_resource_type = 'media_asset'
      and exists (
        select 1 from vouch.media_assets ma
        where ma.organization_id = guest_commands.organization_id
          and ma.id = guest_commands.result_resource_id
          and ma.uploader_guest_session_id = guest_commands.guest_session_id
      ))
    or (operation = 'guest_submission_version'
      and result_resource_type = 'submission_version' and exists (
        select 1 from vouch.submission_versions sv
        where sv.organization_id = guest_commands.organization_id
          and sv.id = guest_commands.result_resource_id
          and sv.uploader_guest_session_id = guest_commands.guest_session_id
      ))
  )
);
create policy guest_audit_insert on vouch.audit_events for insert to vouch_guest
with check (
  organization_id = vouch_private.organization_id()
  and actor_kind = 'guest' and actor_user_id is null
  and actor_guest_session_id = vouch_private.guest_session_id()
  and vouch_private.guest_scope_active()
);

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
    'feedback', '[]'::jsonb
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
