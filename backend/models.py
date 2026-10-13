"""Data types for the Campus Customs agent team.

Nothing in this file touches the database. Shop facts live in SQLite and reach
the agents only through the MCP server; these are the shapes the agents pass
between themselves and the shapes the audit trail is written in.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

AgentName = Literal["boss", "inventory", "accounting", "facilities", "customer_service"]

ALL_AGENTS: tuple[AgentName, ...] = (
    "boss",
    "inventory",
    "accounting",
    "facilities",
    "customer_service",
)


# --------------------------------------------------------------------------
# Dependencies carried through a run
# --------------------------------------------------------------------------


@dataclass
class TeamDeps:
    """Shared state for one run of the team.

    `depth` is what stops agents delegating in circles: every delegation hands
    the callee a copy of these deps with depth + 1, and the delegate tool
    refuses once MAX_DELEGATION_DEPTH is reached. `chain` is kept so a refusal
    can say who was already on the call stack.
    """

    run_id: str
    agent: AgentName = "boss"
    depth: int = 0
    chain: tuple[AgentName, ...] = ("boss",)
    delegations_used: list[int] = field(default_factory=lambda: [0])

    def child(self, callee: AgentName) -> "TeamDeps":
        """Deps for an agent one level down the delegation chain."""
        return TeamDeps(
            run_id=self.run_id,
            agent=callee,
            depth=self.depth + 1,
            chain=self.chain + (callee,),
            # Shared one-element list, so the delegation budget is counted
            # across the whole run rather than per branch.
            delegations_used=self.delegations_used,
        )


# --------------------------------------------------------------------------
# What the specialists hand back
# --------------------------------------------------------------------------


class SpecialistReport(BaseModel):
    """What any of the four specialist agents returns for one subtask."""

    agent: AgentName = Field(description="Which agent produced this report.")
    summary: str = Field(
        description="What was found and what was done, in plain words, citing the "
        "numbers that came back from the MCP tools."
    )
    facts_used: list[str] = Field(
        default_factory=list,
        description="The specific shop facts this rests on, each tied to the tool it "
        'came from, e.g. "check_stock CC-TEE-WHITE/S -> qty 0".',
    )
    actions_taken: list[str] = Field(
        default_factory=list,
        description="Writes actually made through MCP tools, e.g. a prepared request "
        "id, a ticket update, a recorded draft. Empty if nothing was written.",
    )
    blocked_by: str = Field(
        default="",
        description="What stands in the way, if anything, e.g. an unpaid invoice "
        "holding up a vendor, or a missing human approval. Empty if clear.",
    )
    needs_human: bool = Field(
        default=False,
        description="True when a person must act before this can go further, which "
        "is always the case for a payment.",
    )
    handoff_to: list[AgentName] = Field(
        default_factory=list,
        description="Agents that should pick this up next, if any.",
    )


# --------------------------------------------------------------------------
# What the Boss hands back
# --------------------------------------------------------------------------


class TicketDecision(BaseModel):
    """The Boss's final call on one ticket."""

    ticket_id: int = Field(description="The ticket this decision is about.")
    subject: str = Field(description="Short restatement of what the ticket wants.")
    assigned_to: list[AgentName] = Field(
        description="Which agents handled or should handle this ticket."
    )
    priority: int = Field(
        description="Where this sits in the day's order, 1 being done first.", ge=1
    )
    decision: str = Field(
        description="The call itself, in plain words: what happens to this ticket "
        "and why, including the cash reasoning if money is involved."
    )
    money_involved: float | None = Field(
        default=None, description="Cash this ticket would consume, or null if none."
    )
    awaiting_human: bool = Field(
        default=False, description="True if a person must approve something first."
    )
    status_set: str = Field(
        default="", description="Status written back to the ticket, if any."
    )


class DayPlan(BaseModel):
    """The Boss's output for a whole run over the open tickets."""

    date_today: str = Field(description="The shop's working date, from desk.date_today.")
    opening_cash: float = Field(description="Cash on hand at the start, from the MCP tool.")
    decisions: list[TicketDecision] = Field(description="One entry per open ticket.")
    cash_plan: str = Field(
        description="How the money is sequenced across the tickets and what it adds "
        "up to against the opening balance, including anything that does not fit."
    )
    awaiting_human_approval: list[str] = Field(
        default_factory=list,
        description="Everything a person must approve before it can proceed.",
    )
    notes: str = Field(
        default="", description="Anything else the owner should know, including what "
        "could not be settled and why."
    )


# --------------------------------------------------------------------------
# Audit trail
# --------------------------------------------------------------------------


class AuditStep(BaseModel):
    """One step of one agent's loop, appended to output/audit_trail.json.

    The file is append-only across runs: `run_id` groups the steps of a single
    run so that older runs stay readable alongside newer ones.
    """

    timestamp: str = Field(description="When the step was recorded, ISO 8601 local time.")
    run_id: str = Field(description="Shared id for every step of one run.")
    step: int = Field(description="Position of this step within the run, starting at 1.")
    agent: AgentName = Field(description="Which agent took this step.")
    depth: int = Field(description="How deep in the delegation chain this agent is running.")
    kind: Literal["tool_call", "delegation", "agent_result"] = Field(
        description="What sort of step this is."
    )
    tool_name: str = Field(default="", description="MCP tool called, if this was a tool call.")
    tool_args: str = Field(default="", description="Short rendering of the arguments.")
    tool_result: str = Field(default="", description="Short rendering of what came back.")
    delegated_to: str = Field(
        default="", description="Agent handed the subtask, if this was a delegation."
    )
    delegated_task: str = Field(default="", description="Short rendering of the subtask.")
    stop_reason: str = Field(
        description="Why the step ended: 'in_progress' while the loop continues, then "
        "'completed', 'limit_reached', 'delegation_refused', or an error."
    )
