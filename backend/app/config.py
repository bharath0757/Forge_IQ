import os
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = "sqlite:///./test.db"
    
    # CORS Configuration
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000,*"
    
    # AI Providers ("deterministic", "openai", "anthropic")
    ai_provider: str = "deterministic"
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    
    # File Storage
    storage_dir: str = "uploads"
    max_file_size_mb: int = 50

    @property
    def cors_origins_list(self) -> List[str]:
        if not self.cors_origins:
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    model_config = SettingsConfigDict(
        env_file=os.environ.get("ENV_FILE", ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
