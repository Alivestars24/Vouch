-- Revising a draft records supersession without granting marketers human approval rights.
alter policy api_human_insert on vouch.review_events with check (
  actor_user_id = vouch_private.user_id() and (
    vouch_private.has_role(organization_id, array['reviewer'])
    or (vouch_private.has_role(organization_id, array['admin','marketer'])
      and action = 'superseded'
      and exists (select 1 from vouch.review_contexts rc
        where rc.id = review_context_id and rc.organization_id = review_events.organization_id
          and rc.review_status = 'superseded' and rc.revision = review_revision
          and rc.manifest_hash = review_events.manifest_hash))
  )
);
