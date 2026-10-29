-- Transactional synthetic coverage for the restricted creator guest runtime.
begin;
select no_plan();

-- Local migration owner may create roles but does not inherit SET ROLE automatically.
-- These grants and every synthetic row are rolled back below.
grant vouch_guest, vouch_retention to postgres;
grant usage on schema extensions to vouch_guest;
grant usage on schema extensions to vouch_retention;

create function pg_temp.vouch_guest_test_id(name text) returns uuid
language sql immutable as $$
  select md5('vouch.creator-guest.test.' || name)::uuid
$$;

insert into vouch.organizations
  (id, slug, name, budget_cap_minor, budget_held_minor, budget_settled_minor, budget_currency)
values (
  pg_temp.vouch_guest_test_id('organization'), 'creator-guest-test', 'Creator guest test',
  1000, 0, 0, 'USD'
);
insert into vouch.users (id, email, display_name, auth_subject)
values (
  pg_temp.vouch_guest_test_id('issuer'), 'issuer@creator-guest.vouch.test',
  'Synthetic issuer', pg_temp.vouch_guest_test_id('issuer-subject')
);
insert into vouch.memberships (id, organization_id, user_id, active)
values (
  pg_temp.vouch_guest_test_id('membership'),
  pg_temp.vouch_guest_test_id('organization'),
  pg_temp.vouch_guest_test_id('issuer'), true
);
insert into vouch.membership_roles (id, organization_id, membership_id, role)
values (
  pg_temp.vouch_guest_test_id('membership-role'),
  pg_temp.vouch_guest_test_id('organization'),
  pg_temp.vouch_guest_test_id('membership'), 'admin'
);
insert into vouch.brands (id, organization_id, name)
values (
  pg_temp.vouch_guest_test_id('brand'),
  pg_temp.vouch_guest_test_id('organization'), 'Synthetic brand'
);
insert into vouch.products (id, organization_id, brand_id, name, category, sku, version)
values (
  pg_temp.vouch_guest_test_id('product'),
  pg_temp.vouch_guest_test_id('organization'),
  pg_temp.vouch_guest_test_id('brand'), 'Synthetic product', 'fixture', 'guest-test', 1
);
insert into vouch.creators
  (id, organization_id, name, handle, rights_status, evidence_timestamp)
values (
  pg_temp.vouch_guest_test_id('creator'),
  pg_temp.vouch_guest_test_id('organization'),
  'Synthetic creator', '@synthetic', 'permission_recorded', now()
);
insert into vouch.rule_pack_versions
  (id, organization_id, name, version, status, source_uri, content_hash, rules)
values (
  pg_temp.vouch_guest_test_id('rules'),
  pg_temp.vouch_guest_test_id('organization'),
  'Synthetic rules', '1', 'reviewed', 'fixture://creator-guest', repeat('a', 64), '[]'
);
insert into vouch.campaigns
  (id, organization_id, name, objective, market, product_id, rule_pack_version_id,
   created_by, created_at)
values (
  pg_temp.vouch_guest_test_id('campaign'),
  pg_temp.vouch_guest_test_id('organization'),
  'Synthetic campaign', 'Guest foundation test', 'IN',
  pg_temp.vouch_guest_test_id('product'), pg_temp.vouch_guest_test_id('rules'),
  pg_temp.vouch_guest_test_id('issuer'), now()
);
insert into vouch.campaign_creators (id, organization_id, campaign_id, creator_id)
values (
  pg_temp.vouch_guest_test_id('campaign-creator'),
  pg_temp.vouch_guest_test_id('organization'),
  pg_temp.vouch_guest_test_id('campaign'),
  pg_temp.vouch_guest_test_id('creator')
);
insert into vouch.submissions (id, organization_id, campaign_id, creator_id, created_at)
values (
  pg_temp.vouch_guest_test_id('submission'),
  pg_temp.vouch_guest_test_id('organization'),
  pg_temp.vouch_guest_test_id('campaign'),
  pg_temp.vouch_guest_test_id('creator'), now()
);

insert into vouch.guest_grants
  (id, organization_id, campaign_id, creator_id, submission_id, issued_by_user_id,
   issuance_recovery_id, renewal_root_id, scope_kind, invitation_secret_hash,
   allowed_actions, expires_at, created_at)
