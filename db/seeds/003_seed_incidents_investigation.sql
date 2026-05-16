-- Person B's 4 demo seeds. Person A writes the other 4.
-- All four start as `status='investigating'` so the investigation worker
-- picks them up on first boot. They populate the dashboard within seconds
-- of services coming up.
--
-- Re-running this file is idempotent (ON CONFLICT DO NOTHING on id).

INSERT INTO incidents
    (id, received_at, source, sender, subject, body, iocs, triage, status)
VALUES
-- ─── 1. Romance / investment pivot ───────────────────────────────────────────
(
    '11111111-1111-1111-1111-111111111111',
    now() - interval '6 minutes',
    'email_imap',
    'Olivia M. <olivia.mccarthy@protonmail.com>',
    'It''s been so long, my love',
    'Hi James, I miss you so much. I just got my bonus from the trading platform — over $14,000 in one week! I told you about it last month. The link my advisor sent me is here: https://crypto-yield-pro.io/refer/o-mccarthy. He says if you deposit by Friday you can match my returns. I want to plan our future together. Send me a kiss before I sleep.',
    '{
       "urls": ["https://crypto-yield-pro.io/refer/o-mccarthy"],
       "phones": [],
       "wallets": [],
       "handles": []
     }'::jsonb,
    '{
       "is_scam": true,
       "confidence": 0.92,
       "scam_type": "romance",
       "tells": [
         {"span": "bonus from the trading platform",
          "why": "Romance scammers pivot to investment pitches once trust is built."},
         {"span": "https://crypto-yield-pro.io/refer/o-mccarthy",
          "why": "Suspicious crypto domain with a personal referral path."},
         {"span": "deposit by Friday",
          "why": "Manufactured urgency around an unverifiable deadline."}
       ],
       "reasoning": "Affection language combined with an investment URL is the textbook pig-butchering opener."
     }'::jsonb,
    'investigating'
),
-- ─── 2. Crypto airdrop / wallet drainer ─────────────────────────────────────
(
    '22222222-2222-2222-2222-222222222222',
    now() - interval '4 minutes',
    'email_imap',
    'Coinbase Rewards <no-reply@coinbase-airdrop.app>',
    'You qualified for a 4.81 ETH airdrop',
    'Hello Coinbase user,

Your wallet 0x71C7656EC7ab88b098defB751B7401B5f6d8976F has been selected for our Q1 2026 community airdrop totaling 4.81 ETH.

Claim within 48 hours: https://coinbase-airdrop.app/claim

Connect your wallet and sign the verification transaction to receive funds. After 48 hours your share is redistributed.

Coinbase Rewards Team',
    '{
       "urls": ["https://coinbase-airdrop.app/claim"],
       "phones": [],
       "wallets": ["0x71C7656EC7ab88b098defB751B7401B5f6d8976F"],
       "handles": []
     }'::jsonb,
    '{
       "is_scam": true,
       "confidence": 0.96,
       "scam_type": "crypto-airdrop",
       "tells": [
         {"span": "coinbase-airdrop.app",
          "why": "Domain mimics Coinbase but isn''t coinbase.com."},
         {"span": "sign the verification transaction",
          "why": "Asking you to sign a transaction is how wallet-drainer scams work."},
         {"span": "Claim within 48 hours",
          "why": "Time pressure is a classic phishing pattern."}
       ],
       "reasoning": "Look-alike Coinbase domain plus a sign-transaction-to-claim funnel is wallet-drain."
     }'::jsonb,
    'investigating'
),
-- ─── 3. Pig-butchering / wrong-number opener ───────────────────────────────
(
    '33333333-3333-3333-3333-333333333333',
    now() - interval '3 minutes',
    'email_imap',
    'Mei Lin <meili.investments@gmail.com>',
    'Hey Daniel — sorry, wrong number?',
    'Hi! Oh my god I''m so sorry, my assistant must have given me the wrong contact. You''re not Daniel right? Anyway, since we''re chatting — what do you do? I''m in fintech, just relocated to Singapore from Vancouver. I''m trading on GS Markets and the strategy my uncle taught me is wild, made 31% last month. If you''re curious I can show you. https://gs-markets-pro.com/m/welcome

Mei',
    '{
       "urls": ["https://gs-markets-pro.com/m/welcome"],
       "phones": [],
       "wallets": [],
       "handles": []
     }'::jsonb,
    '{
       "is_scam": true,
       "confidence": 0.94,
       "scam_type": "pig-butchering",
       "tells": [
         {"span": "wrong number",
          "why": "Wrong-number opener is the universal pig-butchering entry."},
         {"span": "uncle taught me",
          "why": "Family-mentor framing builds false trust around a fake platform."},
         {"span": "https://gs-markets-pro.com/m/welcome",
          "why": "Unfamiliar trading domain not registered to a real broker."}
       ],
       "reasoning": "Cold contact plus investment pivot plus unfamiliar broker domain is pig-butchering."
     }'::jsonb,
    'investigating'
),
-- ─── 4. Fake support / account takeover ─────────────────────────────────────
(
    '44444444-4444-4444-4444-444444444444',
    now() - interval '90 seconds',
    'email_imap',
    'Apple Support <support@apple-security-alerts.net>',
    '[Action Required] Suspicious sign-in to your Apple ID',
    'Dear Customer,

We detected a sign-in to your Apple ID from an unrecognized device:
  Location: Lagos, Nigeria
  Device: Windows PC
  Time: Today, 03:42 AM

If this was not you, secure your account immediately:
https://apple-security-alerts.net/verify

You have 24 hours to confirm your identity or your account will be locked for security reasons.

Apple Support',
    '{
       "urls": ["https://apple-security-alerts.net/verify"],
       "phones": [],
       "wallets": [],
       "handles": []
     }'::jsonb,
    '{
       "is_scam": true,
       "confidence": 0.97,
       "scam_type": "fake-support",
       "tells": [
         {"span": "apple-security-alerts.net",
          "why": "Apple doesn''t send security emails from this domain."},
         {"span": "24 hours",
          "why": "Urgency is a primary phishing lever."},
         {"span": "secure your account immediately",
          "why": "Real Apple alerts never link out to verify."}
       ],
       "reasoning": "Look-alike Apple domain plus urgency plus single-CTA link is account takeover."
     }'::jsonb,
    'investigating'
)
ON CONFLICT (id) DO NOTHING;
