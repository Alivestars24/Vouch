-- ADR-029 read-only guest foundation. Guest upload/actor expansion follows additively.
alter table vouch.campaign_creators
  add constraint uq_campaign_creator_guest_scope
  unique (organization_id, campaign_id, creator_id);
alter table vouch.submissions
  add constraint uq_submission_guest_scope
  unique (organization_id, id, campaign_id, creator_id);

create table vouch.guest_grants (
  id uuid primary key,
  organization_id uuid not null,
  campaign_id uuid not null,
  creator_id uuid not null,
  submission_id uuid not null,
  issued_by_user_id uuid not null references vouch.users(id),
  scope_kind varchar(32) not null
    check (scope_kind in ('existing_submission', 'created_submission')),
  invitation_secret_hash varchar(64) not null unique
    check (invitation_secret_hash ~ '^[a-f0-9]{64}$'),
  allowed_actions json not null
    check (allowed_actions::jsonb = '["read_submission"]'::jsonb),
  expires_at timestamptz not null,
  consumed_at timestamptz,
  revoked_at timestamptz,
  source_count integer not null default 0 check (source_count between 0 and 5),
  reserved_bytes integer not null default 0 check (reserved_bytes between 0 and 25000000),
  created_at timestamptz not null,
  unique (organization_id, id),
  foreign key (organization_id) references vouch.organizations(id) on delete cascade,
  foreign key (organization_id, campaign_id)
    references vouch.campaigns(organization_id, id) on delete cascade,
  foreign key (organization_id, creator_id)
    references vouch.creators(organization_id, id),
  foreign key (organization_id, campaign_id, creator_id)
    references vouch.campaign_creators(organization_id, campaign_id, creator_id),
  foreign key (organization_id, submission_id, campaign_id, creator_id)
    references vouch.submissions(organization_id, id, campaign_id, creator_id)
    on delete cascade,
  check (expires_at > created_at),
  check (consumed_at is null or consumed_at >= created_at),
  check (revoked_at is null or revoked_at >= created_at)
);
create index ix_guest_grant_expiry on vouch.guest_grants(expires_at, revoked_at);
create index ix_guest_grant_organization on vouch.guest_grants(organization_id);
create index ix_guest_grant_submission on vouch.guest_grants(submission_id);
create index ix_guest_grant_issuer on vouch.guest_grants(issued_by_user_id);

create table vouch.guest_sessions (
  id uuid primary key,
  organization_id uuid not null,
  grant_id uuid not null unique,
  session_secret_hash varchar(64) not null unique
    check (session_secret_hash ~ '^[a-f0-9]{64}$'),
  expires_at timestamptz not null,
  revoked_at timestamptz,
  created_at timestamptz not null,
  unique (organization_id, id),
  foreign key (organization_id, grant_id)
    references vouch.guest_grants(organization_id, id) on delete cascade,
  check (expires_at > created_at),
  check (revoked_at is null or revoked_at >= created_at)
);
create index ix_guest_session_expiry on vouch.guest_sessions(expires_at, revoked_at);
create index ix_guest_session_organization on vouch.guest_sessions(organization_id);
create index ix_guest_session_grant on vouch.guest_sessions(grant_id);

create table vouch.guest_exchange_attempts (
  id uuid primary key default gen_random_uuid(),
  client_bucket_hash varchar(64) not null
    check (client_bucket_hash ~ '^[a-f0-9]{64}$'),
  token_digest varchar(64) not null check (token_digest ~ '^[a-f0-9]{64}$'),
  attempted_at timestamptz not null default now()
);
create index ix_guest_exchange_client_window
  on vouch.guest_exchange_attempts(client_bucket_hash, attempted_at);
create index ix_guest_exchange_token_window
  on vouch.guest_exchange_attempts(token_digest, attempted_at);

alter table vouch.guest_grants enable row level security;
alter table vouch.guest_sessions enable row level security;
alter table vouch.guest_exchange_attempts enable row level security;
revoke all on table vouch.guest_grants, vouch.guest_sessions,
  vouch.guest_exchange_attempts from public, anon, authenticated;

do $$ begin
  if not exists (select 1 from pg_catalog.pg_roles where rolname = 'vouch_guest') then
    create role vouch_guest nologin nosuperuser nocreatedb nocreaterole noinherit nobypassrls;
  end if;
