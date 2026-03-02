import re

from viberecall_mcp.config import get_settings


def sanitize_project_id(project_id: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", project_id).strip("-").lower()
    return normalized or "project"


def project_db_name(project_id: str) -> str:
    settings = get_settings()
    return f"{settings.neo4j_database_prefix}{sanitize_project_id(project_id)}"
