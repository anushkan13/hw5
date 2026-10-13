# HW 5 — AI Prompts Log

This file records every prompt issued to the AI assistant for HW 5, organized by problem.

---

## Problem 1: Vibe Coder Prompts

### Prompt 1 (initial)

> Today, we will be working in the HW 5 folder. Navigate there, and create an AI_prompts.md. In this file, please input a section for every problem we go through, including the following for each:
>
> * The problem number and title
> * The prompts I type to you pertaining to each problem
>    * If I issue any follow-up prompts for any problem, add those too, noting one sentence regarding what was missing in my first prompt that required a follow-up to clarify, etc.
>
> This message pertains to Problem 1: Vibe Coder Prompts.
> Confirm every time I prompt you that the AI_prompts.md has been updated.
> Note that we will be using the PORTKEY_API_KEY and OpenAI models (ONLY gpt-6-luna). Do not ramp up models, only use Luna here.

**Outcome:** Created `AI_prompts.md` in the HW 5 folder with this logging structure. No follow-up needed yet.

### Prompt 2 (follow-up)

> gpt-6-luna is correct here. AGENTS.md can also be updated accordingly to reflect this due to an OpenAI update since it was written originally.

**Why a follow-up was needed:** The first prompt specified `gpt-6-luna` while the project's `AGENTS.md` still said `gpt-5.6-luna`, so the model name had to be confirmed and the project instructions brought up to date.

**Outcome:** Updated `AGENTS.md` instruction 1 to reference `gpt-6-luna`.

---

## Problem 2: Study the Campus Customs Database

### Prompt 1 (initial)

> Problem 2: Study the Campus Customs Database
>
> Open data/campus_customs.db and go through every table. List each table's columns with their types, and show one sample row from each so I can see the shape of the data. Then, look at the three open tickets and show how each one links to the other tables (which ticket points at SKU, vendor, lease, cash account, etc.).
>
> For now, only print these results to the screen just yet, don't write files for this purpose yet.
> Additionally, copy the original database to data/campus_customs_new.db, leaving data/campus_customs.db untouched. The copy is the working file that later problems will update.
>
> Further, start output/harness.md. For each table, list its fields and one short line as to why the table is relevant for the below agents that will ultimately be created for this assignment at a later stage:
>
> * Boss: reads each ticket, decides who should work on it, and makes final calls.
> * Inventory: checks stock by SKU and size, spot shortfalls, and figures out which vendor can restock.
> * Accounting: watches cash and invoices, checks margins, and prepares payments or purchase orders for human approval.
> * Facilities: handles the shop space side (leases, rent, etc.).
> * Customer Service: drafts messages for customers.
>
> Keep the entry in output/harness.md concise and plain for now. The file will grow in future problems.
>
> As a general rule, only change/update output/harness.md when I explicitly request it in my prompts for a problem. Do not add anything to the harness or any other file on your own initiative.

**Outcome:** Inspected all 9 tables (schema + sample row) and printed the ticket-to-table link map to screen only. Copied `data/campus_customs.db` to `data/campus_customs_new.db`. Created `output/harness.md` with per-table fields and agent relevance notes. No follow-up needed.

---

## Problem 3: Build the MCP Server

### Prompt 1 (initial)

> Problem 3: Build the MCP Server
>
> Write an MCP server in mcp_server/ using FastMCP that talks to data/campus_customs_new.db.
> At this time, the server does not need to run or need to be connected, and please note that no data should every be invented; only read what is in the database.
>
> Write 3 tools with clear names, where each one is a tool that you know will be needed for the open tickets:
>
> 1. A stock-check tool that reads the inventory table ad returns the on-hand quantity for a given SKU and size (and name/location). This will pertain to ticket 101, for example.
> 2. A lease/rent lookup tool that reads the leases table and returns the rent amount and next-due data for a lease. This will pertain to ticket 102, for example.
> 3. A margin/pricing lookup tool that reads the pricing table and returns unit_cost and list_price (and the margin) for an SKU. This will pertain to ticket 103, for example.
>
> Further, add mcp_server/README.md explaining what the MCP server is for, which database file it uses (data/campus_customs_new.db), and the three tools it has.
>
> Then, update output/harness.md to outline the three tools, which table each reads, which ticket each helps unlock, and one sentence (only) regarding the reason that the tool is correct for the ticket it unlocks. Be specific and tie each tool to the ticket - do not write something vague, like "reads inventory".

**Outcome:** Created `mcp_server/server.py` with FastMCP tools `check_stock`, `get_lease_terms`, and `get_margin`, all opening the working DB in SQLite read-only mode and returning `found: False` rather than inventing values. Added `mcp_server/README.md`, created the HW 5 `.venv` with `requirements.txt`, and appended the tool table to `output/harness.md`. No follow-up needed.

---

## Problem 4: Add the MCP Server to Vibe Coder and Test Each Tool

### Prompt 1 (initial)

