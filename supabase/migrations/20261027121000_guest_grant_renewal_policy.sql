-- Renewal keeps the original capability set and the highest quota already
-- consumed by the family. Fresh grants remain mutation-capable with zero use.

create function vouch_private.guest_grant_insert_preserves_limits(
  candidate_id uuid,
  candidate_renewal_root_id uuid,
  candidate_allowed_actions jsonb,
  candidate_source_count integer,
  candidate_reserved_bytes integer
) returns boolean
language sql stable security definer set search_path = '' as $$
  select case
    when candidate_id = candidate_renewal_root_id then
      candidate_allowed_actions =
        '["read_submission", "upload_source", "submit_version"]'::jsonb
      and candidate_source_count = 0
      and candidate_reserved_bytes = 0
    else exists (
      select 1
      from vouch.guest_grants root
      where root.organization_id = vouch_private.organization_id()
        and root.id = candidate_renewal_root_id
        and root.renewal_root_id = root.id
        and root.allowed_actions::jsonb = candidate_allowed_actions
        and candidate_source_count = (
          select max(family.source_count)
          from vouch.guest_grants family
          where family.organization_id = root.organization_id
            and family.renewal_root_id = root.id
        )
        and candidate_reserved_bytes = (
          select max(family.reserved_bytes)
          from vouch.guest_grants family
          where family.organization_id = root.organization_id
            and family.renewal_root_id = root.id
        )
    )
  end
$$;

revoke all on function vouch_private.guest_grant_insert_preserves_limits(
  uuid, uuid, jsonb, integer, integer
) from public, anon, authenticated, vouch_worker, vouch_retention, vouch_guest;
grant execute on function vouch_private.guest_grant_insert_preserves_limits(
  uuid, uuid, jsonb, integer, integer
) to vouch_api;

alter policy api_guest_grant_insert on vouch.guest_grants
with check (
  organization_id = (select vouch_private.organization_id())
  and issued_by_user_id = (select vouch_private.user_id())
  and invitation_secret_hash ~ '^[a-f0-9]{64}$'
  and allowed_actions::jsonb in (
    '["read_submission"]'::jsonb,
    '["read_submission", "upload_source", "submit_version"]'::jsonb
  )
  and consumed_at is null and revoked_at is null
  and vouch_private.guest_grant_insert_preserves_limits(
    id,
    renewal_root_id,
    allowed_actions::jsonb,
    source_count,
    reserved_bytes
  )
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
