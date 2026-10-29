-- Application timestamps are assigned immediately before INSERT, after the API
-- transaction may already have begun during identity resolution. PostgreSQL
-- `now()` is transaction-start time, so compare those values to the wall clock.
alter policy api_guest_grant_insert on vouch.guest_grants
with check (
  organization_id = (select vouch_private.organization_id())
  and issued_by_user_id = (select vouch_private.user_id())
  and invitation_secret_hash ~ '^[a-f0-9]{64}$'
  and allowed_actions::jsonb = '["read_submission"]'::jsonb
  and consumed_at is null and revoked_at is null
  and source_count = 0 and reserved_bytes = 0
  and created_at >= clock_timestamp() - interval '1 minute'
  and created_at <= clock_timestamp() + interval '1 minute'
  and expires_at > clock_timestamp()
  and expires_at <= created_at + interval '48 hours'
  and ((scope_kind = 'created_submission'
      and vouch_private.has_role(organization_id, array['admin', 'marketer']))
    or (scope_kind = 'existing_submission'
      and vouch_private.has_role(organization_id, array['admin', 'marketer', 'reviewer'])))
);
