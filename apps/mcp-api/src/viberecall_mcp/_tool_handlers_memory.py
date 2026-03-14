from __future__ import annotations

from viberecall_mcp.auth import AuthenticatedToken

import viberecall_mcp.tool_handlers as root


async def handle_save(
    *,
    tool_name: str,
    request_id: str,
    project_id: str,
    token: AuthenticatedToken,
    arguments: dict,
    payload_hash: str,
    idempotency_key: str | None,
) -> dict:
    root.ensure_plan_access(token, tool_name)
    root.ensure_scope(token, "memory:write")
    replay = await root.maybe_replay_idempotent_response(
        tool_name=tool_name,
        project_id=project_id,
        idempotency_key=idempotency_key,
        payload_hash=payload_hash,
    )
    if replay is not None:
        return replay

    await root.enforce_rate_limit(token, project_id, tool_name)
    await root.enforce_quota(
        session=arguments["session"],
        token=token,
        project_id=project_id,
        tool_name=tool_name,
        arguments=arguments,
    )

    await root.claim_idempotency_slot(
        tool_name=tool_name,
        project_id=project_id,
        idempotency_key=idempotency_key,
    )

    episode_id = root.new_id("ep")
    operation_id = root.new_id("op")
    content = str(arguments["content"])
    content_ref: str | None = None
    inline_content: str | None = content
    summary: str | None = None
    if len(content.encode("utf-8")) > root.settings.raw_episode_inline_max_bytes:
        content_ref = root.episode_storage_key(project_id, episode_id)
        try:
            await root.put_text(object_key=content_ref, content=content)
        except root.ObjectStorageError as exc:
            raise root.ToolRuntimeError(
                "UPSTREAM_ERROR",
                "Failed to store large episode content",
                {"reason": str(exc)},
            ) from exc
        inline_content = None
        summary = content[:160].strip() or None

    try:
        await root.create_episode(
            session=arguments["session"],
            episode_id=episode_id,
            project_id=project_id,
            content=inline_content,
            content_ref=content_ref,
            summary=summary,
            reference_time=arguments.get("reference_time"),
            metadata_json=root.json.dumps(arguments.get("metadata") or {}),
            job_id=None,
            enrichment_status="pending",
            commit=False,
        )
        canonical_result = await root.save_canonical_episode(
            arguments["session"],
            project_id=project_id,
            episode_id=episode_id,
            content=content,
            reference_time=arguments.get("reference_time"),
            metadata=arguments.get("metadata") or {},
        )
        await root.create_operation(
            arguments["session"],
            operation_id=operation_id,
            project_id=project_id,
            token_id=token.token_id,
            request_id=request_id,
            kind="save",
            resource_type="episode",
            resource_id=episode_id,
            metadata={"reference_time": arguments.get("reference_time")},
        )
        await root.create_outbox_event(
            arguments["session"],
            event_id=root.new_id("evt"),
            operation_id=operation_id,
            project_id=project_id,
            event_type="save.ingest",
            payload={
                "episode_id": episode_id,
                "request_id": request_id,
                "token_id": token.token_id,
            },
        )
        await arguments["session"].commit()
        job_id = None
        try:
            await root.dispatch_outbox_events(arguments["session"], operation_id=operation_id, limit=1)
        except Exception as exc:  # noqa: BLE001
            root.logger.warning(
                "save_outbox_dispatch_failed_after_commit",
                project_id=project_id,
                operation_id=operation_id,
                error=str(exc),
            )
        operation = await root.get_operation_record(arguments["session"], project_id=project_id, operation_id=operation_id)
        job_id = operation.get("job_id") if operation else job_id
        response = root.build_output_envelope(
            request_id=request_id,
            ok=True,
            result={
                "accepted": True,
                "episode_id": episode_id,
                "operation_id": operation_id,
                "observation_doc_id": canonical_result.observation_doc_id,
                "fact_group_id": canonical_result.fact_group_id,
                "fact_version_id": canonical_result.fact_version_id,
                "ingest_state": "PENDING",
                "status": "ACCEPTED",
                "ingested_at": root.datetime.now(root.timezone.utc).isoformat(),
                "enrichment": {"mode": "ASYNC", "job_id": job_id},
            },
        )
        await root.persist_idempotent_response(
            tool_name=tool_name,
            project_id=project_id,
            idempotency_key=idempotency_key,
            payload_hash=payload_hash,
            response=response,
        )
        return response
    except Exception:
        await root.release_idempotency_slot(
            tool_name=tool_name,
            project_id=project_id,
            idempotency_key=idempotency_key,
        )
        raise


