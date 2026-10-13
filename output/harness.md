# Campus Customs — Agent Harness

Working database: `data/campus_customs_new.db` (copy of `data/campus_customs.db`, which stays untouched).

## Agents

Five PydanticAI agents, all on `gpt-6-luna` through Portkey, all able to delegate to
any of the others (full connectivity). Prompt files live in `backend/prompts/`.

| Agent | Role | Prompt | Writes it can make |
|---|---|---|---|
| **Boss** | Reads each open ticket, decides who works it, sequences the day under the cash constraint, makes the final call. Never approves or makes payments. | `boss.md` | `update_ticket` |
| **Inventory** | Checks stock by SKU **and** size, spots shortfalls, picks the vendor by specialty and computes the ETA from `lead_days`. Knows an unpaid invoice blocks a vendor from shipping, and hands that to Accounting. Prepares restocks; never pays. | `inventory.md` | `prepare_purchase_request`, `update_ticket` |
| **Accounting** | Watches cash and invoices, checks margins for discount requests, prepares payments and POs for human approval. Executes a payment only when a human approval is already on file. | `accounting.md` | `prepare_purchase_request`, `make_payment`, `update_ticket` |
| **Facilities** | The shop space: leases, rent amount, next-due date. Prepares the rent payment under exactly the same rules as Accounting. | `facilities.md` | `prepare_purchase_request`, `make_payment`, `update_ticket` |
| **Customer Service** | Drafts order updates, stockout apologies with a real vendor-lead-time ETA, and discount quotes. Drafts stay on the board; it never sends email and never contacts a vendor. | `customer_service.md` | `record_customer_message`, `update_ticket` |

Agent-to-agent talking is PydanticAI: every agent carries a `delegate_to(agent_name, task)`
tool that runs another agent and returns its report. Agent-to-shop talking is MCP and only
MCP — `backend/` contains no SQLite import and no second shop-tools layer.

## Tables and relevance

### `tickets`
Fields: `id`, `type`, `requester`, `subject`, `sku`, `size`, `qty`, `lease_id`, `invoice_id`, `status`, `notes`, `created_at`

- Boss: the work queue — `type` and the link fields are what routing decisions are made from.
- Inventory: `sku`/`size`/`qty` say exactly what stock to check.
- Accounting: `invoice_id` ties a ticket to money owed.
- Facilities: `lease_id` ties a ticket to a space.
- Customer Service: `requester`, `subject`, and `notes` are the raw material for a reply.

### `inventory`
Fields: `sku`, `name`, `size`, `qty`, `location`

- Inventory: the stock-on-hand table; `qty` per `sku`+`size` is how a shortfall is detected.
- Boss: tells the Boss whether a ticket is fillable now or needs a restock path.
- Customer Service: `name` and `location` give the customer-facing product wording.

### `pricing`
Fields: `sku`, `unit_cost`, `list_price`

- Accounting: margin = `list_price` − `unit_cost`; the basis for approving or refusing a discount.
- Boss: a price-override ticket cannot be decided without this table.
- Customer Service: `list_price` is the number quoted to a customer.

### `vendors`
Fields: `id`, `name`, `specialty`, `lead_days`

- Inventory: `specialty` and `lead_days` pick the vendor that can restock a short SKU in time.
- Accounting: vendor identity for invoices and purchase orders.
- Customer Service: `lead_days` is what turns into a realistic ETA in a message.

### `invoices`
Fields: `id`, `vendor_id`, `amount`, `due_date`, `status`, `description`

- Accounting: open amounts and due dates — what has to be paid and when.
- Boss: an overdue invoice can block or reprioritize a ticket.
- Inventory: `description` links an invoice back to the SKU it was raised for.

### `leases`
Fields: `id`, `space_name`, `landlord`, `monthly_rent`, `next_due`, `notes`

- Facilities: the shop space record; rent amount and next due date.
- Accounting: rent is a committed outflow to reserve cash against.
- Boss: a rent notice is routed to Facilities on the strength of this table.

### `cash_accounts`
Fields: `name`, `balance`, `date`

