# Investigation Tier — Person B

**Owner:** Person B
**Time budget:** 4 hours
**Your job:** when triage flags something, figure out what the scammer is actually trying to do. Walk the link, look up the domain, synthesize a forensic report. Own the UI that displays it.

---

## What you're building

Three committed deliverables:

1. **Sandbox Walker** — spins a browser in an isolated container, walks the scam link, captures what fields are harvested and where the funnel terminates
2. **Domain Intel + Synthesizer** — looks up domain reputation, writes the user-facing card combining all evidence
3. **Card detail drawer** — the four-section forensic breakdown UI with the sandbox replay viewer

Your input: `incidents` rows with `status='investigating'`. Your output: `investigation` jsonb + screenshots, `status='done'`.

---

## What's the same regardless of ingestion source

Person A is building email-as-the-committed-surface, with screenshot as a stretch goal. **For you, nothing changes.** Both sources land in the same `incidents` table with the same `iocs.urls`. If URLs exist, the walker runs. If not (e.g., a Tinder profile screenshot with no link), the walker is skipped and you run domain-intel + synthesizer on the extracted content alone.

So: build the same pipeline, just make the walker gracefully skip when `iocs.urls` is empty. Two lines of guard code.

---

## The handoff contract (lock with Person A in minute 0)

Person A's `DETECTION.md` has the full schema. Key points for you:

**You read:** rows with `status='investigating'`. Triage has already extracted IOCs. Your starting point is usually `iocs.urls[0]`, but handle the empty case.

**You write:**
- `investigation` jsonb — full card matching contract
- `screenshots` text[] — URLs to sandbox screenshots in storage
- `estimated_loss_usd` int — your guess at what the scammer wanted, drives the hero "saved you $X"
- `status = 'done'` when complete

`how_we_caught_it` combines findings from both tiers. Triage adds one entry, your domain-intel and sandbox-walker each add entries. Synthesizer assembles the final array.

---

## Hour-by-hour plan

### Hour 0:00–0:30 — Setup + contract lock

1. **15 min with Person A.** Lock schema and card contract. Non-negotiable.
2. Deploy topology: one Zeabur service for your investigation pipeline (Python), one separate Zeabur service for the sandbox container (Playwright + Chromium). Person A handles api+frontend. Three services, one Postgres.
3. Write 4 seed incidents (Person A writes the other 4). You take: romance, crypto-airdrop, pig-butchering, fake-support. These populate the dashboard at demo start.

### Hour 0:30–2:00 — Sandbox Walker (the demo)

Highest-risk piece. Start now even if other things aren't ready.

**The container:** separate Zeabur service, Dockerfile with `python:3.11 + playwright + chromium`. One endpoint:
```
POST /walk { "url": "..." }
→ {
    "steps": [
      {"screenshot_url": "...", "url": "...", "form_fields": ["name", "email", "card_number"], "page_text": "..."}
    ],
    "final_url": "...",
    "harvested_fields": ["card_number", "ssn", "address"],
    "funnel_terminus": "payment_processor" | "telegram" | "whatsapp" | "unknown"
  }
```

**The walker loop** (max 5 steps, 60s timeout):
1. Navigate via Playwright. Real-looking user agent, not headless-default.
2. Screenshot. Upload to Zeabur object storage or any S3-compatible bucket. Get URL.
3. Snapshot all `<input>` elements with `name`, `type`, `placeholder`. That's what they're harvesting.
4. Fill inputs with decoys by field name:
   - `email|mail` → `decoy@example.com`
   - `name|first|last` → `John Smith`
   - `card|cc|credit` → `4242424242424242` (valid Luhn, not real)
   - `cvv|cvc` → `123`
   - `ssn|social` → `000-00-0000`
   - `phone|tel` → `5555550100`
   - `address` → `123 Main St`
   - `zip|postal` → `90210`
   - else → `test`
5. Click most submit-looking button (text matches `/continue|submit|next|pay|verify/i`).
6. Capture redirect chain. Stop on: known payment processor domain, `t.me|wa.me|telegram|whatsapp`, or 5 steps.

**Actionbook integration:** use for selector resolution and action manuals on common templates. 30-min budget. If it doesn't click, fall back to the heuristic — it works on 80% of scam sites because they're built sloppily.

**Safety detail for the demo Q&A:** container has no creds mounted, no persistent volume, network egress only, killed after each run. When a judge asks "what if it's malware," you have a clean answer.

**Risk mitigation — do this at hour 1:30:** pick 3 candidate demo scams. Run the walker against each. Save output JSON as fixtures in `/fixtures/walks/`. At hour 3, if live walker is flaky, synthesizer reads from fixtures keyed by scam_type. Demo still works. **Judges will not know.**

### Hour 2:00–2:45 — Domain Intel + Synthesizer

Use AgentField coordination: walker + domain-intel run in parallel, synthesizer waits on both.

**Domain Intel agent** (fast, parallel with walker):
- Input: URL from `iocs.urls[0]`
- Bright Data WHOIS endpoint. Fallback: `python-whois` library — same data, no API key, 5 min to integrate.
- Output:
  ```json
  {
    "domain": "usps-redelivery.co",
    "age_days": 3,
    "registrar": "Namecheap",
    "ssl_age_days": 2,
    "flags": ["recently_registered", "no_business_email"]
  }
  ```
- Anything under 30 days is a major flag.

