from __future__ import annotations

import argparse
import json
import time
import uuid
from dataclasses import dataclass
from typing import Any
from urllib import error, request

from viberecall_mcp.tool_validation_matrix import SMOKE_PROFILE_DEFINITIONS


DEFAULT_PROTOCOL_VERSION = "2025-06-18"


class SmokeFailure(RuntimeError):
    """Raised when a smoke validation step fails."""


@dataclass(slots=True)
class SmokeContext:
    base_url: str
    project_id: str
    session_id: str | None = None

    @property
    def endpoint(self) -> str:
        return f"{self.base_url.rstrip('/')}/p/{self.project_id}/mcp"


@dataclass(slots=True)
class SmokeConfig:
    profiles: tuple[str, ...]
    shared_token: str | None
    profile_tokens: dict[str, str]
    query: str
    tag: str
    index_repo_source: dict[str, Any] | None
    index_timeout_seconds: int
    poll_interval_seconds: float


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke test a deployed VibeRecall MCP endpoint.")
    parser.add_argument("--base-url", required=True, help="Public MCP base URL, for example https://api.example.com")
    parser.add_argument("--project-id", required=True, help="Project identifier bound to the MCP token")
    parser.add_argument("--token", default=None, help="Shared fallback token used when a profile-specific token is absent")
    parser.add_argument("--core-token", default=None, help="Token used for the core profile")
    parser.add_argument("--ops-token", default=None, help="Token used for the ops profile")
    parser.add_argument("--graph-token", default=None, help="Token used for the graph profile")
    parser.add_argument("--index-token", default=None, help="Token used for the index profile")
    parser.add_argument("--resolution-token", default=None, help="Token used for the resolution profile")
    parser.add_argument(
        "--profile",
        action="append",
        choices=sorted(SMOKE_PROFILE_DEFINITIONS),
        default=[],
        help="Smoke profile to execute. Repeat to run multiple profiles. Defaults to core.",
    )
    parser.add_argument(
        "--query",
        default="production smoke test",
        help="Base query string used for retrieval checks",
    )
    parser.add_argument(
        "--tag",
        default="deploy-smoke",
        help="Base tag written into temporary smoke metadata",
    )
    parser.add_argument("--index-repo-url", default=None, help="Remote git URL used by the index smoke profile")
    parser.add_argument("--index-ref", default=None, help="Git ref used by the index smoke profile")
    parser.add_argument("--index-repo-name", default=None, help="Logical repo name used by the index smoke profile")
    parser.add_argument(
        "--index-timeout-seconds",
        type=int,
        default=90,
        help="How long to wait for index readiness before failing the index profile",
    )
    parser.add_argument(
        "--poll-interval-seconds",
        type=float,
        default=2.0,
        help="Polling interval for the index profile readiness checks",
    )
    return parser.parse_args(argv)


