-- Mutation commands must fail closed when their exact source has been
-- tombstoned. Allow only tombstones linked to a source owned by this guest
-- session; no submission or cross-tenant tombstone enumeration is exposed.

grant select on vouch.tombstones to vouch_guest;

create policy guest_source_tombstone_read on vouch.tombstones for select to vouch_guest
using (
  organization_id = vouch_private.organization_id()
  and resource_type = 'media_asset'
  and vouch_private.guest_scope_active()
  and exists (
    select 1
    from vouch.media_assets ma
    where ma.organization_id = tombstones.organization_id
      and ma.id = tombstones.resource_id
      and ma.uploader_user_id is null
      and ma.uploader_guest_session_id = vouch_private.guest_session_id()
  )
);
