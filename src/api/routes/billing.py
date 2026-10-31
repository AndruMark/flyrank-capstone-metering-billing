from fastapi import APIRouter, Header, HTTPException, status
from fastapi.responses import JSONResponse
from src.models.schemas import MeterRequest, GenerateRequest, UsageRollupResponse
from src.services.metering import MeteringService, QuotaExceededException, PaymentRequiredException
from src.services.pricing import PricingService
from src.core.database import get_db

router = APIRouter(prefix="/api/v1", tags=["Metering & Billing"])

@router.post("/meter", summary="Direct Usage Metering")
def meter_usage(
    payload: MeterRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key")
):
    try:
        status_code, response = MeteringService.record_usage(
            tenant_id=payload.tenant_id,
            idempotency_key=idempotency_key,
            event_type=payload.event_type,
            input_tokens=payload.input_tokens,
            cached_input_tokens=payload.cached_input_tokens,
            output_tokens=payload.output_tokens,
            reasoning_tokens=payload.reasoning_tokens,
            calls=payload.calls
        )
        return JSONResponse(status_code=status_code, content=response)
    except QuotaExceededException as e:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"error": e.message, "details": e.details},
            headers={"Retry-After": str(e.details.get("retry_after", 86400))}
        )
    except PaymentRequiredException as e:
        return JSONResponse(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            content={"error": e.message, "details": e.details}
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/generate", summary="Dummy Billable AI Endpoint")
def generate_ai_text(
    payload: GenerateRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key")
):
    """
    Exercises the complete billing chain:
    1. Meter API call
    2. Meter AI token consumption with cached & reasoning rules
    3. Return simulated output
    """
    try:
        # Meter the AI tokens
        status_code, response = MeteringService.record_usage(
            tenant_id=payload.tenant_id,
            idempotency_key=idempotency_key,
            event_type="ai_tokens",
            input_tokens=payload.simulated_input_tokens,
            cached_input_tokens=payload.simulated_cached_input_tokens,
            output_tokens=payload.simulated_output_tokens,
            reasoning_tokens=payload.simulated_reasoning_tokens
        )
        return JSONResponse(
            status_code=status_code,
            content={
                "result": f"Simulated generation for prompt: '{payload.prompt[:30]}...'",
                "billing": response
            }
        )
    except QuotaExceededException as e:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"error": e.message, "details": e.details},
            headers={"Retry-After": str(e.details.get("retry_after", 86400))}
        )
    except PaymentRequiredException as e:
        return JSONResponse(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            content={"error": e.message, "details": e.details}
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/usage/{tenant_id}", response_model=UsageRollupResponse, summary="Usage Rollup")
def get_usage_rollup(tenant_id: str):
    try:
        with get_db() as conn:
            data = MeteringService.get_tenant_plan_and_usage(conn, tenant_id)
            
        return {
            "tenant_id": data["tenant_id"],
            "tenant_name": data["tenant_name"],
            "plan_name": data["plan_name"],
            "status": data["status"],
            "api_calls": {
                "used": data["api_calls_used"],
                "limit": data["api_calls_limit"],
                "remaining": max(0, data["api_calls_limit"] - data["api_calls_used"])
            },
            "ai_tokens": {
                "used": data["tokens_used"],
                "limit": data["tokens_limit"],
                "remaining": max(0, data["tokens_limit"] - data["tokens_used"])
            },
            "total_cost_usd": PricingService.nano_to_usd_display(data["total_cost_nano_usd"])
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
