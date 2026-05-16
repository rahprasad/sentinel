// Shared types. Mirrors apps/investigation/src/models.py — keep them in sync.

export type AgentTag = "triage" | "domain-intel" | "sandbox-walker";

export type FunnelTerminus =
  | "payment_processor"
  | "telegram"
  | "whatsapp"
  | "credentials_form"
  | "unknown"
  | "error";

export type IncidentStatus = "triaging" | "investigating" | "done" | "safe";

export type IncidentSource = "email_imap" | "email_webhook" | "screenshot";

export interface Tell {
  span: string;
  why: string;
}

export interface IOCs {
  urls?: string[];
  phones?: string[];
  wallets?: string[];
  handles?: string[];
}

export interface TriageResult {
  is_scam: boolean;
  confidence: number;
  scam_type: string;
  tells: Tell[];
  reasoning?: string;
}

export interface WhatTheySent {
  raw: string;
  tells: Tell[];
}

export interface HowWeCaughtItEntry {
  agent: AgentTag;
  finding: string;
}

export interface CardEvidence {
  domain?: string | null;
  domain_age_days?: number | null;
  final_url?: string | null;
  harvested_fields?: string[];
  funnel_terminus?: FunnelTerminus | null;
}

export interface CardContract {
  scam_type: string;
  what_they_sent: WhatTheySent;
  what_they_wanted: string;
  how_we_caught_it: HowWeCaughtItEntry[];
  how_to_spot_it: string[];
  evidence: CardEvidence;
}

export interface Incident {
  id: string;
  received_at: string;
  source: IncidentSource;
  sender: string | null;
  subject: string | null;
  body: string | null;
  iocs: IOCs;
  triage: TriageResult | null;
  status: IncidentStatus;
  investigation: CardContract | null;
  screenshots: string[];
  estimated_loss_usd: number | null;
}
