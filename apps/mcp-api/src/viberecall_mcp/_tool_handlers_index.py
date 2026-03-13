from __future__ import annotations

from viberecall_mcp.auth import AuthenticatedToken

import viberecall_mcp.tool_handlers as root


async def handle_index_repo(
    *,
    request_id: str,
    project_id: str,
    token: AuthenticatedToken,
    arguments: dict,
) -> dict:
    root.ensure_plan_access(token, "viberecall_index_repo")
    root.ensure_scope(token, "index:run")
    await root.enforce_rate_limit(token, project_id, "viberecall_index_repo")

    mode = root._normalize_full_snapshot_mode(arguments.get("mode"))
    repo_source = root.normalize_repo_source(arguments.get("repo_source") or {})

    session = arguments["session"]
    request = await root.request_index_repo(
        session=session,
        project_id=project_id,
        repo_source=repo_source,
        mode=mode,
        max_files=int(arguments.get("max_files", 5000)),
        requested_by_token_id=token.token_id,
        commit=False,
    )
    operation_id = root.new_id("op")
    await root.create_operation(
        session,
        operation_id=operation_id,
        project_id=project_id,
        token_id=token.token_id,
        request_id=request_id,
        kind="index_repo",
        resource_type="index",
        resource_id=str(request["index_run_id"]),
        metadata={"repo_source": request["repo_source"]},
    )
    await root.create_outbox_event(
        session,
        event_id=root.new_id("evt"),
        operation_id=operation_id,
        project_id=project_id,
        event_type="index_repo.run",
        payload={
            "index_id": str(request["index_run_id"]),
            "request_id": request_id,
            "token_id": token.token_id,
        },
    )
    await session.commit()
    await root.dispatch_outbox_events(session, operation_id=operation_id, limit=1)
    operation = await root.get_operation_record(session, project_id=project_id, operation_id=operation_id)
    return root.build_output_envelope(
        request_id=request_id,
        ok=True,
        result={
            "accepted": True,
            "index_run_id": request["index_run_id"],
            "operation_id": operation_id,
            "job_id": (operation or {}).get("job_id"),
            "project_id": request["project_id"],
            "repo_source": request["repo_source"],
            "mode": request["mode"],
            "queued_at": request["queued_at"],
        },
    )


async def handle_index_status(
    *,
    tool_name: str,
    request_id: str,
    project_id: str,
    token: AuthenticatedToken,
    arguments: dict,
) -> dict:
    root.ensure_plan_access(token, tool_name)
    root.ensure_scope(token, "index:read")
    await root.enforce_rate_limit(token, project_id, tool_name)

    return root.build_output_envelope(
        request_id=request_id,
        ok=True,
        result=await root.index_status(
            session=arguments["session"],
            project_id=project_id,
            index_run_id=str(arguments.get("index_run_id") or "").strip() or None,
        ),
    )


