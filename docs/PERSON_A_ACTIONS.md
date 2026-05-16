# Action items for Person A (Detection tier)

Status as of this push. Investigation tier (Person B / sandbox / synthesizer)
is fully wired up and deployed; the items below are what Person A's detection
tier needs to do for the full demo to be live on Zeabur.

---

## 1. Deploy `apps/api` to Zeabur

**Why:** The web dashboard (`apps/web`) reads `NEXT_PUBLIC_API_URL` and calls
`GET /incidents`, `GET /incidents/{id}`, `GET /stats`, `GET /monitoring`. Right
now those go to `localhost:8000` — nothing on Zeabur serves them, so the
dashboard renders empty.

**How:** Two paths, same project as the investigation service
(`6a08df381985c8ed80e284fb`).

- **CLI:**
  ```bash
  # From repo root, with the api Dockerfile bound to $PORT (Zeabur uses 8080).
  # If apps/api/Dockerfile still hard-codes a port, change CMD to:
  #   CMD uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8080}
  cd apps/api && zeabur deploy --create --name sentinel-api \
      --project-id 6a08df381985c8ed80e284fb
  zeabur variable env --name sentinel-api -f ../../.env -i=false
  zeabur domain create --name sentinel-api -g --domain sentinel-api -y
  ```

- **Dashboard:** New Service → Dockerfile → point at `apps/api`. Same env
  vars. Generate a subdomain.

**Verify:** `curl https://sentinel-api.zeabur.app/incidents` returns the 8
seeded rows (all `status='done'`, all with investigation cards).

---

## 2. Deploy `apps/harness` to Zeabur

**Why:** The harness owns the persistent IMAP IDLE watcher and writes new
rows into Zeabur Postgres with `status='triaging' → 'investigating'`. Without
it deployed, no live email demo — only the seeded incidents work.

**How:** Same pattern.

```bash
cd apps/harness && zeabur deploy --create --name sentinel-harness \
    --project-id 6a08df381985c8ed80e284fb
zeabur variable env --name sentinel-harness -f ../../.env -i=false
```

The harness has no HTTP surface that needs a public domain — the webhook
receiver is for the curl-fallback demo path; expose it only if you want to
trigger ingests from outside Zeabur.

**Watch out:** the IMAP watcher needs `IMAP_HOST/PORT/USERNAME/PASSWORD` env
vars in the service environment. The `.env` file pushed via `variable env`
includes them.

---

## 3. Point `apps/web` at the deployed services + redeploy

**Why:** When `apps/web` runs on Zeabur, `NEXT_PUBLIC_API_URL` defaults to
`localhost:8000` (build-time substitution in Next.js). The dashboard needs
to know where the deployed API and investigation services live.

**How:** Set these env vars on the web service before deploy:

```bash
NEXT_PUBLIC_API_URL=https://sentinel-api.zeabur.app
NEXT_PUBLIC_INVESTIGATION_URL=https://sentinel-investigation.zeabur.app
```

Then `zeabur deploy --create --name sentinel-web` from `apps/web/`.
**Important:** these vars must be set _before_ the build because Next.js
inlines `NEXT_PUBLIC_*` at build time — setting them afterward and
redeploying without rebuilding won't work.

---

## 4. (Optional) Push `/reasoners/investigate` from triage instead of polling

**Why:** Investigation has a 1s-poll worker that picks up
`status='investigating'` rows. That means there's up to 1s between triage
flipping the row and investigation starting. If you call our reasoner
directly from the triage worker, the handoff is instant and visible in the
agent activity stream.

**How:** In `apps/harness/src/triage/worker.py`, after the `status` flip:

```python
async with httpx.AsyncClient(timeout=180) as client:
    try:
        await client.post(
            f"{settings.investigation_url}/reasoners/investigate",
            json={"incident_id": str(incident_id)},
        )
    except Exception:
        # Fire-and-forget: the poll worker will pick this up if the
        # call fails. No need to surface the error.
        pass
```

Set `INVESTIGATION_URL=https://sentinel-investigation.zeabur.app` (or the
internal hostname when both run on Zeabur).

**Optional** because the poll worker already handles every row. Skip if
you're tight on time.

---

## 5. Deploy the AgentField control plane

