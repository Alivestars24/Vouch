-- Guest mutations lock the verified session row so member revocation cannot
-- race publication. PostgreSQL requires UPDATE authority for SELECT FOR UPDATE;
-- expose one column only and keep actual updates denied by RLS.

grant update(revoked_at) on vouch.guest_sessions to vouch_guest;

create policy guest_session_lock on vouch.guest_sessions for update to vouch_guest
using (
  organization_id = vouch_private.organization_id()
  and id = vouch_private.guest_session_id()
  and grant_id = vouch_private.guest_grant_id()
  and vouch_private.guest_scope_active()
)
with check (false);