**Synthesizer agent:**
- Waits for walker + domain-intel (or just domain-intel if no URLs)
- TokenRouter with strong model (GLM-4.6 or Claude Sonnet)
- Output: the full card jsonb

**Synthesizer prompt** (`/prompts/synthesize.md`):
```
You write user-facing scam reports. Output JSON matching this exact schema:
[paste card contract from shared doc]

Rules:
- "how_we_caught_it" entries must reference SPECIFIC evidence. Bad: "suspicious domain." Good: "Domain registered 3 days ago via Namecheap."
- Each entry has "agent" field: "triage", "domain-intel", or "sandbox-walker".
- "what_they_wanted" is one sentence, plain English, names the actual extraction. "They wanted your credit card and SSN" not "credential harvesting attempt."
- "how_to_spot_it" is 2-3 rules a human could apply next time. Friendly, not condescending.
- "tells" should reuse triage spans plus any new ones the evidence now explains.

Estimated loss heuristic:
- delivery=$50, refund=$300, support=$800, crypto=$2000, romance=$5000
- If funnel terminated at payment page asking for card+SSN, 2x.

Evidence:
Original message: {body}
Triage findings: {triage_json}
Domain intel: {domain_intel_json}
Sandbox walk: {walker_json or "skipped — no URL in message"}
```

Write to `incidents.investigation`, copy screenshot URLs to `incidents.screenshots`, set `status='done'`.

**Important:** write discovered IOCs back to Person A's `seen_iocs` table. Domain, wallet addresses extracted from the funnel terminus, Telegram handles. This is what makes the system smarter — next time someone gets a message with the same wallet, triage hits the cache and resolves in 50ms with "we've seen this operation."

### Hour 2:45–3:30 — Card detail drawer

Person A's dashboard shell renders the feed. When a row is clicked, your `<IncidentDrawer />` opens.

**Four sections, in this exact order:**

1. **What they sent you** — original message with `tells` rendered as inline highlighted spans. Hover → tooltip with `why`. Soft yellow/red underline, not garish highlight.
2. **What they wanted** — `what_they_wanted` in larger type. Below it, icon row showing harvested fields with labels (💳 Card number, 🆔 SSN, 📍 Address).
3. **How we caught it** — bulleted list from `how_we_caught_it`, each bullet prefixed with small agent tag (`triage`, `domain-intel`, `sandbox-walker`). Below: **the sandbox replay**.
4. **How to spot it next time** — `how_to_spot_it` rules in callout box. Friendly tone.

**The sandbox replay component:**
- Horizontal strip of screenshot thumbnails from `incidents.screenshots`
- Click → expand to full size with caption derived from walker step data
- Captions specific: "Step 2: Fake USPS payment page. Asked for card number AND SSN — real USPS never does this."
- This is the visceral demo moment. Spend time on polish.

**For incidents with no URLs (screenshot-source scams with no link):**
- Skip the sandbox replay section
- "How we caught it" only shows triage + domain-intel findings (or just triage)
- Show the original screenshot image instead, with the VLM-extracted tells overlaid
- Pre-test this path once before demo if Person A ships the screenshot stretch

**Implementation note:** you're working in Person A's Next.js codebase. Stay out of their components, ship yours self-contained. They expose `<IncidentDrawer incidentId={id} />` as the prop shape. You fetch `/incidents/{id}` and render.

### Hour 3:30–3:50 — End-to-end + polish

1. Run full pipeline: scam in → triage → investigation → card in drawer. Should complete in 30-60s.
2. If anything's flaky, swap that piece to fixtures. Synthesizer on real walker + fixture domain-intel is fine. Fixture walker + live synthesizer is fine. Judges see the final output, not the wiring.
3. Polish the drawer: typography matches Person A's shell, generous spacing, screenshot scrubber feels smooth.

### Hour 3:50–4:00 — Demo prep

1. Pick live demo scam with Person A. Run end-to-end twice.
2. Have fixture-based fallback ready: a "manual trigger" button that loads a pre-investigated incident if live fails.
3. Walk through demo narration once together.

If Person A built the screenshot stretch:
- Verify the drawer renders correctly for the no-URL path
- Have one screenshot scam pre-tested as the second demo beat

---

## Tool quick-reference

- **AgentField:** decorator on each agent, coordination primitive for fan-out.
- **Actionbook:** form-filling and selectors in the walker. 30-min budget; fall back to heuristic if needed.
- **Bright Data:** WHOIS, reputation. Fallback: `python-whois`.
- **TokenRouter:** synthesizer uses strong model (GLM-4.6 or Claude Sonnet).
- **Zeabur:** separate container for sandbox. Ephemeral, no persistence.

---

## Hard cuts if you fall behind

- **Hour 2 and walker not working:** skip Actionbook, plain Playwright + heuristic form-filling. If still flaky, walker runs in "snapshot mode" — just screenshots and DOM inspection, no form-filling. Funnel terminus from URL inspection only.
- **Hour 3 and walker still flaky:** synthesizer reads fixtures keyed by scam_type. Live demo's triage runs real, investigation fixture-driven. Still demos well.
- **Hour 3:30 and drawer behind:** drop the sandbox replay scrubber, embed one hero screenshot in "how we caught it." Half the work, 80% of impact.

---

## The one thing that matters

The headline demo moment is the card opening to reveal what the scammer was actually trying to do. The sandbox replay strip is what makes that moment feel real instead of generated. Even if the live walker fails and you're rendering fixtures, the screenshots themselves are what the audience remembers.

Everything else in your tier supports that moment.
