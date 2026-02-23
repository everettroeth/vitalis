"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """All configuration is loaded from environment variables (or .env file)."""

    # --- App ---
    app_name: str = "Vitalis"
    app_version: str = "0.1.0"
    debug: bool = False
    log_level: str = "INFO"
    environment: str = "development"  # development | staging | production

    # --- Supabase ---
    supabase_url: str
    supabase_service_role_key: str  # server-side only — never expose to client
    supabase_db_url: str  # direct postgres connection string for asyncpg

    # --- Clerk ---
    clerk_secret_key: str
    clerk_publishable_key: str
    clerk_webhook_secret: str  # svix signing secret for webhook verification
    clerk_jwks_url: str = "https://api.clerk.com/v1/jwks"

    # --- Cloudflare R2 ---
    r2_account_id: str
    r2_access_key_id: str
    r2_secret_access_key: str
    r2_bucket_name: str = "vitalis-files"
    r2_public_url: str = ""  # optional custom domain for public assets

    # --- Rate Limiting ---
    rate_limit_per_minute: int = 60
    rate_limit_burst: int = 10

    # --- CORS ---
    cors_origins: list[str] = ["http://localhost:3000"]

    # --- Security ---
    allowed_upload_types: list[str] = [
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/webp",
    ]
    max_upload_size_bytes: int = 50 * 1024 * 1024  # 50 MB

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
