from __future__ import annotations

import argparse
import json
import sys
import uuid
from dataclasses import dataclass
from typing import Any
from urllib import error, request


DEFAULT_PROTOCOL_VERSION = "2025-06-18"


class SmokeFailure(RuntimeError):
    """Raised when the deployed MCP smoke flow fails."""


@dataclass(slots=True)
class SmokeContext:
    base_url: str
    project_id: str
    token: str
    session_id: str | None = None

    @property
    def endpoint(self) -> str:
        return f"{self.base_url.rstrip('/')}/p/{self.project_id}/mcp"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke test a deployed VibeRecall MCP endpoint.")
    parser.add_argument("--base-url", required=True, help="Public MCP base URL, for example https://api.example.com")
    parser.add_argument("--project-id", required=True, help="Project identifier bound to the MCP token")
    parser.add_argument("--token", required=True, help="Plaintext MCP token for the target project")
    parser.add_argument(
        "--query",
        default="production smoke test",
        help="Search query used for retrieval checks",
    )
    parser.add_argument(
        "--tag",
        default="deploy-smoke",
        help="Tag written into the temporary smoke episode metadata",
    )
    return parser.parse_args()


def _decode_payload(response, body: bytes) -> dict[str, Any]:
    content_type = response.headers.get("content-type", "")
    text = body.decode("utf-8")
    if content_type.startswith("text/event-stream"):
        for line in text.splitlines():
            if line.startswith("data: "):
                return json.loads(line.removeprefix("data: "))
        raise SmokeFailure("SSE response did not include a data frame")
    return json.loads(text)


def _post_json(
    context: SmokeContext,
    payload: dict[str, Any],
    *,
    include_auth: bool,
    extra_headers: dict[str, str] | None = None,
) -> tuple[dict[str, Any], Any]:
    headers = {
        "accept": "application/json, text/event-stream",
        "content-type": "application/json",
    }
    if context.session_id:
        headers["mcp-session-id"] = context.session_id
    if include_auth:
        headers["authorization"] = f"Bearer {context.token}"
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
            body = response.read()
            return _decode_payload(response, body), response
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SmokeFailure(f"HTTP {exc.code} from MCP endpoint: {body}") from exc
    except error.URLError as exc:
        raise SmokeFailure(f"Could not reach MCP endpoint: {exc}") from exc


def _tool_call(
    context: SmokeContext,
    *,
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


def list_tools(context: SmokeContext) -> list[str]:
    payload, _ = _post_json(
        context,
        {"jsonrpc": "2.0", "id": "smoke-tools", "method": "tools/list", "params": {}},
        include_auth=True,
    )
    try:
        return [tool["name"] for tool in payload["result"]["tools"]]
    except (KeyError, TypeError) as exc:
        raise SmokeFailure(f"Unexpected tools/list payload: {payload}") from exc


def main() -> int:
    args = parse_args()
    context = SmokeContext(base_url=args.base_url, project_id=args.project_id, token=args.token)

    initialize_session(context)
    tool_names = list_tools(context)
    required_tools = {
        "viberecall_save",
        "viberecall_search",
        "viberecall_get_facts",
        "viberecall_update_fact",
        "viberecall_timeline",
        "viberecall_get_status",
        "viberecall_delete_episode",
    }
    missing_tools = sorted(required_tools.difference(tool_names))
    if missing_tools:
        raise SmokeFailure(f"Missing expected tools: {', '.join(missing_tools)}")

    status_payload = _tool_call(
        context,
        request_id="smoke-status",
        tool_name="viberecall_get_status",
        arguments={},
    )
    if status_payload.get("ok") is not True:
        raise SmokeFailure(f"Status check failed: {status_payload}")

    marker = str(uuid.uuid4())
    content = f"{args.query} marker {marker}"
    save_payload = _tool_call(
        context,
        request_id="smoke-save",
        tool_name="viberecall_save",
        arguments={
            "content": content,
            "metadata": {
                "type": "deploy-smoke",
                "tags": [args.tag],
                "files": ["ops/vercel-render-public-ga.md"],
            },
        },
        idempotency_key=f"deploy-smoke-save:{marker}",
    )
    if save_payload.get("ok") is not True:
        raise SmokeFailure(f"Save failed: {save_payload}")
    episode_id = save_payload["result"]["episode_id"]

    timeline_payload = _tool_call(
        context,
        request_id="smoke-timeline",
        tool_name="viberecall_timeline",
        arguments={"limit": 10},
    )
    if timeline_payload.get("ok") is not True:
        raise SmokeFailure(f"Timeline failed: {timeline_payload}")
    if episode_id not in {item.get("episode_id") for item in timeline_payload["result"]["episodes"]}:
        raise SmokeFailure(f"Timeline did not include the saved smoke episode: {timeline_payload}")

    search_payload = _tool_call(
        context,
        request_id="smoke-search",
        tool_name="viberecall_search",
        arguments={"query": content, "limit": 10},
    )
    if search_payload.get("ok") is not True:
        raise SmokeFailure(f"Search failed: {search_payload}")
    fact_result = next(
        (item for item in search_payload["result"]["results"] if item.get("kind") == "fact"),
        None,
    )
    if fact_result is None:
        raise SmokeFailure(f"Search did not return a fact result for the smoke marker: {search_payload}")
    fact_id = fact_result["fact"]["id"]

    facts_payload = _tool_call(
        context,
        request_id="smoke-facts",
        tool_name="viberecall_get_facts",
        arguments={"filters": {"tag": args.tag}, "limit": 20},
    )
    if facts_payload.get("ok") is not True or not facts_payload["result"]["facts"]:
        raise SmokeFailure(f"Get facts failed: {facts_payload}")

    update_payload = _tool_call(
        context,
        request_id="smoke-update",
        tool_name="viberecall_update_fact",
        arguments={
            "fact_id": fact_id,
            "new_text": f"{content} updated",
            "effective_time": "2026-03-08T12:00:00Z",
            "reason": "deployed smoke coverage",
        },
        idempotency_key=f"deploy-smoke-update:{marker}",
    )
    if update_payload.get("ok") is not True:
        raise SmokeFailure(f"Update fact failed: {update_payload}")

    delete_payload = _tool_call(
        context,
        request_id="smoke-delete",
        tool_name="viberecall_delete_episode",
        arguments={"episode_id": episode_id},
    )
    if delete_payload.get("ok") is not True or delete_payload["result"]["status"] not in {"DELETED", "NOT_FOUND"}:
        raise SmokeFailure(f"Delete episode failed: {delete_payload}")

    print(
        json.dumps(
            {
                "ok": True,
                "base_url": context.base_url,
                "project_id": context.project_id,
                "session_id": context.session_id,
                "tool_count": len(tool_names),
                "deleted_episode_id": episode_id,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SmokeFailure as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
