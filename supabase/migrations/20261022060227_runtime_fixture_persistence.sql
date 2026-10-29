-- Generated from vouch_backend.models; update through an additive migration.

create schema if not exists vouch;

revoke all on schema vouch from public, anon, authenticated;

alter default privileges in schema vouch revoke all on tables from anon, authenticated;


CREATE TABLE vouch.organizations (
	id UUID NOT NULL,
	slug VARCHAR(80) NOT NULL,
	name VARCHAR(160) NOT NULL,
	budget_cap_minor INTEGER NOT NULL,
	budget_held_minor INTEGER NOT NULL,
	budget_settled_minor INTEGER NOT NULL,
	budget_currency VARCHAR(3) NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (slug)
)

;

alter table vouch."organizations" enable row level security;


CREATE TABLE vouch.users (
	id UUID NOT NULL,
	email VARCHAR(320) NOT NULL,
	display_name VARCHAR(160) NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (email)
)

;

alter table vouch."users" enable row level security;


CREATE TABLE vouch.audit_events (
	id UUID NOT NULL,
	organization_id UUID NOT NULL,
	actor_user_id UUID,
	actor_kind VARCHAR(24) NOT NULL,
	action VARCHAR(100) NOT NULL,
	resource_type VARCHAR(50) NOT NULL,
	resource_id UUID NOT NULL,
	safe_metadata JSON NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(organization_id) REFERENCES vouch.organizations (id),
	UNIQUE (organization_id, id)
)

;

alter table vouch."audit_events" enable row level security;

CREATE INDEX ix_vouch_audit_events_organization_id ON vouch.audit_events (organization_id);


CREATE TABLE vouch.brands (
	id UUID NOT NULL,
	organization_id UUID NOT NULL,
	name VARCHAR(160) NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(organization_id) REFERENCES vouch.organizations (id) ON DELETE CASCADE,
	UNIQUE (organization_id, id)
)

;

alter table vouch."brands" enable row level security;

CREATE INDEX ix_vouch_brands_organization_id ON vouch.brands (organization_id);


CREATE TABLE vouch.creators (
	id UUID NOT NULL,
	organization_id UUID NOT NULL,
	name VARCHAR(160) NOT NULL,
	handle VARCHAR(160) NOT NULL,
	rights_status VARCHAR(40) NOT NULL,
	evidence_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(organization_id) REFERENCES vouch.organizations (id) ON DELETE CASCADE,
	UNIQUE (organization_id, id)
)

;

alter table vouch."creators" enable row level security;

CREATE INDEX ix_vouch_creators_organization_id ON vouch.creators (organization_id);


CREATE TABLE vouch.deletion_requests (
	id UUID NOT NULL,
	organization_id UUID NOT NULL,
	resource_type VARCHAR(50) NOT NULL,
	resource_id UUID NOT NULL,
	status VARCHAR(24) NOT NULL,
	destinations JSON NOT NULL,
	requested_by UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	completed_at TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (id),
	FOREIGN KEY(organization_id) REFERENCES vouch.organizations (id),
	UNIQUE (organization_id, id),
	FOREIGN KEY(requested_by) REFERENCES vouch.users (id)
)

;

alter table vouch."deletion_requests" enable row level security;

CREATE INDEX ix_vouch_deletion_requests_organization_id ON vouch.deletion_requests (organization_id);


CREATE TABLE vouch.jobs (
	id UUID NOT NULL,
	organization_id UUID NOT NULL,
	kind VARCHAR(40) NOT NULL,
	resource_id UUID NOT NULL,
	logical_key VARCHAR(128) NOT NULL,
	status VARCHAR(32) NOT NULL,
	attempt_count INTEGER NOT NULL,
	max_attempts INTEGER NOT NULL,
	retry_after TIMESTAMP WITH TIME ZONE,
	lease_owner VARCHAR(100),
	lease_until TIMESTAMP WITH TIME ZONE,
	fence INTEGER NOT NULL,
	scenario VARCHAR(40) NOT NULL,
	last_error_code VARCHAR(64),
	last_error_message VARCHAR(300),
	result_id UUID,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(organization_id) REFERENCES vouch.organizations (id) ON DELETE CASCADE,
	UNIQUE (organization_id, logical_key),
	UNIQUE (organization_id, id)
)

;

alter table vouch."jobs" enable row level security;

CREATE INDEX ix_job_claim ON vouch.jobs (status, retry_after, lease_until);