> Problem 4: Add the MCP Server to Vibe Coder and Test Each Tool
>
> Add the MCP server to this project so you (Claude Code) can call its tools directly.
>
> Save the connection config as mcp.json at the project root in whatever format your local MCP server. Make sure you are actually connected and can call the three tools.
>
> Then, smoke-test all three tools by calling them through the MCP connection, using inputs from the tickets:
>
> * check_stock for ticket 101
> * get_lease_terms for ticket 102
> * get_margin for ticket 103
>
> Save the evidence to output/mcp_smoke.json. For each tool record three things: the prompt you asked to trigger the call, the tool name, and the tool's output. The outputs must match the values in data/campus_customs_new.db.

**Outcome:** Wrote `mcp.json` (and a matching `.mcp.json`, the filename Claude Code actually loads) at the HW 5 root, registering `campus-customs` over stdio with absolute paths to the venv interpreter and `mcp_server/server.py`. Launched the server over the MCP stdio protocol, confirmed it exposes all three tools, called each with the ticket inputs, and wrote `output/mcp_smoke.json`. All three outputs were cross-checked against `data/campus_customs_new.db` with direct SQL and match exactly.

**Caveat raised to the user:** Claude Code loads MCP servers at session start, so the in-session tool list will not include `campus-customs` until the session is restarted; the smoke test was therefore run through a real MCP stdio client rather than the in-session tool list.


### Prompt 2 (follow-up)

> Continuing in Problem 4 of HW5. Resume the session here so that I can approve campus-customs when prompted, and we can continue working as specified in the previous session.

**Why a follow-up was needed:** The first prompt assumed the MCP server would become callable in-session, but the session had been started with the parent folder (`AI Foundations for Managers`) as its root, where no `.mcp.json` exists — so `campus-customs` was never offered for approval and the in-session tool list stayed empty.

**Outcome:** Confirmed via the session connector status that only `visualize` and `scheduled-tasks` were registered. Re-rooted the session to the `HW 5` folder so that `HW 5/.mcp.json` is discovered at the next session start, which is when Claude Code reads MCP configs. Re-ran the three tools over a real MCP stdio connection to verify the server is still healthy: it starts as `campus-customs` on FastMCP 4.1.0, exposes `check_stock`, `get_lease_terms`, and `get_margin`, and returns values identical to those already recorded in `output/mcp_smoke.json`, so that evidence file required no changes. Confirmed with the user that `.mcp.json` stays only in `HW 5/` rather than being duplicated to the parent root.

---

## Problem 5: Build the Agent Team and Grow the MCP Tools

### Prompt 1 (initial)

> Problem 5: Build the Agent Team and Grow the MCP Tools
>
> Build the full Campus Customs agent team with PydanticAI. Five agents (Boss, Inventory, Accounting, Facilities, Customer Service), all on gpt-6-luna through Portkey using PORTKEY_API_KEY, all able to delegate to each other (full connectivity).
>
> Layout:
>
> * One prompt file per agent in backend/prompts/ (boss, inventory, accounting, facilities, customer_service).
> * Data types in backend/models.py.
> * Agent code under backend/ (your choice of file split, as long as the five roles are clear).
>
> How the two kinds of "talking" work:
>
> * Agent-to-agent delegation is PydanticAI (any agent can hand a subtask to any other).
> * All shop facts and changes go through the MCP server over data/campus_customs_new.db. Do NOT read or write the database directly from the backend, and do NOT build a second shop-tools layer that bypasses MCP. Add whatever shop tools the agents need to mcp_server.
>
> Write a detailed prompt per agent in plain words. Detailed and complete rather than short and generic. Each prompt must cover that agent's scope plus the shop rules it needs: [Boss / Inventory / Accounting / Facilities / Customer Service scopes and rules as specified]
>
> Every prompt should also say: get all shop facts from the MCP tools and never invent data, you may delegate to any other agent, and stay within your role.
>
> MCP tools to add (in mcp_server, over data/campus_customs_new.db); keep the existing check_stock, get_lease_terms, get_margin: [reads: tickets, invoices, vendors, cash, desk.date_today; writes: ONE payment tool gated on human approval with no-negative-cash guard, a prepared purchase/restock draft, a ticket status/notes update, a recorded customer message draft; read tools on a read-only connection and write tools on a writable one]
>
> Audit trail: as the agents run, append each agent-loop step to output/audit_trail.json: the time, which agent, the tool it called with short args and a short result, any delegation to another agent, and the stop reason. Append, never wipe it between runs.
>
> Update output/harness.md: list each agent and its role; list each tool and each MCP tool (including the new ones) with which table it uses; and add a short safety section with the guardrails a real business would want when agents touch real customers and real money, plus the limits that keep token use in check.
>
> Update mcp_server/README.md so its tool list matches the full set now.

**Outcome:** Built the five-agent PydanticAI team and grew the MCP server from 3 tools to 19.

