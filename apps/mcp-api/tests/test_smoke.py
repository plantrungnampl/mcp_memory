from viberecall_mcp.mcp_server import build_initialize_result, get_tool_definitions


def test_initialize_capabilities_present() -> None:
    result = build_initialize_result()
    assert "tools" in result["capabilities"]


def test_five_public_tools_registered() -> None:
    tools = get_tool_definitions()
    assert [tool["name"] for tool in tools] == [
        "viberecall_save",
        "viberecall_search",
        "viberecall_get_facts",
        "viberecall_update_fact",
        "viberecall_timeline",
    ]
