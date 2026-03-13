import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


APP_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[4]
_LOCAL_DATABASE_URL_PLACEHOLDERS = {
    "postgresql://postgres:postgres@localhost:5432/viberecall",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/viberecall",
}
_LOCAL_SECRET_PLACEHOLDERS = {
    "token_pepper": "change-me",
    "export_signing_secret": "dev-export-secret",
    "control_plane_internal_secret": "dev-control-plane-secret",
    "stripe_webhook_secret": "whsec_dev",
}
_GRAPHITI_API_KEY_PLACEHOLDERS = {
    "",
    "replace-with-openai-key",
}


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
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/viberecall"
    token_pepper: str = "change-me"
    falkordb_host: str = "localhost"
    falkordb_port: int = 6380
    falkordb_username: str = ""
    falkordb_password: str = ""
    falkordb_graph_prefix: str = "vr-"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"
    memory_backend: Literal["local", "falkordb", "graphiti"] = "local"
    kv_backend: Literal["local", "redis"] = "local"
    queue_backend: Literal["eager", "celery"] = "eager"
    max_payload_bytes: int = 262_144
    allowed_origins: str = ""
    rate_limit_token_capacity: int = 60
    rate_limit_project_capacity: int = 300
    rate_limit_window_seconds: int = 60
    dependency_probe_cache_ok_ttl_seconds: float = 3.0
    dependency_probe_cache_error_ttl_seconds: float = 12.0
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
    graphiti_mcp_bridge_mode: Literal["legacy", "upstream_bridge"] = "legacy"
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
    index_repo_allowed_roots: str = ""
    index_bundle_max_bytes: int = 52_428_800
    index_remote_git_enabled: bool = False
    index_git_credential_refs_json: str = "{}"
    operation_dispatch_retry_limit: int = 8
    export_storage_mode: Literal["local"] = "local"
    export_local_dir: str = ".runtime-exports"
    export_url_ttl_seconds: int = 3600
    export_signing_secret: str = "dev-export-secret"
    public_web_url: str = "http://localhost:3000"
    public_mcp_base_url: str = "http://localhost:8010"
    control_plane_internal_secret: str = ""
    stripe_webhook_secret: str = "whsec_dev"
    stripe_webhook_tolerance_seconds: int = 300

    model_config = SettingsConfigDict(
        env_file=resolve_env_file(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_runtime_secrets(self) -> "Settings":
        violations: list[str] = []
        if not self.control_plane_internal_secret.strip():
            violations.append("CONTROL_PLANE_INTERNAL_SECRET must be configured")

        if not self.token_pepper.strip():
            violations.append("TOKEN_PEPPER must be configured")

        graphiti_api_key = (self.graphiti_api_key or "").strip()
        if self.memory_backend == "graphiti" and graphiti_api_key.lower() in _GRAPHITI_API_KEY_PLACEHOLDERS:
            violations.append("GRAPHITI_API_KEY must be configured when MEMORY_BACKEND=graphiti")

        if violations:
            raise ValueError("; ".join(violations))

        if self.app_env.lower() == "development":
            return self

        if self.database_url.strip() in _LOCAL_DATABASE_URL_PLACEHOLDERS:
            violations.append("DATABASE_URL must be configured for non-development environments")

        for field_name, placeholder in _LOCAL_SECRET_PLACEHOLDERS.items():
            if str(getattr(self, field_name)).strip() == placeholder:
                violations.append(f"{field_name.upper()} must be overridden outside development")

        if violations:
            raise ValueError("; ".join(violations))
        return self

    def resolved_index_repo_allowed_roots(self) -> tuple[Path, ...]:
        raw = self.index_repo_allowed_roots.strip()
        if not raw:
            return (REPO_ROOT.resolve(),)

        roots: list[Path] = []
        for chunk in raw.replace("\n", ",").split(","):
            candidate = chunk.strip()
            if not candidate:
                continue
            roots.append(Path(candidate).expanduser().resolve())

        return tuple(roots) if roots else (REPO_ROOT.resolve(),)

    def resolved_index_git_credential_refs(self) -> dict[str, dict]:
        raw = self.index_git_credential_refs_json.strip() or "{}"
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("INDEX_GIT_CREDENTIAL_REFS_JSON must be valid JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError("INDEX_GIT_CREDENTIAL_REFS_JSON must decode to an object")

        normalized: dict[str, dict] = {}
        for key, value in payload.items():
            ref = str(key).strip()
            if not ref:
                raise ValueError("INDEX_GIT_CREDENTIAL_REFS_JSON contains an empty credential ref")
            if not isinstance(value, dict):
                raise ValueError(f"Credential ref '{ref}' must be an object")

            allowed_hosts = value.get("allowed_hosts") or []
            if not isinstance(allowed_hosts, list) or not allowed_hosts:
                raise ValueError(f"Credential ref '{ref}' must define a non-empty allowed_hosts list")
            normalized_hosts = []
            for host in allowed_hosts:
                host_value = str(host).strip().lower()
                if not host_value:
                    raise ValueError(f"Credential ref '{ref}' contains an empty allowed_hosts entry")
                normalized_hosts.append(host_value)

            username = str(value.get("username") or "").strip()
            password = str(value.get("password") or "").strip()
            token = str(value.get("token") or "").strip()
            if token and password:
                raise ValueError(f"Credential ref '{ref}' must not define both token and password")
            if not token and not password:
                raise ValueError(f"Credential ref '{ref}' must define token or password")

            normalized[ref] = {
                "allowed_hosts": normalized_hosts,
                "username": username,
                "password": password,
                "token": token,
            }
        return normalized


@lru_cache
def get_settings() -> Settings:
    return Settings()
