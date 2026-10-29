-- Permit an active, mutation-scoped creator session to append exactly the
-- next immutable version. The service holds the submission lineage lock and
-- supplies the expected current-version UUID; RLS and this trigger retain an
-- independent database boundary.

drop policy if exists guest_submission_publish on vouch.submissions;
create policy guest_submission_publish on vouch.submissions for update to vouch_guest
using (
  organization_id = vouch_private.organization_id()
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

drop policy if exists guest_version_insert on vouch.submission_versions;
create policy guest_version_insert on vouch.submission_versions for insert to vouch_guest
with check (
  organization_id = vouch_private.organization_id()
  and uploader_user_id is null
  and uploader_guest_session_id = vouch_private.guest_session_id()
  and rights_attested
  and vouch_private.guest_scope_active()
  and exists (
    select 1
    from vouch.guest_grants g
    join vouch.submissions s
      on s.organization_id = g.organization_id and s.id = g.submission_id
    left join vouch.submission_versions current_version
      on current_version.organization_id = s.organization_id
     and current_version.submission_id = s.id
     and current_version.id = s.current_version_id
    where g.id = vouch_private.guest_grant_id()
      and g.organization_id = submission_versions.organization_id
      and g.submission_id = submission_versions.submission_id
      and g.allowed_actions::jsonb @> '["submit_version"]'::jsonb
      and s.deleted_at is null
      and (
        (s.current_version_id is null and submission_versions.version_no = 1)
        or (
          current_version.id is not null
          and submission_versions.version_no = current_version.version_no + 1
        )
      )
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

create or replace function vouch_private.guard_guest_submission_publication() returns trigger
language plpgsql set search_path = '' as $$
begin
  if current_user = 'vouch_guest'
    and new.current_version_id is distinct from old.current_version_id
  then
    if new.current_version_id is null
      or not exists (
        select 1
        from vouch.submission_versions next_version
        left join vouch.submission_versions previous_version
          on previous_version.organization_id = old.organization_id
         and previous_version.submission_id = old.id
         and previous_version.id = old.current_version_id
        where next_version.organization_id = new.organization_id
          and next_version.submission_id = new.id
          and next_version.id = new.current_version_id
          and next_version.uploader_guest_session_id = vouch_private.guest_session_id()
          and (
            (old.current_version_id is null and next_version.version_no = 1)
            or (
              previous_version.id is not null
              and next_version.version_no = previous_version.version_no + 1
            )
          )
      ) then
      raise insufficient_privilege using message = 'Invalid guest submission publication';
    end if;
  end if;
  return new;
end
$$;

revoke all on function vouch_private.guard_guest_submission_publication()
  from public, anon, authenticated;