async def handle_search(
    *,
    tool_name: str,
    request_id: str,
    project_id: str,
    token: AuthenticatedToken,
    arguments: dict,
) -> dict:
    root.ensure_plan_access(token, tool_name)
    root.ensure_scope(token, "memory:read")
    await root.enforce_rate_limit(token, project_id, tool_name)

    requested_scope, scope_applied = root._resolve_memory_scope(arguments)
    seed = root.make_seed(root._seed_payload(arguments))
    snapshot_token = arguments.get("snapshot_token")
    if snapshot_token is not None and str(snapshot_token) != seed:
        raise root.ToolRuntimeError(
            "INVALID_ARGUMENT",
            "snapshot_token does not match the current query shape",
            {"snapshot_token": snapshot_token},
        )
    fact_offset, episode_offset = root._decode_search_cursor(arguments.get("cursor"), seed)
    limit = arguments.get("limit", 10)
    filters = arguments.get("filters") or {}
    canonical_results: list[dict] = []
    if episode_offset == 0:
        canonical_results = await root.search_canonical_memory(
            arguments["session"],
            project_id=project_id,
            query=str(arguments["query"]),
            filters=filters,
            sort=str(arguments.get("sort") or "RELEVANCE"),
            limit=limit + 1,
            offset=fact_offset,
        )
    if canonical_results or tool_name == "viberecall_search_memory":
        page = canonical_results[:limit]
        next_cursor = None
        if len(canonical_results) > limit:
            next_cursor = root._encode_search_cursor(
                fact_offset=fact_offset + len(page),
                episode_offset=0,
                seed=seed,
            )
        return root.build_output_envelope(
            request_id=request_id,
            ok=True,
            result=root._canonical_search_payload(
                page=page,
                next_cursor=next_cursor,
                snapshot_token=seed,
                requested_scope=requested_scope,
                scope_applied=scope_applied,
            ),
        )

    dependency_detail = await root.get_graph_dependency_failure_detail()
    if dependency_detail is not None and tool_name == "viberecall_search_memory":
        return root.build_output_envelope(
            request_id=request_id,
            ok=True,
            result=root._canonical_search_payload(
                page=[],
                next_cursor=None,
                snapshot_token=seed,
                requested_scope=requested_scope,
                scope_applied=scope_applied,
            ),
        )

    await root.ensure_graph_memory_dependencies_ready()

    if root._use_upstream_graphiti_bridge():
        try:
            fact_results = await root.get_graphiti_upstream_bridge().search_facts(
                project_id,
                query=arguments["query"],
                filters=filters,
                sort=arguments.get("sort", "RELEVANCE"),
                limit=limit + 1,
                offset=fact_offset,
            )
        except Exception as exc:  # noqa: BLE001
            root.logger.warning(
                "graphiti_upstream_bridge_search_failed",
                project_id=project_id,
                error=str(exc),
            )
            fact_results = await root.get_memory_core().search(
                project_id,
                query=arguments["query"],
                filters=filters,
                sort=arguments.get("sort", "RELEVANCE"),
                limit=limit + 1,
                offset=fact_offset,
            )
    else:
        fact_results = await root.get_memory_core().search(
            project_id,
            query=arguments["query"],
            filters=filters,
            sort=arguments.get("sort", "RELEVANCE"),
            limit=limit + 1,
            offset=fact_offset,
        )
    episode_results = await root.list_recent_raw_episodes(
        arguments["session"],
        project_id=project_id,
        query=arguments["query"],
        window_seconds=root.settings.recent_episode_window_seconds,
        limit=limit + 1,
        offset=episode_offset,
    )
    merged = fact_results + [
        {
            "kind": "episode",
            "episode": {
                "episode_id": episode["episode_id"],
                "reference_time": episode["reference_time"],
                "ingested_at": episode["ingested_at"],
                "summary": episode["summary"],
                "metadata": episode["metadata"],
                "salience_score": episode.get("salience_score", 0.5),
                "salience_class": episode.get("salience_class", "WARM"),
            },
            "score": root._SEARCH_EPISODE_SCORE,
        }
        for episode in episode_results
    ]
    merged.sort(key=root._search_result_sort_key, reverse=True)
    page = []
    fact_consumed = 0
    episode_consumed = 0
    for item in merged[:limit]:
        if item["kind"] == "fact":
            fact_consumed += 1
            page.append(
                {
                    "kind": "fact",
                    "fact": item["fact"],
                    "entities": item["entities"],
                    "provenance": item["provenance"],
                    "score": item["score"],
                }
            )
        else:
            episode_consumed += 1
            page.append(item)
    has_more = len(fact_results) > fact_consumed or len(episode_results) > episode_consumed
    next_cursor = None
    if has_more:
        next_cursor = root._encode_search_cursor(
            fact_offset=fact_offset + fact_consumed,
            episode_offset=episode_offset + episode_consumed,
            seed=seed,
        )
    fact_page = [item for item in page if item.get("kind") == "fact"]
    recent_episode_page = [item["episode"] for item in page if item.get("kind") == "episode"]
    expanded_entities = root._expanded_entities_from_page(fact_page, limit=max(limit, 1))
    return root.build_output_envelope(
        request_id=request_id,
        ok=True,
        result={
            "results": page,
            "next_cursor": next_cursor,
            "snapshot_token": seed,
            "scope_requested": requested_scope,
            "scope_applied": scope_applied,
            "seeds": [root._search_seed_entry(item) for item in page],
            "recent_episodes": recent_episode_page,
            "expanded_entities": expanded_entities,
        },
    )


