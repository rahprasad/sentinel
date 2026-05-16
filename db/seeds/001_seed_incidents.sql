-- =============================================================================
-- Seed incidents for demo dashboard. 4 committed types covering the main scam
-- categories Person A owns.  All have status='done' so the dashboard has data
-- on first load.  Person B writes 4 more.
-- =============================================================================

-- 1. Phishing — Fake USPS redelivery
INSERT INTO incidents (id, received_at, source, sender, subject, body, iocs, triage, status, estimated_loss_usd)
VALUES (
    gen_random_uuid(),
    now() - interval '4 hours',
    'email_imap',
    'USPS Delivery <no-reply@usps-redelivery.co>',
    'Action Required: Your package could not be delivered',
    'Dear Customer, your package with tracking number US982431573 could not be delivered. Please schedule a redelivery and pay the $0.99 holding fee at https://usps-redelivery.co/track?id=US982431573 within 48 hours or your package will be returned to sender.',
    '{"urls": ["https://usps-redelivery.co/track?id=US982431573"], "phones": [], "wallets": [], "handles": []}'::jsonb,
    '{"is_scam": true, "confidence": 0.95, "scam_type": "phishing", "tells": [{"span": "usps-redelivery.co", "why": "Domain does not match usps.com"}, {"span": "$0.99 holding fee", "why": "USPS never charges redelivery fees"}], "reasoning": "Sender domain impersonates USPS; link leads to a recently-registered domain asking for payment"}'::jsonb,
    'done',
    50
);

-- 2. Romance — Pig butchering crypto pitch
INSERT INTO incidents (id, received_at, source, sender, subject, body, iocs, triage, status, estimated_loss_usd)
VALUES (
    gen_random_uuid(),
    now() - interval '1 day',
    'email_imap',
    'Jessica Wei <jessica.wei795@gmail.com>',
    'Re: Great meeting you!',
    'Hey! It was so nice talking to you today. I have been trading crypto for a while and making consistent returns. I use this platform — https://btc-vault-trade.io — and my portfolio is up 340% this quarter. Want me to show you how? You can start with as little as $500. My ETH wallet for the initial deposit is 0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D. Let me know! 💕',
    '{"urls": ["https://btc-vault-trade.io"], "phones": [], "wallets": ["0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"], "handles": []}'::jsonb,
    '{"is_scam": true, "confidence": 0.92, "scam_type": "romance", "tells": [{"span": "btc-vault-trade.io", "why": "Recently-registered crypto exchange domain"}, {"span": "340% this quarter", "why": "Unrealistic returns promise"}, {"span": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D", "why": "Direct ETH wallet for deposit"}], "reasoning": "Classic pig butchering: romance angle + fake crypto platform + direct wallet deposit"}'::jsonb,
    'done',
    5000
);

-- 3. Delivery — Fake DHL customs charge
INSERT INTO incidents (id, received_at, source, sender, subject, body, iocs, triage, status, estimated_loss_usd)
VALUES (
    gen_random_uuid(),
    now() - interval '2 days',
    'email_webhook',
    'DHL Express <notifications@dhl-express-notice.com>',
    'Your shipment requires customs payment',
    'Your international shipment (AWB 5483729103) is being held at customs. A duty of $2.85 must be paid before delivery can proceed. Pay now: https://dhl-express-notice.com/pay?ref=5483729103 to avoid return to origin. Contact: +1 (888) 555-0147.',
    '{"urls": ["https://dhl-express-notice.com/pay?ref=5483729103"], "phones": ["+18885550147"], "wallets": [], "handles": []}'::jsonb,
    '{"is_scam": true, "confidence": 0.93, "scam_type": "delivery", "tells": [{"span": "dhl-express-notice.com", "why": "Domain does not match dhl.com"}, {"span": "$2.85", "why": "Tiny amount to lower suspicion"}], "reasoning": "Impersonated DHL domain with suspicious low customs charge to bait victims"}'::jsonb,
    'done',
    50
);

-- 4. Crypto — Airdrop phishing
INSERT INTO incidents (id, received_at, source, sender, subject, body, iocs, triage, status, estimated_loss_usd)
VALUES (
    gen_random_uuid(),
    now() - interval '5 days',
    'email_webhook',
    'Uniswap <airdrop@uniswap-claim.org>',
    'Uniswap $UNI Airdrop — Claim Your Tokens',
    'Congratulations! You are eligible for the Uniswap $UNI airdrop. Connect your wallet at https://uniswap-claim.org/airdrop to claim 400 UNI tokens (approx $2,800). Offer expires in 72 hours. Follow us @UniswapAirdrop for updates.',
    '{"urls": ["https://uniswap-claim.org/airdrop"], "phones": [], "wallets": [], "handles": ["@UniswapAirdrop"]}'::jsonb,
    '{"is_scam": true, "confidence": 0.97, "scam_type": "crypto", "tells": [{"span": "uniswap-claim.org", "why": "Not the real uniswap.org domain"}, {"span": "400 UNI tokens", "why": "High-value lure to encourage wallet connection"}, {"span": "@UniswapAirdrop", "why": "Unofficial social handle"}], "reasoning": "Fake airdrop site impersonating Uniswap to drain connected wallets"}'::jsonb,
    'done',
    2000
);
