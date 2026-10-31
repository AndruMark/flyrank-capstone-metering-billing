import uuid
import pytest
from fastapi.testclient import TestClient
from src.main import app
from src.core.database import init_db, get_db
from src.core.seeder import seed_data

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_database():
    init_db()
    seed_data()

def test_probe_1_idempotent_metering():
    """Probe 1: Same request sent twice with one idempotency key produces one usage event."""
    idem_key = str(uuid.uuid4())
    payload = {
        "tenant_id": "tenant_free_1",
        "event_type": "api_call",
        "calls": 1
    }
    
    # First request
    res1 = client.post("/api/v1/meter", json=payload, headers={"Idempotency-Key": idem_key})
    assert res1.status_code == 201
    
    # Second request (network retry)
    res2 = client.post("/api/v1/meter", json=payload, headers={"Idempotency-Key": idem_key})
    assert res2.status_code == 201
    assert res1.json() == res2.json()
    
    # Verify in DB that only 1 record exists
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM usage_events WHERE idempotency_key = ?", (idem_key,))
        count = cursor.fetchone()[0]
        assert count == 1

def test_probe_2_quota_boundary_enforcement():
    """Probe 2: Request at quota limit succeeds; next request returns 429."""
    tenant = "tenant_free_boundary"
    with get_db() as conn:
        conn.execute("INSERT OR REPLACE INTO tenants (id, name, plan_id, status) VALUES (?, ?, 'free', 'active');", (tenant, "Boundary Tester"))
    
    # Free plan limit is 1,000 API calls
    # Fill 999 calls
    client.post("/api/v1/meter", json={"tenant_id": tenant, "event_type": "api_call", "calls": 999}, headers={"Idempotency-Key": str(uuid.uuid4())})
    
    # Request 1,000 (Boundary call -> Allowed)
    res_boundary = client.post("/api/v1/meter", json={"tenant_id": tenant, "event_type": "api_call", "calls": 1}, headers={"Idempotency-Key": str(uuid.uuid4())})
    assert res_boundary.status_code == 201
    
    # Request 1,001 (Over limit -> 429 Too Many Requests)
    res_over = client.post("/api/v1/meter", json={"tenant_id": tenant, "event_type": "api_call", "calls": 1}, headers={"Idempotency-Key": str(uuid.uuid4())})
    assert res_over.status_code == 429
    assert "quota exceeded" in res_over.json()["error"].lower()
    assert "Retry-After" in res_over.headers

def test_probe_2_payment_required_on_past_due():
    """402 Payment Required returned when tenant is in past_due state."""
    res = client.post(
        "/api/v1/meter",
        json={"tenant_id": "tenant_unpaid_1", "event_type": "api_call", "calls": 1},
        headers={"Idempotency-Key": str(uuid.uuid4())}
    )
    assert res.status_code == 402
    assert "payment required" in res.json()["error"].lower()

def test_probe_5_ai_token_pricing_rules():
    """Probe 5: Cached input at 50% discount and reasoning tokens priced as output tokens."""
    idem_key = str(uuid.uuid4())
    payload = {
        "tenant_id": "tenant_pro_1",
        "prompt": "Test reasoning pricing",
        "simulated_input_tokens": 1000,          # 1,000 * 150 = 150,000 nano
        "simulated_cached_input_tokens": 1000,   # 1,000 * 75  = 75,000 nano (50% discount)
        "simulated_output_tokens": 500,          # 500 * 600   = 300,000 nano
        "simulated_reasoning_tokens": 500        # 500 * 600   = 300,000 nano (output rate)
    }
    # Total expected cost: 150,000 + 75,000 + 300,000 + 300,000 = 825,000 nano-USD ($0.000825)
    res = client.post("/api/v1/generate", json=payload, headers={"Idempotency-Key": idem_key})
    assert res.status_code == 201
    billing = res.json()["billing"]
    assert billing["cost_nano_usd"] == 825000
    assert billing["cost_display"] == "$0.000825"
