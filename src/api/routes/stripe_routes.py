from fastapi import APIRouter, Request, Header, HTTPException, status
from fastapi.responses import JSONResponse
from src.models.schemas import CheckoutRequest
from src.services.stripe_service import StripeService

router = APIRouter(prefix="/api/v1", tags=["Stripe Billing Integration"])

@router.post("/billing/checkout", summary="Initiate Subscription Checkout Session")
def create_checkout(payload: CheckoutRequest):
    result = StripeService.create_checkout_session(
        tenant_id=payload.tenant_id,
        success_url=payload.success_url,
        cancel_url=payload.cancel_url
    )
    return JSONResponse(status_code=status.HTTP_200_OK, content=result)

@router.post("/webhooks/stripe", summary="Signature-Verified Stripe Webhook Receiver")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="stripe-signature")
):
    payload = await request.body()
    event = StripeService.verify_and_parse_webhook(payload, stripe_signature)
    status_code, response = StripeService.process_webhook_event(event)
    return JSONResponse(status_code=status_code, content=response)
