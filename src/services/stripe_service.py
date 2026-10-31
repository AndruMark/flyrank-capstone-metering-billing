import json
import stripe
from typing import Dict, Any, Tuple
from fastapi import HTTPException, status
from src.core.config import settings
from src.core.database import get_db

stripe.api_key = settings.STRIPE_SECRET_KEY

class StripeService:
    @classmethod
    def create_checkout_session(cls, tenant_id: str, success_url: str, cancel_url: str) -> Dict[str, Any]:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, status, stripe_customer_id FROM tenants WHERE id = ?;", (tenant_id,))
            tenant = cursor.fetchone()
            if not tenant:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Tenant '{tenant_id}' not found.")

        if settings.STRIPE_SECRET_KEY.startswith("sk_test_placeholder"):
            mock_session_id = f"cs_test_{tenant_id}_pro"
            return {
                "checkout_url": f"https://checkout.stripe.com/c/pay/{mock_session_id}",
                "session_id": mock_session_id,
                "mode": "test_simulation",
                "tenant_id": tenant_id,
                "plan": "pro"
            }

        try:
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                mode="subscription",
                client_reference_id=tenant_id,
                metadata={"tenant_id": tenant_id, "plan_id": "pro"},
                line_items=[{
                    "price_data": {
                        "currency": "usd",
                        "product_data": {
                            "name": "Pro Subscription Plan",
                            "description": "50k API calls and 10M tokens monthly allowance"
                        },
                        "unit_amount": 2900,
                        "recurring": {"interval": "month"}
                    },
                    "quantity": 1
                }],
                success_url=success_url,
                cancel_url=cancel_url
            )
            return {
                "checkout_url": session.url,
                "session_id": session.id,
                "tenant_id": tenant_id,
                "plan": "pro"
            }
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Stripe API Error: {str(e)}")

    @classmethod
    def verify_and_parse_webhook(cls, payload: bytes, sig_header: str) -> Dict[str, Any]:
        if not sig_header:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing stripe-signature header.")

        try:
            event = stripe.Webhook.construct_event(
                payload=payload,
                sig_header=sig_header,
                secret=settings.STRIPE_WEBHOOK_SECRET
            )
            return event
        except stripe.SignatureVerificationError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Stripe webhook signature.")
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Webhook payload parsing error: {str(e)}")

    @classmethod
    def process_webhook_event(cls, event: Any) -> Tuple[int, Dict[str, Any]]:
        # Convert StripeObject to standard Python dict for safe .get() access
        event_dict = event.to_dict() if hasattr(event, "to_dict") else event
        event_id = event_dict["id"]
        event_type = event_dict["type"]
        raw_data = event_dict["data"]["object"]
        data_object = raw_data.to_dict() if hasattr(raw_data, "to_dict") else raw_data

        with get_db() as conn:
            cursor = conn.cursor()
            
            # Deduplication Check (Probe 4)
            cursor.execute("SELECT event_id FROM processed_stripe_events WHERE event_id = ?;", (event_id,))
            if cursor.fetchone():
                return 200, {
                    "status": "ignored",
                    "reason": "duplicate_event",
                    "event_id": event_id
                }

            # State Synchronization
            if event_type == "checkout.session.completed":
                tenant_id = data_object.get("client_reference_id") or data_object.get("metadata", {}).get("tenant_id")
                customer_id = data_object.get("customer")
                subscription_id = data_object.get("subscription")

                if tenant_id:
                    cursor.execute("""
                        UPDATE tenants 
                        SET plan_id = 'pro', status = 'active', 
                            stripe_customer_id = ?, stripe_subscription_id = ?
                        WHERE id = ?;
                    """, (customer_id, subscription_id, tenant_id))

            elif event_type == "customer.subscription.updated":
                subscription_id = data_object.get("id")
                sub_status = data_object.get("status")
                cursor.execute("""
                    UPDATE tenants 
                    SET status = ? 
                    WHERE stripe_subscription_id = ?;
                """, (sub_status, subscription_id))

            elif event_type == "customer.subscription.deleted":
                subscription_id = data_object.get("id")
                cursor.execute("""
                    UPDATE tenants 
                    SET plan_id = 'free', status = 'active', stripe_subscription_id = NULL 
                    WHERE stripe_subscription_id = ?;
                """, (subscription_id,))

            # Mark Event as Processed
            cursor.execute("""
                INSERT INTO processed_stripe_events (event_id, event_type)
                VALUES (?, ?);
            """, (event_id, event_type))

        return 200, {
            "status": "processed",
            "event_id": event_id,
            "event_type": event_type
        }
