"""The Campus Customs agent team.

Five PydanticAI agents -- boss, inventory, accounting, facilities,
customer_service -- all running gpt-6-luna through Portkey, all able to
delegate to any of the others.

Two kinds of talking, kept strictly apart:

  * Agent to agent is PydanticAI. Each agent carries a `delegate_to` tool that
    runs another agent and hands back its report.
  * Agent to shop is MCP, and only MCP. There is no SQLite import in this
    package and no second shop-tools layer: every fact and every change goes
    through mcp_server/server.py over data/campus_customs_new.db.

What keeps a run bounded:

  * MAX_REQUESTS / MAX_TOOL_CALLS cap one agent's loop.
  * MAX_DELEGATION_DEPTH stops agents handing work round in circles.
  * MAX_DELEGATIONS caps the whole run's delegations.
  * Only gpt-6-luna is used. Nothing here escalates to a larger model.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai import Agent, RunContext
from pydantic_ai.mcp import MCPToolset, StdioTransport
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIChatModelSettings
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import UsageLimits

from audit import RunRecorder, short
from models import ALL_AGENTS, AgentName, DayPlan, SpecialistReport, TeamDeps

HW5_DIR = Path(__file__).resolve().parent.parent
PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
MCP_CONFIG = HW5_DIR / "mcp.json"

# The key is looked for in the project root first, which is where a fresh clone
# puts it after copying .env.example, and then one level up, which is where this
# course's shared key lives.
ENV_CANDIDATES = (HW5_DIR / ".env", HW5_DIR.parent / ".env")

# Only ever this model. The assignment's cheap model, and nothing steps up.
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-6-luna")

# Per-agent loop caps. The Boss gets more headroom than the specialists: it
# works every ticket in the queue and each delegate_to counts as a tool call,
# so a cap sized for one specialist's subtask would cut the day plan short.
MAX_REQUESTS = 14
MAX_TOOL_CALLS = 20
BOSS_MAX_REQUESTS = 28
BOSS_MAX_TOOL_CALLS = 40

# Delegation caps. Depth is what prevents an endless A -> B -> A loop; the
# total is a backstop on a run that keeps fanning out sideways.
MAX_DELEGATION_DEPTH = 3
MAX_DELEGATIONS = 12


# --------------------------------------------------------------------------
# Model
# --------------------------------------------------------------------------


def env_file() -> Path:
    """The .env actually in use, preferring one inside the project."""
    for candidate in ENV_CANDIDATES:
        if candidate.exists():
            return candidate
    return ENV_CANDIDATES[0]


def make_client() -> AsyncOpenAI:
    """OpenAI client pointed at Portkey, keyed from .env."""
    load_dotenv(env_file())
    key = os.getenv("PORTKEY_API_KEY")
    if not key:
        raise RuntimeError(
            "PORTKEY_API_KEY is not set. Copy .env.example to .env in the project "
            f"root and put your key in it (looked in: "
            f"{', '.join(str(c) for c in ENV_CANDIDATES)})."
        )
    return AsyncOpenAI(
        api_key=key,
        base_url="https://api.portkey.ai/v1",
        default_headers={"x-portkey-api-key": key},
    )


# gpt-6-luna rejects function tools over /v1/chat/completions unless reasoning
# effort is switched off, so every agent runs with it set to "none".
MODEL_SETTINGS = OpenAIChatModelSettings(openai_reasoning_effort="none")


def build_model() -> OpenAIChatModel:
    return OpenAIChatModel(MODEL_NAME, provider=OpenAIProvider(openai_client=make_client()))


def load_prompt(name: str) -> str:
    path = PROMPT_DIR / f"{name}.md"
    if not path.exists():
        raise RuntimeError(f"Prompt file not found: {path}")
    return path.read_text()


def mcp_command() -> tuple[str, list[str]]:
    """Read the server command from the same mcp.json Problem 4 registered.

    One source of truth: if the connection config changes, the agents follow.
    """
    if not MCP_CONFIG.exists():
        raise RuntimeError(f"MCP config not found: {MCP_CONFIG}")
    entry = json.loads(MCP_CONFIG.read_text())["mcpServers"]["campus-customs"]
    return _resolve(entry["command"]), [_resolve(a) for a in entry["args"]]


def _resolve(value: str) -> str:
    """Resolve a project-relative path from mcp.json against the project root."""
    candidate = HW5_DIR / value
    return str(candidate) if not value.startswith("/") and candidate.exists() else value


# --------------------------------------------------------------------------
# The team
# --------------------------------------------------------------------------


class CampusCustomsTeam:
    """Builds the five agents over one shared MCP connection.

    Use as an async context manager so the MCP server process starts once and
    every agent in the run talks to that same server:

        async with CampusCustomsTeam(recorder) as team:
            plan = await team.run_boss("Work today's open tickets.")
    """

    def __init__(self, recorder: RunRecorder) -> None:
        self.recorder = recorder
        self.model = build_model()

        command, args = mcp_command()
        # Every MCP tool call is routed through _record_tool_call so the audit
        # trail sees it as it happens, not reconstructed afterwards.
        self.toolset = MCPToolset(
            StdioTransport(command, args, cwd=str(HW5_DIR)),
            process_tool_call=self._record_tool_call,
        )

        self.agents: dict[AgentName, Agent] = {}
        for name in ALL_AGENTS:
            self.agents[name] = self._build_agent(name)

    @staticmethod
    def limits_for(agent: AgentName) -> UsageLimits:
        if agent == "boss":
            return UsageLimits(
                request_limit=BOSS_MAX_REQUESTS, tool_calls_limit=BOSS_MAX_TOOL_CALLS
            )
        return UsageLimits(request_limit=MAX_REQUESTS, tool_calls_limit=MAX_TOOL_CALLS)

    # -- MCP call auditing ------------------------------------------------

    async def _record_tool_call(
        self,
        ctx: RunContext[TeamDeps],
        call_tool: Any,
        name: str,
        args: dict[str, Any],
    ) -> Any:
        """Run one MCP tool call and write it to the audit trail either way."""
        deps = ctx.deps
        try:
            result = await call_tool(name, args)
        except Exception as exc:
            self.recorder.tool_call(
                agent=deps.agent,
                depth=deps.depth,
                tool_name=name,
                tool_args=args,
                tool_result=f"ERROR: {exc}",
                stop_reason="tool_error",
            )
            raise
        self.recorder.tool_call(
            agent=deps.agent,
            depth=deps.depth,
            tool_name=name,
            tool_args=args,
            tool_result=result,
        )
        return result

    # -- Agent construction -----------------------------------------------

    def _build_agent(self, name: AgentName) -> Agent:
        output_type = DayPlan if name == "boss" else SpecialistReport
        agent = Agent(
            self.model,
            deps_type=TeamDeps,
            system_prompt=load_prompt(name),
            toolsets=[self.toolset],
            output_type=output_type,
            model_settings=MODEL_SETTINGS,
            retries=2,
            name=name,
        )

        others = [a for a in ALL_AGENTS if a != name]

        @agent.tool
        async def delegate_to(
            ctx: RunContext[TeamDeps], agent_name: str, task: str
        ) -> dict[str, Any]:
            """Hand a subtask to another agent and get their report back.

            Use this when the work belongs to someone else's role. Ask for
            something specific -- the ticket id and the question or action you
            want -- rather than handing over the whole ticket.

            Args:
                agent_name: One of the other agents on the team.
                task: What you want them to find out or do, in plain words.

            Returns:
                Their report, or refused=True with a reason if the delegation
                could not be made.
            """
            return await self._delegate(ctx, agent_name, task, caller=name, allowed=others)

        return agent

    # -- Delegation --------------------------------------------------------

    async def _delegate(
        self,
        ctx: RunContext[TeamDeps],
        agent_name: str,
        task: str,
        caller: AgentName,
        allowed: list[AgentName],
    ) -> dict[str, Any]:
        deps = ctx.deps
        callee = agent_name.strip().lower().replace("-", "_").replace(" ", "_")

        def refuse(reason: str, message: str) -> dict[str, Any]:
            self.recorder.delegation(
                agent=caller,
                depth=deps.depth,
                delegated_to=callee,
                task=task,
                result=message,
                stop_reason="delegation_refused",
            )
            return {"refused": True, "reason": reason, "message": message}

        if callee not in allowed:
            return refuse(
                "unknown_agent",
                f"'{agent_name}' is not an agent you can delegate to. "
                f"Choose one of: {', '.join(allowed)}.",
            )

        if deps.depth + 1 > MAX_DELEGATION_DEPTH:
            return refuse(
                "depth_limit",
                f"Delegation depth limit of {MAX_DELEGATION_DEPTH} reached "
                f"(chain so far: {' -> '.join(deps.chain)}). Do this part "
                "yourself from the tool results you already have, or report it "
                "as unfinished. Do not retry this delegation.",
            )

        if deps.delegations_used[0] >= MAX_DELEGATIONS:
            return refuse(
                "delegation_budget",
                f"This run has used its {MAX_DELEGATIONS} delegations. Finish "
                "with the tool results you already have and say what is left.",
            )

        deps.delegations_used[0] += 1
        child = deps.child(callee)

        self.recorder.delegation(
            agent=caller, depth=deps.depth, delegated_to=callee, task=task
        )

        try:
            result = await self.agents[callee].run(
                task,
                deps=child,
                usage_limits=self.limits_for(callee),
            )
        except Exception as exc:
            self.recorder.agent_result(
                agent=callee, depth=child.depth, result=f"ERROR: {exc}", stop_reason="error"
            )
            return {
                "refused": True,
                "reason": "agent_error",
                "message": f"{callee} could not complete the task: {exc}",
            }

        report = result.output
        self.recorder.agent_result(
            agent=callee,
            depth=child.depth,
            result=report.model_dump() if hasattr(report, "model_dump") else report,
            stop_reason="completed",
        )
        self.recorder.delegation(
            agent=caller,
            depth=deps.depth,
            delegated_to=callee,
            task=task,
            result=short(report.summary if hasattr(report, "summary") else report),
            stop_reason="completed",
        )
        return report.model_dump() if hasattr(report, "model_dump") else {"report": str(report)}

    # -- Entry point -------------------------------------------------------

    async def run_boss(self, instruction: str) -> DayPlan:
        deps = TeamDeps(run_id=self.recorder.run_id, agent="boss", depth=0, chain=("boss",))
        try:
            result = await self.agents["boss"].run(
                instruction,
                deps=deps,
                usage_limits=self.limits_for("boss"),
            )
        except Exception as exc:
            self.recorder.agent_result(
                agent="boss", depth=0, result=f"ERROR: {exc}", stop_reason="error"
            )
            raise
        self.recorder.agent_result(
            agent="boss", depth=0, result=result.output.model_dump(), stop_reason="completed"
        )
        return result.output

    async def __aenter__(self) -> "CampusCustomsTeam":
        await self.toolset.__aenter__()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.toolset.__aexit__(*exc)
