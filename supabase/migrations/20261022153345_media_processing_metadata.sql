-- Measured metadata is provenance only; no normalized derivative bytes are retained.
alter table vouch.media_assets add column processing_metadata json not null default '{}';
grant update(processing_metadata) on vouch.media_assets to vouch_api;
-- Retention can still scrub content but cannot replace measured provenance.
