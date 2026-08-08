"""Application configuration settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Silsila API"
    ENVIRONMENT: str = "development"

    class Config:
        env_file = ".env"


settings = Settings()
