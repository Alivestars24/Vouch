-- The member-only role lookup is not executable by the guest runtime. Keep it
-- in a separate branch so unrelated guest publication does not evaluate it.

create or replace function vouch_private.guard_api_submission_update() returns trigger
language plpgsql security invoker set search_path = '' as $$
begin
  if current_user = 'vouch_api' or (
    pg_has_role(current_user, 'vouch_api', 'member')
    and not exists (
      select 1 from pg_catalog.pg_roles where rolname = current_user
        and (rolsuper or rolbypassrls)
    )
  ) then
    if new is distinct from old
      and not vouch_private.has_role(old.organization_id, array['admin','marketer']) then
      raise insufficient_privilege using message = 'Member may lock but not change submissions';
    end if;
  end if;
  return new;
end
$$;
revoke all on function vouch_private.guard_api_submission_update()
  from public, anon, authenticated;
