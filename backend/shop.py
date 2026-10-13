"""The backend's only route to the shop's data: the MCP server.

There is no SQLite here and no second shop-tools layer. Every fact the API
returns, and every change it makes to shop data, is an MCP tool call against
mcp_server/server.py over data/campus_customs_new.db -- the same server and the
same tools the agents use.

The connection is opened per call rather than held open. That costs a process
spawn, but it means the reset route works: a freshly copied database gets its
`approvals`, `prepared_requests`, and `message_drafts` tables rebuilt by the
server's own startup on the very next call, with no stale handle pointing at
the file that was replaced.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastmcp import Client

HW5_DIR = Path(__file__).resolve().parent.parent
MCP_CONFIG = HW5_DIR / "mcp.json"


def _resolve(value: str) -> str:
    """Turn a project-relative path in mcp.json into an absolute one.

    mcp.json stores the interpreter and the server script as paths relative to
    the project root, so the file works on any machine after a clone. The
    backend is started from backend/, so those have to be resolved before the
    server can be spawned. Anything that is already absolute, or that does not
    name a file in the project, is passed through untouched.
    """
    candidate = HW5_DIR / value
    return str(candidate) if not value.startswith("/") and candidate.exists() else value


def _config() -> dict:
    if not MCP_CONFIG.exists():
        raise RuntimeError(f"MCP config not found: {MCP_CONFIG}")
    raw = json.loads(MCP_CONFIG.read_text())
    for entry in raw.get("mcpServers", {}).values():
        if "command" in entry:
            entry["command"] = _resolve(entry["command"])
        entry["args"] = [_resolve(a) for a in entry.get("args", [])]
        entry.setdefault("cwd", str(HW5_DIR))
    return raw


async def call(tool: str, args: dict[str, Any] | None = None) -> Any:
    """Call one MCP tool and return its parsed result."""
    async with Client(_config()) as client:
        result = await client.call_tool(tool, args or {})
        return result.data


async def call_many(calls: list[tuple[str, dict[str, Any]]]) -> list[Any]:
    """Call several MCP tools over one connection, in order.

    Saves spawning the server once per tool when a route needs a few facts.
    """
    out: list[Any] = []
    async with Client(_config()) as client:
        for tool, args in calls:
            result = await client.call_tool(tool, args or {})
            out.append(result.data)
    return out


async def warm_up() -> list[str]:
    """Start the server once and list its tools.

    Used right after a database reset so the server recreates the tables it
    owns before the next request needs them.
    """
    async with Client(_config()) as client:
        return [t.name for t in await client.list_tools()]
