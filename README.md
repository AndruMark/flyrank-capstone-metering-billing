# Usage Metering & Billing Engine

A resilient, multi-tenant usage metering and subscription billing service built with **Python 3.14**, **FastAPI**, and **Stripe Test Mode**. It guarantees **exactly-once billing event processing** via cryptographic idempotency keys, enforces deterministic quota thresholds, calculates AI token consumption under production pricing rules, and synchronizes subscription states through signature-verified webhooks.

---

## 1. System Architecture

```text
                           [ Client Request ]
                                   │
                    POST /api/v1/generate or /meter
                                   │
                     ┌─────────────▼─────────────┐
                     │   Idempotency Validation  │
                     │  (Checked Key Cache/DB)   │
                     └─────────────┬─────────────┘
                                   │
                      Duplicate? ──┴──> [ Return Cached Response (0 ms) ]
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
                     │ (Qty, Cost Micro-units)   │
                     └───────────────────────────┘
2. Subscription Plans & Quota BoundariesPlanAPI Calls LimitAI Token AllowanceFresh Input ($/1M)Cached Input ($/1M)Output / Reasoning ($/1M)Free1,000 / month100,000 / month$0.15$0.075 (50% disc.)$0.60Pro50,000 / month10,000,000 / month$0.15$0.075 (50% disc.)$0.60Token Billing MathematicsFresh Input Tokens: Billed at $0.15 per million (150 micro-cents / token).Cached Input Tokens: Billed at 50% discount ($0.075 / 1M).Reasoning Tokens: Counted and billed as Output Tokens ($0.60 / 1M).Money Storage: Handled strictly as 64-bit integer micro-cents (1 USD = 100,000,000 micro-cents) to eradicate IEEE-754 floating-point drift.3. Quickstart & One-Command RunPowerShell# 1. Activate environment
.\.venv\Scripts\Activate.ps1

# 2. Run the application
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
