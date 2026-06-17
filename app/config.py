from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://user:password@postgres/transactions"
    REDIS_URL: str = "redis://redis:6379/0"
    GEMINI_API_KEY: str = ""
    UPLOAD_DIR: str = "uploads"

    model_config = {"env_file": ".env"}


settings = Settings()
