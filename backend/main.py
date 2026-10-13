"""FastAPI backend for the Campus Customs desk dashboard.

Run from the backend/ folder:

    uvicorn main:app --reload --port 8000

How the layers stay separated:

  * Shop reads and shop writes go through the MCP server (`shop.py`). There is
    no SQLite in this file and no second shop-tools layer.
  * The agent run goes through the existing team in `team.py`, unchanged. The
    agents prepare payments and drafts; they never execute a payment.
  * Writing a human approval is the one thing that is deliberately NOT an MCP
    tool, because an agent must not be able to authorise its own spending. It
    lives in `mcp_server/approve_cli.py` and is reached only by the approve
    route below, which is the single place in the whole system that can
    authorise money leaving the shop.

The approve route is included for completeness, as asked. Running the board
does not call it, and nothing else in the system can.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

BACKEND_DIR = Path(__file__).resolve().parent
HW5_DIR = BACKEND_DIR.parent

# uvicorn is started from backend/, so make sibling modules importable and
# reach mcp_server/ for the human-approval path.
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(HW5_DIR / "mcp_server"))

import shop  # noqa: E402
from approve_cli import ApprovalError, record_approval  # noqa: E402
from audit import AUDIT_PATH, RunRecorder  # noqa: E402
from team import CampusCustomsTeam  # noqa: E402

PRISTINE_DB = HW5_DIR / "data" / "campus_customs.db"
WORKING_DB = HW5_DIR / "data" / "campus_customs_new.db"

app = FastAPI(
    title="Campus Customs Desk API",
    description="Backend for the agent-team dashboard.",
    version="1.0.0",
)

# The React dev server runs on another origin in development, so the browser
# needs these headers before it will let the dashboard call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# One agent run at a time. Two concurrent runs would interleave their writes to
# the same tickets and the same audit trail for no benefit.
_run_lock = asyncio.Lock()


# --------------------------------------------------------------------------
# Request and response shapes
# --------------------------------------------------------------------------


class TicketSummary(BaseModel):
    id: int
    type: str
    requester: str
    subject: str
    status: str
    is_open: bool = Field(description="True while the ticket is still 'open'.")
    is_resolved: bool = Field(description="True once the ticket reads 'resolved'.")
    sku: str | None = None
    size: str | None = None
    qty: int | None = None
    lease_id: int | None = None
    invoice_id: int | None = None
    notes: str | None = None
    created_at: str


class RunResponse(BaseModel):
    ticket_id: int
    run_id: str
    steps_recorded: int
    plan: dict[str, Any]


class ApprovalRequest(BaseModel):
    kind: str = Field(description='What is being paid, e.g. "invoice" or "rent".')
    amount: float = Field(gt=0, description="Exact amount being approved.")
    approved_by: str = Field(min_length=1, description="Name of the human approving.")
    ref_id: int | None = Field(default=None, description="Invoice id, lease id, etc.")
    account: str = Field(default="checking", description="Cash account to pay from.")


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------


@app.get("/api/health")
async def health() -> dict[str, Any]:
    """Liveness check, plus proof the MCP server is reachable."""
    try:
        tools = await shop.warm_up()
    except Exception as exc:
        raise HTTPException(503, f"MCP server unreachable: {exc}") from exc
    return {"ok": True, "mcp_tools": len(tools), "working_db": WORKING_DB.name}


@app.get("/api/tickets", response_model=list[TicketSummary])
async def get_tickets() -> list[TicketSummary]:
    """Every ticket on the board, each flagged open or resolved."""
    data = await shop.call("list_tickets")
    out: list[TicketSummary] = []
    for t in data.get("tickets", []):
        status = (t.get("status") or "").lower()
        out.append(
            TicketSummary(
                **{k: t.get(k) for k in (
                    "id", "type", "requester", "subject", "status", "sku", "size",
                    "qty", "lease_id", "invoice_id", "notes", "created_at",
                )},
                is_open=status == "open",
                is_resolved=status == "resolved",
            )
        )
    return out


@app.post("/api/tickets/{ticket_id}/run", response_model=RunResponse)
async def run_ticket(ticket_id: int) -> RunResponse:
    """Run the agent team on one ticket.

    The agents read the shop through MCP, delegate among themselves, and
    prepare payments and drafts for a human. They do not execute payments --
    `make_payment` refuses without an approval that only the approve route can
    write.
    """
    ticket = await shop.call("get_ticket", {"ticket_id": ticket_id})
    if not ticket.get("found"):
        raise HTTPException(404, f"No ticket {ticket_id}.")

    if _run_lock.locked():
        raise HTTPException(409, "An agent run is already in progress. Wait for it to finish.")

    async with _run_lock:
        run_id = f"run-{datetime.now(timezone.utc).astimezone():%Y%m%dT%H%M%S}-{uuid4().hex[:6]}"
        recorder = RunRecorder(run_id)
        task = (
            f"Work ticket {ticket_id} only, and nothing else on the board. "
            "Start by getting the shop's working date and the cash balance, then read "
            f"ticket {ticket_id} and delegate to the agent whose role it belongs to. "
            "Prepare anything that needs paying for a human to approve -- you never "
            "approve or make payments yourself -- and update the ticket with the call "
            "you make."
        )
        try:
            async with CampusCustomsTeam(recorder) as team:
                plan = await team.run_boss(task)
        except Exception as exc:
            raise HTTPException(
                500,
                f"The agent run failed: {exc}. "
                f"{recorder.steps_recorded} step(s) were still written to the audit trail.",
            ) from exc

    return RunResponse(
        ticket_id=ticket_id,
        run_id=run_id,
        steps_recorded=recorder.steps_recorded,
        plan=plan.model_dump(),
    )


@app.get("/api/events")
async def get_events(limit: int = 50, run_id: str | None = None) -> dict[str, Any]:
    """Recent agent events: what each agent did and which tools it used.

    Read straight from the append-only audit trail the agents write as they
    run, so the board can poll this to refresh.
    """
    if not AUDIT_PATH.exists():
        return {"count": 0, "total": 0, "runs": [], "events": []}

    try:
        trail = json.loads(AUDIT_PATH.read_text())
    except json.JSONDecodeError as exc:
        raise HTTPException(500, f"The audit trail is not valid JSON: {exc}") from exc
    if not isinstance(trail, list):
        trail = [trail]

    runs = list(dict.fromkeys(e.get("run_id", "") for e in trail))
    if run_id:
        trail = [e for e in trail if e.get("run_id") == run_id]

    limit = max(1, min(limit, 500))
    recent = trail[-limit:]
    return {
        "count": len(recent),
        "total": len(trail),
        "runs": runs,
        "latest_run": runs[-1] if runs else None,
        "events": recent,
    }


@app.post("/api/approvals")
async def approve_and_pay(body: ApprovalRequest) -> dict[str, Any]:
    """The human-approval step, and the only route that changes cash.

    Two steps, in order:

    1. Record the approval. This is the row no agent can write -- it lives
       outside the MCP tool surface precisely so that an agent cannot
       authorise its own spending.
    2. Execute the payment through the existing `make_payment` MCP tool, which
       keeps every guard it already had: it matches the approval exactly,
       refuses if the balance will not cover the amount, never lets a balance
       go negative, marks the approval spent so it cannot fund a second
       payment, and closes the invoice when one is being settled.

    If step 2 refuses, the approval stays on file unspent and no money moves;
    the response says so rather than pretending the payment happened.
    """
    try:
        approval = record_approval(
            kind=body.kind,
            amount=body.amount,
            approved_by=body.approved_by,
            ref_id=body.ref_id,
            account=body.account,
        )
    except ApprovalError as exc:
        raise HTTPException(400, str(exc)) from exc

    payment = await shop.call(
        "make_payment",
        {
            "kind": body.kind,
            "ref_id": body.ref_id,
            "amount": body.amount,
            "account": body.account,
        },
    )

    balance = await shop.call("get_cash_balance", {"account": body.account})

    return {
        "approved": True,
        "approval": approval,
        "paid": bool(payment.get("paid")),
        "payment": payment,
        "balance": balance.get("balance"),
        "note": (
            "Payment executed and the cash balance updated."
            if payment.get("paid")
            else f"Approval recorded but no money moved: {payment.get('reason')}. "
                 "The approval is still on file, unspent."
        ),
    }


@app.get("/api/cash")
async def get_cash(account: str = "checking") -> dict[str, Any]:
    """The current balance of a cash account, read through MCP."""
    data = await shop.call("get_cash_balance", {"account": account})
    if not data.get("found"):
        raise HTTPException(404, data.get("message", f"No cash account named {account}."))
    return data


@app.post("/api/reset")
async def reset_database() -> dict[str, Any]:
    """Reset the working database to the original values for a fresh run.

    Copies the pristine `campus_customs.db` over the working
    `campus_customs_new.db`, then starts the MCP server once so it rebuilds the
    three tables it owns (`approvals`, `prepared_requests`, `message_drafts`)
    on the fresh copy before the next request needs them.

    The audit trail is deliberately left alone: it is append-only across runs
    by design, and wiping it would erase the record of what the agents did.
    """
    if not PRISTINE_DB.exists():
        raise HTTPException(500, f"Pristine database missing at {PRISTINE_DB}.")
    if _run_lock.locked():
        raise HTTPException(409, "An agent run is in progress. Wait for it to finish.")

    shutil.copyfile(PRISTINE_DB, WORKING_DB)
    tools = await shop.warm_up()
    cash = await shop.call("get_cash_balance", {"account": "checking"})

    return {
        "reset": True,
        "copied": f"{PRISTINE_DB.name} -> {WORKING_DB.name}",
        "mcp_tools": len(tools),
        "balance": cash.get("balance"),
        "audit_trail": "left intact (append-only across runs)",
    }