def resolve_profile_names(requested_profiles: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    if not requested_profiles:
        return ("core",)

    ordered: list[str] = []
    seen: set[str] = set()
    for profile_name in requested_profiles:
        if profile_name not in SMOKE_PROFILE_DEFINITIONS:
            raise SmokeFailure(f"Unknown smoke profile: {profile_name}")
        if profile_name in seen:
            continue
        seen.add(profile_name)
        ordered.append(profile_name)
    return tuple(ordered)


def resolve_profile_token(
    profile_name: str,
    *,
    shared_token: str | None,
    profile_tokens: dict[str, str],
) -> str:
    token = profile_tokens.get(profile_name) or shared_token
    if token:
        return token
    raise SmokeFailure(f"Missing token for smoke profile '{profile_name}'")


def ensure_profile_tools_available(profile_name: str, tool_names: list[str]) -> None:
    profile = SMOKE_PROFILE_DEFINITIONS[profile_name]
    missing_tools = sorted(set(profile.tool_names).difference(tool_names))
    if missing_tools:
        joined = ", ".join(missing_tools)
        raise SmokeFailure(f"Profile '{profile_name}' is missing expected tools: {joined}")


def build_index_repo_source(
    *,
    repo_url: str | None,
    ref: str | None,
    repo_name: str | None,
) -> dict[str, str]:
    if not repo_url or not ref or not repo_name:
        raise SmokeFailure("Index profile requires --index-repo-url, --index-ref, and --index-repo-name")
    return {
        "type": "git",
        "remote_url": repo_url,
        "ref": ref,
        "repo_name": repo_name,
    }


def _decode_payload(response, body: bytes) -> dict[str, Any]:
    content_type = response.headers.get("content-type", "")
    text = body.decode("utf-8")
    if content_type.startswith("text/event-stream"):
        for line in text.splitlines():
            if line.startswith("data: "):
                return json.loads(line.removeprefix("data: "))
        raise SmokeFailure("SSE response did not include a data frame")
    return json.loads(text)


def _decode_event_stream(response) -> dict[str, Any]:
    while True:
        raw_line = response.readline()
        if not raw_line:
            break
        line = raw_line.decode("utf-8", errors="replace").strip()
        if line.startswith("data: "):
            return json.loads(line.removeprefix("data: "))
    raise SmokeFailure("SSE response did not include a data frame")


def _post_json(
    context: SmokeContext,
    payload: dict[str, Any],
    *,
    include_auth: bool,
    token: str | None = None,
    extra_headers: dict[str, str] | None = None,
) -> tuple[dict[str, Any], Any]:
    headers = {
        "accept": "application/json, text/event-stream",
        "content-type": "application/json",
    }
    if context.session_id:
        headers["mcp-session-id"] = context.session_id
    if include_auth:
        if not token:
            raise SmokeFailure("Authenticated smoke call requires a token")
        headers["authorization"] = f"Bearer {token}"
    if extra_headers:
        headers.update(extra_headers)

    req = request.Request(
        context.endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=30) as response:
            content_type = response.headers.get("content-type", "")
            if content_type.startswith("text/event-stream"):
                return _decode_event_stream(response), response
            body = response.read()
            return _decode_payload(response, body), response
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SmokeFailure(f"HTTP {exc.code} from MCP endpoint: {body}") from exc
    except error.URLError as exc:
        raise SmokeFailure(f"Could not reach MCP endpoint: {exc}") from exc


def _require_ok(payload: dict[str, Any], *, step: str) -> dict[str, Any]:
    if payload.get("ok") is not True:
        raise SmokeFailure(f"{step} failed: {payload}")
    return payload["result"]


def _tool_call(
    context: SmokeContext,
    *,
    token: str,
    request_id: str,
    tool_name: str,
    arguments: dict[str, Any],
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
    payload, _ = _post_json(
        context,
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        },
        include_auth=True,
        token=token,
        extra_headers=headers,
    )
    try:
        text_payload = payload["result"]["content"][0]["text"]
    except (KeyError, IndexError, TypeError) as exc:
        raise SmokeFailure(f"Unexpected tools/call payload for {tool_name}: {payload}") from exc
    return json.loads(text_payload)


def initialize_session(context: SmokeContext) -> None:
    payload, response = _post_json(
        context,
        {
            "jsonrpc": "2.0",
            "id": "smoke-init",
            "method": "initialize",
            "params": {
                "protocolVersion": DEFAULT_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "deployed-smoke", "version": "1.0"},
            },
        },
        include_auth=False,
    )
    session_id = response.headers.get("mcp-session-id")
    if not session_id:
        raise SmokeFailure(f"Missing mcp-session-id in initialize response: {payload}")
    context.session_id = session_id


def list_tools(context: SmokeContext, token: str) -> list[str]:
    payload, _ = _post_json(
        context,
        {"jsonrpc": "2.0", "id": "smoke-tools", "method": "tools/list", "params": {}},
        include_auth=True,
        token=token,
    )
    try:
        return [tool["name"] for tool in payload["result"]["tools"]]
    except (KeyError, TypeError) as exc:
        raise SmokeFailure(f"Unexpected tools/list payload: {payload}") from exc


