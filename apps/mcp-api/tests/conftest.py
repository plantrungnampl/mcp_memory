from __future__ import annotations

import asyncio

import pytest

from viberecall_mcp.runtime import reset_runtime_state


@pytest.fixture(autouse=True)
def _reset_runtime_after_test() -> None:
    yield
    asyncio.run(reset_runtime_state())
