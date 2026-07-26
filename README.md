# Sentinel

Always-on, agent-powered scam protection. Built in one day at a Llama Ventures
hackathon (May 2026).

Sentinel watches an inbox in real time, triages anything suspicious with an LLM
agent, and — when a message looks like a scam — dispatches an investigation
agent that safely walks the scam funnel in a sandboxed browser, collects
evidence, and synthesizes an incident report onto a live dashboard.

## Architecture

Five services, one Postgres, one agent control plane:

| Service | What it does |
|---|---|
| `apps/harness` | Persistent monitoring loop — IMAP IDLE email watcher, webhook ingest endpoint, LLM triage worker, heartbeat |
| `apps/investigation` | Investigation agent — orchestrates domain intel, sandbox walks, and LLM synthesis into incident reports |
| `apps/sandbox` | Playwright service that follows scam funnels with synthetic data and captures screenshot evidence |
| `apps/api` | FastAPI + Postgres backend for the dashboard (incidents, stats, monitoring status) |
| `apps/web` | Next.js dashboard — hero stats, live incident feed, cross-service agent activity panel |

Agents register with an AgentField control plane for cross-agent routing and
observability. Scam-walk fixtures in `fixtures/walks/` cover phishing,
crypto/airdrop, romance, pig-butchering, delivery, and fake-support funnels.

```text
inbox (IMAP IDLE) ──▶ harness ──triage──▶ incident (Postgres)
                                             │ status='investigating'
                                             ▼
                                      investigation agent
                                    ┌──────┴──────────┐
                              domain intel      sandbox walk (Playwright)
                                    └──────┬──────────┘
                                       synthesizer
                                             ▼
                                   incident report ──▶ Next.js dashboard
```

## Run locally

```bash
cp .env.example .env        # IMAP creds, model + service config
docker compose up           # Postgres + control plane + harness + api + sandbox + investigation
cd apps/web && npm install && npm run dev
```

The email watcher expects a dedicated IMAP account (e.g. a Gmail app
password). Without live credentials, seeded incidents and recorded fixtures
still drive the dashboard.

## Status

Hackathon-scope build. Email is the committed ingestion surface; screenshot
ingestion exists as a second surface stub. Not hardened for production use.
