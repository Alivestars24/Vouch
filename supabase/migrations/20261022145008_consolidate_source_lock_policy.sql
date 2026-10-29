-- api_source_lock already covers the narrower member predicate. The independent
-- guard_api_submission_update trigger retains marketer/admin-only content changes.
drop policy api_update on vouch.submissions;