end $$;
-- The runtime startup probe resolves `vouch.organizations` through search_path.
-- Schema USAGE permits name resolution only; the guest role receives no table grants.
grant usage on schema vouch, vouch_private to vouch_guest;

create function vouch_private.guest_grant_id() returns uuid
language sql stable set search_path = '' as $$
  select nullif(current_setting('vouch.guest_grant_id', true), '')::uuid
$$;
create function vouch_private.guest_session_id() returns uuid
language sql stable set search_path = '' as $$
  select nullif(current_setting('vouch.guest_session_id', true), '')::uuid
$$;

create function vouch_private.guest_grant_issuer_active(
  target_grant uuid,
  require_consumed boolean,
  checked_at timestamptz
) returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (
    select 1
    from vouch.guest_grants g
    join vouch.memberships m
      on m.organization_id = g.organization_id
      and m.user_id = g.issued_by_user_id
      and m.active
    join vouch.membership_roles mr
      on mr.organization_id = m.organization_id
      and mr.membership_id = m.id
    join vouch.campaign_creators cc
      on cc.organization_id = g.organization_id
      and cc.campaign_id = g.campaign_id
      and cc.creator_id = g.creator_id
    join vouch.submissions s
      on s.organization_id = g.organization_id
      and s.id = g.submission_id
      and s.campaign_id = g.campaign_id
      and s.creator_id = g.creator_id
      and s.deleted_at is null
    where g.id = target_grant
      and g.revoked_at is null
      and g.expires_at > checked_at
      and ((require_consumed and g.consumed_at is not null)
        or (not require_consumed and g.consumed_at is null))
      and ((g.scope_kind = 'created_submission' and mr.role in ('admin', 'marketer'))
        or (g.scope_kind = 'existing_submission'
          and mr.role in ('admin', 'marketer', 'reviewer')))
      and not exists (
        select 1 from vouch.tombstones t
        where t.organization_id = g.organization_id
          and t.resource_type = 'submission'
          and t.resource_id = g.submission_id
      )
  )
$$;

create function vouch_private.exchange_guest_invitation(
  presented_token_digest text,
  privacy_client_bucket text,
  new_session_id uuid,
  new_session_digest text
) returns table (
  session_id uuid,
  organization_id uuid,
  grant_id uuid,
  campaign_id uuid,
  creator_id uuid,
  submission_id uuid,
  allowed_actions json,
  session_expires_at timestamptz
)
language plpgsql security definer set search_path = '' as $$
declare
  checked_at timestamptz := clock_timestamp();
  client_attempts integer;
  token_attempts integer;
  discovered_grant uuid;
  discovered_organization uuid;
  locked_grant vouch.guest_grants%rowtype;
  created_session vouch.guest_sessions%rowtype;
begin
  if presented_token_digest !~ '^[a-f0-9]{64}$'
    or privacy_client_bucket !~ '^[a-f0-9]{64}$'
    or new_session_digest !~ '^[a-f0-9]{64}$' then
    return;
  end if;

  perform pg_catalog.pg_advisory_xact_lock(
    pg_catalog.hashtextextended('vouch.guest.client.' || privacy_client_bucket, 0)
  );
  perform pg_catalog.pg_advisory_xact_lock(
    pg_catalog.hashtextextended('vouch.guest.token.' || presented_token_digest, 0)
  );
  delete from vouch.guest_exchange_attempts
    where attempted_at < checked_at - interval '24 hours';
  select count(*)::integer into client_attempts
    from vouch.guest_exchange_attempts
    where client_bucket_hash = privacy_client_bucket
      and attempted_at >= checked_at - interval '15 minutes';
  select count(*)::integer into token_attempts
    from vouch.guest_exchange_attempts
    where token_digest = presented_token_digest
      and attempted_at >= checked_at - interval '15 minutes';
  insert into vouch.guest_exchange_attempts(client_bucket_hash, token_digest, attempted_at)
    values (privacy_client_bucket, presented_token_digest, checked_at);
  if client_attempts >= 10 or token_attempts >= 5 then
    return;
  end if;

  select g.id, g.organization_id into discovered_grant, discovered_organization
    from vouch.guest_grants g
    where g.invitation_secret_hash = presented_token_digest;
  if discovered_grant is null then
    return;
  end if;

  perform pg_catalog.pg_advisory_xact_lock(
    pg_catalog.hashtextextended('vouch.lineage.' || discovered_organization::text, 0)
  );
  select g.* into locked_grant
    from vouch.guest_grants g
    where g.id = discovered_grant
      and g.invitation_secret_hash = presented_token_digest
    for update;
  if locked_grant.id is null or not vouch_private.guest_grant_issuer_active(
    locked_grant.id, false, checked_at
  ) then
    return;
  end if;

  insert into vouch.guest_sessions(
    id, organization_id, grant_id, session_secret_hash, expires_at, created_at
  ) values (
    new_session_id,
    locked_grant.organization_id,
    locked_grant.id,
    new_session_digest,
    least(locked_grant.expires_at, checked_at + interval '30 minutes'),
    checked_at
  ) returning * into created_session;
  update vouch.guest_grants set consumed_at = checked_at where id = locked_grant.id;
  perform set_config('vouch.organization_id', locked_grant.organization_id::text, true);
  perform set_config('vouch.guest_grant_id', locked_grant.id::text, true);
  perform set_config('vouch.guest_session_id', created_session.id::text, true);
  return query select created_session.id, locked_grant.organization_id, locked_grant.id,
    locked_grant.campaign_id, locked_grant.creator_id, locked_grant.submission_id,
    locked_grant.allowed_actions, created_session.expires_at;
