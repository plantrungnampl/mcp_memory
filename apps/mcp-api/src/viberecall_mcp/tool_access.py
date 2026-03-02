FREE_PLAN_TOOLS = {
    "viberecall_save",
    "viberecall_search",
    "viberecall_timeline",
}


def is_tool_allowed_for_plan(plan: str, tool_name: str) -> bool:
    if plan in {"pro", "team"}:
        return True
    if plan == "free":
        return tool_name in FREE_PLAN_TOOLS
    return False


def filter_tools_for_plan(plan: str, tools: list[dict]) -> list[dict]:
    return [tool for tool in tools if is_tool_allowed_for_plan(plan, tool["name"])]
