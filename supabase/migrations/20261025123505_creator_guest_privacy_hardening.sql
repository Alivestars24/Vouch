create index ix_guest_exchange_attempt_expiry
  on vouch.guest_exchange_attempts(attempted_at);

create function vouch_private.prune_guest_exchange_attempts() returns integer
language plpgsql security definer set search_path = '' as $$
declare
  removed integer;
begin
  delete from vouch.guest_exchange_attempts
    where attempted_at < clock_timestamp() - interval '24 hours';
  get diagnostics removed = row_count;
  return removed;
end
$$;
revoke all on function vouch_private.prune_guest_exchange_attempts()
  from public, anon, authenticated, vouch_api, vouch_worker, vouch_guest;
grant execute on function vouch_private.prune_guest_exchange_attempts()
  to vouch_retention;

-- Re-pin the scoped DTO to the exact submission/version lineage. The application
-- maintains this pointer, but guest reads fail closed if legacy or inconsistent
-- data points at a version owned by another submission.
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
      and sv.submission_id = s.id
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
    and sv.submission_id = s.id
  where s.organization_id = scoped_grant.organization_id
    and s.id = scoped_grant.submission_id
    and s.campaign_id = scoped_grant.campaign_id
    and s.creator_id = scoped_grant.creator_id
    and s.deleted_at is null
    and (s.current_version_id is null or sv.id is not null);
  return result;
end
$$;