- Accounting: the cash ceiling — nothing can be paid beyond `balance`.
- Boss: decides what gets paid first when cash does not cover everything.
- Facilities: confirms rent is actually affordable before committing.

### `payments`
Fields: `id`, `kind`, `ref_id`, `amount`, `account`, `paid_at`, `approved_by`

- Accounting: the ledger of outflows; `approved_by` records the human sign-off.
- Boss: the audit trail of what was actually approved and acted on.
- Facilities: where a rent payment is recorded once made.

### `desk`
Fields: `date_today`, `notes`

- Boss: supplies "today" (2026-08-31), so due dates and overdue status are judged against a fixed date rather than the real clock.
- Accounting / Facilities: same reference date for "due in 2 days" and "overdue" calls.

## MCP server tools

Server: `mcp_server/server.py` (FastMCP) over `data/campus_customs_new.db`. This is the
only route between the agents and the shop's data.

**Two connections, on purpose.** Read tools open the database in SQLite read-only mode
(`mode=ro`), so a read tool physically cannot change data even if it is buggy — a write
attempt on that connection raises `attempt to write a readonly database`. Only the four
write tools at the bottom open a writable connection.

Every tool returns `found: False` with a message when a row is absent, so an agent is never
handed a fabricated quantity, rent, price, or date.

### Read tools

| Tool | Table(s) | What it is for |
|---|---|---|
| `get_today()` | `desk` | The shop's working date (2026-08-31). Every overdue and ETA judgement counts from this, not the real clock. |
| `list_open_tickets()` | `tickets` | The Boss's work queue — open tickets only. |
| `list_tickets(status)` | `tickets` | The whole board, open and resolved alike, optionally filtered by status. What the dashboard reads, since the work queue deliberately hides finished tickets. |
| `get_ticket(ticket_id)` | `tickets` | One ticket with its link fields, so it can be traced to the table it needs. |
| `check_stock(sku, size)` | `inventory` | On-hand qty for a SKU **and** size together — the table's real key. |
| `get_lease_terms(lease_id)` | `leases` | Rent amount and next-due date, to check a landlord's claim against the record. |
| `get_margin(sku)` | `pricing` | `unit_cost`, `list_price`, and the margin between them. |
| `get_invoice(invoice_id)` | `invoices` + `vendors` | An invoice, its status, and whether it is overdue against `desk.date_today`. |
| `list_vendor_invoices(vendor_id)` | `invoices` | A vendor's unpaid invoices, plus `blocks_shipping` — the flag that says the vendor will not ship. |
| `get_vendor(vendor_id)` | `vendors` | Name, specialty, and `lead_days` for an ETA. |
| `find_vendors(specialty)` | `vendors` | Find a supplier by specialty, or list them all. |
| `get_cash_balance(account)` | `cash_accounts` | The hard spending ceiling. |
| `list_approvals(unused_only)` | `approvals` | The human approvals on file. Agents can read these but cannot create them. |
| `list_prepared_requests(ticket_id)` | `prepared_requests` | Drafts awaiting approval. Checked before preparing, to avoid drafting the same bill twice. |
| `list_message_drafts(ticket_id)` | `message_drafts` | Unsent customer messages on the board. |
| `list_payments()` | `payments` | Payments that actually happened. |

### Write tools

| Tool | Table(s) | What it is for |
|---|---|---|
| **`make_payment(kind, ref_id, amount, account)`** | `approvals`, `cash_accounts`, `payments`, `invoices` | **The approval gate and the no-negative-cash guard.** See below. |
| `prepare_purchase_request(...)` | `prepared_requests` | Records a restock or payment as a **draft** awaiting approval. Never an order, never a purchase. Deduplicates on `kind` + `ref_id` so one obligation cannot reach the desk twice. |
| `update_ticket(ticket_id, status, notes)` | `tickets` | Sets status and **appends** to notes, so a ticket's history survives. |
| `record_customer_message(...)` | `message_drafts` | Pins a drafted message to the board with status `draft`. Nothing is sent. |

### Tables the server adds

The original schema has nowhere to put a prepared purchase order, an unsent draft, or a
human's approval, so the server creates three small tables of its own on first start.
`data/campus_customs.db` is never touched.

