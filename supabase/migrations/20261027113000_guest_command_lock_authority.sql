-- Idempotency retries lock their immutable command row. Grant only enough
-- authority for SELECT FOR UPDATE; RLS keeps every actual update impossible.

grant update(id) on vouch.guest_commands to vouch_guest;

create policy guest_command_lock on vouch.guest_commands for update to vouch_guest
using (
  organization_id = vouch_private.organization_id()
  and guest_session_id = vouch_private.guest_session_id()
  and vouch_private.guest_scope_active()
)
with check (false);
