from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

class MeterRequest(BaseModel):
    tenant_id: str = Field(..., min_length=1)
    event_type: str = Field(..., pattern="^(api_call|ai_tokens)$")
    input_tokens: int = Field(default=0, ge=0)
    cached_input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    reasoning_tokens: int = Field(default=0, ge=0)
    calls: int = Field(default=1, ge=1)

class GenerateRequest(BaseModel):
    tenant_id: str = Field(..., min_length=1)
    prompt: str = Field(..., min_length=1)
    # Simulated model telemetry
    simulated_input_tokens: int = Field(default=100, ge=0)
    simulated_cached_input_tokens: int = Field(default=0, ge=0)
    simulated_output_tokens: int = Field(default=50, ge=0)
    simulated_reasoning_tokens: int = Field(default=0, ge=0)

class UsageRollupResponse(BaseModel):
    tenant_id: str
    tenant_name: str
    plan_name: str
    status: str
    api_calls: Dict[str, Any]
    ai_tokens: Dict[str, Any]
    total_cost_usd: str
