from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    PROJECT_NAME: str = "Usage Metering & Billing Engine"
    ENVIRONMENT: str = "development"
    PORT: int = 8000

    STRIPE_SECRET_KEY: str = "sk_test_placeholder"
    STRIPE_WEBHOOK_SECRET: str = "whsec_test_secret"

    # Pricing constants in nano-USD units
    COST_PER_API_CALL_CENTS: int = 1
    COST_INPUT_TOKEN_MICRO: int = 150
    COST_CACHED_INPUT_TOKEN_MICRO: int = 75
    COST_OUTPUT_TOKEN_MICRO: int = 600
    COST_REASONING_TOKEN_MICRO: int = 600

settings = Settings()