def _record_operation_id(state: dict[str, Any], payload: dict[str, Any]) -> None:
    operation_id = payload.get("result", {}).get("operation_id")
    if operation_id:
        state.setdefault("operation_ids", []).append(str(operation_id))


def _core_marker(config: SmokeConfig, suffix: str) -> str:
    return f"{config.tag}-{suffix}-{uuid.uuid4().hex[:8]}"


def run_core_profile(context: SmokeContext, *, token: str, config: SmokeConfig, state: dict[str, Any]) -> dict[str, Any]:
    ensure_profile_tools_available("core", list_tools(context, token))

    canonical_marker = _core_marker(config, "canonical")
    canonical_payload = _tool_call(
        context,
        token=token,
        request_id="core-save-episode",
        tool_name="viberecall_save_episode",
        arguments={
            "content": f"{config.query} canonical marker {canonical_marker}",
            "metadata": {"type": "deploy-smoke", "tags": [canonical_marker]},
        },
        idempotency_key=f"core-save-episode:{canonical_marker}",
    )
    canonical_result = _require_ok(canonical_payload, step="core save_episode")
    _record_operation_id(state, canonical_payload)

    fact_group_id = canonical_result["fact_group_id"]
    fact_version_id = canonical_result["fact_version_id"]

    get_fact_payload = _tool_call(
        context,
        token=token,
        request_id="core-get-fact",
        tool_name="viberecall_get_fact",
        arguments={"fact_group_id": fact_group_id},
    )
    get_fact_result = _require_ok(get_fact_payload, step="core get_fact")
    if get_fact_result["current"]["fact_version_id"] != fact_version_id:
        raise SmokeFailure(f"core get_fact returned the wrong fact version: {get_fact_payload}")

    search_memory_payload = _tool_call(
        context,
        token=token,
        request_id="core-search-memory",
        tool_name="viberecall_search_memory",
        arguments={"query": canonical_marker, "limit": 10},
    )
    search_memory_result = _require_ok(search_memory_payload, step="core search_memory")
    if fact_group_id not in {item.get("fact_group_id") for item in search_memory_result["facts"]}:
        raise SmokeFailure(f"core search_memory did not return the canonical fact: {search_memory_payload}")

    pin_payload = _tool_call(
        context,
        token=token,
        request_id="core-pin-memory",
        tool_name="viberecall_pin_memory",
        arguments={"target_kind": "FACT", "target_id": fact_group_id, "pin_action": "PIN"},
    )
    pin_result = _require_ok(pin_payload, step="core pin_memory")
    if pin_result["resolved_target"]["fact_group_id"] != fact_group_id:
        raise SmokeFailure(f"core pin_memory resolved the wrong fact group: {pin_payload}")

    pinned_fact_payload = _tool_call(
        context,
        token=token,
        request_id="core-get-fact-pinned",
        tool_name="viberecall_get_fact",
        arguments={"fact_group_id": fact_group_id},
    )
    pinned_fact_result = _require_ok(pinned_fact_payload, step="core get_fact(after pin)")
    if pinned_fact_result["current"]["salience_class"] != "PINNED":
        raise SmokeFailure(f"core get_fact did not reflect the pinned salience state: {pinned_fact_payload}")

    wm_task_id = f"task-{canonical_marker}"
    wm_session_id = f"session-{canonical_marker}"
    wm_patch_payload = _tool_call(
        context,
        token=token,
        request_id="core-working-memory-patch",
        tool_name="viberecall_working_memory_patch",
        arguments={
            "task_id": wm_task_id,
            "session_id": wm_session_id,
            "patch": {"plan": ["verify smoke", "check memory"], "active_constraints": {"profile": "core"}},
            "checkpoint_note": "core smoke checkpoint",
        },
    )
    _require_ok(wm_patch_payload, step="core working_memory_patch")

    wm_get_payload = _tool_call(
        context,
        token=token,
        request_id="core-working-memory-get",
        tool_name="viberecall_working_memory_get",
        arguments={"task_id": wm_task_id, "session_id": wm_session_id},
    )
    wm_get_result = _require_ok(wm_get_payload, step="core working_memory_get")
    if wm_get_result["state"]["active_constraints"]["profile"] != "core":
        raise SmokeFailure(f"core working_memory_get returned the wrong state: {wm_get_payload}")

    legacy_marker = _core_marker(config, "legacy")
    save_payload = _tool_call(
        context,
        token=token,
        request_id="core-save",
        tool_name="viberecall_save",
        arguments={
            "content": f"{config.query} legacy marker {legacy_marker}",
            "metadata": {"type": "deploy-smoke", "tags": [legacy_marker], "files": ["ops/vercel-digitalocean-public-ga.md"]},
        },
        idempotency_key=f"core-save:{legacy_marker}",
    )
    save_result = _require_ok(save_payload, step="core save")
    _record_operation_id(state, save_payload)

    search_payload = _tool_call(
        context,
        token=token,
        request_id="core-search",
        tool_name="viberecall_search",
        arguments={"query": legacy_marker, "limit": 10},
    )
    search_result = _require_ok(search_payload, step="core search")
    fact_result = next((item for item in search_result["results"] if item.get("kind") == "fact"), None)
    if fact_result is None:
        raise SmokeFailure(f"core search did not return a fact result: {search_payload}")

    facts_payload = _tool_call(
        context,
        token=token,
        request_id="core-get-facts",
        tool_name="viberecall_get_facts",
        arguments={"filters": {"tag": legacy_marker}, "limit": 20},
    )
    facts_result = _require_ok(facts_payload, step="core get_facts")
    if not facts_result["facts"]:
        raise SmokeFailure(f"core get_facts returned no facts: {facts_payload}")

    update_payload = _tool_call(
        context,
        token=token,
        request_id="core-update-fact",
        tool_name="viberecall_update_fact",
        arguments={
            "fact_id": fact_result["fact"]["id"],
            "new_text": f"{config.query} legacy marker {legacy_marker} updated",
            "effective_time": "2026-03-08T12:00:00Z",
            "reason": "deployed smoke coverage",
        },
        idempotency_key=f"core-update:{legacy_marker}",
    )
    _require_ok(update_payload, step="core update_fact")
    _record_operation_id(state, update_payload)

    timeline_payload = _tool_call(
        context,
        token=token,
        request_id="core-timeline",
        tool_name="viberecall_timeline",
        arguments={"limit": 20},
    )
    timeline_result = _require_ok(timeline_payload, step="core timeline")
    if save_result["episode_id"] not in {item.get("episode_id") for item in timeline_result["episodes"]}:
        raise SmokeFailure(f"core timeline did not include the saved episode: {timeline_payload}")

    delete_payload = _tool_call(
        context,
        token=token,
        request_id="core-delete",
        tool_name="viberecall_delete_episode",
        arguments={"episode_id": save_result["episode_id"]},
    )
    delete_result = _require_ok(delete_payload, step="core delete_episode")
    if delete_result["status"] not in {"DELETED", "NOT_FOUND"}:
        raise SmokeFailure(f"core delete_episode returned an unexpected status: {delete_payload}")

    state["canonical"] = {"fact_group_id": fact_group_id, "fact_version_id": fact_version_id}
    state["legacy"] = {"episode_id": save_result["episode_id"], "fact_id": fact_result["fact"]["id"]}
    return {
        "fact_group_id": fact_group_id,
        "fact_version_id": fact_version_id,
        "deleted_episode_id": save_result["episode_id"],
    }