values
  (pg_temp.vouch_guest_test_id('grant'),
   pg_temp.vouch_guest_test_id('organization'),
   pg_temp.vouch_guest_test_id('campaign'),
   pg_temp.vouch_guest_test_id('creator'),
   pg_temp.vouch_guest_test_id('submission'),
   pg_temp.vouch_guest_test_id('issuer'),
   pg_temp.vouch_guest_test_id('grant-recovery'),
   pg_temp.vouch_guest_test_id('grant'),
   'existing_submission', repeat('1', 64), '["read_submission"]',
   now() + interval '48 hours', now()),
  (pg_temp.vouch_guest_test_id('throttled-grant'),
   pg_temp.vouch_guest_test_id('organization'),
   pg_temp.vouch_guest_test_id('campaign'),
   pg_temp.vouch_guest_test_id('creator'),
   pg_temp.vouch_guest_test_id('submission'),
   pg_temp.vouch_guest_test_id('issuer'),
   pg_temp.vouch_guest_test_id('throttled-grant-recovery'),
   pg_temp.vouch_guest_test_id('throttled-grant'),
   'existing_submission', repeat('2', 64), '["read_submission"]',
   now() + interval '48 hours', now());

select ok(
  (select not rolcanlogin and not rolsuper and not rolcreatedb and not rolcreaterole
     and not rolinherit and not rolbypassrls
   from pg_roles where rolname = 'vouch_guest'),
  'guest runtime role is a restricted non-login, non-inheriting role'
);
select ok(
  has_table_privilege('vouch_guest', 'vouch.guest_grants', 'SELECT')
  and has_column_privilege(
    'vouch_guest', 'vouch.guest_grants', 'source_count', 'UPDATE'
  )
  and has_column_privilege(
    'vouch_guest', 'vouch.guest_grants', 'reserved_bytes', 'UPDATE'
  )
  and not has_table_privilege(
    'vouch_guest', 'vouch.guest_grants',
    'INSERT,DELETE,TRUNCATE,REFERENCES,TRIGGER'
  )
  and has_table_privilege('vouch_guest', 'vouch.guest_sessions', 'SELECT')
  and has_column_privilege(
    'vouch_guest', 'vouch.guest_sessions', 'revoked_at', 'UPDATE'
  )
  and not has_table_privilege(
    'vouch_guest', 'vouch.guest_sessions',
    'INSERT,DELETE,TRUNCATE,REFERENCES,TRIGGER'
  )
  and not has_table_privilege(
    'vouch_guest', 'vouch.guest_exchange_attempts',
    'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER'
  )
  and has_column_privilege(
    'vouch_guest', 'vouch.guest_commands', 'id', 'UPDATE'
  )
  and not has_table_privilege(
    'vouch_guest', 'vouch.guest_commands',
    'DELETE,TRUNCATE,REFERENCES,TRIGGER'
  )
  and not has_table_privilege(
    'vouch_guest', 'vouch.creator_feedback',
    'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER'
  )
  and has_table_privilege('vouch_guest', 'vouch.tombstones', 'SELECT')
  and not has_table_privilege(
    'vouch_guest', 'vouch.tombstones',
    'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER'
  ),
  'guest role has only the exact RLS-scoped persistence and row-lock privileges needed for mutation'
);
select ok(
  (select bool_and(not has_table_privilege(
      data_api_role, relation_name,
      'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER'
    ))
   from (values ('anon'), ('authenticated')) roles(data_api_role)
   cross join (values
     ('vouch.guest_grants'),
     ('vouch.guest_sessions'),
     ('vouch.guest_exchange_attempts')
   ) relations(relation_name)),
  'Data API roles have no direct access to guest persistence'
);
select ok(
  has_function_privilege(
    'vouch_guest',
    'vouch_private.exchange_guest_invitation(text,text,uuid,text)', 'EXECUTE'
  )
  and has_function_privilege(
    'vouch_guest', 'vouch_private.resolve_guest_session(text)', 'EXECUTE'
  )
  and has_function_privilege(
    'vouch_guest', 'vouch_private.guest_submission_context()', 'EXECUTE'
  )
  and has_function_privilege(
    'vouch_guest', 'vouch_private.lock_guest_source(uuid)', 'EXECUTE'
  )
  and not has_function_privilege(
    'vouch_guest',
    'vouch_private.guest_grant_issuer_active(uuid,boolean,timestamp with time zone)',
    'EXECUTE'
  )
  and not has_function_privilege(
    'vouch_guest', 'vouch_private.prune_guest_exchange_attempts()', 'EXECUTE'
  )
  and has_function_privilege(
    'vouch_retention', 'vouch_private.prune_guest_exchange_attempts()', 'EXECUTE'
  ),
  'guest capabilities and retention pruning are granted only to their exact runtimes'
);
select ok(
  (select bool_and(
     not has_function_privilege(
       data_api_role,
       'vouch_private.exchange_guest_invitation(text,text,uuid,text)', 'EXECUTE'
     )
     and not has_function_privilege(
       data_api_role, 'vouch_private.resolve_guest_session(text)', 'EXECUTE'
     )
     and not has_function_privilege(
       data_api_role, 'vouch_private.guest_submission_context()', 'EXECUTE'
     )
   ) from (values ('anon'), ('authenticated')) roles(data_api_role)),
  'Data API roles cannot call guest capability functions'
);