end
$$;

create function vouch_private.resolve_guest_session(presented_session_digest text)
returns table (
  session_id uuid,
  organization_id uuid,
  grant_id uuid,
  campaign_id uuid,
  creator_id uuid,
  submission_id uuid,
  allowed_actions json,
  session_expires_at timestamptz
)
language plpgsql security definer set search_path = '' as $$
declare
  checked_at timestamptz := clock_timestamp();
  matched_session vouch.guest_sessions%rowtype;
  matched_grant vouch.guest_grants%rowtype;
begin
  if presented_session_digest !~ '^[a-f0-9]{64}$' then
    return;
  end if;
  select gs.* into matched_session
    from vouch.guest_sessions gs
    where gs.session_secret_hash = presented_session_digest
      and gs.revoked_at is null
      and gs.expires_at > checked_at;
  if matched_session.id is null then
    return;
  end if;
  select g.* into matched_grant
    from vouch.guest_grants g
    where g.id = matched_session.grant_id
      and g.organization_id = matched_session.organization_id;
  if matched_grant.id is null or not vouch_private.guest_grant_issuer_active(
    matched_grant.id, true, checked_at
  ) then
    return;
  end if;
  perform set_config('vouch.organization_id', matched_grant.organization_id::text, true);
  perform set_config('vouch.guest_grant_id', matched_grant.id::text, true);
  perform set_config('vouch.guest_session_id', matched_session.id::text, true);
  return query select matched_session.id, matched_grant.organization_id, matched_grant.id,
    matched_grant.campaign_id, matched_grant.creator_id, matched_grant.submission_id,
    matched_grant.allowed_actions, matched_session.expires_at;
end
$$;

create function vouch_private.guest_submission_context() returns jsonb
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
  if scoped_session.id is null then
    return null;
  end if;
  select g.* into scoped_grant
    from vouch.guest_grants g
    where g.id = scoped_session.grant_id
      and g.organization_id = scoped_session.organization_id;
  if scoped_grant.id is null or not vouch_private.guest_grant_issuer_active(
    scoped_grant.id, true, checked_at
  ) then
    return null;
  end if;
  if exists (
    select 1
    from vouch.submissions s
    join vouch.submission_versions sv on sv.id = s.current_version_id
      and sv.organization_id = s.organization_id
    left join vouch.media_assets ma on ma.id = sv.asset_id
      and ma.organization_id = sv.organization_id
    where s.id = scoped_grant.submission_id
      and (ma.id is null or ma.deleted_at is not null or ma.retention_deadline <= checked_at
        or exists (
          select 1 from vouch.tombstones t
          where t.organization_id = s.organization_id
            and t.resource_type = 'media_asset' and t.resource_id = sv.asset_id
        ))
  ) then
    return null;
  end if;

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
    'allowed_actions', '["read_submission"]'::jsonb,
    'feedback', '[]'::jsonb
  ) into result
  from vouch.submissions s
  join vouch.campaigns c on c.id = s.campaign_id and c.organization_id = s.organization_id
  join vouch.products p on p.id = c.product_id and p.organization_id = c.organization_id
  join vouch.brands b on b.id = p.brand_id and b.organization_id = p.organization_id
  join vouch.creators cr on cr.id = s.creator_id and cr.organization_id = s.organization_id
  left join vouch.submission_versions sv on sv.id = s.current_version_id
    and sv.organization_id = s.organization_id
  where s.organization_id = scoped_grant.organization_id
    and s.id = scoped_grant.submission_id
    and s.campaign_id = scoped_grant.campaign_id
    and s.creator_id = scoped_grant.creator_id
    and s.deleted_at is null;
  return result;