async def handle_get_context_pack(
    *,
    request_id: str,
    project_id: str,
    token: AuthenticatedToken,
    arguments: dict,
) -> dict:
    root.ensure_plan_access(token, "viberecall_get_context_pack")
    root.ensure_scope(token, "index:read")
    await root.enforce_rate_limit(token, project_id, "viberecall_get_context_pack")

    query = str(arguments["query"])
    limit = int(arguments.get("limit", 12))
    requested_scope, scope_applied = root._resolve_memory_scope(arguments)
    context = await root.build_context_pack(
        session=arguments["session"],
        project_id=project_id,
        query=query,
        limit=limit,
    )
    has_ready_index = str(context.get("status") or "") == "READY"

    fallback_fact_results: list[dict] = []
    fallback_entity_rows: list[dict] = []
    if not has_ready_index:
        fallback_fact_results = [
            item
            for item in await root.search_canonical_memory(
                arguments["session"],
                project_id=project_id,
                query=query,
                filters=None,
                sort="RELEVANCE",
                limit=max(limit * 3, 25),
                offset=0,
            )
            if item.get("kind") == "fact"
        ][:limit]
        fallback_entity_rows = list(
            (
                await root.search_canonical_entities(
                    arguments["session"],
                    project_id=project_id,
                    query=query,
                    entity_kinds=None,
                    salience_classes=None,
                    limit=max(limit, 1),
                )
            ).get("entities")
            or []
        )[:limit]

    timeline_rows = await root.list_timeline_episodes(
        arguments["session"],
        project_id=project_id,
        from_time=None,
        to_time=None,
        limit=max(limit * 5, 50),
        offset=0,
    )
    matched_timeline = sorted(
        [row for row in timeline_rows if root._match_query_in_episode(query=query, episode=row)],
        key=root._episode_context_sort_key,
        reverse=True,
    )[:limit]
    facts_timeline = [
        {
            "episode_id": row["episode_id"],
            "reference_time": row.get("reference_time"),
            "ingested_at": row.get("ingested_at"),
            "summary": row.get("summary"),
            "metadata": row.get("metadata") or {},
            "salience_score": row.get("salience_score"),
            "salience_class": row.get("salience_class"),
            "citation_id": f"episode:{row['episode_id']}",
        }
        for row in matched_timeline
    ]

    citations = list(context.get("citations") or [])
    citations.extend(
        [
            {
                "citation_id": str((item.get("fact") or {}).get("fact_version_id") or ""),
                "source_type": "canonical_fact",
                "fact_version_id": (item.get("fact") or {}).get("fact_version_id"),
                "fact_group_id": (item.get("fact") or {}).get("fact_group_id"),
                "statement": (item.get("fact") or {}).get("statement") or (item.get("fact") or {}).get("text"),
                "valid_at": (item.get("fact") or {}).get("valid_at"),
                "score": item.get("score"),
            }
            for item in fallback_fact_results
            if (item.get("fact") or {}).get("fact_version_id")
        ]
    )
    citations.extend(
        [
            {
                "citation_id": f"episode:{row['episode_id']}",
                "source_type": "timeline_episode",
                "episode_id": row["episode_id"],
                "reference_time": row.get("reference_time"),
                "summary": row.get("summary"),
                "salience_score": row.get("salience_score"),
                "salience_class": row.get("salience_class"),
            }
            for row in matched_timeline
        ]
    )
    context["citations"] = citations
    context["facts_timeline"] = facts_timeline
    code_anchors = [item for item in citations if item.get("source_type") == "code_chunk"]
    expanded_entities = [root._entity_payload(item) for item in (context.get("relevant_symbols") or [])[:limit]]
    if not expanded_entities and fallback_fact_results:
        expanded_entities = root._expanded_entities_from_page(fallback_fact_results, limit=max(limit, 1))
    if not expanded_entities and fallback_entity_rows:
        expanded_entities = [root._entity_payload(item) for item in fallback_entity_rows[:limit]]

    if has_ready_index:
        context.setdefault("context_mode", "code_augmented")
        context.setdefault("index_status", "READY")
        context.setdefault("index_hint", None)
    else:
        has_memory_fallback = bool(fallback_fact_results or facts_timeline or expanded_entities)
        context["status"] = "READY" if has_memory_fallback else "EMPTY"
        context["context_mode"] = "memory_only" if has_memory_fallback else "empty"
        context["index_status"] = "MISSING"
        context["index_hint"] = {
            "recommended": True,
            "tool": "viberecall_index_repo",
            "reason": "No READY code index snapshot is available for this project.",
        }
        context["architecture_overview"] = (
            f"Memory-only context for this query: {len(fallback_fact_results)} relevant facts, "
            f"{len(facts_timeline)} timeline episodes, and {len(expanded_entities)} matched entities. "
            "Run viberecall_index_repo for architecture and code citations."
            if has_memory_fallback
            else None
        )
        context["related_modules"] = []
        context["related_files"] = []

    gaps = list(context.get("gaps") or [])
    if not has_ready_index:
        gaps.append("No READY code index snapshot; context pack is memory-only until viberecall_index_repo completes.")
    context["gaps"] = gaps

    working_memory = None
    task_id = arguments.get("task_id")
    session_id = arguments.get("session_id")
    if task_id and session_id:
        working_memory = root._working_memory_response(
            await root.get_working_memory(
                arguments["session"],
                project_id=project_id,
                task_id=str(task_id),
                session_id=str(session_id),
            ),
            task_id=str(task_id),
            session_id=str(session_id),
        )
    context["scope_requested"] = requested_scope
    context["scope_applied"] = scope_applied
    context["code_anchors"] = code_anchors
    context["decision_history"] = facts_timeline
    context["reasoning_graph"] = {
        "query": query,
        "expanded_entities": expanded_entities,
        "anchor_count": len(code_anchors),
    }
    context["working_memory_patch"] = root._working_memory_patch_from_context(
        query=query,
        scope_applied=scope_applied,
        citations=code_anchors,
        facts_timeline=facts_timeline,
        expanded_entities=expanded_entities,
    )
    if working_memory is not None:
        context["working_memory"] = working_memory

    return root.build_output_envelope(
        request_id=request_id,
        ok=True,
        result=context,
    )