set local role vouch_guest;
select is(
  (select count(*)::integer from vouch.guest_grants), 0,
  'guest role cannot enumerate grants before a session establishes scope'
);
select is(
  (select count(*)::integer
   from vouch_private.exchange_guest_invitation(
     repeat('1', 64), repeat('a', 64),
     pg_temp.vouch_guest_test_id('session'), repeat('3', 64)
   )),
  1, 'an active invitation exchanges exactly once'
);
select is(
  (select count(*)::integer
   from vouch_private.exchange_guest_invitation(
     repeat('1', 64), repeat('a', 64),
     pg_temp.vouch_guest_test_id('replay-session'), repeat('4', 64)
   )),
  0, 'the consumed invitation cannot be replayed'
);
select is(
  (select count(*)::integer
   from vouch_private.resolve_guest_session(repeat('3', 64))),
  1, 'the issued session resolves while its issuer remains authorized'
);
select is(
  (select vouch_private.guest_grant_id()),
  pg_temp.vouch_guest_test_id('grant'),
  'session resolution establishes the exact guest grant scope'
);
select is(
  (select vouch_private.guest_session_id()),
  pg_temp.vouch_guest_test_id('session'),
  'session resolution establishes the exact guest session scope'
);
select is(
  (select vouch_private.guest_submission_context() -> 'campaign'),
  jsonb_build_object(
    'name', 'Synthetic campaign', 'market', 'IN', 'brand_name', 'Synthetic brand'
  ),
  'guest context exposes only the allowlisted campaign summary'
);
select is(
  (select vouch_private.guest_submission_context() -> 'creator'),
  jsonb_build_object('name', 'Synthetic creator', 'handle', '@synthetic'),
  'guest context exposes only the allowlisted creator summary'
);
select ok(
  (select (context ? 'session_expires_at')
    and context -> 'allowed_actions' = '["read_submission"]'::jsonb
    and context -> 'feedback' = '[]'::jsonb
    and context #> '{submission,current_version}' = 'null'::jsonb
    and context #>> '{submission,review_state}' = 'awaiting_brand_review'
    and (select array_agg(key order by key) from jsonb_object_keys(context) keys(key))
      = array[
        'allowed_actions', 'campaign', 'creator', 'feedback',
        'session_expires_at', 'submission'
      ]
    and (select array_agg(key order by key)
         from jsonb_object_keys(context -> 'submission') keys(key))
      = array['approved_version_no', 'current_version', 'review_state']
    and not (context ?| array[
      'id', 'organization_id', 'campaign_id', 'creator_id', 'submission_id',
      'invitation_secret_hash', 'session_secret_hash'
    ])
   from (select vouch_private.guest_submission_context() as context) scoped),
  'guest context is an allowlisted read-only DTO without identifiers or secret digests'
);