def run_ops_profile(context: SmokeContext, *, token: str, config: SmokeConfig, state: dict[str, Any]) -> dict[str, Any]:
    available_tools = list_tools(context, token)
    ensure_profile_tools_available("ops", available_tools)

    status_payload = _tool_call(
        context,
        token=token,
        request_id="ops-status",
        tool_name="viberecall_get_status",
        arguments={},
    )
    status_result = _require_ok(status_payload, step="ops get_status")

    operation_id = next(iter(state.get("operation_ids", [])), None)
    if operation_id is None:
        if "viberecall_save_episode" not in available_tools:
            raise SmokeFailure("ops profile needs an existing operation id or a token that can call viberecall_save_episode")
        marker = _core_marker(config, "ops")
        seed_payload = _tool_call(
            context,
            token=token,
            request_id="ops-seed-save-episode",
            tool_name="viberecall_save_episode",
            arguments={
                "content": f"{config.query} ops marker {marker}",
                "metadata": {"type": "deploy-smoke", "tags": [marker]},
            },
            idempotency_key=f"ops-save-episode:{marker}",
        )
        seed_result = _require_ok(seed_payload, step="ops seed save_episode")
        operation_id = seed_result["operation_id"]
        state.setdefault("operation_ids", []).append(operation_id)

    operation_payload = _tool_call(
        context,
        token=token,
        request_id="ops-get-operation",
        tool_name="viberecall_get_operation",
        arguments={"operation_id": operation_id},
    )
    operation_result = _require_ok(operation_payload, step="ops get_operation")
    if operation_result["operation"]["operation_id"] != operation_id:
        raise SmokeFailure(f"ops get_operation returned the wrong operation: {operation_payload}")

    return {
        "status": status_result["status"],
        "operation_id": operation_id,
        "operation_status": operation_result["operation"]["status"],
    }


