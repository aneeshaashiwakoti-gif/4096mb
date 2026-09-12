"""Factory for instantiating LLM providers."""

from app.config import settings
from app.llm.base import LLMProvider
from app.llm.demo_provider import DemoProvider
from app.llm.openai_provider import OpenAIProvider
from app.llm.gemini_provider import GeminiProvider
from app.utils.logging import logger


def get_llm_provider() -> LLMProvider:
    """Return an active LLMProvider instance based on system configuration."""
    if settings.DEMO_MODE:
        return DemoProvider()

    provider_name = settings.LLM_PROVIDER.lower()
    if provider_name == "openai":
        return OpenAIProvider() if settings.OPENAI_API_KEY else DemoProvider()
    if provider_name == "gemini":
        return GeminiProvider() if settings.GEMINI_API_KEY else DemoProvider()
    else:
        logger.warning(f"Unknown LLM provider '{provider_name}'. Defaulting to DemoProvider.")
        return DemoProvider()
