-- New analysis bindings include measured metadata. The API cannot rewrite a finalized
-- asset's provenance in-place; deletion may clear content without changing its hashes.
create function vouch_private.guard_media_provenance() returns trigger
language plpgsql set search_path = '' as $$
begin
  if (current_user='vouch_api' or (pg_has_role(current_user,'vouch_api','member')
    and not exists(select 1 from pg_catalog.pg_roles where rolname=current_user
      and (rolsuper or rolbypassrls)))) and old.status='validated'
    and (new.processing_metadata::jsonb is distinct from old.processing_metadata::jsonb
      or new.sha256 is distinct from old.sha256
      or new.duration_ms is distinct from old.duration_ms
      or new.validated_content_type is distinct from old.validated_content_type
      or new.actual_bytes is distinct from old.actual_bytes) then
    raise insufficient_privilege using message='Finalized media provenance is immutable';
  end if;
  return new;
end $$;
revoke all on function vouch_private.guard_media_provenance() from public,anon,authenticated;
create trigger guard_media_provenance before update on vouch.media_assets
  for each row execute function vouch_private.guard_media_provenance();
