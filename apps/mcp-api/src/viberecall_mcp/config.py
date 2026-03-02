from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


APP_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[4]


def resolve_env_file() -> str:
    root_env = REPO_ROOT / ".env"
    if root_env.exists():
        return str(root_env)

    app_env = APP_DIR / ".env"
    if app_env.exists():
        return str(app_env)

    return ".env"


class Settings(BaseSettings):
    app_env: str = "development"
    log_level: str = "info"
    database_url: str = "postgresql://postgres:antrungnam123@123@db.yimrsadgbvemndimowlh.supabase.co:5432/postgres"
    token_pepper: str = "change-me"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "neo4j123"
    neo4j_database_prefix: str = "vr-"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"
    memory_backend: Literal["local", "neo4j", "graphiti"] = "local"
    kv_backend: Literal["local", "redis"] = "local"
    queue_backend: Literal["eager", "celery"] = "eager"
    max_payload_bytes: int = 262_144
    allowed_origins: str = ""
    rate_limit_token_capacity: int = 60
    rate_limit_project_capacity: int = 300
    rate_limit_window_seconds: int = 60
    recent_episode_window_seconds: int = 300
    quota_free_monthly_vibe_tokens: int = 100_000
    quota_pro_monthly_vibe_tokens: int = 5_000_000
    quota_team_monthly_vibe_tokens: int = 20_000_000
    vibe_in_mul: float = 1.0
    vibe_out_mul: float = 1.0
    graphiti_api_key: str | None = None
    graphiti_llm_model: str = "gpt-4.1-mini"
    graphiti_embedder_model: str = "text-embedding-3-small"
    graphiti_add_episode_timeout_seconds: float = 20.0
    object_storage_mode: Literal["local", "r2"] = "local"
    object_local_dir: str = ".runtime-objects"
    object_bucket: str = ""
    object_endpoint: str = ""
    object_region: str = "auto"
    object_access_key_id: str = ""
    object_secret_access_key: str = ""
    object_force_path_style: bool = True
    raw_episode_inline_max_bytes: int = 65_536
    inline_migration_db_size_threshold_bytes: int = 21_474_836_480
    export_storage_mode: Literal["local"] = "local"
    export_local_dir: str = ".runtime-exports"
    export_url_ttl_seconds: int = 3600
    export_signing_secret: str = "dev-export-secret"
    public_web_url: str = "http://localhost:3000"
    public_mcp_base_url: str = "http://localhost:8000"
    control_plane_internal_secret: str = "dev-control-plane-secret"
    stripe_webhook_secret: str = "whsec_dev"
    stripe_webhook_tolerance_seconds: int = 300

    model_config = SettingsConfigDict(
        env_file=resolve_env_file(),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
