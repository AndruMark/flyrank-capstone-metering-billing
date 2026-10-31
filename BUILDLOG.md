# Engineering Build Log - Usage Metering & Billing Engine

## Project Context
- **Track**: Backend AI Engineering
- **Student**: AndruMark
- **Project**: Usage Metering & Billing Engine (Live Capstone)
- **Stack**: Python 3.14, FastAPI, SQLite, Stripe SDK, Pydantic V2

---

## Phase 1: Architecture & Domain Modeling
- **Focus**: Setting up project contracts, configuration schemas, and repository hygiene.
- **Where AI Helped**: Drafted the initial directory layout and schema definitions.
- **Where AI Was Wrong / Human Audit**:
  * AI proposed storing currency as floating-point numbers (`float`). Overridden: Currency must strictly be integer nano-units (1 USD = 1,000,000,000 nano-units) to prevent IEEE-754 precision loss.
  * AI suggested installing `uvicorn[standard]` which failed on Windows due to PyYAML C-extensions requiring MSVC Build Tools. Swapped to core `uvicorn` using pure Python `h11`.

---

## Phase 2: Core Billing, Idempotency & Quota Engine
- **Focus**: Implementing database migrations, idempotency tracking, and quota boundary checking.
- **Where AI Helped**: Generated SQL table definitions and FastAPI routing boilerplate.
- **Where AI Was Wrong / Human Audit**:
  * AI's quota check performed a post-action rollback if the limit was exceeded. Overridden: Quotas must be checked *before* recording the event to prevent unnecessary primary key sequence depletion and race conditions.
  * Boundary test failed on repeated local runs due to residual database rows. Added database cleanup fixtures to `tests/test_phase2.py`.

---

## Phase 3: Stripe Test Mode & Signature Verification
- **Focus**: Implementing Checkout session creation, HMAC signature verification, and deduplicated event handling.
- **Where AI Helped**: Drafted Stripe webhook signature verification helper using `stripe.Webhook.construct_event`.
- **Where AI Was Wrong / Human Audit**:
  * In `stripe>=11.0.0`, event payload objects are `StripeObject` instances that reject standard dictionary `.get()` method calls with an `AttributeError`. Refactored `StripeService.process_webhook_event` to convert objects via `.to_dict()` safely.

---

## Phase 4: Verification, Cost Rollups & Documentation
- **Focus**: End-to-end probe verification, test suite consolidation, and performance analysis.
- **Human Audit**: Formulated comprehensive `EVIDENCE.md` matrix with verified test transcripts directly validating all 5 evaluation probes.
