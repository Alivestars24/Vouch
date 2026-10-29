-- Lock one source without granting the guest role broad UPDATE visibility.
-- The helper returns no row content and accepts only a source owned by the
-- active scoped guest session and campaign.

create function vouch_private.lock_guest_source(asset_id uuid) returns boolean
language plpgsql security definer set search_path = '' as $$
begin
  perform 1
  from vouch.media_assets ma
  join vouch.guest_sessions gs
    on gs.organization_id = ma.organization_id
    and gs.id = ma.uploader_guest_session_id
  join vouch.guest_grants g
    on g.organization_id = gs.organization_id and g.id = gs.grant_id
  where ma.organization_id = vouch_private.organization_id()
    and ma.id = asset_id
    and ma.uploader_user_id is null
    and gs.id = vouch_private.guest_session_id()
    and g.id = vouch_private.guest_grant_id()
    and g.campaign_id = ma.campaign_id
    and ma.deleted_at is null and ma.status <> 'deleted'
    and vouch_private.guest_scope_active()
  for update of ma;
  return found;
end
$$;
revoke all on function vouch_private.lock_guest_source(uuid)
  from public, anon, authenticated, vouch_api, vouch_worker, vouch_retention;
grant execute on function vouch_private.lock_guest_source(uuid) to vouch_guest;