**Why:** AgentField agents heartbeat to a control plane for live
observability — workflow DAG, execution timelines, cryptographic audit
trail per investigation. Right now both the harness agent and investigation
agent emit workflow events that hit `localhost:8080` and 404 (non-fatal,
but no dashboard).

With the control plane deployed, you get a full observability UI at
its public URL.

**How (dashboard, recommended):**
1. Zeabur dashboard → New Service → **Deploy from Prebuilt Image**
2. Image: `agentfield/control-plane:latest`
3. Port: `8080`
4. Bind a domain (e.g. `agentfield-control-plane`)
5. **Then update env on both agents:**
   ```bash
   # On harness:
   zeabur variable update --name sentinel-harness \
       -k AGENTFIELD_SERVER=http://agentfield-control-plane.zeabur.internal:8080
   # On investigation:
   zeabur variable update --name sentinel-investigation \
       -k AGENTFIELD_SERVER=http://agentfield-control-plane.zeabur.internal:8080
   ```
6. Redeploy both: `zeabur deploy --service-id <id>`

**Why dashboard not CLI:** the AgentField control plane is a prebuilt
Docker image. The Zeabur CLI source-deploy detects a `FROM`-only Dockerfile
as `static` and refuses to build it (tried). Dashboard's prebuilt-image flow
handles it cleanly.

---

## What's already live (so you don't redo it)

| Resource | Status | Notes |
|---|---|---|
| Zeabur Postgres | Live | Schema + 8 seed incidents loaded; all have full investigation cards |
| `sentinel-investigation` service | Live | `https://sentinel-investigation.zeabur.app` |
| `sentinel-sandbox` service | Live | Internal: `sentinel-sandbox.zeabur.internal:8080` |
| `seen_iocs` cache | Live | Populated by investigation's synthesizer on each card |
| `/agent-activity` endpoint | Live | The web dashboard's `AgentActivityPanel` polls this |
| Live agent panel in dashboard | Coded | Renders once you set `NEXT_PUBLIC_INVESTIGATION_URL` |

## Surface map (what calls what)

```
  ┌─────────────┐  ──IMAP IDLE──▶  ┌───────────────────┐ INSERT incidents row
  │  Gmail demo │                  │ harness (Person A)│ ─────────────────────┐
  └─────────────┘                  └───────────────────┘                       │
                                            │                                  ▼
                                            │ triage.classify (Qwen/Flash)     ┌───────────────────┐
                                            ▼                                  │ Zeabur Postgres   │
                                  ┌───────────────────┐ UPDATE status →        │  incidents        │
                                  │ harness triage    │ 'investigating'        │  harness_status   │
                                  │ worker (Person A) │ ──────────────────────▶│  seen_iocs        │
                                  └───────────────────┘                        └───────────────────┘
                                                                                        ▲
                                                                                        │ poll status='investigating'
                                                                                        │
                                            ┌───────────────────────────────────────────┘
                                            ▼
                              ┌────────────────────────────────────────────┐
                              │  investigation (Person B)                  │
                              │  https://sentinel-investigation.zeabur.app │
                              │                                            │
                              │  orchestrator ─┬─▶ sandbox-walker  ────────┼─▶ sentinel-sandbox.zeabur.internal
                              │                ├─▶ domain-intel (python-whois)
                              │                └─▶ synthesizer  ───────────┼─▶ TokenRouter / GLM-4.6
                              │                                            │
                              │  records every step in /agent-activity     │
                              └────────────────────────────────────────────┘
                                            │
                                            ▼ poll /incidents/{id}, /agent-activity
                              ┌────────────────────────────────────────────┐
                              │  web (Person A)                            │
                              │  IncidentFeed → IncidentDrawer (Person B)  │
                              │  AgentActivityPanel (Person B)             │
                              └────────────────────────────────────────────┘
```

The agent activity panel pulls directly from investigation's
`/agent-activity` — it does not need the API server to be deployed. Once
you ship `apps/api` and the dashboard knows where to find it, the
`IncidentFeed` will populate with the 8 seeded incidents and the
`AgentActivityPanel` will show every reasoner/skill run as it happens.

## Priority

If you have time for only one item: **#1 (`apps/api`)**. Without it the
dashboard has nothing to show. Everything else is incremental.
