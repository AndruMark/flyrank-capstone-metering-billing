from contextlib import asynccontextmanager
from fastapi import FastAPI
from src.core.config import settings
from src.core.database import init_db
from src.api.routes.billing import router as billing_router
from src.api.routes.stripe_routes import router as stripe_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description="Idempotent Usage Metering and Subscription Quota Billing Engine",
    lifespan=lifespan
)

app.include_router(billing_router)
app.include_router(stripe_router)

@app.get("/health", tags=["System"])
def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT
    }
