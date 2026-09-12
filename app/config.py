"""Application configuration settings using Pydantic Settings."""

from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration settings for CodeImpact Person 3 Backend."""

    # Demo Mode: When True, runs offline using deterministic mock responses
    DEMO_MODE: bool = True

    # Server settings
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # LLM settings
    LLM_PROVIDER: str = "openai"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_TIMEOUT_SECONDS: float = 30.0
    GEMINI_MODEL: str = "gemini-1.5-flash"

    # CORS settings (comma-separated string or list)
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173"

    # Embedding settings
    EMBEDDING_PROVIDER: str = "openai"  # "voyage", "openai", "gemini", "local"
    VOYAGE_API_KEY: str = ""
    VOYAGE_MODEL: str = "voyage-code-3"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-large"
    GEMINI_API_KEY: str = ""
    GEMINI_EMBEDDING_MODEL: str = "models/gemini-embedding-001"
    EMBEDDING_BATCH_SIZE: int = 100
    EMBEDDING_CACHE_DB: str = "output/embedding_cache.db"
    SYMBOL_INDEX_DB: str = "output/symbol_index.db"
    VECTOR_STORE_DB: str = "output/vector_store.db"
    # Enables Person 2's existing embedding retriever for the live project
    # index. Disabled by default so a local project works offline.
    VECTOR_RETRIEVAL_ENABLED: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def get_cors_origins(self) -> List[str]:
        """Parse comma-separated allowed origins into a list."""
        if not self.ALLOWED_ORIGINS:
            return ["*"]
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]


settings = Settings()
