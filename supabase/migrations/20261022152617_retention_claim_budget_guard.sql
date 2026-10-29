-- The automatic process cannot acquire a fourth paid/remote cleanup attempt or reopen
-- a failed receipt. A member command may explicitly retry without changing max_attempts.
create function vouch_private.guard_deletion_claim_lease() returns trigger
language plpgsql set search_path = '' as $$
begin
  if exists(select 1 from pg_catalog.pg_roles where rolname=current_user
    and (rolsuper or rolbypassrls)) then return new; end if;
  if new.fence>old.fence then
    if old.lease_until>now() or new.lease_until<=now()
      or new.lease_until>now()+interval '5 minutes' then
      raise insufficient_privilege using message='Deletion claim requires an available bounded lease';
    end if;
    if (current_user='vouch_retention' or pg_has_role(current_user,'vouch_retention','member'))
      and (old.status='failed' or new.attempt_count>old.max_attempts) then
      raise insufficient_privilege using message='Automatic deletion retry budget is exhausted';
    end if;
  elsif new.lease_owner is not null
    and (new.lease_owner is distinct from old.lease_owner or new.lease_until is distinct from old.lease_until) then
    raise insufficient_privilege using message='Deletion lease ownership requires a new fence';
  end if;
  return new;
end $$;
revoke all on function vouch_private.guard_deletion_claim_lease() from public,anon,authenticated;
create trigger guard_deletion_claim_lease before update on vouch.deletion_requests
  for each row execute function vouch_private.guard_deletion_claim_lease();
