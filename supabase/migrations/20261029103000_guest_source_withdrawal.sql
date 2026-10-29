-- Exact-scope creator withdrawal. The guest receives no table grants: two
-- security-definer functions validate the active session, assignment, renewal
-- family and receipt/source lineage before exposing an ID or starting erasure.

alter table vouch.deletion_requests drop constraint deletion_actor;
alter table vouch.deletion_requests add constraint deletion_actor check (
  (requested_by_kind = 'member' and requested_by is not null)
  or (requested_by_kind in ('retention', 'guest') and requested_by is null)
);

alter table vouch.consent_receipts drop constraint consent_revocation_attribution;
alter table vouch.consent_receipts add constraint consent_revocation_attribution check (
  (revoked_at is null and revoked_by is null and revocation_actor_kind is null
    and revocation_reason is null)
  or (revoked_at is not null and revocation_actor_kind is not null
    and revocation_reason is not null and revoked_at >= accepted_at and (
      (revocation_actor_kind = 'member' and revoked_by is not null
        and revocation_reason in ('withdrawn', 'source_deleted'))
      or (revocation_actor_kind = 'retention' and revoked_by is null
        and revocation_reason in ('expired', 'source_deleted'))
      or (revocation_actor_kind = 'guest' and revoked_by is null
        and revocation_reason = 'withdrawn')
    ))
);

create function vouch_private.guest_current_source_context() returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object('version_id', sv.id, 'receipt_id', cr.id)
  from vouch.guest_sessions gs
  join vouch.guest_grants g
    on g.organization_id = gs.organization_id and g.id = gs.grant_id
  join vouch.submissions s
    on s.organization_id = g.organization_id and s.id = g.submission_id
    and s.campaign_id = g.campaign_id and s.creator_id = g.creator_id
  join vouch.submission_versions sv
    on sv.organization_id = s.organization_id and sv.submission_id = s.id
    and sv.id = s.current_version_id
  join vouch.media_assets ma
    on ma.organization_id = sv.organization_id and ma.id = sv.asset_id
  join vouch.consent_receipts cr
    on cr.organization_id = ma.organization_id and cr.asset_id = ma.id
  where gs.id = vouch_private.guest_session_id()
    and gs.grant_id = vouch_private.guest_grant_id()
    and gs.organization_id = vouch_private.organization_id()
    and gs.revoked_at is null and gs.expires_at > clock_timestamp()
    and s.deleted_at is null and ma.deleted_at is null
    and ma.retention_deadline > clock_timestamp()
    and vouch_private.guest_grant_issuer_active(g.id, true, clock_timestamp())
$$;
revoke all on function vouch_private.guest_current_source_context()
  from public, anon, authenticated, vouch_api, vouch_worker, vouch_retention;
grant execute on function vouch_private.guest_current_source_context() to vouch_guest;

