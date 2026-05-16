-- =============================================================================
-- Seed harness_status rows so the dashboard shows monitoring sources on first
-- load.  Starts as 'paused' — the harness heartbeat will flip them to 'active'
-- once it connects.
-- =============================================================================

INSERT INTO harness_status (source, last_check, state, items_scanned_total, error_message)
VALUES
    ('email_imap',  now() - interval '1 minute', 'paused', 0, NULL),
    ('email_webhook', now() - interval '1 minute', 'paused', 0, NULL)
ON CONFLICT (source) DO NOTHING;