async def handle_get_facts(
    *,
    request_id: str,
    project_id: str,
    token: AuthenticatedToken,
    arguments: dict,
) -> dict:
    root.ensure_plan_access(token, "viberecall_get_facts")
    root.ensure_scope(token, "memory:read")
    await root.enforce_rate_limit(token, project_id, "viberecall_get_facts")

    seed = root.make_seed(root._seed_payload(arguments))
    offset = root.decode_cursor(arguments.get("cursor"), seed)
    limit = arguments.get("limit", 50)
    canonical_facts = await root.list_canonical_facts(
        arguments["session"],
        project_id=project_id,
        filters=arguments.get("filters") or {},
        limit=limit + 1,
        offset=offset,
    )
    if canonical_facts:
        page = [
            {
                "id": fact["fact_version_id"],
                "fact_group_id": fact["fact_group_id"],
                "text": fact["statement"],
                "statement": fact["statement"],
                "valid_at": fact["valid_from"],
                "invalid_at": fact["valid_to"],
                "entities": [
                    entity_id
                    for entity_id in [fact["subject_entity_id"], fact.get("object_entity_id")]
                    if entity_id
                ],
                "provenance": {"episode_id": fact.get("created_from_episode_id")},
            }
            for fact in canonical_facts[:limit]
        ]
        next_cursor = root.encode_cursor(offset + limit, seed) if len(canonical_facts) > limit else None
        return root.build_output_envelope(
            request_id=request_id,
            ok=True,
            result={"facts": page, "next_cursor": next_cursor},
        )

    await root.ensure_graph_memory_dependencies_ready()

    if root._use_upstream_graphiti_bridge():
        try:
            facts = await root.get_graphiti_upstream_bridge().list_facts(
                project_id,
                filters=arguments.get("filters") or {},
                limit=limit + 1,
                offset=offset,
            )
        except Exception as exc:  # noqa: BLE001
            root.logger.warning(
                "graphiti_upstream_bridge_get_facts_failed",
                project_id=project_id,
                error=str(exc),
            )
            facts = await root.get_memory_core().get_facts(
                project_id,
                filters=arguments.get("filters") or {},
                limit=limit + 1,
                offset=offset,
            )
    else:
        facts = await root.get_memory_core().get_facts(
            project_id,
            filters=arguments.get("filters") or {},
            limit=limit + 1,
            offset=offset,
        )
    page = [
        {
            "id": fact["id"],
            "text": fact["text"],
            "valid_at": fact["valid_at"],
            "invalid_at": fact["invalid_at"],
            "entities": fact["entities"],
            "provenance": fact["provenance"],
        }
        for fact in facts[:limit]
    ]
    next_cursor = root.encode_cursor(offset + limit, seed) if len(facts) > limit else None
    return root.build_output_envelope(
        request_id=request_id,
        ok=True,
        result={"facts": page, "next_cursor": next_cursor},
    )


