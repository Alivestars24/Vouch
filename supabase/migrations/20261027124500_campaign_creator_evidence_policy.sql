-- The restricted API may attach one validated evidence record to a legacy roster
-- row. Column grants and RLS make the link write-once and campaign-compatible.
grant update (evidence_id) on vouch.campaign_creators to vouch_api;

create policy api_campaign_creator_evidence_link
on vouch.campaign_creators
for update to vouch_api
using (
  evidence_id is null
  and vouch_private.has_role(organization_id, array['admin', 'marketer'])
)
with check (
  evidence_id is not null
  and vouch_private.has_role(organization_id, array['admin', 'marketer'])
  and exists (
    select 1
    from vouch.creator_evidence ce
    join vouch.campaigns c
      on c.organization_id = campaign_creators.organization_id
     and c.id = campaign_creators.campaign_id
    join vouch.products p
      on p.organization_id = c.organization_id
     and p.id = c.product_id
    where ce.organization_id = campaign_creators.organization_id
      and ce.id = campaign_creators.evidence_id
      and ce.creator_id = campaign_creators.creator_id
      and ce.permission_status <> 'permission_unknown'
      and ce.verification_status <> 'unavailable'
      and (
        (ce.match_kind = 'exact_product' and ce.product_id = p.id)
        or (
          ce.match_kind = 'category_relevance'
          and lower(trim(ce.category)) = lower(trim(p.category))
        )
      )
  )
);
