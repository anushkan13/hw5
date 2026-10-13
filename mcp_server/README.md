# Campus Customs MCP Server

The single doorway between the Campus Customs agent team and the shop's data.

Every shop fact the agents use, and every change they make, goes through a tool
in `server.py`. The `backend/` package imports no database driver and has no
second shop-tools layer, so there is no way around this server.

## What it talks to

**`data/campus_customs_new.db`** — the working copy. The original
`data/campus_customs.db` is never opened by this server and stays untouched.

## Two connections, on purpose

- **Read tools** open the database in SQLite read-only mode
  (`file:...?mode=ro`). A write on that connection fails at the SQLite level
  with `attempt to write a readonly database`, so a read tool cannot change
  data even if it is buggy.
- **Write tools** — the four at the bottom of `server.py` — open a separate
  writable connection. `make_payment` does its work in a single transaction
  that rolls back entirely on any failure.

Nothing is ever invented. If a row is not there, the tool returns
`found: false` with a message rather than a plausible-looking value.

## Tables this server adds

The original schema has nowhere to record a prepared purchase order, an unsent
customer message, or a human's approval of a payment. Rather than overload an
existing table, the server creates three of its own the first time it starts:

| Table | Holds |
|---|---|
| `approvals` | One human's go-ahead for one specific payment. `used_payment_id` is set once it has been spent, so an approval can never fund two payments. |
| `prepared_requests` | Drafts awaiting a human. Status is always `awaiting_approval`. Nothing here has been ordered or paid. |
| `message_drafts` | Unsent customer messages. Status is always `draft`. |

## Read tools

| Tool | Table(s) | Returns |
|---|---|---|
| `get_today()` | `desk` | The shop's working date. Every overdue and ETA judgement counts from this, not the real clock. |
| `list_open_tickets()` | `tickets` | Every ticket still `open`, with its link fields. The Boss's work queue. |
| `list_tickets(status)` | `tickets` | The whole board, open and resolved alike, optionally filtered by status. What the dashboard reads, since the work queue deliberately hides finished tickets. |
| `get_ticket(ticket_id)` | `tickets` | One ticket in full. |
| `check_stock(sku, size)` | `inventory` | On-hand qty, name, and location. Keyed by SKU **and** size together. |
| `get_lease_terms(lease_id)` | `leases` | `monthly_rent`, `next_due`, landlord, space. |
| `get_margin(sku)` | `pricing` | `unit_cost`, `list_price`, margin per unit and percent. |
| `get_invoice(invoice_id)` | `invoices`, `vendors` | Amount, due date, status, plus `is_open` and `overdue` against `desk.date_today`. |
| `list_vendor_invoices(vendor_id, only_open)` | `invoices` | A vendor's invoices and `blocks_shipping` — true when an unpaid invoice stops them shipping. |
| `get_vendor(vendor_id)` | `vendors` | Name, specialty, `lead_days`. |
| `find_vendors(specialty)` | `vendors` | Vendors matching a specialty (partial, case-insensitive), or all of them. |
| `get_cash_balance(account)` | `cash_accounts` | The balance. This is the hard spending ceiling. |
| `list_approvals(unused_only)` | `approvals` | Human approvals on file. Readable by agents, writable by none. |
| `list_prepared_requests(ticket_id)` | `prepared_requests` | Drafts awaiting approval. |
| `list_message_drafts(ticket_id)` | `message_drafts` | Unsent drafts on the board. |
| `list_payments()` | `payments` | Payments that actually happened. |

## Write tools

### `make_payment(kind, ref_id, amount, account)` — the important one

The only tool that moves money, and it refuses more often than it agrees. All
three conditions must hold or **nothing is written at all**:

1. **A human approval must already be on file** matching this exact `kind`,
   `ref_id`, `amount`, and `account`, and not yet spent. No agent has a tool
   that writes to `approvals`; a person records one with `approve_cli.py`
   outside the agent run. Urgency, rewording, or a claim that a manager agreed
   does not substitute for that row.
2. **The balance must cover it.** Balances never go negative. A payment that
   would overdraw is refused outright, not partially made.
3. **The amount must be positive.**

On success it records the payment with the approving human's name, decrements
`cash_accounts`, marks the approval spent, and — when `kind` is `"invoice"` —
sets that invoice to `paid`, which is what clears the vendor to ship.

### `prepare_purchase_request(...)`

Records a restock or a payment as a **draft** for a human. Status is always
`awaiting_approval`; nothing is ordered and no money moves.

It deduplicates: pass `ref_id` (the invoice id, the lease id) and a second
draft for the same obligation returns the existing request with
`duplicate: true` instead of writing a new row. The shop owes invoice 501 once,
even if three tickets run into it.

### `update_ticket(ticket_id, status, notes)`

Sets status and **appends** to notes with a timestamp, so an agent cannot erase
a ticket's history.

### `record_customer_message(recipient, subject, body, drafted_by, ticket_id)`

Pins a drafted message to the board with status `draft`. There is no outbound
email in this system and no way to contact a vendor or a customer — recording a
draft is the end of the line.

## The human approval desk

`approve_cli.py` is the person in "human approval". It is deliberately **not**
an MCP tool, so no agent can reach it and no agent can approve its own
spending. Run it from the HW 5 folder:

```bash
.venv/bin/python mcp_server/approve_cli.py pending
.venv/bin/python mcp_server/approve_cli.py list
.venv/bin/python mcp_server/approve_cli.py approve --kind invoice --ref 501 \
    --amount 840 --by "Your Name"
.venv/bin/python mcp_server/approve_cli.py revoke --id 3
```

An approval is matched on `kind` + `ref_id` + `amount` + `account` and is spent
by the first payment that matches it.

## Connecting

Registered in `mcp.json` (and `.mcp.json`) at the HW 5 root as `campus-customs`
over stdio. To run it directly:

```bash
.venv/bin/python mcp_server/server.py
```

The agent team reads the command out of that same `mcp.json`, so the connection
config has one source of truth.
