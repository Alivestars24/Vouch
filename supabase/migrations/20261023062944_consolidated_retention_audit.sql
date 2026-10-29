-- Preserve both narrow audit capabilities with one INSERT policy per runtime role.
drop policy retention_audit on vouch.audit_events;
drop policy retention_consent_audit on vouch.audit_events;
create policy retention_audit on vouch.audit_events for insert to vouch_retention
  with check (organization_id=(select vouch_private.organization_id())
    and actor_kind='retention' and actor_user_id is null and (
      (vouch_private.retention_scope_active(organization_id)
        and action like 'deletion.%' and resource_type='deletion_request'
        and vouch_private.retention_request_allowed(resource_id,organization_id))
      or (action='processing.authorization_revoked' and resource_type='consent_receipt'
        and exists (select 1 from vouch.consent_receipts cr where cr.id=resource_id
          and cr.organization_id=audit_events.organization_id and cr.revoked_at is not null
          and cr.revoked_by is null and cr.revocation_actor_kind='retention'
          and vouch_private.retention_asset_allowed(cr.asset_id,cr.organization_id)
          and vouch_private.consent_source_deleted(cr.asset_id,cr.organization_id)))));