CREATE INDEX ix_vouch_jobs_organization_id ON vouch.jobs (organization_id);

CREATE INDEX ix_vouch_jobs_resource_id ON vouch.jobs (resource_id);


CREATE TABLE vouch.memberships (
	id UUID NOT NULL,
	organization_id UUID NOT NULL,
	user_id UUID NOT NULL,
	active BOOLEAN NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (organization_id, user_id),
	FOREIGN KEY(user_id) REFERENCES vouch.users (id) ON DELETE CASCADE,
	FOREIGN KEY(organization_id) REFERENCES vouch.organizations (id) ON DELETE CASCADE,
	UNIQUE (organization_id, id)
)

;

alter table vouch."memberships" enable row level security;

CREATE INDEX ix_vouch_memberships_organization_id ON vouch.memberships (organization_id);

CREATE INDEX ix_vouch_memberships_user_id ON vouch.memberships (user_id);


CREATE TABLE vouch.rule_pack_versions (
	id UUID NOT NULL,
	organization_id UUID NOT NULL,
	name VARCHAR(160) NOT NULL,
	version VARCHAR(40) NOT NULL,
	status VARCHAR(40) NOT NULL,
	source_uri VARCHAR(500) NOT NULL,
	content_hash VARCHAR(64) NOT NULL,
	rules JSON NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(organization_id) REFERENCES vouch.organizations (id) ON DELETE CASCADE,
	UNIQUE (organization_id, id)
)

;

alter table vouch."rule_pack_versions" enable row level security;

CREATE INDEX ix_vouch_rule_pack_versions_organization_id ON vouch.rule_pack_versions (organization_id);


CREATE TABLE vouch.tombstones (
	id UUID NOT NULL,
	organization_id UUID NOT NULL,
	resource_type VARCHAR(50) NOT NULL,
	resource_id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (organization_id, resource_type, resource_id),
	FOREIGN KEY(organization_id) REFERENCES vouch.organizations (id),
	UNIQUE (organization_id, id)
)

;

alter table vouch."tombstones" enable row level security;

CREATE INDEX ix_vouch_tombstones_organization_id ON vouch.tombstones (organization_id);


CREATE TABLE vouch.budget_reservations (
	id UUID NOT NULL,
	organization_id UUID NOT NULL,
	job_id UUID NOT NULL,
	logical_key VARCHAR(128) NOT NULL,
	held_minor INTEGER NOT NULL,
	settled_minor INTEGER NOT NULL,
	currency VARCHAR(3) NOT NULL,
	status VARCHAR(24) NOT NULL,
	price_snapshot NUMERIC(10, 4) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	reconciled_at TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (id),
	UNIQUE (job_id),
	UNIQUE (organization_id, id),
	FOREIGN KEY(organization_id, job_id) REFERENCES vouch.jobs (organization_id, id),
	FOREIGN KEY(job_id) REFERENCES vouch.jobs (id),
	FOREIGN KEY(organization_id) REFERENCES vouch.organizations (id),
	UNIQUE (organization_id, logical_key)
)

;

alter table vouch."budget_reservations" enable row level security;

CREATE INDEX ix_vouch_budget_reservations_organization_id ON vouch.budget_reservations (organization_id);


CREATE TABLE vouch.idempotency_records (
	id UUID NOT NULL,
	organization_id UUID NOT NULL,
	actor_user_id UUID NOT NULL,
	operation VARCHAR(80) NOT NULL,
	key VARCHAR(160) NOT NULL,
	request_hash VARCHAR(64) NOT NULL,
	job_id UUID NOT NULL,
	resource_id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (organization_id, actor_user_id, operation, key),
	FOREIGN KEY(actor_user_id) REFERENCES vouch.users (id),
	FOREIGN KEY(job_id) REFERENCES vouch.jobs (id),
	UNIQUE (organization_id, id),
	FOREIGN KEY(organization_id) REFERENCES vouch.organizations (id),
	FOREIGN KEY(organization_id, job_id) REFERENCES vouch.jobs (organization_id, id)
)

;

alter table vouch."idempotency_records" enable row level security;

CREATE INDEX ix_vouch_idempotency_records_organization_id ON vouch.idempotency_records (organization_id);