- **MCP server** (`mcp_server/server.py`): 15 read tools on a `mode=ro` connection and 4 write tools on a writable one. The server creates three tables of its own — `approvals`, `prepared_requests`, `message_drafts` — because the original schema has nowhere to put an approval, a draft PO, or an unsent message; `data/campus_customs.db` is still untouched.
- **The approval gate.** `make_payment` requires an unspent row in `approvals` matching the exact kind, ref_id, amount and account. No agent has any tool that writes to that table — a human uses `mcp_server/approve_cli.py`, which is deliberately not an MCP tool — so an agent cannot approve its own spending. The approval is consumed on use, and the whole thing runs in one transaction that rolls back on any failure.
- **Agent team** (`backend/team.py`, `backend/run_team.py`, `backend/models.py`, `backend/audit.py`, five prompts in `backend/prompts/`): all on `gpt-6-luna`, full connectivity through a `delegate_to` tool, capped at delegation depth 3 and 12 delegations per run. `backend/` imports no database driver; the only shop access is the MCP toolset, built from the same `mcp.json` Problem 4 registered.
- **Audit trail** is captured live through the MCP toolset's `process_tool_call` hook rather than reconstructed after the fact, and appends across runs.

**Verified by running it, not just by reading it:**

- The payment guard was tested directly on a throwaway copy: refuses with no approval; pays and decrements on a valid one; refuses a replay of a spent approval; refuses when the amount does not match; refuses an overdraft and leaves the balance untouched. A write attempted on the read-only connection raises `attempt to write a readonly database`.
- A full team run over the three open tickets produced a correct day plan: found the size-S stockout (qty 0), identified overdue invoice 501 as the thing blocking Bulldog Print Co from shipping, verified rent against lease 1 rather than the landlord's notice, and sequenced $840 + $2,400 against the $3,400 balance. Cash was still 3,400 and the payments table still empty afterwards — nothing moved without a human.
- The whole approval arc was then exercised through the agents: a human approved invoice 501 with the CLI, Accounting found the approval and executed the payment, cash went 3,400 → 2,560, the invoice flipped to `paid`, and Inventory confirmed the vendor was clear to ship with an ETA of 2026-09-05 (5 lead days from `desk.date_today`).

**Two fixes made during testing, both caught by running the team rather than reading the code:**

1. `gpt-6-luna` rejects function tools over `/v1/chat/completions` unless reasoning effort is off, so every agent now runs with `openai_reasoning_effort="none"`.
2. The first full run left three duplicate drafts for the same $840 invoice, because three delegation paths each reached it. `prepare_purchase_request` now deduplicates on `kind` + `ref_id` and returns the existing request, and the prompts tell the agents to pass `ref_id` and check the desk first. The re-run produced exactly one draft per obligation.

