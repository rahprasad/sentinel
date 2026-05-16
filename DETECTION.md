# Detection Tier — Person A

**Owner:** Person A
**Time budget:** 4 hours
**Your job:** keep the user safe persistently. Run the harness that's always watching email, the triage agent that classifies anything it finds, and the dashboard shell that shows the user they're protected.

---

## What you're building

Four committed deliverables + one stretch:

1. **The Harness** — persistent loop monitoring email in real-time (IMAP IDLE)
2. **Triage agent** — classifies messages, extracts IOCs, decides to escalate
3. **Dashboard shell** — landing view with hero stats, live incident feed, monitoring status panel
4. **Handoff to Person B** — set `status='investigating'` and their pipeline takes over
5. **🟡 STRETCH: Screenshot ingestion** — second surface for non-email scams (popups, SMS screenshots, social DMs). Only build if you're ahead of plan at hour 3:00.

The harness is what makes this an always-on shield. Email is the committed surface; screenshot is the stretch.

---

## The product positioning (for your pitch)

Two surfaces, one shield:
- **Email** is persistent and automatic — we're always watching your inbox
- **Screenshot** (if built) is universal — drag in anything you're suspicious about: a Tinder profile, a popup, an SMS, a Discord DM

If screenshot doesn't get built, the slide says "Coming soon: universal screenshot capture + browser extension." Judges accept this framing.

---

## What "persistent harness" means in 4 hours

A polling/watcher worker that monitors ONE real source on an interval, with architecture designed to plug in more sources later.

**The real source: IMAP IDLE on a Gmail account.**
- Create demo Gmail, generate app password (Google Account → Security → 2FA → App passwords)
- `aioimaplib` + IDLE gives push-style notifications when new mail arrives
- ~30 min to wire up, real-time, demos as "we're watching your inbox"
- During demo: send email to demo account from your phone, it lands in the harness in seconds

**Fallback if IMAP doesn't work by minute 30:** poll a public scam feed (r/Scams, PhishTank) every 30s. Same harness architecture, different watcher. Still demos as "always-on monitoring," weaker narrative.

---

## The harness architecture

```
┌────────────────────────────────────────────┐
│  Harness (always running)                  │
│  ┌─────────┐  ┌─────────┐  ┌────────────┐  │
│  │  IMAP   │  │ Webhook │  │ Screenshot │  │
│  │ Watcher │  │ Receiver│  │  Watcher   │  │
│  │         │  │ (curl)  │  │  (STRETCH) │  │
│  └────┬────┘  └────┬────┘  └─────┬──────┘  │
│       └─────────┬──┴─────────────┘         │
│                 ▼                          │
│         normalize_envelope()               │
└─────────────────┬──────────────────────────┘
                  ▼
         ┌─────────────────┐
         │  incidents DB   │  status='triaging'
         └────────┬────────┘
                  ▼
         ┌─────────────────┐
         │  Triage Worker  │
         └────────┬────────┘
                  ▼
            scam? ──► status='investigating' (Person B picks up)
            safe? ──► status='safe'
```

The watchers feed a normalizer that produces a uniform envelope shape regardless of source. The triage worker is source-agnostic. This is why adding screenshot later is genuinely small — it's just a new watcher feeding the same pipeline.

**Concretely:** the harness is a long-running Python process using `asyncio` to run watchers concurrently. Deploy as a separate Zeabur service. No HTTP surface on the harness itself — it just runs.

---

## The handoff contract (lock with Person B in minute 0)

```sql
incidents (
  id uuid pk,
  received_at timestamptz,
  source text,                  -- 'email_imap' | 'email_webhook' | 'screenshot'
  sender text,                  -- email sender, or "Screenshot upload" for stretch
  subject text,                 -- email subject, or inferred context for screenshots
  body text,                    -- email body, or VLM-extracted text for screenshots

  -- YOU write:
  iocs jsonb,                   -- {urls: [], phones: [], wallets: [], handles: []}
  triage jsonb,                 -- {is_scam, confidence, scam_type, tells, reasoning}
  status text,                  -- 'triaging' | 'investigating' | 'done' | 'safe'

  -- PERSON B writes:
  investigation jsonb,
  screenshots text[],
  estimated_loss_usd int
)

harness_status (
  source text pk,
  last_check timestamptz,
  state text,                   -- 'active' | 'error' | 'paused'
  items_scanned_total int,
  error_message text
)
```

