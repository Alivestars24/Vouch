-- Approved product claims and explicit campaign brief requirements.
-- These records are tenant-owned inputs; they do not certify a claim or approve content.

create table vouch.product_claims (
  id uuid primary key,
  organization_id uuid not null references vouch.organizations(id) on delete cascade,
  product_id uuid not null,
  approved_wording text not null check (length(approved_wording) between 1 and 2000),
  evidence_label varchar(160) not null check (length(evidence_label) > 0),
  evidence_uri varchar(500) not null check (length(evidence_uri) > 0),
  expires_at timestamptz,
  status varchar(16) not null check (status in ('approved', 'withdrawn')),
  created_by uuid not null references vouch.users(id),
  created_at timestamptz not null default now(),
  unique (organization_id, id),
  foreign key (organization_id, product_id)
    references vouch.products(organization_id, id) on delete cascade
);

create index ix_product_claims_product
  on vouch.product_claims(organization_id, product_id, created_at);

create table vouch.campaign_requirements (
  id uuid primary key,
  organization_id uuid not null references vouch.organizations(id) on delete cascade,
  campaign_id uuid not null,
  kind varchar(32) not null check (
    kind in ('disclosure', 'product_visibility', 'cta', 'exact_phrase', 'approved_claim')
  ),
  label varchar(160) not null check (length(label) > 0),
  expected_text text,
  claim_id uuid,
  required boolean not null default true,
  created_by uuid not null references vouch.users(id),
  created_at timestamptz not null default now(),
  unique (organization_id, id),
  foreign key (organization_id, campaign_id)
    references vouch.campaigns(organization_id, id) on delete cascade,
  foreign key (organization_id, claim_id)
    references vouch.product_claims(organization_id, id),
  check ((kind = 'approved_claim' and claim_id is not null)
    or (kind <> 'approved_claim' and claim_id is null)),
  check ((kind in ('cta', 'exact_phrase') and expected_text is not null
      and length(expected_text) > 0)
    or (kind not in ('cta', 'exact_phrase')))
);

create index ix_campaign_requirements_campaign
  on vouch.campaign_requirements(organization_id, campaign_id, created_at);

alter table vouch.product_claims enable row level security;
alter table vouch.campaign_requirements enable row level security;

revoke all on vouch.product_claims, vouch.campaign_requirements
  from public, anon, authenticated, vouch_worker, vouch_guest, vouch_retention;
grant select, insert on vouch.product_claims, vouch.campaign_requirements to vouch_api;

create policy api_read on vouch.product_claims for select to vouch_api
using (
  organization_id = vouch_private.organization_id()
  and vouch_private.member_of(organization_id)
);
create policy api_insert on vouch.product_claims for insert to vouch_api
with check (
  organization_id = vouch_private.organization_id()
  and created_by = vouch_private.user_id()
  and status = 'approved'
  and vouch_private.has_role(organization_id, array['admin', 'marketer'])
);

create policy api_read on vouch.campaign_requirements for select to vouch_api
using (
  organization_id = vouch_private.organization_id()
  and vouch_private.member_of(organization_id)
);
create policy api_insert on vouch.campaign_requirements for insert to vouch_api
with check (
  organization_id = vouch_private.organization_id()
  and created_by = vouch_private.user_id()
  and vouch_private.has_role(organization_id, array['admin', 'marketer'])
  and exists (
    select 1 from vouch.campaigns campaign
    where campaign.organization_id = campaign_requirements.organization_id
      and campaign.id = campaign_requirements.campaign_id
  )
);