def run_graph_profile(context: SmokeContext, *, token: str, config: SmokeConfig, state: dict[str, Any]) -> dict[str, Any]:
    available_tools = list_tools(context, token)
    ensure_profile_tools_available("graph", available_tools)
    if "viberecall_save_episode" not in available_tools:
        raise SmokeFailure("graph profile requires a token that can call viberecall_save_episode for seed data")

    marker = _core_marker(config, "graph")
    service_tag = f"{marker}-service"
    session_tag = f"{marker}-session"
    saved_results: list[dict[str, Any]] = []
    for request_id, tag in [("graph-save-1", service_tag), ("graph-save-2", session_tag)]:
        payload = _tool_call(
            context,
            token=token,
            request_id=request_id,
            tool_name="viberecall_save_episode",
            arguments={"content": f"Track tag {tag}", "metadata": {"tags": [tag]}},
            idempotency_key=f"{request_id}:{marker}",
        )
        saved_results.append(_require_ok(payload, step=f"{request_id} save_episode"))
        _record_operation_id(state, payload)

    search_payload = _tool_call(
        context,
        token=token,
        request_id="graph-search-entities",
        tool_name="viberecall_search_entities",
        arguments={"query": marker, "entity_kinds": ["Tag"], "limit": 10},
    )
    search_result = _require_ok(search_payload, step="graph search_entities")
    if not search_result["entities"]:
        raise SmokeFailure(f"graph search_entities returned no entities: {search_payload}")

    service_resolve_payload = _tool_call(
        context,
        token=token,
        request_id="graph-resolve-service",
        tool_name="viberecall_resolve_reference",
        arguments={"mention_text": service_tag, "observed_kind": "Tag", "limit": 5},
    )
    service_resolve_result = _require_ok(service_resolve_payload, step="graph resolve_reference(service)")
    service_entity_id = service_resolve_result["best_match"]["entity_id"]

    session_resolve_payload = _tool_call(
        context,
        token=token,
        request_id="graph-resolve-session",
        tool_name="viberecall_resolve_reference",
        arguments={"mention_text": session_tag, "observed_kind": "Tag", "limit": 5},
    )
    session_resolve_result = _require_ok(session_resolve_payload, step="graph resolve_reference(session)")
    session_entity_id = session_resolve_result["best_match"]["entity_id"]

    neighbors_payload = _tool_call(
        context,
        token=token,
        request_id="graph-get-neighbors",
        tool_name="viberecall_get_neighbors",
        arguments={"entity_id": service_entity_id, "direction": "BOTH", "limit": 10},
    )
    neighbors_result = _require_ok(neighbors_payload, step="graph get_neighbors")
    if neighbors_result["anchor"]["entity_id"] != service_entity_id:
        raise SmokeFailure(f"graph get_neighbors returned the wrong anchor: {neighbors_payload}")

    find_paths_payload = _tool_call(
        context,
        token=token,
        request_id="graph-find-paths",
        tool_name="viberecall_find_paths",
        arguments={"src_entity_id": service_entity_id, "dst_entity_id": session_entity_id, "max_depth": 2, "limit_paths": 5},
    )
    find_paths_result = _require_ok(find_paths_payload, step="graph find_paths")
    if "paths" not in find_paths_result:
        raise SmokeFailure(f"graph find_paths did not return a paths payload: {find_paths_payload}")

    explain_payload = _tool_call(
        context,
        token=token,
        request_id="graph-explain-fact",
        tool_name="viberecall_explain_fact",
        arguments={"fact_version_id": saved_results[0]["fact_version_id"]},
    )
    explain_result = _require_ok(explain_payload, step="graph explain_fact")
    if explain_result["fact"]["fact_version_id"] != saved_results[0]["fact_version_id"]:
        raise SmokeFailure(f"graph explain_fact returned the wrong fact: {explain_payload}")

    state["graph"] = {
        "service_entity_id": service_entity_id,
        "session_entity_id": session_entity_id,
        "service_tag": service_tag,
        "session_tag": session_tag,
    }
    return {
        "entity_ids": [service_entity_id, session_entity_id],
        "search_entity_count": len(search_result["entities"]),
        "path_count": len(find_paths_result["paths"]),
    }