- `approvals` — one human's go-ahead for one specific payment, with `used_payment_id` set once spent.
- `prepared_requests` — drafts awaiting approval; status is always `awaiting_approval`.
- `message_drafts` — unsent customer messages; status is always `draft`.

### Why `make_payment` is the important one

It is the only tool in the system that moves money, and it refuses more often than it
agrees. All three must hold or nothing is written at all (one transaction, rolled back on
any failure):

1. **A human approval must already be on file** matching the exact `kind`, `ref_id`,
   `amount`, and `account`, and not yet spent. Agents have no tool that writes to
   `approvals` — a person records one with `mcp_server/approve_cli.py`, outside the agent
   run. Arguing, rewording, or claiming a manager said yes cannot substitute for that row.
2. **The balance must cover it.** Balances never go negative; a payment that would overdraw
   is refused outright rather than partially made.
3. **The amount must be positive.**

On success it records the payment with the approving human's name, decrements
`cash_accounts`, marks the approval spent so it cannot fund a second payment, sets the
prepared request it settles to `approved_and_paid`, and — for `kind="invoice"` — sets the
invoice to `paid`, which is what unblocks that vendor. Closing out the prepared request
matters more than it looks: without it a paid request still reads `awaiting_approval`, and
every later agent correctly concludes the work is outstanding, so a finished ticket can
never be resolved.

Verified behaviour: refuses with no approval; pays and decrements on a valid approval;
refuses a replay of a spent approval; refuses when the amount does not match the approval;
refuses an overdraft and leaves the balance untouched.

### Original tables, and the ticket each tool unlocks

The three tools from Problem 3 still carry the original tickets:

| Tool | Reads | Unlocks | Why this tool is right for that ticket |
|---|---|---|---|
| `check_stock(sku, size)` | `inventory` | Ticket 101 — customer order, 1x CC-TEE-WHITE size S | Ticket 101 cannot be answered until someone knows whether the specific (CC-TEE-WHITE, S) row has a qty of at least 1, and this tool is the only thing that returns that exact per-size number — it reports qty 0, which is what turns the ticket from "pick and ship" into "reorder". |
| `get_lease_terms(lease_id)` | `leases` | Ticket 102 — rent notice from Elm City Properties | Ticket 102 is an unverified email claiming rent is due in 2 days, and this tool checks that claim against lease 1's stored `monthly_rent` of 2400.00 and `next_due` of 2026-09-02 so the shop pays the recorded amount on the recorded date rather than what the landlord's message asserts. |
| `get_margin(sku)` | `pricing` | Ticket 103 — Yale AI Club bulk discount, 20x CC-HOOD-NAVY size M | Ticket 103 asks for a discount with no stated figure, and this tool supplies the 36.00 per-unit gap between CC-HOOD-NAVY's 22.00 unit_cost and 58.00 list_price, which is the ceiling any bulk discount has to stay inside to avoid selling below cost. |

## Audit trail

Every agent-loop step is appended to `output/audit_trail.json` — never wiped between runs,
with `run_id` grouping the steps of one run. Each entry records the time, the agent and its
delegation depth, the MCP tool called with short args and a short result, any delegation to
another agent, and the stop reason. MCP calls are captured live through the toolset's
`process_tool_call` hook, so the trail reflects what actually happened rather than a
reconstruction, and a failed call is recorded with `stop_reason: tool_error` too.

## Safety

The guardrails a real business would want before letting agents near real customers and
real money.