create function vouch_private.guest_withdraw_source(receipt_id uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  checked_at timestamptz := clock_timestamp();
  tenant uuid := vouch_private.organization_id();
  current_grant_id uuid := vouch_private.guest_grant_id();
  current_session_id uuid := vouch_private.guest_session_id();
  source_asset vouch.media_assets%rowtype;
  source_receipt vouch.consent_receipts%rowtype;
  request_row vouch.deletion_requests%rowtype;
  current_root uuid;
  analysis_ids uuid[] := '{}';
  job_ids uuid[] := '{}';
  version_ids uuid[] := '{}';
  released_minor bigint := 0;
  pending boolean;
  destination_rows jsonb;
begin
  if tenant is null or current_grant_id is null or current_session_id is null
    or not vouch_private.guest_scope_active() then
    raise insufficient_privilege using message = 'Creator access ended';
  end if;

  perform 1 from vouch.organizations o where o.id = tenant for update;
  select coalesce(g.renewal_root_id, g.id) into current_root
    from vouch.guest_grants g where g.organization_id = tenant and g.id = current_grant_id;

  select cr.* into source_receipt
    from vouch.consent_receipts cr
    join vouch.media_assets ma
      on ma.organization_id = cr.organization_id and ma.id = cr.asset_id
    join vouch.guest_sessions source_session
      on source_session.organization_id = ma.organization_id
      and source_session.id = ma.uploader_guest_session_id
      and source_session.id = cr.actor_guest_session_id
    join vouch.guest_grants source_grant
      on source_grant.organization_id = source_session.organization_id
      and source_grant.id = source_session.grant_id
    join vouch.submission_versions sv
      on sv.organization_id = ma.organization_id and sv.asset_id = ma.id
    join vouch.guest_grants current_grant
      on current_grant.organization_id = cr.organization_id
      and current_grant.id = current_grant_id
      and current_grant.submission_id = sv.submission_id
      and current_grant.campaign_id = cr.campaign_id
    where cr.organization_id = tenant and cr.id = receipt_id
      and cr.actor_guest_session_id is not null
      and coalesce(source_grant.renewal_root_id, source_grant.id) = current_root
    for update of cr, ma;
  if source_receipt.id is null then
    return null;
  end if;

  select ma.* into source_asset from vouch.media_assets ma
    where ma.organization_id = tenant and ma.id = source_receipt.asset_id for update;
  select dr.* into request_row from vouch.deletion_requests dr
    where dr.organization_id = tenant and dr.resource_type = 'media_asset'
      and dr.resource_id = source_asset.id;
  if request_row.id is not null then
    return jsonb_build_object(
      'id', request_row.id, 'resource_type', request_row.resource_type,
      'resource_id', request_row.resource_id, 'status', request_row.status,
      'destinations', request_row.destinations::jsonb,
      'requested_by_kind', request_row.requested_by_kind,
      'attempt_count', request_row.attempt_count, 'max_attempts', request_row.max_attempts,
      'retry_after', request_row.retry_after, 'last_error_code', request_row.last_error_code,
      'created_at', request_row.created_at, 'completed_at', request_row.completed_at
    );
  end if;

  select coalesce(array_agg(sv.id), '{}') into version_ids
    from vouch.submission_versions sv
    where sv.organization_id = tenant and sv.asset_id = source_asset.id;
  select coalesce(array_agg(a.id), '{}') into analysis_ids
    from vouch.analyses a
    where a.organization_id = tenant and a.submission_version_id = any(version_ids);
  select coalesce(array_agg(j.id), '{}') into job_ids
    from vouch.jobs j
    where j.organization_id = tenant and j.resource_id = any(analysis_ids)
      and j.status in ('queued', 'running', 'retry_wait');

  update vouch.media_assets set filename = '', object_bytes = null, status = 'deleted',
    processing_metadata = '{}'::json, deleted_at = checked_at
    where organization_id = tenant and id = source_asset.id;
  if source_receipt.revoked_at is null then
    update vouch.consent_receipts set revoked_at = checked_at, revoked_by = null,
      revocation_actor_kind = 'guest', revocation_reason = 'withdrawn'
      where organization_id = tenant and id = source_receipt.id;
  end if;
  update vouch.jobs set status = 'cancelled', fence = fence + 1, lease_owner = null,
    lease_until = null, retry_after = null, updated_at = checked_at
    where organization_id = tenant and id = any(job_ids);
  with released as (
    update vouch.budget_reservations set status = 'released', reconciled_at = checked_at
    where organization_id = tenant and job_id = any(job_ids) and status = 'held'
    returning held_minor
  ) select coalesce(sum(held_minor), 0) into released_minor from released;
  update vouch.organizations set budget_held_minor = greatest(0, budget_held_minor - released_minor)
    where id = tenant and released_minor > 0;
  update vouch.analyses set analysis_status = case when analysis_status in ('queued','running')
      then 'cancelled' else analysis_status end,
    completed_at = case when analysis_status in ('queued','running') then checked_at else completed_at end,
    machine_assessment = 'not_assessed', observed_coverage = '[]'::json,
    missing_intervals = '[]'::json
    where organization_id = tenant and id = any(analysis_ids);
  update vouch.review_contexts set revision = revision + 1, review_status = 'revoked'
    where organization_id = tenant and analysis_id = any(analysis_ids);
  update vouch.submission_versions set caption = ''
    where organization_id = tenant and id = any(version_ids);
  update vouch.evidence_items set description = ''
    where organization_id = tenant and analysis_id = any(analysis_ids);
  update vouch.findings set evidence_text = '', uncertainty = '', suggested_action = ''
    where organization_id = tenant and analysis_id = any(analysis_ids);
  update vouch.finding_decisions set rationale = '' where organization_id = tenant
    and finding_id in (select f.id from vouch.findings f where f.organization_id = tenant
      and f.analysis_id = any(analysis_ids));
  update vouch.review_events set rationale = '' where organization_id = tenant
    and review_context_id in (select rc.id from vouch.review_contexts rc
      where rc.organization_id = tenant and rc.analysis_id = any(analysis_ids));
  update vouch.fix_request_drafts set text = ''
    where organization_id = tenant and analysis_id = any(analysis_ids);
  update vouch.creator_feedback set message = '', start_ms = null, end_ms = null
    where organization_id = tenant and analysis_id = any(analysis_ids);
  insert into vouch.tombstones(id, organization_id, resource_type, resource_id, created_at)
    values(gen_random_uuid(), tenant, 'media_asset', source_asset.id, checked_at)
    on conflict (organization_id, resource_type, resource_id) do nothing;

  pending := source_asset.storage_backend = 'supabase'
    or source_asset.processing_container is not null;
  destination_rows := jsonb_build_array(jsonb_build_object(
    'destination', 'local_fixture_database', 'status', 'completed',
    'deleted_artifact_count', 1, 'redacted_version_count', cardinality(version_ids),
    'redacted_analysis_count', cardinality(analysis_ids)
  ), jsonb_build_object('destination', 'remote_provider',
    'status', 'not_applicable_fixture_mode'));
  if source_asset.storage_backend = 'supabase' then
    destination_rows := destination_rows || jsonb_build_array(jsonb_build_object(
      'destination', 'supabase_storage', 'status', 'pending',
      'asset_ids', jsonb_build_array(source_asset.id)));
  end if;
  if source_asset.processing_container is not null then
    destination_rows := destination_rows || jsonb_build_array(jsonb_build_object(
      'destination', 'local_media_sandbox', 'status', 'pending',
      'asset_ids', jsonb_build_array(source_asset.id),
      'container_names', jsonb_build_array(source_asset.processing_container)));
  end if;
  insert into vouch.deletion_requests(id, organization_id, resource_type, resource_id,
    status, destinations, requested_by, requested_by_kind, attempt_count, max_attempts,
    fence, created_at, completed_at)
  values(gen_random_uuid(), tenant, 'media_asset', source_asset.id,
    case when pending then 'partial' else 'completed' end, destination_rows::json,
    null, 'guest', 0, 3, 0, checked_at, case when pending then null else checked_at end)
  returning * into request_row;
  insert into vouch.audit_events(id, organization_id, actor_user_id, actor_guest_session_id,
    actor_kind, action, resource_type, resource_id, safe_metadata, created_at)
  values
    (gen_random_uuid(), tenant, null, current_session_id, 'guest',
      'processing.authorization_revoked', 'consent_receipt', source_receipt.id,
      jsonb_build_object('reason','withdrawn')::json, checked_at),
    (gen_random_uuid(), tenant, null, current_session_id, 'guest',
      case when pending then 'deletion.requested' else 'deletion.completed' end,
      'deletion_request', request_row.id,
      jsonb_build_object('resource_type','media_asset','resource_id',source_asset.id)::json,
      checked_at);
  return jsonb_build_object(
    'id', request_row.id, 'resource_type', request_row.resource_type,
    'resource_id', request_row.resource_id, 'status', request_row.status,
    'destinations', request_row.destinations::jsonb, 'requested_by_kind', 'guest',
    'attempt_count', 0, 'max_attempts', 3, 'retry_after', null,
    'last_error_code', null, 'created_at', request_row.created_at,
    'completed_at', request_row.completed_at
  );
end
$$;
revoke all on function vouch_private.guest_withdraw_source(uuid)
  from public, anon, authenticated, vouch_api, vouch_worker, vouch_retention;
grant execute on function vouch_private.guest_withdraw_source(uuid) to vouch_guest;
