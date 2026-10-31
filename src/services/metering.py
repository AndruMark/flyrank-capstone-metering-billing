import json
from typing import Optional, Dict, Any, Tuple
from src.core.database import get_db
from src.services.pricing import PricingService

class QuotaExceededException(Exception):
    def __init__(self, message: str, details: Dict[str, Any]):
        self.message = message
        self.details = details
        super().__init__(self.message)

class PaymentRequiredException(Exception):
    def __init__(self, message: str, details: Dict[str, Any]):
        self.message = message
        self.details = details
        super().__init__(self.message)

class MeteringService:
    @staticmethod
    def get_tenant_plan_and_usage(conn, tenant_id: str) -> Dict[str, Any]:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT t.id, t.name, t.status, t.plan_id,
                   p.name as plan_name, p.monthly_api_calls_limit, p.monthly_tokens_limit, p.price_cents
            FROM tenants t
            JOIN plans p ON t.plan_id = p.id
            WHERE t.id = ?;
        """, (tenant_id,))
        tenant = cursor.fetchone()
        if not tenant:
            raise ValueError(f"Tenant '{tenant_id}' does not exist.")
            
        # Get usage for current monthly window
        cursor.execute("""
            SELECT 
                COALESCE(SUM(CASE WHEN event_type = 'api_call' THEN quantity ELSE 0 END), 0) as api_calls_used,
                COALESCE(SUM(CASE WHEN event_type = 'ai_tokens' THEN quantity ELSE 0 END), 0) as tokens_used,
                COALESCE(SUM(cost_nano_usd), 0) as total_cost_nano_usd
            FROM usage_events
            WHERE tenant_id = ? 
              AND created_at >= datetime('now', 'start of month');
        """, (tenant_id,))
        usage = cursor.fetchone()
        
        return {
            "tenant_id": tenant["id"],
            "tenant_name": tenant["name"],
            "status": tenant["status"],
            "plan_id": tenant["plan_id"],
            "plan_name": tenant["plan_name"],
            "api_calls_limit": tenant["monthly_api_calls_limit"],
            "tokens_limit": tenant["monthly_tokens_limit"],
            "api_calls_used": usage["api_calls_used"],
            "tokens_used": usage["tokens_used"],
            "total_cost_nano_usd": usage["total_cost_nano_usd"]
        }

    @classmethod
    def check_quota(cls, conn, tenant_id: str, event_type: str, requested_qty: int):
        data = cls.get_tenant_plan_and_usage(conn, tenant_id)
        
        # Payment Required condition
        if data["status"] in ("past_due", "unpaid", "canceled"):
            raise PaymentRequiredException(
                "Subscription payment required to continue service.",
                {
                    "tenant_id": tenant_id,
                    "status": data["status"],
                    "action_required": "Update billing details at /api/v1/billing/checkout"
                }
            )

        # Quota enforcement
        if event_type == "api_call":
            limit = data["api_calls_limit"]
            current = data["api_calls_used"]
            if current + requested_qty > limit:
                raise QuotaExceededException(
                    f"Monthly API calls quota exceeded ({current}/{limit}).",
                    {
                        "tenant_id": tenant_id,
                        "resource": "api_calls",
                        "current_usage": current,
                        "requested": requested_qty,
                        "limit": limit,
                        "retry_after": 86400
                    }
                )
        elif event_type == "ai_tokens":
            limit = data["tokens_limit"]
            current = data["tokens_used"]
            if current + requested_qty > limit:
                raise QuotaExceededException(
                    f"Monthly token quota exceeded ({current}/{limit}).",
                    {
                        "tenant_id": tenant_id,
                        "resource": "ai_tokens",
                        "current_usage": current,
                        "requested": requested_qty,
                        "limit": limit,
                        "retry_after": 86400
                    }
                )

    @classmethod
    def record_usage(
        cls,
        tenant_id: str,
        idempotency_key: str,
        event_type: str,
        input_tokens: int = 0,
        cached_input_tokens: int = 0,
        output_tokens: int = 0,
        reasoning_tokens: int = 0,
        calls: int = 1
    ) -> Tuple[int, Dict[str, Any]]:
        with get_db() as conn:
            cursor = conn.cursor()
            
            # 1. Exactly-Once Idempotency Check
            cursor.execute("""
                SELECT status_code, response_payload 
                FROM idempotency_records 
                WHERE tenant_id = ? AND idempotency_key = ?;
            """, (tenant_id, idempotency_key))
            cached = cursor.fetchone()
            if cached:
                # Mirror original response with 0 extra side effects
                return cached["status_code"], json.loads(cached["response_payload"])

            # 2. Determine quantity and cost
            if event_type == "api_call":
                qty = calls
                cost_nano = PricingService.calculate_api_call_cost(calls)
            elif event_type == "ai_tokens":
                qty = input_tokens + cached_input_tokens + output_tokens + reasoning_tokens
                cost_nano = PricingService.calculate_token_cost(
                    input_tokens=input_tokens,
                    cached_input_tokens=cached_input_tokens,
                    output_tokens=output_tokens,
                    reasoning_tokens=reasoning_tokens
                )
            else:
                raise ValueError(f"Invalid event_type: {event_type}")

            # 3. Quota Boundary Check (Raises 429/402 before recording)
            cls.check_quota(conn, tenant_id, event_type, qty)

            # 4. Insert Usage Event
            cursor.execute("""
                INSERT INTO usage_events (
                    tenant_id, event_type, quantity,
                    input_tokens, cached_input_tokens, output_tokens, reasoning_tokens,
                    cost_nano_usd, idempotency_key
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                tenant_id, event_type, qty,
                input_tokens, cached_input_tokens, output_tokens, reasoning_tokens,
                cost_nano, idempotency_key
            ))

            response_data = {
                "status": "success",
                "tenant_id": tenant_id,
                "event_type": event_type,
                "quantity": qty,
                "cost_nano_usd": cost_nano,
                "cost_display": PricingService.nano_to_usd_display(cost_nano),
                "idempotency_key": idempotency_key
            }

            # 5. Save Idempotency Record
            cursor.execute("""
                INSERT INTO idempotency_records (tenant_id, idempotency_key, status_code, response_payload)
                VALUES (?, ?, ?, ?);
            """, (tenant_id, idempotency_key, 201, json.dumps(response_data)))

            return 201, response_data
