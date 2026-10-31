# Capstone Verification Evidence

## 1. Metering & Idempotency
- [ ] Exactly-once metering per idempotency key under network retries.
  - *Proof*: TBD (Probe 1 test output)

## 2. Quota Enforcement
- [ ] 429 Too Many Requests on usage limits; 402 Payment Required on unpaid/upgrade boundaries.
  - *Proof*: TBD (Probe 2 test transcript)

## 3. Cost Calculation & Token Rules
- [ ] Cached input tokens priced at 50% of fresh input.
- [ ] Reasoning tokens calculated strictly as output tokens.
  - *Proof*: TBD (Probe 5 verification)

## 4. Stripe Test Mode Integration
- [ ] Signature-verified webhooks (`stripe-signature`).
- [ ] Deduplication of replayed webhook events (`evt_xxx`).
- [ ] Automatic tenant plan synchronization (Free -> Pro).
  - *Proof*: TBD (Probe 3 & Probe 4 transcripts)