CREATE TABLE vouch.membership_roles (
	id UUID NOT NULL,
	organization_id UUID NOT NULL,
	membership_id UUID NOT NULL,
	role VARCHAR(32) NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (membership_id, role),
	FOREIGN KEY(organization_id, membership_id) REFERENCES vouch.memberships (organization_id, id),
	FOREIGN KEY(membership_id) REFERENCES vouch.memberships (id) ON DELETE CASCADE,
	UNIQUE (organization_id, id),
	FOREIGN KEY(organization_id) REFERENCES vouch.organizations (id)
)

;

alter table vouch."membership_roles" enable row level security;

CREATE INDEX ix_vouch_membership_roles_membership_id ON vouch.membership_roles (membership_id);


CREATE TABLE vouch.products (
	id UUID NOT NULL,
	organization_id UUID NOT NULL,
	brand_id UUID NOT NULL,
	name VARCHAR(160) NOT NULL,
	category VARCHAR(80) NOT NULL,
	sku VARCHAR(80) NOT NULL,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(brand_id) REFERENCES vouch.brands (id),
	UNIQUE (organization_id, id),
	FOREIGN KEY(organization_id, brand_id) REFERENCES vouch.brands (organization_id, id),
	FOREIGN KEY(organization_id) REFERENCES vouch.organizations (id) ON DELETE CASCADE
)

;

alter table vouch."products" enable row level security;

CREATE INDEX ix_vouch_products_organization_id ON vouch.products (organization_id);


CREATE TABLE vouch.campaigns (
	id UUID NOT NULL,
	organization_id UUID NOT NULL,
	name VARCHAR(160) NOT NULL,
	objective TEXT NOT NULL,
	market VARCHAR(8) NOT NULL,
	product_id UUID NOT NULL,
	rule_pack_version_id UUID NOT NULL,
	created_by UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(created_by) REFERENCES vouch.users (id),
	FOREIGN KEY(organization_id, rule_pack_version_id) REFERENCES vouch.rule_pack_versions (organization_id, id),
	FOREIGN KEY(product_id) REFERENCES vouch.products (id),
	FOREIGN KEY(organization_id) REFERENCES vouch.organizations (id) ON DELETE CASCADE,
	FOREIGN KEY(organization_id, product_id) REFERENCES vouch.products (organization_id, id),
	UNIQUE (organization_id, id),
	FOREIGN KEY(rule_pack_version_id) REFERENCES vouch.rule_pack_versions (id)
)

;

alter table vouch."campaigns" enable row level security;

CREATE INDEX ix_campaign_org_created ON vouch.campaigns (organization_id, created_at);

CREATE INDEX ix_vouch_campaigns_organization_id ON vouch.campaigns (organization_id);


CREATE TABLE vouch.campaign_creators (
	id UUID NOT NULL,
	organization_id UUID NOT NULL,
	campaign_id UUID NOT NULL,
	creator_id UUID NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(organization_id, campaign_id) REFERENCES vouch.campaigns (organization_id, id),
	FOREIGN KEY(campaign_id) REFERENCES vouch.campaigns (id) ON DELETE CASCADE,
	FOREIGN KEY(organization_id) REFERENCES vouch.organizations (id) ON DELETE CASCADE,
	FOREIGN KEY(organization_id, creator_id) REFERENCES vouch.creators (organization_id, id),
	UNIQUE (campaign_id, creator_id),
	UNIQUE (organization_id, id),
	FOREIGN KEY(creator_id) REFERENCES vouch.creators (id)
)

;

alter table vouch."campaign_creators" enable row level security;

CREATE INDEX ix_vouch_campaign_creators_campaign_id ON vouch.campaign_creators (campaign_id);

CREATE INDEX ix_vouch_campaign_creators_organization_id ON vouch.campaign_creators (organization_id);


CREATE TABLE vouch.media_assets (
	id UUID NOT NULL,
	organization_id UUID NOT NULL,
	campaign_id UUID NOT NULL,
	uploader_user_id UUID NOT NULL,
	filename VARCHAR(255) NOT NULL,
	proposed_content_type VARCHAR(100) NOT NULL,
	validated_content_type VARCHAR(100),
	expected_bytes INTEGER NOT NULL,
	actual_bytes INTEGER,
	sha256 VARCHAR(64),
	duration_ms INTEGER,
	status VARCHAR(32) NOT NULL,
	upload_token_hash VARCHAR(64) NOT NULL,
	finalize_token_hash VARCHAR(64) NOT NULL,
	object_bytes BYTEA,
	rights_attested BOOLEAN NOT NULL,
	retention_deadline TIMESTAMP WITH TIME ZONE NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (id),
	FOREIGN KEY(organization_id, campaign_id) REFERENCES vouch.campaigns (organization_id, id),
	UNIQUE (organization_id, id),
	FOREIGN KEY(uploader_user_id) REFERENCES vouch.users (id),
	FOREIGN KEY(organization_id) REFERENCES vouch.organizations (id) ON DELETE CASCADE,
	FOREIGN KEY(campaign_id) REFERENCES vouch.campaigns (id)
)

