# Capstone Verification Evidence: Usage Metering & Billing Engine

This document provides auditable verification evidence for every requirement in Section 6 and the acceptance probes in Section 12 of the Capstone Brief.

---

## 1. Automated Test Suite Execution (7/7 Passed)

```text
================================= test session starts =================================
platform win32 -- Python 3.15.1, pytest-9.2.0, pluggy-1.7.0
rootdir: C:\Users\myper\Developer\flyrank-capstone-metering-billing
configfile: pytest.ini
testpaths: tests
plugins: anyio-4.15.1
collected 7 items

tests/test_phase2.py::test_probe_1_idempotent_metering PASSED                   [ 14%]
tests/test_phase2.py::test_probe_2_quota_boundary_enforcement PASSED             [ 28%]
tests/test_phase2.py::test_probe_2_payment_required_on_past_due PASSED           [ 42%]
tests/test_phase2.py::test_probe_5_ai_token_pricing_rules PASSED                 [ 57%]
tests/test_phase3.py::test_probe_4_forged_webhook_rejected PASSED                [ 71%]
tests/test_phase3.py::test_probe_3_and_4_checkout_and_idempotent_webhook PASSED  [ 85%]
tests/test_phase3.py::test_subscription_cancellation_downgrades_to_free PASSED   [100%]

================================= 7 passed in 0.61s ==================================
2. Requirement Checklists & Verification Details
A. Metering & Idempotency
[x] A billable action creates exactly one usage event under retries (Idempotency-Key).

[x] Proof in EVIDENCE.md that double-counting cannot happen:

Verification Test: test_probe_1_idempotent_metering

Mechanism: SQLite atomic constraint UNIQUE(tenant_id, idempotency_key) backed by the idempotency_records table.

Evidence: When sending identical payloads with Idempotency-Key: test-key-001, the first call returns HTTP 201 Created and inserts the event; the second call returns HTTP 201 with the exact mirrored payload in 0 ms, maintaining a database count of 1.

B. Quotas & Boundaries
[x] Usage is checked against the tenant's plan; requests over the limit are rejected.

[x] Responses carry the correct status codes (429/402) and an explanatory message:

Verification Test: test_probe_2_quota_boundary_enforcement & test_probe_2_payment_required_on_past_due

Evidence (Boundary Call 1,000/1,000):

JSON
HTTP/1.1 201 Created
{
  "status": "success",
  "tenant_id": "tenant_free_boundary",
  "event_type": "api_call",
  "quantity": 1
}
Evidence (Call 1,001/1,000 -> HTTP 429 Too Many Requests):

JSON
HTTP/1.1 429 Too Many Requests
Retry-After: 86400
{
  "error": "Monthly API calls quota exceeded (1000/1000).",
  "details": {
    "tenant_id": "tenant_free_boundary",
    "resource": "api_calls",
    "current_usage": 1000,
    "requested": 1,
    "limit": 1000,
    "retry_after": 86400
  }
}
Evidence (Past Due Tenant -> HTTP 402 Payment Required):

JSON
HTTP/1.1 402 Payment Required
{
  "error": "Subscription payment required to continue service.",
  "details": {
    "tenant_id": "tenant_unpaid_1",
    "status": "past_due",
    "action_required": "Update billing details at /api/v1/billing/checkout"
  }
}
C. Cost Calculation & AI Token Pricing Rules
[x] Monthly usage rolls up into a cost figure per tenant (GET /api/v1/usage/{tenant_id}).

[x] AI token pricing handles cached input tokens, reasoning tokens, and output pricing correctly.

[x] Pricing constants pinned in config, with proof of correct totals:

Verification Test: test_probe_5_ai_token_pricing_rules

Input Tokens: 1,000 fresh @ $0.15/1M = 150,000 nano-USD

Cached Input Tokens: 1,000 cached @ $0.075/1M (50% discount) = 75,000 nano-USD

Output Tokens: 500 @ $0.60/1M = 300,000 nano-USD

Reasoning Tokens: 500 @ $0.60/1M (billed as output) = 300,000 nano-USD

Calculated Total: 150,000 + 75,000 + 300,000 + 300,000 = 825,000 nano-USD ($0.000825)

Actual Output:

JSON
{
  "cost_nano_usd": 825000,
  "cost_display": "$0.000825"
}
D. Stripe Test Mode Integration
[x] Subscription checkout works end-to-end in Stripe test mode (POST /api/v1/billing/checkout).

[x] Webhooks verify cryptographic signatures, ignore duplicate events, and update plan/status:

Verification Tests: test_probe_4_forged_webhook_rejected, test_probe_3_and_4_checkout_and_idempotent_webhook, test_subscription_cancellation_downgrades_to_free

Forged Signature: Header with invalid HMAC-SHA256 returns HTTP 400 Bad Request ("detail": "Invalid Stripe webhook signature.").

Plan Upgrade: checkout.session.completed event flips tenant_free_1 from Free Tier (1k limit) to Pro Subscription (50k calls, 10M tokens limit).

Event Deduplication: Replaying the identical Stripe event ID returns HTTP 200 OK with {"status": "ignored", "reason": "duplicate_event"}.

E. Data Model & Repository Hygiene
[x] Database includes tenants, plans, subscriptions, and usage events; customer data isolated per tenant.

[x] All required pack files present: README.md, capstone.yaml, EVIDENCE.md, BUILDLOG.md, .env.example.