async def handle_update_fact(
    *,
    tool_name: str,
    request_id: str,
    project_id: str,
    token: AuthenticatedToken,
    arguments: dict,
    payload_hash: str,
    idempotency_key: str | None,
) -> dict:
    root.ensure_plan_access(token, tool_name)
    root.ensure_scope(token, "facts:write")
    replay = await root.maybe_replay_idempotent_response(
        tool_name=tool_name,
        project_id=project_id,
        idempotency_key=idempotency_key,
        payload_hash=payload_hash,
    )
    if replay is not None:
        return replay

    await root.enforce_rate_limit(token, project_id, tool_name)
    await root.enforce_quota(
        session=arguments["session"],
        token=token,
        project_id=project_id,
        tool_name=tool_name,
        arguments=arguments,
    )

    await root.claim_idempotency_slot(
        tool_name=tool_name,
        project_id=project_id,
        idempotency_key=idempotency_key,
    )

    try:
        fact_group_id = arguments.get("fact_group_id")
        expected_current_version_id = arguments.get("expected_current_version_id")
        if fact_group_id is None and arguments.get("fact_id"):
            current = await root.get_current_fact_by_version_or_group(
                arguments["session"],
                project_id=project_id,
                fact_version_id=str(arguments["fact_id"]),
            )
            if current is not None:
                fact_group_id = current["fact_group_id"]
                expected_current_version_id = current["fact_version_id"]
        statement = str(arguments.get("statement") or arguments.get("new_text") or "").strip()
        effective_time = str(arguments.get("effective_time") or arguments.get("valid_from") or "").strip()
        if fact_group_id and expected_current_version_id and statement and effective_time:
            operation_id = root.new_id("op")
            await root.create_operation(
                arguments["session"],
                operation_id=operation_id,
                project_id=project_id,
                token_id=token.token_id,
                request_id=request_id,
                kind="update_fact",
                resource_type="fact_group",
                resource_id=str(fact_group_id),
                metadata={"mode": "canonical"},
            )
            result = await root.update_canonical_fact(
                arguments["session"],
                project_id=project_id,
                fact_group_id=str(fact_group_id),
                expected_current_version_id=str(expected_current_version_id),
                statement=statement,
                effective_time=effective_time,
                reason=arguments.get("reason"),
                metadata=dict(arguments.get("metadata") or {}),
            )
            await root.complete_operation(
                arguments["session"],
                operation_id=operation_id,
                result_payload=result,
            )
            await arguments["session"].commit()
            response = root.build_output_envelope(
                request_id=request_id,
                ok=True,
                result={**result, "operation_id": operation_id},
            )
            await root.persist_idempotent_response(
                tool_name=tool_name,
                project_id=project_id,
                idempotency_key=idempotency_key,
                payload_hash=payload_hash,
                response=response,
            )
            return response

        await root.ensure_graph_memory_dependencies_ready()
        new_fact_id = root.new_id("fact")
        operation_id = root.new_id("op")
        await root.create_operation(
            arguments["session"],
            operation_id=operation_id,
            project_id=project_id,
            token_id=token.token_id,
            request_id=request_id,
            kind="update_fact",
            resource_type="fact",
            resource_id=arguments["fact_id"],
            metadata={"new_fact_id": new_fact_id},
        )
        await root.create_outbox_event(
            arguments["session"],
            event_id=root.new_id("evt"),
            operation_id=operation_id,
            project_id=project_id,
            event_type="update_fact.apply",
            payload={
                "request_id": request_id,
                "token_id": token.token_id,
                "fact_id": arguments["fact_id"],
                "new_fact_id": new_fact_id,
                "new_text": arguments["new_text"],
                "effective_time": arguments["effective_time"],
                "reason": arguments.get("reason"),
            },
        )
        await arguments["session"].commit()
        await root.dispatch_outbox_events(arguments["session"], operation_id=operation_id, limit=1)
        operation = await root.get_operation_record(arguments["session"], project_id=project_id, operation_id=operation_id)
        result = (operation or {}).get("result_json")
        response = root.build_output_envelope(
            request_id=request_id,
            ok=True,
            result={
                **(
                    result
                    or {
                        "old_fact": {"id": arguments["fact_id"], "invalid_at": arguments["effective_time"]},
                        "new_fact": {"id": new_fact_id, "valid_at": arguments["effective_time"]},
                    }
                ),
                "job_id": (operation or {}).get("job_id"),
                "operation_id": operation_id,
            },
        )
        await root.persist_idempotent_response(
            tool_name=tool_name,
            project_id=project_id,
            idempotency_key=idempotency_key,
            payload_hash=payload_hash,
            response=response,
        )
        return response
    except Exception:
        await root.release_idempotency_slot(
            tool_name=tool_name,
            project_id=project_id,
            idempotency_key=idempotency_key,
        )
        raise