| Guardrail | How it is enforced |
|---|---|
| **Human approval before any payment** | `make_payment` requires a matching unspent row in `approvals`. No agent — not even the Boss — has a tool that writes to that table; a person uses `mcp_server/approve_cli.py`. The approval is consumed on use, so it cannot fund a second payment. |
| **No negative balances** | `make_payment` refuses when the balance would go below zero, and rolls back. No partial payments, no overdraft. |
| **Cash only goes out** | No revenue is modelled anywhere. No tool increases a balance, so spending on one ticket genuinely removes it from another — which is what forces the Boss to sequence. |
| **Drafts are never sent** | There is no outbound email, no vendor contact, and no send tool of any kind. `record_customer_message` writes status `draft`; `prepare_purchase_request` writes `awaiting_approval` and says in its own result that nothing was ordered. |
| **All facts from the database via MCP** | `backend/` imports no database driver and has no second shop-tools layer. Every fact reaches an agent through an MCP tool. |
| **Never invent** | Every tool returns `found: False` rather than a plausible value, and every prompt says to report the gap instead of filling it. |
| **Reads cannot write** | Read tools use a `mode=ro` connection; a write on it raises at the SQLite level, not just by convention. |
| **One obligation, one draft** | `prepare_purchase_request` deduplicates on `kind` + `ref_id`, so the same invoice cannot reach the approval desk three times through three different tickets. |
| **Notes are appended, not overwritten** | `update_ticket` appends with a timestamp, so an agent cannot erase a ticket's history. |

### Limits that keep token use in check

| Limit | Value | Where |
|---|---|---|
| Model | **`gpt-6-luna` only** — nothing escalates to a larger model | `team.MODEL_NAME` |
| Model requests per agent run | 28 (Boss) / 14 (specialists) | `team.BOSS_MAX_REQUESTS`, `team.MAX_REQUESTS` |
| Tool calls per agent run | 40 (Boss) / 20 (specialists) | `team.BOSS_MAX_TOOL_CALLS`, `team.MAX_TOOL_CALLS` |
| **Delegation depth** | **3** — stops agents handing a task round in circles forever | `team.MAX_DELEGATION_DEPTH` |
| Delegations per run | 12, counted across the whole run, not per branch | `team.MAX_DELEGATIONS` |
| Output validation retries | 2 | `Agent(..., retries=2)` |
| Audit snippet length | 400 chars per arg/result | `audit.SNIPPET` |

The Boss gets more headroom than the specialists because it works every ticket in the queue
and each `delegate_to` counts against its tool budget. A refused delegation returns
`refused: true` with the reason and an instruction not to retry, so hitting a cap degrades
into an honest "unfinished" rather than a loop.

## Backend routes

FastAPI app in `backend/main.py`, run from the `backend/` folder with
`uvicorn main:app --reload --port 8000`. CORS is enabled for the React dev server
(`localhost:5173` / `localhost:3000`).

| Route | What it does |
|---|---|
| `GET /api/health` | Liveness check that also confirms the MCP server is reachable and reports its tool count. |
| `GET /api/tickets` | Returns every ticket on the board with `is_open` / `is_resolved` flags, read through the MCP `list_tickets` tool. |
| `POST /api/tickets/{ticket_id}/run` | Runs the agent team on that one ticket; the agents prepare payments and drafts for a human and never execute a payment. |
| `GET /api/events?limit=&run_id=` | Returns recent agent events — which agent acted, which tool it called, and any delegation — read from the append-only audit trail so the board can poll to refresh. |
| `POST /api/approvals` | The human-approval step and the only route that can change cash: records the approval no agent can write, then executes it through the existing `make_payment` path, which still refuses if the balance will not cover it. |
| `GET /api/cash?account=` | Returns the current balance of a cash account, read through the MCP `get_cash_balance` tool. |
| `POST /api/reset` | Copies the pristine `campus_customs.db` over the working `campus_customs_new.db` for a fresh run, then restarts the MCP server so it rebuilds its own tables; the audit trail is left intact. |

Shop reads and the agent run go through the existing MCP tools and agent team — there is no
SQLite in `backend/main.py` and no second shop-tools layer. Writing a human approval is the
one deliberate exception: it is not an MCP tool at all, so no agent can reach it, and
`POST /api/approvals` is the single place in the system that can authorise money leaving the
shop.

## The dashboard

`frontend/`, React 19 + Vite 8 + TypeScript, started with `npm run dev` on port 5173 and
talking to the backend at `http://localhost:8000`. No state is held anywhere but the
database and the audit trail; the board is a view of them.

