-- =============================================================================
-- Sentinel initial schema
-- Mirrors the contract in docs/DETECTION.md (Person A) and docs/INVESTIGATION.md (Person B).
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ─── incidents ───────────────────────────────────────────────────────────────
-- One row per scanned message. Status transitions:
--   triaging → investigating → done
--   triaging → safe
CREATE TABLE IF NOT EXISTS incidents (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    received_at         timestamptz NOT NULL DEFAULT now(),
    source              text NOT NULL,           -- 'email_imap' | 'email_webhook' | 'screenshot'
    sender              text,
    subject             text,
    body                text,

    -- Person A writes
    iocs                jsonb NOT NULL DEFAULT '{}'::jsonb,
    triage              jsonb,
    status              text NOT NULL DEFAULT 'triaging',

    -- Person B writes
    investigation       jsonb,
    screenshots         text[] NOT NULL DEFAULT ARRAY[]::text[],
    estimated_loss_usd  int,

    CONSTRAINT incidents_status_check
        CHECK (status IN ('triaging', 'investigating', 'done', 'safe'))
);

CREATE INDEX IF NOT EXISTS incidents_status_received_idx
    ON incidents (status, received_at DESC);

CREATE INDEX IF NOT EXISTS incidents_received_idx
    ON incidents (received_at DESC);

-- ─── harness_status ──────────────────────────────────────────────────────────
-- Heartbeat table powering the "monitoring active" UI.
CREATE TABLE IF NOT EXISTS harness_status (
    source              text PRIMARY KEY,        -- e.g. 'email_imap', 'webhook', 'screenshot'
    last_check          timestamptz NOT NULL DEFAULT now(),
    state               text NOT NULL DEFAULT 'active',
    items_scanned_total int NOT NULL DEFAULT 0,
    error_message       text,

    CONSTRAINT harness_status_state_check
        CHECK (state IN ('active', 'error', 'paused'))
);

-- ─── seen_iocs ───────────────────────────────────────────────────────────────
-- Cache populated by Person B's investigation. Speeds up triage on repeats.
CREATE TABLE IF NOT EXISTS seen_iocs (
    ioc          text NOT NULL,
    ioc_type     text NOT NULL,                  -- 'url' | 'domain' | 'wallet' | 'handle' | 'phone'
    scam_type    text,
    first_seen   timestamptz NOT NULL DEFAULT now(),
    last_seen    timestamptz NOT NULL DEFAULT now(),
    hit_count    int NOT NULL DEFAULT 1,
    PRIMARY KEY (ioc, ioc_type)
);

CREATE INDEX IF NOT EXISTS seen_iocs_type_idx ON seen_iocs (ioc_type);