reset role;
insert into vouch.media_assets (
  id, organization_id, campaign_id, uploader_user_id, filename,
  proposed_content_type, expected_bytes, status, upload_token_hash,
  finalize_token_hash, rights_attested, retention_deadline, created_at,
  storage_backend
) values (
  pg_temp.vouch_guest_test_id('foreign-asset'),
  pg_temp.vouch_guest_test_id('organization'),
  pg_temp.vouch_guest_test_id('campaign'),
  pg_temp.vouch_guest_test_id('issuer'),
  'foreign.mp4', 'video/mp4', 32, 'validated', repeat('6', 64), repeat('7', 64),
  true, now() + interval '1 day', now(), 'database'
);
insert into vouch.submissions (id, organization_id, campaign_id, creator_id, created_at)
values (
  pg_temp.vouch_guest_test_id('foreign-submission'),
  pg_temp.vouch_guest_test_id('organization'),
  pg_temp.vouch_guest_test_id('campaign'),
  pg_temp.vouch_guest_test_id('creator'), now()
);
insert into vouch.submission_versions (
  id, organization_id, submission_id, version_no, asset_id, media_hash, caption,
  caption_hash, uploader_user_id, rights_attested, created_at
) values (
  pg_temp.vouch_guest_test_id('foreign-version'),
  pg_temp.vouch_guest_test_id('organization'),
  pg_temp.vouch_guest_test_id('foreign-submission'), 1,
  pg_temp.vouch_guest_test_id('foreign-asset'), repeat('8', 64),
  'Must never cross the guest boundary', repeat('9', 64),
  pg_temp.vouch_guest_test_id('issuer'), true, now()
);
update vouch.submissions
set current_version_id = pg_temp.vouch_guest_test_id('foreign-version')
where id = pg_temp.vouch_guest_test_id('submission');
set local role vouch_guest;
select is(
  (select vouch_private.guest_submission_context()),
  null::jsonb,
  'guest context fails closed when current_version_id crosses submission lineage'
);
reset role;
update vouch.submissions set current_version_id = null
where id = pg_temp.vouch_guest_test_id('submission');
insert into vouch.media_assets (
  id, organization_id, campaign_id, uploader_user_id, filename,
  proposed_content_type, validated_content_type, expected_bytes, actual_bytes,
  sha256, duration_ms, status, upload_token_hash, finalize_token_hash,
  rights_attested, retention_deadline, created_at, storage_backend
) values (
  pg_temp.vouch_guest_test_id('feedback-asset'),
  pg_temp.vouch_guest_test_id('organization'),
  pg_temp.vouch_guest_test_id('campaign'),
  pg_temp.vouch_guest_test_id('issuer'),
  'feedback.mp4', 'video/mp4', 'video/mp4', 32, 32, repeat('a',64), 10000,
  'validated', repeat('b',64), repeat('c',64), true,
  now() + interval '1 day', now(), 'database'
);
insert into vouch.consent_receipts (
  id, organization_id, asset_id, campaign_id, actor_user_id, purpose,
  notice_version, notice_hash, accepted_at
) values (
  pg_temp.vouch_guest_test_id('feedback-consent'),
  pg_temp.vouch_guest_test_id('organization'),
  pg_temp.vouch_guest_test_id('feedback-asset'),
  pg_temp.vouch_guest_test_id('campaign'),
  pg_temp.vouch_guest_test_id('issuer'), 'campaign_check',
  'feedback-policy-notice-v1', repeat('7',64), now()
);
insert into vouch.submission_versions (
  id, organization_id, submission_id, version_no, asset_id, media_hash, caption,
  caption_hash, uploader_user_id, rights_attested, created_at
) values
  (
    pg_temp.vouch_guest_test_id('feedback-version-1'),
    pg_temp.vouch_guest_test_id('organization'),
    pg_temp.vouch_guest_test_id('submission'), 1,
    pg_temp.vouch_guest_test_id('feedback-asset'), repeat('a',64),
    'Earlier creator draft', repeat('d',64),
    pg_temp.vouch_guest_test_id('issuer'), true, now() - interval '1 minute'
  ),
  (
    pg_temp.vouch_guest_test_id('feedback-version-2'),
    pg_temp.vouch_guest_test_id('organization'),
    pg_temp.vouch_guest_test_id('submission'), 2,
    pg_temp.vouch_guest_test_id('feedback-asset'), repeat('a',64),
    'Current creator draft', repeat('e',64),
    pg_temp.vouch_guest_test_id('issuer'), true, now()
  );
