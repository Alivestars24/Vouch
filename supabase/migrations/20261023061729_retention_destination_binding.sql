-- A system receipt cannot turn its erased source anchor into a capability to delete a
-- different, still-live sandbox. Resolve every declared copy against that exact source.
create function vouch_private.retention_destinations_allowed(
  target uuid, tenant uuid, destinations jsonb
) returns boolean language plpgsql stable security definer set search_path = '' as $$
declare
  source vouch.media_assets%rowtype;
  destination jsonb;
  kind text;
  seen text[] := array[]::text[];
begin
  if tenant is distinct from vouch_private.organization_id()
    or target is distinct from vouch_private.retention_asset_id()
    or jsonb_typeof(destinations) is distinct from 'array' then return false; end if;
  select * into source from vouch.media_assets ma
    where ma.id=target and ma.organization_id=tenant and ma.retention_deadline<=now()
      and ma.status='deleted' and ma.deleted_at is not null;
  if not found then return false; end if;
  for destination in select value from jsonb_array_elements(destinations) loop
    if jsonb_typeof(destination) is distinct from 'object' then return false; end if;
    kind := destination->>'destination';
    if kind is null or kind=any(seen) then return false; end if;
    seen := array_append(seen,kind);
    case kind
      when 'local_fixture_database','remote_provider' then null;
      when 'supabase_storage' then
        if source.storage_backend<>'supabase'
          or destination->'asset_ids' is distinct from jsonb_build_array(target::text)
        then return false; end if;
      when 'local_media_sandbox' then
        if source.processing_container is null
          or source.processing_container !~ ('^vouch-media-'||replace(tenant::text,'-','')
            ||'-'||replace(target::text,'-','')||'-[a-f0-9]{32}$')
          or destination->'asset_ids' is distinct from jsonb_build_array(target::text)
          or destination->'container_names' is distinct from jsonb_build_array(source.processing_container)
        then return false; end if;
      else return false;
    end case;
  end loop;
  -- Do not silently omit a known copy from the system's initial receipt either.
  return (source.storage_backend<>'supabase' or 'supabase_storage'=any(seen))
    and (source.processing_container is null or 'local_media_sandbox'=any(seen));
end $$;
revoke all on function vouch_private.retention_destinations_allowed(uuid,uuid,jsonb)
  from public,anon,authenticated,vouch_api,vouch_worker;
grant execute on function vouch_private.retention_destinations_allowed(uuid,uuid,jsonb)
  to vouch_retention;

drop policy retention_receipt_insert on vouch.deletion_requests;
create policy retention_receipt_insert on vouch.deletion_requests for insert to vouch_retention
  with check (requested_by is null and requested_by_kind='retention'
    and resource_type='media_asset' and resource_id=vouch_private.retention_asset_id()
    and vouch_private.retention_asset_allowed(resource_id,organization_id)
    and vouch_private.retention_destinations_allowed(resource_id,organization_id,destinations::jsonb));