async def handle_timeline(
    *,
    request_id: str,
    project_id: str,
    token: AuthenticatedToken,
    arguments: dict,
) -> dict:
    root.ensure_plan_access(token, "viberecall_timeline")
    root.ensure_scope(token, "memory:read")
    await root.enforce_rate_limit(token, project_id, "viberecall_timeline")
    await root.ensure_graph_memory_dependencies_ready()

    seed = root.make_seed(root._seed_payload(arguments))
    offset = root.decode_cursor(arguments.get("cursor"), seed)
    limit = arguments.get("limit", 50)
    if root._use_upstream_graphiti_bridge():
        try:
            episodes = await root.get_graphiti_upstream_bridge().list_timeline(
                project_id,
                from_time=arguments.get("from"),
                to_time=arguments.get("to"),
                limit=limit + 1,
                offset=offset,
            )
        except Exception as exc:  # noqa: BLE001
            root.logger.warning(
                "graphiti_upstream_bridge_timeline_failed",
                project_id=project_id,
                error=str(exc),
            )
            episodes = await root.list_timeline_episodes(
                arguments["session"],
                project_id=project_id,
                from_time=arguments.get("from"),
                to_time=arguments.get("to"),
                limit=limit + 1,
                offset=offset,
            )
    else:
        episodes = await root.list_timeline_episodes(
            arguments["session"],
            project_id=project_id,
            from_time=arguments.get("from"),
            to_time=arguments.get("to"),
            limit=limit + 1,
            offset=offset,
        )
    page = episodes[:limit]
    next_cursor = root.encode_cursor(offset + limit, seed) if len(episodes) > limit else None
    return root.build_output_envelope(
        request_id=request_id,
        ok=True,
        result={"episodes": page, "next_cursor": next_cursor},
    )


async def handle_get_fact(
    *,
    request_id: str,
    project_id: str,
    token: AuthenticatedToken,
    arguments: dict,
) -> dict:
    root.ensure_plan_access(token, "viberecall_get_fact")
    root.ensure_scope(token, "memory:read")
    await root.enforce_rate_limit(token, project_id, "viberecall_get_fact")
    fact = await root.get_canonical_fact(
        arguments["session"],
        project_id=project_id,
        fact_version_id=arguments.get("fact_version_id"),
        fact_group_id=arguments.get("fact_group_id"),
    )
    if fact is None:
        raise root.ToolRuntimeError(
            "NOT_FOUND",
            "Fact not found",
            {
                "fact_version_id": arguments.get("fact_version_id"),
                "fact_group_id": arguments.get("fact_group_id"),
            },
        )
    return root.build_output_envelope(
        request_id=request_id,
        ok=True,
        result=fact,
    )


async def handle_pin_memory(
    *,
    request_id: str,
    project_id: str,
    token: AuthenticatedToken,
    arguments: dict,
) -> dict:
    root.ensure_plan_access(token, "viberecall_pin_memory")
    root.ensure_scope(token, "facts:write")
    await root.enforce_rate_limit(token, project_id, "viberecall_pin_memory")

    target_kind = str(arguments.get("target_kind") or "").upper()
    if target_kind not in {"FACT", "ENTITY", "EPISODE"}:
        raise root.ToolRuntimeError(
            "INVALID_ARGUMENT",
            "target_kind must be one of FACT, ENTITY, or EPISODE",
            {"target_kind": arguments.get("target_kind")},
        )

    pin_action = str(arguments.get("pin_action") or "").upper()
    if pin_action not in {"PIN", "UNPIN", "DEMOTE"}:
        raise root.ToolRuntimeError(
            "INVALID_ARGUMENT",
            "pin_action must be one of PIN, UNPIN, or DEMOTE",
            {"pin_action": arguments.get("pin_action")},
        )

    target_id = str(arguments.get("target_id") or "").strip()
    if not target_id:
        raise root.ToolRuntimeError(
            "INVALID_ARGUMENT",
            "target_id is required",
            {"target_id": arguments.get("target_id")},
        )

    result = await root.pin_canonical_memory(
        session=arguments["session"],
        project_id=project_id,
        target_kind=target_kind,
        target_id=target_id,
        pin_action=pin_action,
        reason=str(arguments["reason"]) if arguments.get("reason") is not None else None,
    )
    if result is None:
        raise root.ToolRuntimeError(
            "NOT_FOUND",
            "Target not found",
            {
                "target_kind": target_kind,
                "target_id": target_id,
            },
        )

    await arguments["session"].commit()
    return root.build_output_envelope(
        request_id=request_id,
        ok=True,
        result=result,
    )


