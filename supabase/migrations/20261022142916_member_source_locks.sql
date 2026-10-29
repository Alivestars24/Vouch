-- Evidence reads and review commands share a source lock with deletion/publication.
-- PostgreSQL applies UPDATE RLS to SELECT FOR UPDATE, even when no mutation occurs.
create policy api_source_lock on vouch.submissions for update to vouch_api
  using (vouch_private.member_of(organization_id))
  with check (vouch_private.member_of(organization_id));

create function vouch_private.guard_api_submission_update() returns trigger
language plpgsql set search_path = '' as $$
begin
  if (current_user = 'vouch_api' or (pg_has_role(current_user, 'vouch_api', 'member')
    and not exists (select 1 from pg_catalog.pg_roles where rolname = current_user
      and (rolsuper or rolbypassrls))))
    and new is distinct from old
    and not vouch_private.has_role(old.organization_id, array['admin','marketer']) then
    raise insufficient_privilege using message = 'Member may lock but not change submissions';
  end if;
  return new;
end $$;
revoke all on function vouch_private.guard_api_submission_update() from public, anon, authenticated;
create trigger guard_api_submission_update before update on vouch.submissions
  for each row execute function vouch_private.guard_api_submission_update();
