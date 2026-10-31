from src.core.config import settings

class PricingService:
    # 1 USD = 1,000,000,000 Nano-USD (1 Cent = 10,000,000 Nano-USD)
    NANO_PER_CENT = 10_000_000
    NANO_PER_USD = 1_000_000_000

    @classmethod
    def calculate_token_cost(
        cls,
        input_tokens: int = 0,
        cached_input_tokens: int = 0,
        output_tokens: int = 0,
        reasoning_tokens: int = 0
    ) -> int:
        """
        Calculates cost in nano-USD (integers) preventing float rounding drift.
        Rule 1: Cached inputs are discounted 50%.
        Rule 2: Reasoning tokens count strictly as output tokens.
        """
        fresh_input_cost = input_tokens * settings.COST_INPUT_TOKEN_MICRO
        cached_input_cost = cached_input_tokens * settings.COST_CACHED_INPUT_TOKEN_MICRO
        
        # Reasoning tokens are billed at output rate
        effective_output_tokens = output_tokens + reasoning_tokens
        output_cost = effective_output_tokens * settings.COST_OUTPUT_TOKEN_MICRO
        
        return fresh_input_cost + cached_input_cost + output_cost

    @classmethod
    def calculate_api_call_cost(cls, calls: int = 1) -> int:
        return calls * settings.COST_PER_API_CALL_CENTS * cls.NANO_PER_CENT

    @classmethod
    def nano_to_usd_display(cls, nano_usd: int) -> str:
        dollars = nano_usd / cls.NANO_PER_USD
        return f"${dollars:.6f}"