end
$$;

revoke all on function vouch_private.guest_grant_id() from public, anon, authenticated;
revoke all on function vouch_private.guest_session_id() from public, anon, authenticated;
revoke all on function vouch_private.guest_grant_issuer_active(uuid, boolean, timestamptz)
  from public, anon, authenticated, vouch_api, vouch_worker, vouch_retention, vouch_guest;
revoke all on function vouch_private.exchange_guest_invitation(text, text, uuid, text)
  from public, anon, authenticated, vouch_api, vouch_worker, vouch_retention;
revoke all on function vouch_private.resolve_guest_session(text)
  from public, anon, authenticated, vouch_api, vouch_worker, vouch_retention;
revoke all on function vouch_private.guest_submission_context()
  from public, anon, authenticated, vouch_api, vouch_worker, vouch_retention;
grant execute on function vouch_private.guest_grant_id(),
  vouch_private.guest_session_id(),
  vouch_private.exchange_guest_invitation(text, text, uuid, text),
  vouch_private.resolve_guest_session(text),
  vouch_private.guest_submission_context() to vouch_guest;

grant select, insert on vouch.guest_grants to vouch_api;
grant update(revoked_at) on vouch.guest_grants to vouch_api;
grant select on vouch.guest_sessions to vouch_api;
grant update(revoked_at) on vouch.guest_sessions to vouch_api;

create policy api_guest_grant_read on vouch.guest_grants for select to vouch_api
using (
  organization_id = (select vouch_private.organization_id())
  and ((scope_kind = 'created_submission'
      and vouch_private.has_role(organization_id, array['admin', 'marketer']))
    or (scope_kind = 'existing_submission'
      and vouch_private.has_role(organization_id, array['admin', 'marketer', 'reviewer'])))
);
create policy api_guest_grant_insert on vouch.guest_grants for insert to vouch_api
with check (
  organization_id = (select vouch_private.organization_id())
  and issued_by_user_id = (select vouch_private.user_id())
  and invitation_secret_hash ~ '^[a-f0-9]{64}$'
  and allowed_actions::jsonb = '["read_submission"]'::jsonb
  and consumed_at is null and revoked_at is null
  and source_count = 0 and reserved_bytes = 0
  and created_at <= now() and expires_at > now()
  and expires_at <= now() + interval '48 hours 1 minute'
  and ((scope_kind = 'created_submission'
      and vouch_private.has_role(organization_id, array['admin', 'marketer']))
    or (scope_kind = 'existing_submission'
      and vouch_private.has_role(organization_id, array['admin', 'marketer', 'reviewer'])))
);
create policy api_guest_grant_revoke on vouch.guest_grants for update to vouch_api
using (
  organization_id = (select vouch_private.organization_id())
  and ((scope_kind = 'created_submission'
      and vouch_private.has_role(organization_id, array['admin', 'marketer']))
    or (scope_kind = 'existing_submission'
      and vouch_private.has_role(organization_id, array['admin', 'marketer', 'reviewer'])))
)
with check (
  organization_id = (select vouch_private.organization_id())
  and revoked_at is not null
  and ((scope_kind = 'created_submission'
      and vouch_private.has_role(organization_id, array['admin', 'marketer']))
    or (scope_kind = 'existing_submission'
      and vouch_private.has_role(organization_id, array['admin', 'marketer', 'reviewer'])))
);
create policy api_guest_session_read on vouch.guest_sessions for select to vouch_api
using (
  organization_id = (select vouch_private.organization_id())
  and exists (select 1 from vouch.guest_grants g where g.id = grant_id)
);
create policy api_guest_session_revoke on vouch.guest_sessions for update to vouch_api
using (
  organization_id = (select vouch_private.organization_id())
  and exists (select 1 from vouch.guest_grants g where g.id = grant_id)
)
with check (
  organization_id = (select vouch_private.organization_id())
  and revoked_at is not null
  and exists (select 1 from vouch.guest_grants g where g.id = grant_id)
);
