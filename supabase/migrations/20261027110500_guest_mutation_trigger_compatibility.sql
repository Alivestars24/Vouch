-- Reconcile the already-applied guest mutation triggers with their final
-- invoker-scoped definitions. The first migration was exercised locally
-- before these guards were narrowed, so keep the correction additive.

create or replace function vouch_private.guard_guest_grant_quota() returns trigger
language plpgsql security invoker set search_path = '' as $$
begin
  if current_user = 'vouch_guest'
    and (new.source_count <> old.source_count
      or new.reserved_bytes <> old.reserved_bytes) then
    if new.source_count <> old.source_count + 1
      or new.reserved_bytes <= old.reserved_bytes
      or new.reserved_bytes - old.reserved_bytes > 5000000
      or new.source_count > 5 or new.reserved_bytes > 25000000
      or to_jsonb(new) - array['source_count', 'reserved_bytes']
        <> to_jsonb(old) - array['source_count', 'reserved_bytes'] then
      raise insufficient_privilege using message = 'Invalid guest source reservation';
    end if;
  end if;
  return new;
end
$$;
revoke all on function vouch_private.guard_guest_grant_quota()
  from public, anon, authenticated;

create or replace function vouch_private.guard_guest_submission_publication() returns trigger
language plpgsql security invoker set search_path = '' as $$
begin
  if current_user = 'vouch_guest'
    and new.current_version_id is distinct from old.current_version_id then
    if old.current_version_id is not null or new.current_version_id is null
      or not exists (
        select 1 from vouch.submission_versions sv
        where sv.organization_id = new.organization_id
          and sv.submission_id = new.id
          and sv.id = new.current_version_id
          and sv.uploader_guest_session_id = vouch_private.guest_session_id()
      ) then
      raise insufficient_privilege using message = 'Invalid guest submission publication';
    end if;
  end if;
  return new;
end
$$;
revoke all on function vouch_private.guard_guest_submission_publication()
  from public, anon, authenticated;
