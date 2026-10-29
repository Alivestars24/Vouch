-- Expand only. Existing sources remain legacy_no_notice; never invent historical consent.
create table vouch.consent_receipts (
  id uuid primary key,
  organization_id uuid not null references vouch.organizations(id),
  asset_id uuid not null unique references vouch.media_assets(id),
  campaign_id uuid not null references vouch.campaigns(id),
  actor_user_id uuid not null references vouch.users(id),
  purpose varchar(40) not null check (purpose='campaign_check'),
  notice_version varchar(80) not null check (length(notice_version)>0),
  notice_hash varchar(64) not null check (notice_hash ~ '^[a-f0-9]{64}$'),
  accepted_at timestamptz not null,
  revoked_at timestamptz,
  revoked_by uuid references vouch.users(id),
  revocation_actor_kind varchar(24),
  revocation_reason varchar(40),
  unique (organization_id,id),
  foreign key (organization_id,asset_id) references vouch.media_assets(organization_id,id),
  foreign key (organization_id,campaign_id) references vouch.campaigns(organization_id,id),
  constraint consent_revocation_attribution check (
    (revoked_at is null and revoked_by is null and revocation_actor_kind is null
      and revocation_reason is null)
    or (revoked_at is not null and revocation_actor_kind is not null
      and revocation_reason is not null and revoked_at>=accepted_at and (
      (revocation_actor_kind='member' and revoked_by is not null
        and revocation_reason in ('withdrawn','source_deleted'))
      or (revocation_actor_kind='retention' and revoked_by is null
        and revocation_reason in ('expired','source_deleted')))))
);
create index ix_consent_receipts_organization_id on vouch.consent_receipts(organization_id);
-- Worker receipt reads prove that the asset belongs to an existing Check job lineage.
create index ix_submission_versions_org_asset on vouch.submission_versions(organization_id,asset_id);
alter table vouch.consent_receipts enable row level security;
revoke all on vouch.consent_receipts from public,anon,authenticated;

create function vouch_private.consent_source_deleted(target uuid,tenant uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select tenant=vouch_private.organization_id() and exists (
    select 1 from vouch.media_assets ma where ma.id=target and ma.organization_id=tenant
      and (ma.deleted_at is not null or ma.status='deleted' or exists (
        select 1 from vouch.tombstones t where t.organization_id=tenant
          and t.resource_type='media_asset' and t.resource_id=ma.id)))
$$;
revoke all on function vouch_private.consent_source_deleted(uuid,uuid)
  from public,anon,authenticated,vouch_worker;
grant execute on function vouch_private.consent_source_deleted(uuid,uuid)
  to vouch_api,vouch_retention;

grant select,insert on vouch.consent_receipts to vouch_api;
grant select on vouch.consent_receipts to vouch_worker,vouch_retention;
grant update(revoked_at,revoked_by,revocation_actor_kind,revocation_reason)
  on vouch.consent_receipts to vouch_api,vouch_retention;
create policy api_consent_read on vouch.consent_receipts for select to vouch_api
  using (vouch_private.member_of(organization_id));
create policy api_consent_insert on vouch.consent_receipts for insert to vouch_api
  with check (vouch_private.has_role(organization_id,array['admin','marketer'])
    and actor_user_id=vouch_private.user_id() and purpose='campaign_check'
    and revoked_at is null and revoked_by is null and revocation_actor_kind is null
    and revocation_reason is null and exists (
      select 1 from vouch.media_assets ma where ma.id=asset_id
        and ma.organization_id=consent_receipts.organization_id
        and ma.campaign_id=consent_receipts.campaign_id
        and ma.uploader_user_id=actor_user_id and ma.rights_attested
        and ma.status='intent_created' and ma.deleted_at is null
        and ma.created_at>now()-interval '5 minutes' and ma.retention_deadline>now()
        and not exists(select 1 from vouch.tombstones t
          where t.organization_id=ma.organization_id and t.resource_type='media_asset'
            and t.resource_id=ma.id)));
create policy api_consent_revoke on vouch.consent_receipts for update to vouch_api
  using (vouch_private.has_role(organization_id,array['admin','marketer'])
    and vouch_private.consent_source_deleted(asset_id,organization_id))
  with check (vouch_private.has_role(organization_id,array['admin','marketer'])
    and vouch_private.consent_source_deleted(asset_id,organization_id)
    and revoked_at is not null and revoked_by=vouch_private.user_id()
    and revocation_actor_kind='member' and revocation_reason in ('withdrawn','source_deleted'));
create policy worker_consent_read on vouch.consent_receipts for select to vouch_worker
  using (organization_id=(select vouch_private.organization_id()) and exists (
    select 1 from vouch.submission_versions sv
    join vouch.analyses a on a.submission_version_id=sv.id and a.organization_id=sv.organization_id
    join vouch.jobs j on j.resource_id=a.id and j.organization_id=a.organization_id and j.kind='check'
    where sv.asset_id=consent_receipts.asset_id
      and sv.organization_id=consent_receipts.organization_id));
create policy retention_consent_read on vouch.consent_receipts for select to vouch_retention
  using (vouch_private.retention_asset_allowed(asset_id,organization_id)
    and vouch_private.consent_source_deleted(asset_id,organization_id));
create policy retention_consent_revoke on vouch.consent_receipts for update to vouch_retention
  using (vouch_private.retention_asset_allowed(asset_id,organization_id)
    and vouch_private.consent_source_deleted(asset_id,organization_id))
  with check (vouch_private.retention_asset_allowed(asset_id,organization_id)
    and vouch_private.consent_source_deleted(asset_id,organization_id)
    and revoked_at is not null and revoked_by is null and revocation_actor_kind='retention'
    and (revocation_reason='source_deleted' or (revocation_reason='expired' and exists (
      select 1 from vouch.media_assets ma where ma.id=asset_id
        and ma.organization_id=consent_receipts.organization_id and ma.retention_deadline<=now()))));

create function vouch_private.guard_consent_receipt() returns trigger
language plpgsql set search_path = '' as $$
begin
  if to_jsonb(new)=to_jsonb(old) then return new; end if;
  if old.revoked_at is not null or to_jsonb(new)-array['revoked_at','revoked_by',
    'revocation_actor_kind','revocation_reason']<>to_jsonb(old)-array['revoked_at','revoked_by',
    'revocation_actor_kind','revocation_reason'] then
    raise insufficient_privilege using message='Accepted authorization and first revocation are immutable';
  end if;
  return new;
end $$;
revoke all on function vouch_private.guard_consent_receipt() from public,anon,authenticated;
create trigger guard_consent_receipt before update on vouch.consent_receipts
  for each row execute function vouch_private.guard_consent_receipt();