;

alter table vouch."media_assets" enable row level security;

CREATE INDEX ix_vouch_media_assets_campaign_id ON vouch.media_assets (campaign_id);

CREATE INDEX ix_vouch_media_assets_organization_id ON vouch.media_assets (organization_id);


CREATE TABLE vouch.submissions (
	id UUID NOT NULL,
	organization_id UUID NOT NULL,
	campaign_id UUID NOT NULL,
	creator_id UUID NOT NULL,
	current_version_id UUID,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (id),
	FOREIGN KEY(creator_id) REFERENCES vouch.creators (id),
	FOREIGN KEY(organization_id, campaign_id) REFERENCES vouch.campaigns (organization_id, id),
	UNIQUE (organization_id, id),
	FOREIGN KEY(organization_id) REFERENCES vouch.organizations (id) ON DELETE CASCADE,
	FOREIGN KEY(campaign_id) REFERENCES vouch.campaigns (id),
	FOREIGN KEY(organization_id, creator_id) REFERENCES vouch.creators (organization_id, id)
)

;

alter table vouch."submissions" enable row level security;

CREATE INDEX ix_vouch_submissions_campaign_id ON vouch.submissions (campaign_id);

CREATE INDEX ix_vouch_submissions_organization_id ON vouch.submissions (organization_id);


CREATE TABLE vouch.submission_versions (
	id UUID NOT NULL,
	organization_id UUID NOT NULL,
	submission_id UUID NOT NULL,
	version_no INTEGER NOT NULL,
	asset_id UUID NOT NULL,
	media_hash VARCHAR(64) NOT NULL,
	caption TEXT NOT NULL,
	caption_hash VARCHAR(64) NOT NULL,
	uploader_user_id UUID NOT NULL,
	rights_attested BOOLEAN NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(submission_id) REFERENCES vouch.submissions (id) ON DELETE CASCADE,
	FOREIGN KEY(organization_id, submission_id) REFERENCES vouch.submissions (organization_id, id),
	UNIQUE (submission_id, version_no),
	FOREIGN KEY(asset_id) REFERENCES vouch.media_assets (id),
	FOREIGN KEY(organization_id) REFERENCES vouch.organizations (id) ON DELETE CASCADE,
	FOREIGN KEY(organization_id, asset_id) REFERENCES vouch.media_assets (organization_id, id),
	UNIQUE (organization_id, id),
	FOREIGN KEY(uploader_user_id) REFERENCES vouch.users (id)
)

;

alter table vouch."submission_versions" enable row level security;

CREATE INDEX ix_vouch_submission_versions_organization_id ON vouch.submission_versions (organization_id);

CREATE INDEX ix_vouch_submission_versions_submission_id ON vouch.submission_versions (submission_id);


CREATE TABLE vouch.analyses (
	id UUID NOT NULL,
	organization_id UUID NOT NULL,
	submission_version_id UUID NOT NULL,
	job_id UUID,
	analysis_status VARCHAR(32) NOT NULL,
	machine_assessment VARCHAR(40) NOT NULL,
	manifest_hash VARCHAR(64) NOT NULL,
	invocation_mode VARCHAR(16) NOT NULL,
	scenario VARCHAR(40) NOT NULL,
	required_coverage JSON NOT NULL,
	observed_coverage JSON NOT NULL,
	missing_intervals JSON NOT NULL,
	model_versions JSON NOT NULL,
	prompt_version VARCHAR(40) NOT NULL,
	schema_version VARCHAR(40) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	completed_at TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (id),
	FOREIGN KEY(organization_id, submission_version_id) REFERENCES vouch.submission_versions (organization_id, id),
	FOREIGN KEY(submission_version_id) REFERENCES vouch.submission_versions (id),
	UNIQUE (job_id),
	UNIQUE (organization_id, id),
	FOREIGN KEY(organization_id) REFERENCES vouch.organizations (id) ON DELETE CASCADE
)

;

alter table vouch."analyses" enable row level security;

