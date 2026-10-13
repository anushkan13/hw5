"""Run the Campus Customs agent team over the open tickets.

From the HW 5 folder:

    .venv/bin/python backend/run_team.py
    .venv/bin/python backend/run_team.py --task "Work ticket 101 only."

Every step of the run is appended to output/audit_trail.json. The trail is
never wiped, so earlier runs stay readable alongside this one.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit import AUDIT_PATH, RunRecorder  # noqa: E402
from team import (  # noqa: E402
    BOSS_MAX_REQUESTS,
    BOSS_MAX_TOOL_CALLS,
    MAX_DELEGATION_DEPTH,
    MAX_DELEGATIONS,
    MAX_REQUESTS,
    MAX_TOOL_CALLS,
    MODEL_NAME,
    CampusCustomsTeam,
)

DEFAULT_TASK = (
    "Work today's open tickets. Start by getting the shop's working date and "
    "the cash balance, then list the open tickets. For each one, delegate to "
    "the agent whose role it belongs to, and make the final call. The shop has "
    "one pot of money and no income, so sequence the work against the balance "
    "and say plainly what does not fit. Prepare anything that needs paying for "
    "a human to approve -- you never approve or make payments yourself."
)


def render(plan) -> str:
    lines = [
        "",
        "=" * 72,
        f"  CAMPUS CUSTOMS - DAY PLAN for {plan.date_today}",
        f"  Opening cash: {plan.opening_cash:,.2f}",
        "=" * 72,
        "",
    ]
    for d in sorted(plan.decisions, key=lambda x: x.priority):
        money = f"{d.money_involved:,.2f}" if d.money_involved is not None else "-"
        flag = "  [AWAITING HUMAN]" if d.awaiting_human else ""
        lines += [
            f"  #{d.priority}  Ticket {d.ticket_id} - {d.subject}{flag}",
            f"      assigned to : {', '.join(d.assigned_to)}",
            f"      money       : {money}",
            f"      status set  : {d.status_set or '-'}",
            f"      decision    : {d.decision}",
            "",
        ]
    lines += ["  CASH PLAN", f"      {plan.cash_plan}", ""]
    if plan.awaiting_human_approval:
        lines.append("  WAITING ON A HUMAN")
        lines += [f"      - {item}" for item in plan.awaiting_human_approval]
        lines.append("")
    if plan.notes:
        lines += ["  NOTES", f"      {plan.notes}", ""]
    lines.append("=" * 72)
    return "\n".join(lines)


async def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Campus Customs agent team.")
    parser.add_argument("--task", default=DEFAULT_TASK, help="What to tell the Boss.")
    parser.add_argument(
        "--save",
        default="",
        help="Optional path to write the day plan as JSON, e.g. output/day_plan.json",
    )
    args = parser.parse_args()

    run_id = f"run-{datetime.now(timezone.utc).astimezone():%Y%m%dT%H%M%S}-{uuid4().hex[:6]}"
    recorder = RunRecorder(run_id)

    print(f"run_id   : {run_id}")
    print(f"model    : {MODEL_NAME}")
    print(
        f"limits   : boss {BOSS_MAX_REQUESTS} requests / {BOSS_MAX_TOOL_CALLS} tool calls, "
        f"specialists {MAX_REQUESTS} / {MAX_TOOL_CALLS}, "
        f"delegation depth {MAX_DELEGATION_DEPTH}, {MAX_DELEGATIONS} delegations per run"
    )
    print(f"audit    : {AUDIT_PATH}")
    print("\nworking...\n")

    try:
        async with CampusCustomsTeam(recorder) as team:
            plan = await team.run_boss(args.task)
    except Exception as exc:
        print(f"Run failed: {exc}", file=sys.stderr)
        print(f"{recorder.steps_recorded} step(s) were still written to {AUDIT_PATH}.", file=sys.stderr)
        return 1

    print(render(plan))
    print(f"\n{recorder.steps_recorded} step(s) appended to {AUDIT_PATH}")

    if args.save:
        out = Path(args.save)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(plan.model_dump(), indent=2) + "\n")
        print(f"Day plan written to {out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