`harness_status` powers the live "monitoring active" UI. Each watcher heartbeats every 10s.

Card contract Person B writes (paste in shared doc, both agree minute 0):

```json
{
  "scam_type": "Fake USPS redelivery",
  "what_they_sent": {
    "raw": "...",
    "tells": [{"span": "usps-redelivery.co", "why": "domain registered 3 days ago"}]
  },
  "what_they_wanted": "Your credit card and SSN.",
  "how_we_caught_it": [
    {"agent": "triage", "finding": "Sender domain doesn't match usps.com"},
    {"agent": "domain-intel", "finding": "Domain registered 3 days ago"},
    {"agent": "sandbox-walker", "finding": "Site asked for SSN — real USPS never does"}
  ],
  "how_to_spot_it": ["USPS doesn't text about redelivery fees", "..."],
  "evidence": {"domain_age_days": 3, "final_url": "...", "harvested_fields": ["card", "ssn"]}
}
```

---

## Hour-by-hour plan

### Hour 0:00–0:30 — Setup + contract lock

1. **15 min with Person B.** Lock schema, card contract, deploy topology (3 Zeabur services: harness, api+frontend, sandbox container; 1 Postgres).
2. Stand up Postgres. Create tables. Empty Next.js + FastAPI repo, push to GitHub, Zeabur auto-deploys.
3. **Create demo Gmail account RIGHT NOW** — Google sometimes delays app password generation on new accounts, you don't want to discover that at minute 35.
4. Write 4 seed incidents (Person B writes 4 more). Mix types: phishing, romance, delivery, crypto.

### Hour 0:30–1:30 — The Harness

Long-running Python service, async, no HTTP surface (except a tiny webhook for demo).

```python
async def main():
    await asyncio.gather(
        imap_watcher(),         # the real one
        webhook_receiver(),     # curl trigger for demo backup
        triage_worker(),        # processes status='triaging' rows
        heartbeat_loop(),       # updates harness_status every 10s
    )
```

**`imap_watcher()`:**
- Connect via `aioimaplib`, app password auth
- Enter IDLE on INBOX
- On new message: fetch, parse with `email` stdlib, extract sender/subject/body and URLs
- Insert into `incidents` with `status='triaging'`
- Bump `harness_status` for `email_imap`

**`webhook_receiver()`:** small FastAPI, `POST /ingest` for curl. Same normalization.

**`triage_worker()`:** loops every 1s, picks oldest `status='triaging'` row, runs triage, updates row. Same process, no Celery.

**`heartbeat_loop()`:** every 10s, update `harness_status.last_check = now()` for each watcher.

**IOC extraction:** regex for URLs, phone numbers, `0x[a-fA-F0-9]{40}` (ETH), `bc1[a-z0-9]+` (BTC), `@[a-z0-9_]+` (handles). Write to `incidents.iocs`.

### Hour 1:30–2:15 — Triage agent

AgentField-decorated function called by `triage_worker()`.

**Two fast pre-LLM checks:**

1. **IOC cache check.** `seen_iocs(ioc, scam_type, first_seen)` table. Before LLM call, check if any IOC from incoming message matches. If yes: scam, confidence=0.99, copy scam_type from cache. Resolves repeats in ~50ms and powers "we've seen this operation" credibility. Person B's investigation writes discovered IOCs back to this table — that's how the system gets smarter over time.

2. **Brand-domain mismatch heuristic.** Hardcode top 20 brands → real domains (`usps`→`usps.com`, `chase`→`chase.com`, etc.). If body mentions a brand but no link/sender domain matches, append a tell.

