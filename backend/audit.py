"""Append-only audit trail for the Campus Customs agent team.

Every agent-loop step lands in output/audit_trail.json: which agent moved, the
MCP tool it called with short arguments and a short result, any delegation to
another agent, and why the step ended. The file is never wiped between runs --
new steps are appended after the ones already there, and `run_id` groups the
steps that belong to a single run.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from models import AuditStep

# backend/audit.py -> HW 5/ -> HW 5/output/audit_trail.json
AUDIT_PATH = Path(__file__).resolve().parent.parent / "output" / "audit_trail.json"

# Agents run concurrently when the Boss fans work out, so appends are serialised.
_lock = Lock()

# How much of an argument blob or a tool result is kept. Full payloads would
# make the trail unreadable and are already in the database.
SNIPPET = 400


def now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def short(value: Any, limit: int = SNIPPET) -> str:
    """Render a value compactly for the trail, truncating anything long."""
    if value is None:
        return ""
    if isinstance(value, str):
        text = value
    else:
        try:
            text = json.dumps(value, default=str, separators=(",", ":"))
        except (TypeError, ValueError):
            text = str(value)
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _load(path: Path) -> list[dict]:
    """Read the existing trail, tolerating an absent, empty, or damaged file.

    A damaged file is never discarded silently -- it is moved aside first, so
    the earlier record survives even though it can no longer be parsed.
    """
    if not path.exists() or path.stat().st_size == 0:
        return []
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        salvage = path.with_suffix(f".corrupt-{int(datetime.now(timezone.utc).timestamp())}.json")
        path.rename(salvage)
        print(f"[audit] {path.name} was not valid JSON; moved to {salvage.name}")
        return []
    return data if isinstance(data, list) else [data]


def append(step: AuditStep) -> None:
    """Append one step to the trail, keeping everything already written."""
    with _lock:
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        trail = _load(AUDIT_PATH)
        trail.append(step.model_dump())
        tmp = AUDIT_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(trail, indent=2) + "\n")
        tmp.replace(AUDIT_PATH)


class RunRecorder:
    """Numbers the steps of one run and writes them out as they happen."""

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self._step = 0
        self._step_lock = Lock()

    def _next(self) -> int:
        with self._step_lock:
            self._step += 1
            return self._step

    @property
    def steps_recorded(self) -> int:
        return self._step

    def tool_call(
        self,
        agent: str,
        depth: int,
        tool_name: str,
        tool_args: Any,
        tool_result: Any,
        stop_reason: str = "in_progress",
    ) -> None:
        append(
            AuditStep(
                timestamp=now(),
                run_id=self.run_id,
                step=self._next(),
                agent=agent,
                depth=depth,
                kind="tool_call",
                tool_name=tool_name,
                tool_args=short(tool_args),
                tool_result=short(tool_result),
                stop_reason=stop_reason,
            )
        )

    def delegation(
        self,
        agent: str,
        depth: int,
        delegated_to: str,
        task: str,
        result: Any = None,
        stop_reason: str = "in_progress",
    ) -> None:
        append(
            AuditStep(
                timestamp=now(),
                run_id=self.run_id,
                step=self._next(),
                agent=agent,
                depth=depth,
                kind="delegation",
                delegated_to=delegated_to,
                delegated_task=short(task),
                tool_result=short(result),
                stop_reason=stop_reason,
            )
        )

    def agent_result(
        self,
        agent: str,
        depth: int,
        result: Any,
        stop_reason: str,
    ) -> None:
        append(
            AuditStep(
                timestamp=now(),
                run_id=self.run_id,
                step=self._next(),
                agent=agent,
                depth=depth,
                kind="agent_result",
                tool_result=short(result, limit=900),
                stop_reason=stop_reason,
            )
        )