The Boss also needed its own, larger usage caps (28 requests / 40 tool calls against the specialists' 14 / 20), because it works every ticket in the queue and each delegation counts against its tool budget; the first clean run died on the shared cap.

### Prompt 2 (follow-up)

> Reset the working database to pristine now so we start the next problem from a clean board: copy data/campus_customs.db over data/campus_customs_new.db (cash back to 3400, no payments, no drafts). Then confirm that the MCP server recreates its approvals, prepared_requests, and message_drafts tables on startup with create-if-not-exists, so the write tools still work on a freshly reset copy. Don't do a full ticket-resolution run yet, that's a later problem. Leave output/harness.md alone.

**Why a follow-up was needed:** The Problem 5 work left the working database mid-demonstration — invoice 501 paid, cash at 2,560, and drafts on the board — because the payment arc had been exercised end to end, so the board had to be cleared before the next problem could start from the original scenario.

**Outcome:** Copied `data/campus_customs.db` over `data/campus_customs_new.db`. Confirmed the three server-created tables were absent immediately after the copy, then launched the server through `mcp.json` over real MCP stdio — rather than calling `init_db()` directly — and confirmed it created `approvals`, `prepared_requests`, and `message_drafts` on startup. Exercised `prepare_purchase_request`, `record_customer_message`, and `update_ticket` through the MCP connection on that freshly reset copy: all three wrote successfully, and `make_payment` still refused with `no_human_approval`. Also confirmed the create-if-not-exists is idempotent by restarting the server three times against a database holding rows, with the row counts unchanged each time. Then reset a second time to clear the write checks, leaving: date 2026-08-31, cash 3,400.00, tickets 101/102/103 open with original notes, invoice 501 open and overdue, CC-TEE-WHITE size S at qty 0, and zero payments, approvals, prepared requests, and message drafts. `output/harness.md` was not touched. `output/audit_trail.json` was deliberately left alone, since it is specified as append-only across runs.

---

## Problem 6: Plan the Three Tickets

### Prompt 1 (initial)

> Problem 6: Plan the Three Tickets
>
> Build output/desk_tickets.html, a page I can double-click to open, with tabs: 101, 102, 103, Cash, and Reflection. The Cash and Reflection tabs are for later problems, so leave them blank with a short "coming later" note. Each ticket tab has an Expected section (the text below) and an empty Actual section placeholder, clearly labelled, that will be filled in after running the agents.
>
> Use my Expected text below word-for-word, do not rewrite or reinterpret it. The only thing you may adjust is an MCP tool name: if one I wrote doesn't exactly match a real tool in the server, keep my wording and swap in the real tool name so the names line up for the later comparison.
>
> [Expected text for Ticket 101 — Customer order: Bulldog tee; Ticket 102 — Rent notice: lease 1; Ticket 103 — Price override: bulk hoodie discount, each with "Who the Boss calls first, and why", "Expected delegations", and "MCP tools we expect this run to use".]

**Outcome:** Created `output/desk_tickets.html` as a standalone, double-clickable page — no server, no build step, no external dependencies. Five tabs (101, 102, 103, Cash, Reflection), with Cash and Reflection left blank behind a short "coming later" note. Each ticket tab carries a labelled Expected section holding the provided text and an empty, clearly labelled Actual placeholder reading "Not yet run."

**No tool-name swaps were needed.** The two names written as actual tool names, `check_stock` and `make_payment`, were both checked against the live server's 19 tools and are exact matches. The remaining references ("get the cash balance", "update the ticket", and so on) are descriptive prose rather than tool names, so there was nothing to substitute without rewriting the wording. To serve the stated purpose of making the names line up for the later comparison, each ticket tab carries a separate "Tool-name key" block mapping every phrase to its canonical tool name, visually distinct and explicitly labelled as an addition rather than part of the Expected text.

**Verified:** all 20 Expected passages were checked programmatically against the rendered page text after stripping markup, and all 20 are present verbatim. The page was then served locally and driven in a browser: all five tabs are present, exactly one panel is visible at a time, every tab switches to the right panel, the three ticket tabs each carry both an Expected and an Actual section, the two later tabs carry only the "coming later" note, and the console is clean. The temporary static-server entry used for that check was removed from `.claude/launch.json` afterwards.

---

## Problem 6: Plan the Three Tickets

### Prompt 1 (initial)

> Problem 6: Plan the Three Tickets
>
> Build output/desk_tickets.html, a page I can double-click to open, with tabs: 101, 102, 103, Cash, and Reflection. The Cash and Reflection tabs are for later problems, so leave them blank with a short "coming later" note. Each ticket tab has an Expected section (the text below) and an empty Actual section placeholder, clearly labelled, that will be filled in after running the agents.
>
> Use my Expected text below word-for-word, do not rewrite or reinterpret it. The only thing you may adjust is an MCP tool name: if one I wrote doesn't exactly match a real tool in the server, keep my wording and swap in the real tool name so the names line up for the later comparison.
>
> [Expected text supplied for Ticket 101 (customer order, CC-TEE-WHITE size S), Ticket 102 (rent notice, lease 1), and Ticket 103 (price override, CC-HOOD-NAVY bulk discount), each covering who the Boss calls first and why, the expected delegations, and the MCP tools expected for that run.]

**Outcome:** Built `output/desk_tickets.html` as a single self-contained file — no external stylesheets, scripts, or fonts, so it opens by double-click with no server and no network.

- Five tabs: 101, 102, 103, Cash, Reflection. Ticket 101 is shown at load. Tabs are keyboard-navigable (arrows, Home, End) and carry proper `role="tab"` / `aria-selected` wiring.
- Each ticket tab has a clearly labelled green **Expected** section holding the supplied text, and an amber **Actual** section containing an empty dashed placeholder reading "Not yet run — to be filled in after running the agents."
- Cash and Reflection are blank apart from a short "Coming later — this tab is filled in by a later problem" note.

**On the one permitted adjustment:** no tool name needed swapping. The only two literal tool names in the supplied text, `check_stock` and `make_payment`, both match real tools in the server exactly. Every other tool mention was descriptive prose rather than a tool name, so rather than alter any wording, each ticket tab carries a separate, visually distinct "Resolved tool names for the later comparison" strip listing the real tools those phrases map to. That scaffolding sits outside the Expected text and changes none of it.

**Verified rather than assumed:** the Expected text was diffed programmatically against the supplied source — all 25 blocks across the three tickets came back word-for-word identical, with the resolved-tool strips excluded from the comparison. A structural check confirmed all five tab/panel pairs cross-reference correctly, exactly one panel is visible at load, there are three Actual placeholders and two "coming later" notes, and the page references zero external resources.

`output/harness.md` was not touched.

---

## Problem 7: Backend Routes

### Prompt 1 (initial)

> Problem 7: Backend Routes:
>
> Build the FastAPI backend in backend/main.py that the React dashboard will call. It runs from the backend/ folder with: uvicorn main:app --reload --port 8000.
>
> Add these routes: return the three tickets with open/resolved; run the agent team on one ticket (agents prepare payments and drafts, they do not execute payments); return recent agent events read from the audit trail; approve a payment or purchase after a human clicks approve (records the approval the agents can't write themselves, then executes through the existing make_payment path, keeping the guard that refuses if there isn't enough cash — included for comprehensiveness but not to be invoked); return the current checking balance; and reset the database to the original values.
>
> Wiring notes: shop reads and the agent run go through the existing MCP tools and agent team, with no second shop-tools layer in the backend; the approval-writing stays the human path kept out of the agents' reach, so only this route can authorize spending; enable CORS so the React dev server can call the backend.
>
> In output/harness.md, list each route in one line: its URL and what it does. Don't touch anything else in the harness on your own.

**Outcome:** Built `backend/main.py` with seven routes, plus `backend/shop.py` as the backend's only path to shop data.

- `backend/shop.py` holds no SQL and no database driver — it opens a FastMCP client against the same `mcp.json` and calls the same tools the agents use. Connections are opened per call rather than held open, which is what makes the reset route work: a freshly copied database gets its tables rebuilt by the server's own startup on the next call, with no stale handle pointing at the replaced file.
- **The approval path was deduplicated rather than reimplemented.** `mcp_server/approve_cli.py` now exposes a `record_approval()` function, and both the CLI and `POST /api/approvals` call it, so there is exactly one implementation of "a person said yes" instead of two that could drift. It is still not an MCP tool, so no agent can reach it.
- Added one read tool to the MCP server, `list_tickets`, so the dashboard can show resolved tickets too. `list_open_tickets` deliberately hides finished work, and the alternative was hardcoding ticket ids 101/102/103 in the backend. Extending the MCP layer was preferable to bypassing it.
- One agent run at a time, guarded by an `asyncio.Lock`, since two concurrent runs would interleave writes to the same tickets and the same audit trail.

**Verified against a running server, not just by reading:**

- `GET /api/tickets` returned all three with correct `is_open` / `is_resolved` flags; `GET /api/cash` returned 3,400.00; `GET /api/events` paged the trail and filtered correctly by `run_id`.
- `POST /api/tickets/102/run` ran the team end to end: Facilities confirmed lease 1 at $2,400 due 2026-09-02, prepared the rent payment for approval, and the Boss updated the ticket — 14 audit steps, and **cash was still 3,400.00 afterwards**, confirming the agents prepare but do not pay.
- `POST /api/reset` restored all three tickets to their original status and notes, cleared the prepared requests, drafts, approvals and payments, rebuilt the server-owned tables on the fresh copy, and left the audit trail intact at 391 events across 6 runs.
- CORS: preflight from `http://localhost:5173` returned the allow-origin header; a disallowed origin correctly got none.
- Both `uvicorn main:app --port 8000` and the documented `--reload` form start and serve correctly.

**On the approve route, which was not to be invoked:** rather than skip testing it, it was exercised through its *refusal* path — approving $9,999 against a $3,400 balance. That proved the whole chain works (the human approval row is written, `make_payment` is called, the no-negative-cash guard holds) while guaranteeing no payment was made: the response came back `paid: false` with `insufficient_funds`, cash stayed at 3,400.00, the payments table stayed empty, and the approval was reported honestly as still on file and unspent. The leftover unspent approval was then cleared by the reset route. Request validation was also checked: a zero amount and an empty approver name are both rejected with HTTP 422.

The server was stopped with the whole process killed, and the board was left pristine: cash 3,400.00, tickets 101/102/103 open with original notes, and zero prepared requests, drafts, approvals, and payments.

### Prompt 2 (follow-up)

> Add list_tickets to the MCP tools table in the harness.

**Why a follow-up was needed:** Problem 7 said not to touch anything else in the harness, so the `list_tickets` read tool added for the dashboard was left out of the MCP tools table, leaving it one row short of the server.

**Outcome:** Added `list_tickets(status)` to the read-tools table in `output/harness.md`, between `list_open_tickets` and `get_ticket`, noting that it returns the whole board open and resolved alike and is what the dashboard reads. Also tightened the `list_open_tickets` description to "open tickets only" so the difference between the two is obvious. Cross-checked the table against the server programmatically: all 20 tools are now listed, none missing.

### Prompt 3 (follow-up)

> Add it to the README too.

**Why a follow-up was needed:** The previous change covered only `output/harness.md`, leaving the read-tools table in `mcp_server/README.md` one row short of the server for the same reason.

**Outcome:** Added `list_tickets(status)` to the read-tools table in `mcp_server/README.md`, in the same position and with the same description as in the harness, and tightened the `list_open_tickets` line to note it is the Boss's work queue. Verified both documents against the server: each now covers all 20 tools, counting the four write tools that the README documents as their own sections rather than table rows.

---

## Problem 8: Agent Dashboard

### Prompt 1 (initial)

> Problem 8: Agent Dashboard
>
> Build the Campus Customs operations dashboard in frontend/ with React + Vite + TypeScript. It talks to the backend at http://localhost:8000 (make sure the backend allows the Vite origin, usually http://localhost:5173). Start it with npm run dev. It has to actually work against the Problem 7 routes, not just look good.
>
> At minimum the board must list all three tickets, let me pick one and start the agent team on it, show each agent and what it's saying/doing and which tools it used by polling the events route live, mark a ticket resolved when the run finishes, show a short per-agent summary, let a human approve a pay or purchase (the approval is what actually moves money), and show the checking balance so it visibly drops after an approved pay.
>
> The look: each agent is an original bulldog illustration on a stool behind a dark-stained wooden desk with office supplies, each in a different coloured Yale-palette apron, with the agent name on a desk name tag. The Boss is a bigger bulldog in a crown at the head of the room, with the four specialists in a line below. Draw connection lines between all of them (the team is fully connected) and light the line in rainbow colours when one agent is talking to another. Sleek collegiate Yale background. Speech bubble or card at each desk showing what it's saying and which tool it used. Cash balance somewhere with a ledger or cash-drawer feel. An obvious approval prompt with an Approve button. A small reset control. Keep the drawings original.
>
> Then write output/design.md covering the look, how the agents read differently, how resolved tickets and cash show up, and the creative choices that make it enjoyable.

**Outcome:** Built the dashboard in `frontend/` (React 19 + Vite + TypeScript) and verified it end to end against a live backend in a real browser, not just by reading the code.

- **Original artwork.** `Bulldog.tsx` is a hand-written SVG bulldog of my own — low wide skull, three brow wrinkles, rose ears, broad low muzzle, modest underbite, heavy jowls — drawn once and reused in five apron colours chosen from the Yale palette for maximum separation (green, rust, blue, plum, with Yale Blue reserved for the crowned Boss). Stool, desk, paws, mug, pen cup, drawer and brass name tag are all in the same viewBox so each seat scales as a unit.
- **Fully connected room.** All ten agent pairs are drawn as dashed wires behind the desks, lighting in a crawling rainbow while two agents are mid-conversation.
- **Live board.** The run request is long-lived, so the board records the latest run id, fires the request, then polls `GET /api/events` about once a second, picks up the new run as soon as it appears, and does a final sweep when the request returns.

**Five real bugs found by running it, each of which reading the code would have missed:**

1. **The cash balance never visibly dropped** — the single most important requirement. Two causes: `setCashBump` was being queued from inside a `setCash` updater, which silently dropped the new balance, and the follow-up `GET /api/cash` was being served from browser cache. Fixed by driving the ledger from the approve response itself, which already carries the post-payment balance, plus `cache: "no-store"` on reads.
2. **Wires almost never lit.** They were lit for a fixed 4 seconds per delegation, but a real delegation lasts 10–30 seconds. The trail already records `in_progress` and `completed` for each delegation, so the board now replays those and lights the wire for the conversation's actual lifetime.
3. **The rainbow did not paint on horizontal wires.** An object-bounding-box gradient collapses on a line with zero-height bounds; switched to a repeating `userSpaceOnUse` gradient.
4. **Per-agent summaries and approval details were blank.** Agent reports are capped at 900 characters in the audit trail and tool args at 400, so the JSON is cut mid-field and will not parse. Rather than loosen a documented token-control cap, the frontend now reads those fields tolerantly — the trail is a log, not an API.
5. **A long report pushed its own bulldog out of the line of desks.** Speech bubbles are now anchored absolutely above each seat, so all four specialists stay aligned regardless of bubble height.

Also fixed during the build: the Boss's crown was clipped by the room's `overflow: hidden`; "Customer Service" overflowed its name tag (the plate now widens and the lettering shrinks for long names); and a `stroke-width` transition left the lit wires pinned at their dim width.

**Verified live:** all three tickets listed from the API; runs started on tickets 101, 102 and 103; the Boss→Inventory→Accounting delegation chain visible in the bubbles with tool names and extracted results; the Boss→Facilities wire confirmed lit mid-run at the correct coordinates; tickets marked Resolved on completion; approval cards recovered from the event stream; and an approved rent payment taking the drawer from **$3,400.00 to $1,000.00 in-session** with the drawer animation firing, matching the API exactly. Reset restored the board to $3,400 with all three tickets open.

**One honesty note built into the UI:** the agents usually leave a ticket `blocked` or `in_progress` rather than `resolved`, because the truthful state is "waiting on a human". The card therefore shows the green Resolved badge for *the team has worked this* **and** a small italic line reporting what the shop's records actually say, rather than hiding the difference.

**Two additions beyond the brief, both flagged:** `prepare_purchase_request` now echoes the `amount` it recorded (its result was previously incomplete, and the approval card needs that figure), and `.claude/launch.json` was added so the app can be started and driven for verification.

Wrote `output/design.md` covering the room metaphor, how the five agents are distinguished four different ways, the speech-bubble ordering of plain language before tool name, the delegation-span wires, the cash drawer, the approval modal, and the reset control.

---

## Problem 9: Resolve the Tickets

### Prompt 1 (initial)

> Problem 9: Resolve the Tickets
>
> This is the full canonical run. Do it in order, and be exact on the cash math, since wrong cash math loses points even if every ticket shows resolved.
>
> Reset the working database to the pristine original and note the starting checking balance. Run all three tickets (101, 102, 103) through the board until each is fully resolved, approving the payments or purchases the team prepares so the tickets actually resolve and the cash and tables update for real. Fill the Actual section on each ticket tab of output/desk_tickets.html from THIS run — which agents worked, what they delegated to whom, which tools they used — honestly, even where it differs from Expected, keeping Expected as-is. Itemize the money exactly on the Cash tab: starting balance, per-ticket change and why, ending balance, which MUST equal cash_accounts in the working database. Save output/resolved_tickets.json and output/resolved_board.html (with real screenshots of the running board, relative paths). Append the runs to output/audit_trail.json. Finish output/harness.md so it covers the tables, MCP tools, agents, routes, dashboard and safety rules, with real values from the code.

**Outcome:** All three tickets finished at status `resolved` in the database, with the cash reconciling exactly.

| | Cash | Why |
|---|---|---|
| Start | **$3,400.00** | after reset to pristine |
| 101 | −$848.00 | invoice 501 $840.00 (unblocked the vendor) + $8.00 one-unit tee restock |
| 102 | −$2,400.00 | lease 1 rent, verified against the lease record not the landlord's email |
| 103 | $0.00 | $264.00 restock unfundable against $152.00 — $112.00 short |
| End | **$152.00** | equals `cash_accounts.balance` |

`3400.00 − 840.00 − 8.00 − 2400.00 = 152.00`. Three payments totalling $3,248.00, each approved by *Shop Owner*. A script-level assertion refuses to write `resolved_tickets.json` unless the per-ticket changes and the payments both reconcile against the database.

**The cash constraint bit, and that is the point.** The three tickets together asked for $3,512.00 against $3,400.00, so $112.00 could never be funded under any ordering. The twelve-hoodie restock was the right thing to drop — the overdue invoice was blocking a vendor from shipping at all, the rent fell due in two days, and the tee restock was $8.00. Ticket 103 still resolved on the pricing question, with the twelve units honestly marked as not secured.

**One change outside the scoped files, flagged at the time.** The tickets could not be resolved at all until `make_payment` was fixed to close out the prepared request it settles. Previously it marked the invoice paid but left the request at `awaiting_approval` forever, so every later agent read the board as "this is still outstanding" — the Boss said so explicitly, refusing to close ticket 101 while citing a restock that had already been paid. The two requests paid before the fix were backfilled to match the payments that genuinely happened.

**An honest limitation recorded rather than hidden.** After the payments went through the agents still would not mark tickets resolved, because `check_stock` still read 0 and their prompts forbid claiming goods arrived. The shop date is frozen at 2026-08-31, so delivery can never land. Closing each ticket was therefore a human instruction given to the Boss through `run_team.py --task`, which is the real team writing to the real audit trail. The Actual sections say so.

**Differences from Expected, all recorded on the ticket tabs:** Accounting never touched ticket 102 (Facilities owns the same cash and request tools and did both itself, so the predicted hop never formed); the shared invoice-501 block never appeared on ticket 103 because ticket 101 had already paid it; ticket 103 produced two customer drafts rather than one; and each ticket took several runs rather than one. Confirmed as predicted: no agent ever called `make_payment` — every call came from the human approval route.

**Verified, not asserted:** all three statuses read from the database; the payments table holds exactly three rows; the audit trail grew to 747 steps across 22 runs with earlier history intact; all 25 Expected blocks in `desk_tickets.html` remain byte-identical; all 20 MCP tools are listed in the harness; and the three screenshots are real captures of the running board, linked by relative path and confirmed to resolve from `output/`.

---

## Problem 10: Reflection

### Prompt 1 (initial)

> Problem 10: Reflection
>
> Within the output/desk_tickets.html Reflection tab, write the following:
>
> [Supplied Q1–Q5 in full: how the agents performed on each ticket and why; how Actual compared to Expected on each; what would have been simpler as a single agent with tools; three new problems this team could already solve; and three it could not, with the tools or agents that would be needed.]

**Outcome:** Wrote the supplied Q1–Q5 into the Reflection tab of `output/desk_tickets.html`, word-for-word. Verified by diffing the rendered text against the supplied source: all 20 blocks identical. The Problem 6 Expected sections are still 25/25 intact and the Cash tab is unchanged, so the whole page now has five filled tabs and no "coming later" notes left.

**One factual issue raised rather than silently corrected.** Q3 describes the Boss's limits as "delegation caps (28 steps, 40 delegations) ... (14/20)". The numbers are right but the units are not: in `backend/team.py`, 28 is `BOSS_MAX_REQUESTS` (model requests per run) and 40 is `BOSS_MAX_TOOL_CALLS` (tool calls per run), against 14 and 20 for the specialists. Delegations are capped separately at `MAX_DELEGATIONS = 12` per run with `MAX_DELEGATION_DEPTH = 3`, so "40 delegations" overstates that cap by more than three times. A corrected phrasing was offered that keeps the original voice; the text was left as written pending that decision, since it is the user's own reflection.

**Everything else in the reflection was checked against the record and holds:** run counts of 4 / 3 / 2 per ticket, the 79-step second run on 103 being the largest of the session, `get_margin` genuinely being read on 101, Accounting never touching 102, the Boss's bookkeeping-conflict catch, the $50 / $1,000 / $28 pricing, 8 of 20 in stock and request #4 still `awaiting_approval`, the Customer Service to Boss call being the only delegation back up to the Boss, and the full cash chain of $3,400 − $848 − $2,400 − $0 = $152 matching `cash_accounts`.

### Prompt 2 (follow-up)

> You can correct the errors in the reflection. The servers can also be shut down for now.

**Why a follow-up was needed:** The first prompt supplied the reflection text to be written in as-is, so the factual slips found while checking it against the audit trail were flagged rather than fixed, and the decision on whether to change the user's own words was left to them.

**Outcome:** Applied three minimal corrections to the Reflection tab, each preserving the original voice and argument, and verified by diff that nothing else in the reflection changed (6 changed lines: 3 removed, 3 added).

1. **Q1, ticket 103** — "the biggest of anything we ran" became "the biggest single run of the three tickets". The 79-step run was the largest of the canonical run, but three earlier Problem 5 runs were bigger at 132, 117 and 101 steps.
2. **Q3, the Boss's limits** — "bigger delegation caps (28 steps, 40 delegations) than the specialists (14/20)" became "a bigger budget (28 model requests and 40 tool calls) than the specialists (14 and 20)". The figures were right but mislabelled: 28 is `BOSS_MAX_REQUESTS` and 40 is `BOSS_MAX_TOOL_CALLS`, while delegations are capped separately at `MAX_DELEGATIONS = 12` per run with `MAX_DELEGATION_DEPTH = 3`.
3. **Q2, the approval gate** — "no agent ever called make_payment itself" became "no agent called make_payment itself on any of these runs". Zero agent calls in the canonical run, but one earlier Problem 5 test did have Accounting execute a payment once a human approval was on file, so the unscoped "ever" was too strong.

Re-verified afterwards: the Problem 6 Expected blocks are still 25/25 intact, all five tabs are filled, no placeholders and no "coming later" notes remain, and the Cash tab still reconciles to $152.00.

Stopped both dev servers — `uvicorn` on port 8000 and the Vite server on 5173 — killing the whole process in each case rather than just freeing the port, per the project instructions. Both ports confirmed free afterwards, with no stray `vite` or `npm run dev` processes. The one remaining `mcp_server/server.py` process is this Claude Code session's own `campus-customs` connection, not a leak from the app. The working database is untouched by the shutdown.

---

## Problem 11: Submit to GitHub

### Prompt 1 (initial)

> Problem 11: Submit to GitHub
>
> Push this project to a new public GitHub repo so graders can clone and run it. Match the file layout in the screenshot I'm attaching. Before pushing: do not commit my real .env, make sure .gitignore ignores .env and my local .claude/ folder, and keep .env.example in the repo; do commit both database files in data/ so graders can run without rebuilding data, fixing .gitignore if it excludes .db files; create output/github_url.txt with the repo URL. Update README.md so a grader can run everything from a fresh clone, with the real commands from this project: copy the original DB over the working copy for a clean run, start the MCP server, start the FastAPI backend on port 8000, start the React board, and reset the DB before a full three-ticket run. After pushing, give me the repo URL and confirm my real .env is not in the repo and both data/ files are.

**Outcome:** Pushed to **https://github.com/anushkan13/hw5** (public, 56 files). Wrote `.env.example`, a rewritten `.gitignore`, a full `README.md`, and `output/github_url.txt`.

**Three portability problems found and fixed, because without them a grader could not run the project at all:**

1. **`mcp.json` and `.mcp.json` hardcoded `/Users/anushkanair/...`** for both the interpreter and the server script. Changed to paths relative to the project root, with `backend/shop.py` and `backend/team.py` resolving them against that root and pinning the subprocess `cwd`, since the backend is started from `backend/`.
2. **`.env` was read from outside the project** (`HW5_DIR.parent`), so a clone had nowhere to put the key that `.env.example` describes. Now the project root is checked first and the parent second, which keeps the existing local setup working and makes a clone work too.
3. **A fresh `pip install -r requirements.txt` failed outright.** Unpinned installs pulled a newer `cryptography` with no wheel for this platform, so pip fell back to a Rust source build and died. Pinned every dependency to the verified versions and added a pip upgrade step to the README.

**Verified by actually cloning the published repo** into a temp directory, building a venv, installing from the pinned requirements, copying the pristine database over the working copy, and running both the MCP server (20 tools, cash $3,400.00, all three tickets `open`, payment gate correctly refusing with `no_human_approval`) and the FastAPI backend (`/api/health`, `/api/cash`, `/api/tickets` all responding). Every command in the README was run before being written down.

**Confirmed against the remote tree, not just the local one:** no `.env` anywhere in the repo, `.env.example` present, no `.claude/` files, and both `data/campus_customs.db` (53,248 bytes) and `data/campus_customs_new.db` (73,728 bytes) published.

**Two deviations from the screenshot, both deliberate.** The screenshot is abbreviated — it shows `frontend/` with no children at all — so it was treated as the intended top-level organisation rather than an exhaustive file list. The repo additionally contains the files the project cannot run without (`backend/team.py`, `shop.py`, `audit.py`, `run_team.py`, `mcp_server/approve_cli.py`, `mcp.json` alongside `.mcp.json`, and `output/screens/` which `resolved_board.html` links to). `output/day_plan.json`, a stale artifact from Problem 5 that is not in the screenshot, was untracked but left on disk.