**LLM call via TokenRouter** with a cheap fast model (Qwen-flash or GLM-flash):

```
You are a scam triage classifier. Output JSON only:
{
  "is_scam": bool,
  "confidence": 0.0-1.0,
  "scam_type": "phishing"|"romance"|"delivery"|"refund"|"crypto"|"support"|"other"|"none",
  "tells": [{"span": "exact text from message", "why": "one sentence"}],
  "reasoning": "one sentence"
}

Rules:
- "tells" highlight 2-4 specific spans a human could learn to spot.
- If under 0.6 confidence, set is_scam=false.

Message:
From: {sender}
Subject: {subject}
Body: {body}
URLs: {urls}
```

Write `triage` jsonb. Set `status='investigating'` if scam else `'safe'`. Person B's pipeline takes over.

### Hour 2:15–3:00 — Dashboard shell

Next.js, Tailwind, dark mode.

**Landing view:**
```
┌─────────────────────────────────────────┐
│  ScamShield                       ⚙ 👤  │
├─────────────────────────────────────────┤
│  🟢 Monitoring active                   │
│     Scanning inbox · last check 3s ago  │
│     247 messages scanned today          │
│                                         │
│     [+ Drop screenshot to scan]   🟡    │  ← stretch goal placeholder
├─────────────────────────────────────────┤
│   Blocked 47 scams this month           │
│   Saved you an estimated $12,400        │
├─────────────────────────────────────────┤
│  Recent activity                        │
│  🟢 [investigating...] Fake USPS  2s    │
│  🛡 Pig butchering attempt       4h    │
│  🛡 Fake Coinbase login          1d    │
├─────────────────────────────────────────┤
│  Trending this week                     │
│  ↑ 300%  Fake USPS texts               │
└─────────────────────────────────────────┘
```

The MonitoringStatus panel is non-negotiable — it's what makes the persistent harness visible. Pulls from `harness_status` every 3s.

The screenshot drop zone shows as disabled/"Coming soon" until you build the stretch — render it from minute 1 so when the stretch ships it just lights up.

Components:
- `<MonitoringStatus />` — green dot, source name, time since last check, items scanned. >60s old → yellow "reconnecting." >5min → red "error."
- `<HeroStats />` — blocked count + savings from `/stats`
- `<IncidentFeed />` — polls `/incidents` every 2s
- `<IncidentRow />` — icon, scam type, one-liner, status pill, time ago
- `<InvestigatingProgress />` — animated step indicator when `status='investigating'`. Cycle: "Checking domain reputation" → "Walking the link in a sandbox" → "Writing your report"
- `<TrendingStrip />` — hardcoded plausible data
- `<ScreenshotDropZone />` — disabled by default, enabled when stretch ships

Click a row → opens Person B's `<IncidentDrawer incidentId={id} />`.

**Frontend endpoints:**
```
GET /incidents       → newest first
GET /incidents/{id}  → single row
GET /stats           → { blocked_count, estimated_savings_usd, scanned_today }
GET /monitoring      → harness_status rows
POST /ingest/screenshot → STRETCH endpoint
```

### Hour 3:00 — DECISION POINT 🟡

Where are you?

**If polished and on-track:** build the screenshot stretch (see below). 45 min budget.

**If anything is shaky:** skip the stretch. Use the time to bulletproof the demo path. Run end-to-end 3 times. Fix the worst bug.

The stretch only happens if everything else is genuinely green. Don't let "almost done" pull you in.

### Hour 3:00–3:45 — STRETCH: Screenshot ingestion (if green)

This is small because the architecture was designed for it.

**Backend (~20 min):**
- `POST /ingest/screenshot` endpoint accepts multipart image upload
- Save image to Zeabur storage, get URL
- Call TokenRouter with Qwen-VL or GLM-V (vision model):
  ```
  Extract all visible text from this image. Identify the context (SMS, email, social DM, popup, website, dating profile). Output JSON:
  {
    "extracted_text": "all text in image",
    "context": "sms" | "email" | "dm" | "popup" | "website" | "profile" | "other",
    "platform_hint": "WhatsApp" | "Instagram" | "Tinder" | etc | null,
    "urls": [...]
  }
  ```