update vouch.submissions
set current_version_id = pg_temp.vouch_guest_test_id('feedback-version-1')
where id = pg_temp.vouch_guest_test_id('submission');
insert into vouch.analyses (
  id, organization_id, submission_version_id, analysis_status,
  machine_assessment, manifest_hash, invocation_mode, scenario,
  required_coverage, observed_coverage, missing_intervals, model_versions,
  prompt_version, schema_version, created_at, completed_at
) values (
  pg_temp.vouch_guest_test_id('feedback-analysis'),
  pg_temp.vouch_guest_test_id('organization'),
  pg_temp.vouch_guest_test_id('feedback-version-1'),
  'completed', 'fixes_suggested', repeat('f',64), 'fixture', 'clean',
  '["speech","visual"]', '["speech","visual"]', '[]', '{}',
  'fixture-v1', '1', now(), now()
);
insert into vouch.fix_request_drafts
  (id, organization_id, analysis_id, text, created_by, created_at)
values (
  pg_temp.vouch_guest_test_id('feedback-draft'),
  pg_temp.vouch_guest_test_id('organization'),
  pg_temp.vouch_guest_test_id('feedback-analysis'),
  'Internal rationale must never reach the creator DTO.',
  pg_temp.vouch_guest_test_id('issuer'), now()
);
insert into vouch.review_contexts (
  id, organization_id, analysis_id, submission_id, submission_version_id,
  review_status, revision, manifest_hash
) values (
  pg_temp.vouch_guest_test_id('feedback-review'),
  pg_temp.vouch_guest_test_id('organization'),
  pg_temp.vouch_guest_test_id('feedback-analysis'),
  pg_temp.vouch_guest_test_id('submission'),
  pg_temp.vouch_guest_test_id('feedback-version-1'),
  'unreviewed', 1, repeat('f',64)
);
insert into vouch.creator_feedback (
  id, organization_id, submission_id, submission_version_id, analysis_id,
  fix_request_draft_id, message, start_ms, end_ms, invocation_mode,
  analysis_status, manifest_hash, published_by_user_id, idempotency_key,
  request_digest, published_at
) values (
  pg_temp.vouch_guest_test_id('feedback'),
  pg_temp.vouch_guest_test_id('organization'),
  pg_temp.vouch_guest_test_id('submission'),
  pg_temp.vouch_guest_test_id('feedback-version-1'),
  pg_temp.vouch_guest_test_id('feedback-analysis'),
  pg_temp.vouch_guest_test_id('feedback-draft'),
  'Please remove the unsupported result claim.', 1200, 3400, 'fixture',
  'completed', repeat('f',64), pg_temp.vouch_guest_test_id('issuer'),
  'creator-feedback-key', repeat('1',64), now()
);
update vouch.submissions
set current_version_id = pg_temp.vouch_guest_test_id('feedback-version-2')
where id = pg_temp.vouch_guest_test_id('submission');
set local role vouch_guest;
select ok(
  (select jsonb_array_length(context -> 'feedback') = 1
    and context #>> '{feedback,0,version_no}' = '1'
    and context #>> '{feedback,0,message}' = 'Please remove the unsupported result claim.'
    and context #>> '{feedback,0,start_ms}' = '1200'
    and context #>> '{feedback,0,end_ms}' = '3400'
    and context #>> '{feedback,0,invocation_mode}' = 'fixture'
    and context #>> '{feedback,0,analysis_status}' = 'completed'
    and context #>> '{feedback,0,manifest_hash}' = repeat('f',64)
    and (context #>> '{feedback,0,historical}')::boolean
    and (context #> '{feedback,0}') ? 'published_at'
    and (select array_agg(key order by key)
      from jsonb_object_keys(context #> '{feedback,0}') keys(key)) = array[
        'analysis_status', 'end_ms', 'historical', 'invocation_mode',
        'manifest_hash', 'message', 'published_at', 'start_ms', 'version_no'
      ]
    and context::text not like '%Internal rationale%'
   from (select vouch_private.guest_submission_context() as context) scoped),
  'guest context exposes only the published snapshot and truthful historical provenance'
);
reset role;
update vouch.creator_feedback set message = '', start_ms = null, end_ms = null
where id = pg_temp.vouch_guest_test_id('feedback');
set local role vouch_guest;
select is(
  (select vouch_private.guest_submission_context() -> 'feedback'),
  '[]'::jsonb,
  'scrubbed feedback is omitted while a newer active version remains visible'
);

-- Ten earlier attempts from one privacy bucket block an otherwise valid invitation.
select is(
  (select count(*)::integer
   from generate_series(1, 10) attempt_no
   cross join lateral vouch_private.exchange_guest_invitation(
     md5('invalid-token-' || attempt_no::text) || md5('invalid-token-tail-' || attempt_no::text),
     repeat('b', 64),
     md5('invalid-session-' || attempt_no::text)::uuid,
     md5('invalid-session-digest-' || attempt_no::text)
       || md5('invalid-session-tail-' || attempt_no::text)
   )),
  0, 'invalid invitation attempts disclose no matching grant'
);
select is(
  (select count(*)::integer
   from vouch_private.exchange_guest_invitation(
     repeat('2', 64), repeat('b', 64),
     pg_temp.vouch_guest_test_id('throttled-session'), repeat('5', 64)
   )),
  0, 'durable client throttling blocks a valid invitation after ten recent attempts'
);

reset role;
select is(
  (select count(*)::integer from vouch.guest_exchange_attempts
   where client_bucket_hash = repeat('b', 64)),
  10, 'a blocked client bucket cannot amplify exchange-attempt writes'
);
select is(
  (select consumed_at from vouch.guest_grants
   where id = pg_temp.vouch_guest_test_id('throttled-grant')),
  null::timestamptz, 'a throttled invitation remains unconsumed'
);

set local role vouch_guest;
select is(
  (select count(*)::integer
   from generate_series(1, 12) attempt_no
   cross join lateral vouch_private.exchange_guest_invitation(
     repeat('9', 64),
     md5('token-client-' || attempt_no::text)
       || md5('token-client-tail-' || attempt_no::text),
     md5('token-session-' || attempt_no::text)::uuid,
     md5('token-session-digest-' || attempt_no::text)
       || md5('token-session-tail-' || attempt_no::text)
   )),
  0, 'invalid repeated tokens disclose no matching grant'
);
reset role;
select is(
  (select count(*)::integer from vouch.guest_exchange_attempts
   where token_digest = repeat('9', 64)),
  5, 'a blocked token bucket cannot amplify exchange-attempt writes'
);

insert into vouch.guest_exchange_attempts(client_bucket_hash, token_digest, attempted_at)
values (repeat('e', 64), repeat('f', 64), clock_timestamp() - interval '24 hours 1 second');
set local role vouch_retention;
select is(
  (select vouch_private.prune_guest_exchange_attempts()),
  1, 'retention removes expired privacy buckets without another guest exchange'
);
reset role;
select is(
  (select count(*)::integer from vouch.guest_exchange_attempts
   where client_bucket_hash = repeat('e', 64)),
  0, 'expired privacy buckets are absent after retention pruning'
);

update vouch.memberships set active = false
where id = pg_temp.vouch_guest_test_id('membership');
set local role vouch_guest;
select is(
  (select count(*)::integer
   from vouch_private.resolve_guest_session(repeat('3', 64))),
  0, 'session resolution fails closed after issuer authority is removed'
);
select is(
  (select vouch_private.guest_submission_context()),
  null::jsonb, 'guest context fails closed after issuer authority is removed'
);

reset role;
update vouch.memberships set active = true
where id = pg_temp.vouch_guest_test_id('membership');
update vouch.guest_grants set revoked_at = now()
where id = pg_temp.vouch_guest_test_id('grant');
set local role vouch_guest;
select is(
  (select count(*)::integer
   from vouch_private.resolve_guest_session(repeat('3', 64))),
  0, 'session resolution fails closed after grant revocation'
);
select is(
  (select vouch_private.guest_submission_context()),
  null::jsonb, 'guest context fails closed after grant revocation'
);

reset role;
select * from finish();
rollback;
