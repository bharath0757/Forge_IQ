import os
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database — defaults to SQLite for zero-config local dev / Render free tier
    database_url: str = "sqlite:///./forgeiq.db"

    # CORS — in production, replace * with your actual frontend URL(s)
    # e.g. "https://your-app.vercel.app,https://your-app.netlify.app"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000,*"

    # AI Providers: "deterministic" (offline), "openai", "anthropic"
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

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def uploads_path(self) -> str:
        """Absolute path to the uploads directory."""
        if os.path.isabs(self.storage_dir):
            return self.storage_dir
        return os.path.join(os.getcwd(), self.storage_dir)

    model_config = SettingsConfigDict(
        env_file=os.environ.get("ENV_FILE", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