def _poll_index_ready(
    context: SmokeContext,
    *,
    token: str,
    index_run_id: str,
    timeout_seconds: int,
    poll_interval_seconds: float,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_payload: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        payload = _tool_call(
            context,
            token=token,
            request_id="index-get-index-status",
            tool_name="viberecall_get_index_status",
            arguments={"index_run_id": index_run_id},
        )
        result = _require_ok(payload, step="index get_index_status")
        last_payload = result
        status = str(result["status"]).upper()
        if status == "READY":
            return result
        if status in {"FAILED", "CANCELED"}:
            raise SmokeFailure(f"index profile failed while waiting for readiness: {payload}")
        time.sleep(poll_interval_seconds)
    raise SmokeFailure(f"index profile timed out waiting for READY status: {last_payload}")


def run_index_profile(context: SmokeContext, *, token: str, config: SmokeConfig, state: dict[str, Any]) -> dict[str, Any]:
    ensure_profile_tools_available("index", list_tools(context, token))
    if config.index_repo_source is None:
        raise SmokeFailure("index profile is missing repository source configuration")

    marker = _core_marker(config, "index")
    index_payload = _tool_call(
        context,
        token=token,
        request_id="index-run",
        tool_name="viberecall_index_repo",
        arguments={
            "repo_source": config.index_repo_source,
            "mode": "FULL_SNAPSHOT",
            "idempotency_key": f"index-run:{marker}",
        },
        idempotency_key=f"index-run:{marker}",
    )
    index_result = _require_ok(index_payload, step="index index_repo")
    if index_result.get("accepted") is not True:
        raise SmokeFailure(f"index profile did not get an accepted index run: {index_payload}")

    index_run_id = index_result["index_run_id"]
    ready_result = _poll_index_ready(
        context,
        token=token,
        index_run_id=index_run_id,
        timeout_seconds=config.index_timeout_seconds,
        poll_interval_seconds=config.poll_interval_seconds,
    )

    legacy_status_payload = _tool_call(
        context,
        token=token,
        request_id="index-legacy-status",
        tool_name="viberecall_index_status",
        arguments={"index_run_id": index_run_id},
    )
    legacy_status_result = _require_ok(legacy_status_payload, step="index index_status")
    if str(legacy_status_result["status"]).upper() != "READY":
        raise SmokeFailure(f"index legacy status did not report READY: {legacy_status_payload}")

    context_pack_payload = _tool_call(
        context,
        token=token,
        request_id="index-context-pack",
        tool_name="viberecall_get_context_pack",
        arguments={"query": config.query, "limit": 8},
    )
    context_pack_result = _require_ok(context_pack_payload, step="index get_context_pack")
    if str(context_pack_result["status"]).upper() != "READY":
        raise SmokeFailure(f"index context pack did not return READY: {context_pack_payload}")

    state["index_run_id"] = index_run_id
    return {
        "index_run_id": index_run_id,
        "status": ready_result["status"],
        "context_mode": context_pack_result.get("context_mode"),
    }


def run_resolution_profile(context: SmokeContext, *, token: str, config: SmokeConfig, state: dict[str, Any]) -> dict[str, Any]:
    available_tools = list_tools(context, token)
    ensure_profile_tools_available("resolution", available_tools)
    for setup_tool in ("viberecall_save_episode", "viberecall_resolve_reference", "viberecall_get_operation"):
        if setup_tool not in available_tools:
            raise SmokeFailure(f"resolution profile requires setup tool '{setup_tool}' to be visible for the token")

    marker = _core_marker(config, "resolution")
    target_tag = f"{marker}-service"
    source_tag = f"{marker}-api"
    split_source_tag = f"{marker}-session"

    for request_id, tag in [
        ("resolution-save-target", target_tag),
        ("resolution-save-source", source_tag),
        ("resolution-save-split-source", split_source_tag),
    ]:
        payload = _tool_call(
            context,
            token=token,
            request_id=request_id,
            tool_name="viberecall_save_episode",
            arguments={"content": f"Track tag {tag}", "metadata": {"tags": [tag]}},
            idempotency_key=f"{request_id}:{marker}",
        )
        _require_ok(payload, step=f"{request_id} save_episode")
        _record_operation_id(state, payload)

    merge_payload = _tool_call(
        context,
        token=token,
        request_id="resolution-merge",
        tool_name="viberecall_merge_entities",
        arguments={
            "target_entity_id": f"tag::{target_tag}",
            "source_entity_ids": [f"tag::{source_tag}"],
            "reason": "deployed smoke merge validation",
        },
    )
    merge_result = _require_ok(merge_payload, step="resolution merge_entities")
    merge_operation_id = merge_result["operation_id"]
    state.setdefault("operation_ids", []).append(merge_operation_id)

    merge_operation_payload = _tool_call(
        context,
        token=token,
        request_id="resolution-merge-operation",
        tool_name="viberecall_get_operation",
        arguments={"operation_id": merge_operation_id},
    )
    merge_operation_result = _require_ok(merge_operation_payload, step="resolution get_operation(merge)")
    if merge_operation_result["operation"]["operation_id"] != merge_operation_id:
        raise SmokeFailure(f"resolution merge operation lookup returned the wrong operation: {merge_operation_payload}")

    resolve_alias_payload = _tool_call(
        context,
        token=token,
        request_id="resolution-resolve-old-alias",
        tool_name="viberecall_resolve_reference",
        arguments={"mention_text": source_tag, "observed_kind": "Tag", "limit": 5},
    )
    resolve_alias_result = _require_ok(resolve_alias_payload, step="resolution resolve_reference(after merge)")
    if resolve_alias_result["best_match"]["entity_id"] != f"tag::{target_tag}":
        raise SmokeFailure(f"resolution merge did not redirect the old alias: {resolve_alias_payload}")

    split_payload = _tool_call(
        context,
        token=token,
        request_id="resolution-split",
        tool_name="viberecall_split_entity",
        arguments={
            "source_entity_id": f"tag::{split_source_tag}",
            "reason": "deployed smoke split validation",
            "partitions": [
                {
                    "new_entity": {
                        "entity_kind": "Tag",
                        "canonical_name": f"{split_source_tag}-core",
                    },
                    "alias_values": [split_source_tag],
                    "fact_bindings": [],
                }
            ],
        },
    )
    split_result = _require_ok(split_payload, step="resolution split_entity")
    if not split_result["created_entity_ids"]:
        raise SmokeFailure(f"resolution split did not create a new entity: {split_payload}")

    split_operation_payload = _tool_call(
        context,
        token=token,
        request_id="resolution-split-operation",
        tool_name="viberecall_get_operation",
        arguments={"operation_id": split_result["operation_id"]},
    )
    _require_ok(split_operation_payload, step="resolution get_operation(split)")

    split_resolve_payload = _tool_call(
        context,
        token=token,
        request_id="resolution-resolve-split-alias",
        tool_name="viberecall_resolve_reference",
        arguments={"mention_text": split_source_tag, "observed_kind": "Tag", "limit": 5},
    )
    split_resolve_result = _require_ok(split_resolve_payload, step="resolution resolve_reference(after split)")
    if split_resolve_result["best_match"]["entity_id"] not in set(split_result["created_entity_ids"]):
        raise SmokeFailure(f"resolution split did not move the alias to a created entity: {split_resolve_payload}")

    return {
        "merge_operation_id": merge_operation_id,
        "split_operation_id": split_result["operation_id"],
        "created_entity_ids": split_result["created_entity_ids"],
    }


PROFILE_RUNNERS = {
    "core": run_core_profile,
    "ops": run_ops_profile,
    "graph": run_graph_profile,
    "index": run_index_profile,
    "resolution": run_resolution_profile,
}


def _profile_tokens_from_args(args: argparse.Namespace) -> dict[str, str]:
    tokens: dict[str, str] = {}
    for profile_name in SMOKE_PROFILE_DEFINITIONS:
        token_value = getattr(args, f"{profile_name}_token")
        if token_value:
            tokens[profile_name] = token_value
    return tokens


def build_config_from_args(args: argparse.Namespace) -> SmokeConfig:
    return SmokeConfig(
        profiles=resolve_profile_names(args.profile),
        shared_token=args.token,
        profile_tokens=_profile_tokens_from_args(args),
        query=args.query,
        tag=args.tag,
        index_repo_source=build_index_repo_source(
            repo_url=args.index_repo_url,
            ref=args.index_ref,
            repo_name=args.index_repo_name,
        )
        if "index" in resolve_profile_names(args.profile)
        else None,
        index_timeout_seconds=args.index_timeout_seconds,
        poll_interval_seconds=args.poll_interval_seconds,
    )


def run_smoke(context: SmokeContext, config: SmokeConfig) -> dict[str, Any]:
    initialize_session(context)

    state: dict[str, Any] = {"operation_ids": []}
    profile_results: dict[str, Any] = {}
    for profile_name in config.profiles:
        token = resolve_profile_token(
            profile_name,
            shared_token=config.shared_token,
            profile_tokens=config.profile_tokens,
        )
        profile_results[profile_name] = PROFILE_RUNNERS[profile_name](
            context,
            token=token,
            config=config,
            state=state,
        )

    return {
        "ok": True,
        "base_url": context.base_url,
        "project_id": context.project_id,
        "session_id": context.session_id,
        "profiles": config.profiles,
        "profile_results": profile_results,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = build_config_from_args(args)
    context = SmokeContext(base_url=args.base_url, project_id=args.project_id)
    result = run_smoke(context, config)
    print(json.dumps(result, indent=2))
    return 0