| Piece | File | What it does |
|---|---|---|
| Room and board | `src/App.tsx` | Ticket rail, the five seats, the run log, the Boss's decision card, the approval modal and the cash ledger. |
| Bulldog character | `src/Bulldog.tsx` | One original SVG bulldog — stool, dog, paws, desk, supplies and name tag in a single viewBox — reused in five apron colours. |
| Seating and phrasing | `src/agents.ts` | Where each agent sits, its apron colour, and the mapping from raw tool names to plain language (`check_stock` → "Counting what's on the shelf"). |
| API client | `src/api.ts` | Thin `fetch` wrapper, reads sent with `cache: "no-store"`. |
| Types | `src/types.ts` | The shapes the backend returns. |

**How it reads.** The Boss sits at the head of the room, crowned and larger; the four
specialists sit in a line below. All ten agent pairs are drawn as dashed wires, and a wire
lights in a crawling rainbow for as long as those two agents are actually mid-conversation —
driven off the `in_progress` and `completed` delegation events in the trail, not a timer.
Each bulldog carries a speech bubble with what it is doing in plain words, the tool name
underneath, and the figure that came back.

**Live updates.** The run request is long-lived, so the board notes the latest run id, fires
the request, then polls `GET /api/events` about once a second and streams the new run's steps
in, with a final sweep when the request returns.

**Money.** The balance sits in the masthead as a brass-and-cream cash drawer. On an approved
payment it jolts and the number falls, driven from the approve response itself rather than a
re-read. Anything the agents prepare appears under "Waiting on you" as a gold card; the modal
states what is being approved, in the agent's own words, with the amount editable.

**Honesty about status.** A ticket card shows a green **Resolved** badge once its run
finishes, and underneath it, in small italics, whatever the shop's records actually say — so a
ticket the agents left `blocked` is never silently presented as closed.

## Running it

Everything needs `PORTKEY_API_KEY` in the **root** `.env` (two levels up from `backend/`).

**The dashboard**, which is the normal way in — two terminals:

```
cd backend && uvicorn main:app --reload --port 8000     # API on :8000
cd frontend && npm run dev                              # board on :5173
```

**The team on its own**, without the dashboard:

```
.venv/bin/python backend/run_team.py                           # work every open ticket
.venv/bin/python backend/run_team.py --task "Ticket 101 only."  # one ticket, your wording
```

**The human approval desk**, which no agent can reach:

```
.venv/bin/python mcp_server/approve_cli.py pending        # what is waiting on a human
.venv/bin/python mcp_server/approve_cli.py list           # approvals already on file
.venv/bin/python mcp_server/approve_cli.py approve --kind invoice --ref 501 \
    --amount 840 --by "Your Name"
```

**The MCP server** directly, if you want to drive the tools yourself:

```
.venv/bin/python mcp_server/server.py
```

To start over, either press **Reset board** on the dashboard or `POST /api/reset`; both copy
the pristine `data/campus_customs.db` over the working `data/campus_customs_new.db`. The
audit trail is deliberately left alone, because it is append-only across runs.

## The canonical run

One worked example of the whole system, recorded in `output/resolved_tickets.json`,
`output/desk_tickets.html` and `output/resolved_board.html`.

Opening balance **$3,400.00**, shop working date **2026-08-31**. All three tickets finished
at status `resolved`.

| Ticket | Cash | Why |
|---|---|---|
| 101 — Bulldog tee | **−$848.00** | Invoice 501 ($840.00) paid, which cleared the vendor to ship, plus a $8.00 one-unit restock. Both approved by a human. |
| 102 — Rent notice | **−$2,400.00** | Lease 1 rent, verified against the lease record rather than the landlord's email, approved by a human and paid. |
| 103 — Bulk discount | **$0.00** | Quoted at $50.00 a hoodie against a $22.00 cost floor. The 12-unit restock costs $264.00 and the drawer held $152.00, so it was never approved. |

`$3,400.00 − $840.00 − $8.00 − $2,400.00 = $152.00`, which is what `cash_accounts.balance`
reads in the working database.

The three tickets together asked for $3,512.00 against $3,400.00 of cash, so **$112.00 of it
could never be funded**. That is the point of the exercise rather than a failure: the shop
paid the bill that was blocking a vendor, paid the rent that was due in two days, and left
the largest discretionary item — twelve hoodies — honestly marked as not secured.
