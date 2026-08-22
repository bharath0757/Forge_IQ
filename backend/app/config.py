import os
from typing import List
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database — defaults to SQLite for zero-config local dev / /tmp in serverless
    database_url: str = "sqlite:///./forgeiq.db"

    # CORS — in production, replace * with your actual frontend URL(s)
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000,*"

    # AI Providers: "deterministic" (offline), "openai", "anthropic", "nvidia"
    ai_provider: str = "deterministic"
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    nvidia_api_key: str = ""
    nvidia_model: str = "nvidia/nemotron-3.5-lightning-30b-a3b"
    nvidia_embed_model: str = "nvidia/nemotron-3-embed-1b"

    # File Storage
    storage_dir: str = "uploads"
    max_file_size_mb: int = 50

    @field_validator("max_file_size_mb", mode="before")
    @classmethod
    def parse_max_file_size(cls, v):
        if v is None or v == "" or (isinstance(v, str) and v.strip() == ""):
            return 50
        try:
            return int(v)
        except (ValueError, TypeError):
            return 50

    @field_validator("database_url", mode="before")
    @classmethod
    def parse_database_url(cls, v):
        is_serverless = bool(
            os.environ.get("VERCEL") == "1"
            or os.environ.get("AWS_LAMBDA_FUNCTION_NAME")
            or os.environ.get("VERCEL_ENV")
        )
        if v is None or v == "" or (isinstance(v, str) and v.strip() == ""):
            if is_serverless:
                return "sqlite:////tmp/forgeiq.db"
            return "sqlite:///./forgeiq.db"

        val_str = str(v).strip()
        if is_serverless and val_str.startswith("sqlite:///."):
            return "sqlite:////tmp/forgeiq.db"

        return val_str

    @field_validator("storage_dir", mode="before")
    @classmethod
    def parse_storage_dir(cls, v):
        is_serverless = bool(
            os.environ.get("VERCEL") == "1"
            or os.environ.get("AWS_LAMBDA_FUNCTION_NAME")
            or os.environ.get("VERCEL_ENV")
        )
        if v is None or v == "" or (isinstance(v, str) and v.strip() == ""):
            if is_serverless:
                return "/tmp/uploads"
            return "uploads"

        val_str = str(v).strip()
        if is_serverless and not val_str.startswith("/tmp"):
            return "/tmp/uploads"
        return val_str

    @field_validator("ai_provider", mode="before")
    @classmethod
    def parse_ai_provider(cls, v):
        if v is None or v == "" or (isinstance(v, str) and v.strip() == ""):
            return "deterministic"
        return str(v).strip()

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if v is None or v == "" or (isinstance(v, str) and v.strip() == ""):
            return "http://localhost:3000,http://127.0.0.1:3000,*"
        return str(v).strip()

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

