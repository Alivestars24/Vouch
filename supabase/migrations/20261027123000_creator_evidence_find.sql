-- Tenant-owned curated Find evidence. Catalog authoring remains provisioning-owned;
-- the API may only read evidence and add validated creators to campaign rosters.
create table vouch.creator_evidence (
  id uuid primary key,
  organization_id uuid not null,
  creator_id uuid not null,
  product_id uuid,
  category varchar(80) not null,
  match_kind varchar(40) not null,
  source_kind varchar(40) not null,
  source_uri varchar(500) not null,
  source_label varchar(160) not null,
  permission_status varchar(40) not null,
  verification_status varchar(40) not null,
  evidence_mode varchar(40) not null,
  description text not null,
  captured_at timestamptz not null,
  unique (organization_id, id),
  foreign key (organization_id) references vouch.organizations(id) on delete cascade,
  foreign key (organization_id, creator_id)
    references vouch.creators(organization_id, id) on delete cascade,
  foreign key (organization_id, product_id)
    references vouch.products(organization_id, id),
  constraint ck_creator_evidence_match_kind
    check (match_kind in ('exact_product', 'category_relevance')),
  constraint ck_creator_evidence_permission_status
    check (permission_status in
      ('permission_recorded', 'license_recorded', 'permission_unknown')),
  constraint ck_creator_evidence_verification_status
    check (verification_status in ('verified', 'unreviewed', 'unavailable')),
  constraint ck_creator_evidence_mode
    check (evidence_mode in ('human_curated', 'model_analyzed', 'cached')),
  constraint ck_creator_evidence_source_kind
    check (source_kind in ('fixture', 'workspace_provided', 'authorized_connector')),
  constraint ck_creator_evidence_exact_product
    check (match_kind <> 'exact_product' or product_id is not null)
);

create index ix_creator_evidence_org_creator
  on vouch.creator_evidence(organization_id, creator_id);
create index ix_creator_evidence_org_category
  on vouch.creator_evidence(organization_id, category);

alter table vouch.creator_evidence enable row level security;
grant select on vouch.creator_evidence to vouch_api;
create policy api_read on vouch.creator_evidence for select to vouch_api
  using (vouch_private.member_of(organization_id));
