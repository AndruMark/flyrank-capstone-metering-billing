# Usage Metering & Billing Engine

A resilient, multi-tenant usage metering and subscription billing service built with **Python 3.14**, **FastAPI**, and **Stripe Test Mode**. It guarantees **exactly-once billing event processing** via cryptographic idempotency keys, enforces deterministic quota thresholds, calculates AI token consumption under production pricing rules, and synchronizes subscription states through signature-verified webhooks.

---

## 1. System Architecture

```text
                           [ Client Request ]
                                   │
              POST /api/v1/generate or POST /api/v1/meter
                                   │
                     ┌─────────────▼─────────────┐
                     │   Idempotency Validation  │
                     │  (Checked Key Cache/DB)   │
                     └─────────────┬─────────────┘
                                   │
                      Duplicate? ──┴──> [ Return Cached 201 Response (0 ms) ]
                                   │ No
                     ┌─────────────▼─────────────┐
                     │    Quota Check Service    │
                     │  (Current Usage vs Plan)  │
                     └─────────────┬─────────────┘
                                   │
                  Limit Exceeded? ─┴──> [ 429 Too Many Requests / 402 Payment Required ]
                                   │ Allowed
                     ┌─────────────▼─────────────┐
                     │  Record Usage Event (DB)  │
                     │ (Qty, Cost Nano-units)    │
                     └─────────────┬─────────────┘
                                   │
                     ┌─────────────▼─────────────┐
                     │ Save Idempotency Snapshot │
                     └───────────────────────────┘

[ Stripe Test Mode ] ──> POST /api/v1/webhooks/stripe
                                   │
                     ┌─────────────▼─────────────┐
                     │ HMAC-SHA256 Signature     │
                     │ Verification (whsec_...)  │
                     └─────────────┬─────────────┘
                                   │ Invalid? ──> 400 Bad Request
                                   │ Valid
                     ┌─────────────▼─────────────┐
                     │ Deduplication Check       │
                     │ (processed_stripe_events) │
                     └─────────────┬─────────────┘
                                   │ Duplicate? ──> 200 OK (Ignored)
                                   │ New
                     ┌─────────────▼─────────────┐
                     │ Update Tenant Plan/Status │
                     │ (Free -> Pro on Checkout) │
                     └───────────────────────────┘
2. Subscription Plans & Quota BoundariesPlanAPI Calls LimitAI Token AllowanceFresh Input ($/1M)Cached Input (/1M)∣Output/Reasoning(/1M)Free1,000 / month100,000 / month$0.15$0.075 (50% disc.)Pro50,000 / month10,000,000 / month$0.15$0.075 (50% disc.)Token Billing MathematicsFresh Input Tokens: Billed at $0.15 per million (150 nano-USD / token).Cached Input Tokens: Billed at 50% discount ($0.075 / 1M = 75 nano-USD / token).Reasoning Tokens: Counted and billed as Output Tokens ($0.60 / 1M = 600 nano-USD / token).Money Math: Handled strictly as 64-bit integer nano-USD (1 USD = 1,000,000,000 nano-USD, 1 Cent = 10,000,000 nano-USD) to eradicate floating-point rounding drift.3. Quickstart & One-Command RunSetup EnvironmentPowerShell# 1. Activate virtual environment
.\.venv\Scripts\Activate.ps1

# 2. Seed initial demo data (Free, Pro, and Past-Due tenants)
python -m src.core.seeder

# 3. Launch application server
uvicorn src.main:app --host 0.0.0.0 --port 8000
Run Automated Acceptance ProbesPowerShellpytest -v
4. API SpecificationMethodEndpointDescriptionHeadersGET/healthSystem health check and statusNonePOST/api/v1/meterDirect usage event recordingIdempotency-Key (required)POST/api/v1/generateBillable dummy AI generation endpointIdempotency-Key (required)GET/api/v1/usage/{tenant_id}Aggregated monthly usage rollupNonePOST/api/v1/billing/checkoutCreate Stripe Checkout upgrade sessionNonePOST/api/v1/webhooks/stripeSignature-verified webhook receiverstripe-signature (required)5. Honest LimitationsSQLite Concurrency Bottleneck: SQLite utilizes a database-level lock on writes. While fully ACID-compliant and adequate for single-instance services, a high-throughput production platform processing thousands of concurrent metering requests should migrate to PostgreSQL with connection pooling.Local Webhook Delivery: Webhook testing relies on the Stripe CLI (stripe listen --forward-to localhost:8000/api/v1/webhooks/stripe) or simulated HMAC-signed payloads. Production deployment requires public HTTPS endpoints registered in the Stripe Dashboard.Monthly Window Aggregation: Monthly consumption rollups execute via SQL queries on indexed usage_events. For millions of events per tenant, rollups should be pre-aggregated into daily/hourly bucket tables or a Redis counter cache.
