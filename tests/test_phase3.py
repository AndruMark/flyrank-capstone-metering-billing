import time
import json
import hmac
import hashlib
import uuid
import pytest
from fastapi.testclient import TestClient
from src.main import app
from src.core.config import settings
from src.core.database import init_db, get_db
from src.core.seeder import seed_data

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_database():
    init_db()
    with get_db() as conn:
        conn.execute("DELETE FROM usage_events;")
        conn.execute("DELETE FROM idempotency_records;")
        conn.execute("DELETE FROM processed_stripe_events;")
    seed_data()

def generate_stripe_signature(payload: str, secret: str) -> str:
    timestamp = int(time.time())
    signed_payload = f"{timestamp}.{payload}"
    sig = hmac.new(secret.encode("utf-8"), signed_payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={sig}"

def test_probe_4_forged_webhook_rejected():
    payload = json.dumps({"id": "evt_forged_1", "type": "checkout.session.completed", "data": {"object": {}}})
    bad_signature = "t=1234567,v1=invalid_hex_signature"
    
    res = client.post(
        "/api/v1/webhooks/stripe",
        content=payload,
        headers={"Content-Type": "application/json", "stripe-signature": bad_signature}
    )
    assert res.status_code == 400
    assert "invalid stripe webhook signature" in res.json()["detail"].lower()

def test_probe_3_and_4_checkout_and_idempotent_webhook():
    tenant_id = "tenant_free_1"
    event_id = f"evt_test_{uuid.uuid4().hex}"
    
    usage_before = client.get(f"/api/v1/usage/{tenant_id}").json()
    assert usage_before["plan_name"] == "Free Tier"
    assert usage_before["api_calls"]["limit"] == 1000
    
    payload_dict = {
        "id": event_id,
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_session_123",
                "client_reference_id": tenant_id,
                "customer": "cus_test_123",
                "subscription": "sub_test_pro_123"
            }
        }
    }
    payload_str = json.dumps(payload_dict)
    valid_sig = generate_stripe_signature(payload_str, settings.STRIPE_WEBHOOK_SECRET)
    
    # 1. First delivery
    res1 = client.post(
        "/api/v1/webhooks/stripe",
        content=payload_str,
        headers={"Content-Type": "application/json", "stripe-signature": valid_sig}
    )
    assert res1.status_code == 200
    assert res1.json()["status"] == "processed"
    
    # Verify upgraded to Pro
    usage_after = client.get(f"/api/v1/usage/{tenant_id}").json()
    assert usage_after["plan_name"] == "Pro Subscription"
    assert usage_after["api_calls"]["limit"] == 50000
    assert usage_after["ai_tokens"]["limit"] == 10000000
    
    # 2. Replay duplicate event
    res2 = client.post(
        "/api/v1/webhooks/stripe",
        content=payload_str,
        headers={"Content-Type": "application/json", "stripe-signature": valid_sig}
    )
    assert res2.status_code == 200
    assert res2.json()["status"] == "ignored"
    assert res2.json()["reason"] == "duplicate_event"

def test_subscription_cancellation_downgrades_to_free():
    tenant_id = "tenant_pro_1"
    sub_id = "sub_active_pro"
    
    with get_db() as conn:
        conn.execute("UPDATE tenants SET stripe_subscription_id = ? WHERE id = ?;", (sub_id, tenant_id))
    
    payload_dict = {
        "id": f"evt_del_{uuid.uuid4().hex}",
        "type": "customer.subscription.deleted",
        "data": {"object": {"id": sub_id}}
    }
    payload_str = json.dumps(payload_dict)
    sig = generate_stripe_signature(payload_str, settings.STRIPE_WEBHOOK_SECRET)
    
    res = client.post(
        "/api/v1/webhooks/stripe",
        content=payload_str,
        headers={"Content-Type": "application/json", "stripe-signature": sig}
    )
    assert res.status_code == 200
    
    usage = client.get(f"/api/v1/usage/{tenant_id}").json()
    assert usage["plan_name"] == "Free Tier"