async def handle_delete_episode(
    *,
    request_id: str,
    project_id: str,
    token: AuthenticatedToken,
    arguments: dict,
) -> dict:
    root.ensure_plan_access(token, "viberecall_delete_episode")
    root.ensure_scope(token, "delete:write")
    await root.enforce_rate_limit(token, project_id, "viberecall_delete_episode")

    episode_id = str(arguments["episode_id"])
    delete_context = await root.get_episode_for_project(
        arguments["session"],
        project_id=project_id,
        episode_id=episode_id,
    )

    dependency_detail = await root.get_graph_dependency_failure_detail()
    delete_result = None
    graph_deleted = False
    graph_skipped = dependency_detail is not None

    if dependency_detail is None:
        try:
            delete_result = await root.get_memory_core().delete_episode(project_id, episode_id=episode_id)
        except Exception as exc:  # noqa: BLE001
            root.logger.warning(
                "delete_episode_graph_cleanup_failed",
                project_id=project_id,
                episode_id=episode_id,
                error=str(exc),
            )
            raise root.ToolRuntimeError(
                "UPSTREAM_ERROR",
                "Episode delete cleanup failed before persistence cleanup",
                {"episode_id": episode_id},
            ) from exc

        if delete_result.remaining_fact_count > 0:
            raise root.ToolRuntimeError(
                "UPSTREAM_ERROR",
                "Episode delete cleanup incomplete",
                {
                    "episode_id": episode_id,
                    "deleted_episode_node": delete_result.deleted_episode_node,
                    "remaining_fact_count": delete_result.remaining_fact_count,
                },
            )
        graph_deleted = delete_result.remaining_fact_count == 0 and (delete_result.found or delete_context is not None)
    else:
        root.logger.warning(
            "delete_episode_graph_cleanup_skipped",
            project_id=project_id,
            episode_id=episode_id,
            detail=dependency_detail,
        )

    canonical_deleted = await root.delete_canonical_episode(
        arguments["session"],
        project_id=project_id,
        episode_id=episode_id,
    )
    canonical_found = bool(canonical_deleted["fact_group_ids"] or canonical_deleted["fact_version_ids"])

    if not graph_deleted and not canonical_found and delete_context is None:
        return root.build_output_envelope(
            request_id=request_id,
            ok=True,
            result={
                "episode_id": episode_id,
                "status": "NOT_FOUND",
                "deleted": {
                    "postgres": False,
                    "object_storage": False,
                    "graph": False,
                    "canonical": False,
                    "graph_skipped": graph_skipped,
                },
            },
        )

    deleted_row = await root.delete_episode_for_project(
        arguments["session"],
        project_id=project_id,
        episode_id=episode_id,
    )
    postgres_deleted = deleted_row is not None
    object_deleted = False

    if delete_context is not None and delete_context.get("content_ref"):
        try:
            object_deleted = await root.delete_object(object_key=str(delete_context["content_ref"]))
        except root.ObjectStorageError as exc:
            root.logger.warning(
                "delete_episode_object_cleanup_failed",
                project_id=project_id,
                episode_id=episode_id,
                error=str(exc),
            )
    status = "DELETED" if (graph_deleted or canonical_found or postgres_deleted) else "NOT_FOUND"

    return root.build_output_envelope(
        request_id=request_id,
        ok=True,
        result={
            "episode_id": episode_id,
            "status": status,
            "deleted": {
                "postgres": postgres_deleted,
                "object_storage": object_deleted,
                "graph": graph_deleted,
                "canonical": canonical_found,
                "graph_skipped": graph_skipped,
            },
        },
    )
