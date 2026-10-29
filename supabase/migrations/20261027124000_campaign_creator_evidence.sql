-- Preserve the exact creator evidence used for a Find roster decision. Existing
-- roster rows remain readable with a null link until an authorized member adds
-- evidence through the campaign-scoped command.
alter table vouch.creator_evidence
  add constraint uq_creator_evidence_org_id_creator
  unique (organization_id, id, creator_id);

alter table vouch.campaign_creators
  add column evidence_id uuid;

alter table vouch.campaign_creators
  add constraint fk_campaign_creator_evidence_scope
  foreign key (organization_id, evidence_id, creator_id)
  references vouch.creator_evidence(organization_id, id, creator_id);

create index ix_campaign_creators_evidence_id
  on vouch.campaign_creators(evidence_id);