CREATE INDEX ix_vouch_analyses_organization_id ON vouch.analyses (organization_id);

CREATE INDEX ix_vouch_analyses_submission_version_id ON vouch.analyses (submission_version_id);


CREATE TABLE vouch.evidence_items (
	id UUID NOT NULL,
	organization_id UUID NOT NULL,
	analysis_id UUID NOT NULL,
	modality VARCHAR(32) NOT NULL,
	start_ms INTEGER,
	end_ms INTEGER,
	precision VARCHAR(32) NOT NULL,
	description TEXT NOT NULL,
	captured_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(organization_id) REFERENCES vouch.organizations (id) ON DELETE CASCADE,
	FOREIGN KEY(organization_id, analysis_id) REFERENCES vouch.analyses (organization_id, id),
	UNIQUE (organization_id, id),
	FOREIGN KEY(analysis_id) REFERENCES vouch.analyses (id) ON DELETE CASCADE
)

;

alter table vouch."evidence_items" enable row level security;

CREATE INDEX ix_vouch_evidence_items_analysis_id ON vouch.evidence_items (analysis_id);

CREATE INDEX ix_vouch_evidence_items_organization_id ON vouch.evidence_items (organization_id);


CREATE TABLE vouch.findings (
	id UUID NOT NULL,
	organization_id UUID NOT NULL,
	analysis_id UUID NOT NULL,
	rule_id VARCHAR(100) NOT NULL,
	rule_version VARCHAR(40) NOT NULL,
	severity VARCHAR(16) NOT NULL,
	evidence_ids JSON NOT NULL,
	start_ms INTEGER,
	end_ms INTEGER,
	evidence_text TEXT NOT NULL,
	uncertainty VARCHAR(80) NOT NULL,
	suggested_action TEXT NOT NULL,
	fingerprint VARCHAR(64) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(organization_id) REFERENCES vouch.organizations (id) ON DELETE CASCADE,
	FOREIGN KEY(analysis_id) REFERENCES vouch.analyses (id) ON DELETE CASCADE,
	FOREIGN KEY(organization_id, analysis_id) REFERENCES vouch.analyses (organization_id, id),
	UNIQUE (organization_id, id)
)

;

alter table vouch."findings" enable row level security;

CREATE INDEX ix_vouch_findings_analysis_id ON vouch.findings (analysis_id);

CREATE INDEX ix_vouch_findings_fingerprint ON vouch.findings (fingerprint);

CREATE INDEX ix_vouch_findings_organization_id ON vouch.findings (organization_id);


CREATE TABLE vouch.fix_request_drafts (
	id UUID NOT NULL,
	organization_id UUID NOT NULL,
	analysis_id UUID NOT NULL,
	text TEXT NOT NULL,
	created_by UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(analysis_id) REFERENCES vouch.analyses (id),
	FOREIGN KEY(organization_id, analysis_id) REFERENCES vouch.analyses (organization_id, id),
	UNIQUE (organization_id, id),
	FOREIGN KEY(created_by) REFERENCES vouch.users (id),
	FOREIGN KEY(organization_id) REFERENCES vouch.organizations (id) ON DELETE CASCADE
)

;

alter table vouch."fix_request_drafts" enable row level security;

CREATE INDEX ix_vouch_fix_request_drafts_organization_id ON vouch.fix_request_drafts (organization_id);


CREATE TABLE vouch.review_contexts (
	id UUID NOT NULL,
	organization_id UUID NOT NULL,
	analysis_id UUID NOT NULL,
	submission_id UUID NOT NULL,
	submission_version_id UUID NOT NULL,
	review_status VARCHAR(32) NOT NULL,
	revision INTEGER NOT NULL,
	manifest_hash VARCHAR(64) NOT NULL,
	superseded_at TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (id),
	UNIQUE (analysis_id),
	FOREIGN KEY(submission_version_id) REFERENCES vouch.submission_versions (id),
	FOREIGN KEY(organization_id, submission_id) REFERENCES vouch.submissions (organization_id, id),
	FOREIGN KEY(analysis_id) REFERENCES vouch.analyses (id) ON DELETE CASCADE,
	UNIQUE (organization_id, id),
	FOREIGN KEY(organization_id, analysis_id) REFERENCES vouch.analyses (organization_id, id),
	FOREIGN KEY(organization_id, submission_version_id) REFERENCES vouch.submission_versions (organization_id, id),
	FOREIGN KEY(submission_id) REFERENCES vouch.submissions (id),
	FOREIGN KEY(organization_id) REFERENCES vouch.organizations (id) ON DELETE CASCADE
)

