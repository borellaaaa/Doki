from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Doki"
    DOKI_VERSION: str = "1.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Security
    SECRET_KEY: str = "dev_secret_key_troque_em_producao"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./doki.db"

    # ChromaDB
    CHROMA_PATH: str = "./chroma_db"

    # Moderation
    MAX_MESSAGE_LENGTH: int = 4000
    RATE_LIMIT_PER_MINUTE: int = 30

    # Embeddings
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    # LLM Backend: "ollama" ou "openai_compatible"
    LLM_BACKEND: str = "ollama"
    LLM_BASE_URL: str = "http://localhost:11434"
    LLM_MODEL: str = "mistral"
    LLM_API_KEY: str = ""
    LLM_MAX_TOKENS: int = 2048
    LLM_TEMPERATURE: float = 0.3

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
