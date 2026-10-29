-- Bound unauthenticated exchange writes and add non-secret invitation recovery lineage.
alter table vouch.guest_grants
  add column issuance_recovery_id uuid,
  add column renewal_root_id uuid;

update vouch.guest_grants
set issuance_recovery_id = id,
    renewal_root_id = id;

alter table vouch.guest_grants
  alter column issuance_recovery_id set not null,
  alter column renewal_root_id set not null,
  add constraint uq_guest_grant_renewal_root_scope unique (
    organization_id,
    id,
    campaign_id,
    creator_id,
    submission_id,
    issued_by_user_id,
    issuance_recovery_id
  ),
  add constraint fk_guest_grant_renewal_root_scope foreign key (
    organization_id,
    renewal_root_id,
    campaign_id,
    creator_id,
    submission_id,
    issued_by_user_id,
    issuance_recovery_id
  ) references vouch.guest_grants (
    organization_id,
    id,
    campaign_id,
    creator_id,
    submission_id,
    issued_by_user_id,
    issuance_recovery_id
  ) on delete cascade;

create index ix_guest_grant_recovery on vouch.guest_grants(
  organization_id,
  issued_by_user_id,
  issuance_recovery_id,
  created_at
);

create or replace function vouch_private.exchange_guest_invitation(
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
  select count(*)::integer into client_attempts
    from vouch.guest_exchange_attempts
    where client_bucket_hash = privacy_client_bucket
      and attempted_at >= checked_at - interval '15 minutes';
  select count(*)::integer into token_attempts
    from vouch.guest_exchange_attempts
    where token_digest = presented_token_digest
      and attempted_at >= checked_at - interval '15 minutes';
  if client_attempts >= 10 or token_attempts >= 5 then
    return;
  end if;
  insert into vouch.guest_exchange_attempts(client_bucket_hash, token_digest, attempted_at)
    values (privacy_client_bucket, presented_token_digest, checked_at);

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
