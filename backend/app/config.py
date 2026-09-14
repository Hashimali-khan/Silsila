"""Application configuration — reads from environment variables / .env file."""

from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Silsila API"
    ENVIRONMENT: str = "development"
    SECRET_KEY: str = "change-me-in-production"
    FRONTEND_URL: str = "http://localhost:3000"

    # Database (Heroku Postgres)
    DATABASE_URL: str
    DATABASE_POOL_MIN: int = 5
    DATABASE_POOL_MAX: int = 20

    # Clerk Auth
    CLERK_SECRET_KEY: str
    CLERK_JWT_ISSUER: str  # e.g. https://your-domain.clerk.accounts.dev

    # Voyage AI — embeddings ONLY, no fallback provider
    VOYAGE_API_KEY: str
    VOYAGE_MODEL: str = "voyage-4/"
    VOYAGE_EMBEDDING_DIM: int = 1024
    VOYAGE_TOKEN_BUDGET: int = 200_000_000  # 200M one-time grant

    # Qdrant — vector store
    QDRANT_URL: str
    QDRANT_API_KEY: str
    QDRANT_COLLECTION: str = "silsila_chunks"

    # Groq — primary LLM
    GROQ_API_KEY: str
    GROQ_MODEL: str = "openai/gpt-oss-120b"

    # Gemini — fallback LLM + entity suggestion only
    GEMINI_API_KEY: str
    GEMINI_FLASH_MODEL: str = "gemini-2.0-flash"

    # Sentry (optional — Phase 6)
    SENTRY_DSN: str = ""
    
    # Entity Extraction
    USE_LLM_EXTRACTOR: bool = False  # Set to True to use Gemini for entity extraction (saves ~1GB RAM for Heroku)

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.FRONTEND_URL.split(",")]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # ignore unknown env vars (e.g. CLERK_PUBLISHABLE_KEY for frontend)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