;

alter table vouch."review_contexts" enable row level security;

CREATE INDEX ix_vouch_review_contexts_organization_id ON vouch.review_contexts (organization_id);

CREATE INDEX ix_vouch_review_contexts_submission_id ON vouch.review_contexts (submission_id);


CREATE TABLE vouch.approvals (
	id UUID NOT NULL,
	organization_id UUID NOT NULL,
	review_context_id UUID NOT NULL,
	analysis_id UUID NOT NULL,
	submission_version_id UUID NOT NULL,
	manifest_hash VARCHAR(64) NOT NULL,
	review_revision INTEGER NOT NULL,
	media_hash VARCHAR(64) NOT NULL,
	caption_hash VARCHAR(64) NOT NULL,
	model_versions JSON NOT NULL,
	prompt_version VARCHAR(40) NOT NULL,
	actor_user_id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(organization_id, analysis_id) REFERENCES vouch.analyses (organization_id, id),
	FOREIGN KEY(submission_version_id) REFERENCES vouch.submission_versions (id),
	FOREIGN KEY(organization_id, submission_version_id) REFERENCES vouch.submission_versions (organization_id, id),
	FOREIGN KEY(review_context_id) REFERENCES vouch.review_contexts (id),
	UNIQUE (organization_id, id),
	FOREIGN KEY(organization_id, review_context_id) REFERENCES vouch.review_contexts (organization_id, id),
	FOREIGN KEY(actor_user_id) REFERENCES vouch.users (id),
	FOREIGN KEY(analysis_id) REFERENCES vouch.analyses (id),
	FOREIGN KEY(organization_id) REFERENCES vouch.organizations (id) ON DELETE CASCADE
)

;

alter table vouch."approvals" enable row level security;

CREATE INDEX ix_vouch_approvals_organization_id ON vouch.approvals (organization_id);


CREATE TABLE vouch.finding_decisions (
	id UUID NOT NULL,
	organization_id UUID NOT NULL,
	finding_id UUID NOT NULL,
	review_context_id UUID NOT NULL,
	decision VARCHAR(24) NOT NULL,
	rationale TEXT NOT NULL,
	actor_user_id UUID NOT NULL,
	review_revision INTEGER NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(review_context_id) REFERENCES vouch.review_contexts (id),
	FOREIGN KEY(organization_id) REFERENCES vouch.organizations (id) ON DELETE CASCADE,
	FOREIGN KEY(organization_id, review_context_id) REFERENCES vouch.review_contexts (organization_id, id),
	FOREIGN KEY(actor_user_id) REFERENCES vouch.users (id),
	FOREIGN KEY(finding_id) REFERENCES vouch.findings (id),
	UNIQUE (organization_id, id),
	FOREIGN KEY(organization_id, finding_id) REFERENCES vouch.findings (organization_id, id)
)

;

alter table vouch."finding_decisions" enable row level security;

CREATE INDEX ix_vouch_finding_decisions_finding_id ON vouch.finding_decisions (finding_id);

CREATE INDEX ix_vouch_finding_decisions_organization_id ON vouch.finding_decisions (organization_id);


CREATE TABLE vouch.review_events (
	id UUID NOT NULL,
	organization_id UUID NOT NULL,
	review_context_id UUID NOT NULL,
	action VARCHAR(32) NOT NULL,
	rationale TEXT NOT NULL,
	actor_user_id UUID NOT NULL,
	review_revision INTEGER NOT NULL,
	manifest_hash VARCHAR(64) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(review_context_id) REFERENCES vouch.review_contexts (id),
	FOREIGN KEY(actor_user_id) REFERENCES vouch.users (id),
	FOREIGN KEY(organization_id, review_context_id) REFERENCES vouch.review_contexts (organization_id, id),
	FOREIGN KEY(organization_id) REFERENCES vouch.organizations (id) ON DELETE CASCADE,
	UNIQUE (organization_id, id)
)

;

alter table vouch."review_events" enable row level security;

CREATE INDEX ix_vouch_review_events_organization_id ON vouch.review_events (organization_id);

revoke all on all tables in schema vouch from public, anon, authenticated;

-- The API/worker use server-only database credentials and explicit tenant scope.

-- This local fixture persistence path must not be deployed with header identity.