- Build envelope: `source='screenshot'`, `sender='Screenshot upload'`, `subject=context+platform`, `body=extracted_text`, `iocs.urls=urls`
- Insert with `status='triaging'`. Same triage pipeline runs.

**Frontend (~15 min):**
- Enable `<ScreenshotDropZone />`. Drag-drop or click to upload.
- POST to `/ingest/screenshot`, show "Analyzing screenshot..." loader.
- On response, the new incident appears in the feed via the normal polling.

**Demo addition (~10 min):**
- Pre-test with 2-3 screenshots: WhatsApp pig-butchering convo, fake Zoom security popup, sketchy Tinder profile.
- During demo: drop one in after the email demo lands. "Scams aren't just email — drop a screenshot of anything suspicious."

### Hour 3:45–4:00 — Demo prep

**The demo narrative:**

> "ScamShield is always watching your inbox. [point at monitoring panel: 🟢 active, 247 scanned today] Watch what happens when a scam arrives."

Send scam email from your phone to demo Gmail. Card appears live, transitions through investigating → done. Person B opens the drawer, walks the four sections.

If stretch shipped, second beat:

> "Email is the persistent surface. But scams come from everywhere — popups, texts, DMs. So we built a universal capture too."

Drop a pre-tested screenshot. Same pipeline, same card quality.

**Fallback ladder:**
- IMAP flakes → curl `/ingest` with prepared scam JSON. Frame as "manual trigger for demo."
- Live walker flakes → Person B's fixtures take over; you don't have to do anything.
- Whole thing breaks → backup tab pre-loaded with seeded "done" state. Walk through that.

---

## Tool quick-reference

- **AgentField:** triage agent decorator. 10-min cap on docs.
- **TokenRouter:** triage uses cheap fast model (Qwen-flash/GLM-flash). Stretch screenshot uses vision model (Qwen-VL/GLM-V).
- **Zeabur:** 3 services + Postgres.
- **`aioimaplib`:** async IMAP IDLE.
- **Evermind:** stretch — swap `seen_iocs` for Evermind storage if time at hour 3:00 instead of screenshot. Pick one stretch, not both.

---

## Hard cuts if you fall behind

- **Hour 1, IMAP not connecting:** swap to Reddit/PhishTank polling. Persistent monitoring story holds, weaker narrative.
- **Hour 2, triage flaky:** ship LLM-only, skip IOC cache and brand heuristic.
- **Hour 3, dashboard behind:** drop trending strip, drop screenshot zone entirely, drop animations. MonitoringStatus stays.
- **Hour 3:30, IMAP unreliable for demo:** disable IMAP watcher, mock the heartbeat to show green. Demo runs on curl. Honest framing in pitch.

The screenshot stretch is genuinely optional. If you skip it and email is rock-solid, the demo is still strong. If you build it half-broken, the demo is worse than not having it.

---

## What you DON'T own

- Sandbox walker, domain intel, synthesizer (Person B)
- Card detail drawer (Person B)
- Screenshot replay component for incident detail (Person B)

If you finish committed work at hour 3:00 and decide to skip the screenshot stretch, help Person B polish the drawer instead. Their tier is harder and the drawer is the demo's emotional peak.

---

## The persistence story (for your pitch)

When a judge asks "how is this different from Gmail's spam filter":

> "Gmail flags messages into a folder. We do three things Gmail can't: we walk the scam in a sandbox to figure out what they're actually trying to extract, we build a graph of scammer infrastructure so the next victim is caught instantly, and we show users HOW we caught it so they learn to spot the next one. Gmail protects your inbox. We make you scam-proof — and not just on email."

The persistent harness makes "always watching" true. The screenshot surface (if built) makes "not just on email" true. Without both, you can still tell the story with screenshot framed as next-up.
