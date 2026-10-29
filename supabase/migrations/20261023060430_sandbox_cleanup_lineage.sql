-- Register empty containers before any media can enter them. Keep their exact identity through
-- deletion so tmpfs erasure is a declared, confirmed destination rather than an elapsed-time guess.
alter table vouch.media_assets
  add column processing_container varchar(160),
  add column processing_lease_until timestamptz;
grant update(processing_container,processing_lease_until) on vouch.media_assets to vouch_api;

create or replace function vouch_private.retention_asset_allowed(target uuid, tenant uuid)
returns boolean language sql stable security definer set search_path = '' as $$
  select tenant = vouch_private.organization_id() and exists (
    select 1 from vouch.media_assets ma where ma.id = target and ma.organization_id = tenant
      and ((ma.id = vouch_private.retention_asset_id() and ma.retention_deadline <= now())
        or (ma.deleted_at is not null and ma.status = 'deleted' and exists (
          select 1 from vouch.deletion_requests dr
          where dr.id = vouch_private.retention_request_id() and dr.organization_id = tenant
            and ((dr.resource_type = 'media_asset' and dr.resource_id = ma.id)
              or exists (select 1 from jsonb_array_elements(dr.destinations::jsonb) d
                where d->>'destination' in ('supabase_storage','local_media_sandbox')
                  and coalesce(d->'asset_ids','[]'::jsonb) ? ma.id::text)))))
  )
$$;

create function vouch_private.guard_media_container_ref() returns trigger
language plpgsql set search_path = '' as $$
begin
  if (current_user='vouch_api' or (pg_has_role(current_user,'vouch_api','member')
    and not exists(select 1 from pg_catalog.pg_roles where rolname=current_user
      and (rolsuper or rolbypassrls))))
    and (new.processing_container is distinct from old.processing_container
      or new.processing_lease_until is distinct from old.processing_lease_until) then
    if old.status <> 'content_uploaded' or old.deleted_at is not null
      or new.processing_container !~ ('^vouch-media-'||replace(old.organization_id::text,'-','')
        ||'-'||replace(old.id::text,'-','')||'-[a-f0-9]{32}$')
      or new.processing_container is null or new.processing_lease_until is null
      or new.processing_lease_until<=now() or new.processing_lease_until>now()+interval '2 minutes'
    then raise insufficient_privilege using message='Only scoped pending media can register a bounded sandbox';
    end if;
  end if;
  return new;
end $$;
revoke all on function vouch_private.guard_media_container_ref() from public,anon,authenticated;
create trigger guard_media_container_ref before update on vouch.media_assets
  for each row execute function vouch_private.guard_media_container_ref();
