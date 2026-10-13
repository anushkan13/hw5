"""Campus Customs MCP server.

The single doorway between the agent team and the shop's data. Every shop fact
the agents use, and every change they make, goes through a tool below. Nothing
here invents, estimates, or assumes a value: if a row is not in
data/campus_customs_new.db, the tool says so and returns found=False.

Two connections, on purpose:

    _query(...)  opens the database in SQLite read-only mode (mode=ro), so a
                 read tool physically cannot change data even if it is buggy.
    _write(...)  opens a writable connection, and only the four write tools
                 at the bottom of this file use it.

The payment tool is the important one. It is the approval gate and the
no-negative-cash guard, and it is written so that an agent cannot talk its way
past either. See make_payment for the details.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

# mcp_server/server.py -> HW 5/ -> HW 5/data/campus_customs_new.db
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "campus_customs_new.db"

mcp = FastMCP("campus-customs")


# --------------------------------------------------------------------------
# Connections
# --------------------------------------------------------------------------


def _query(sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    """Run a read-only query. Opened with mode=ro so it cannot write."""
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def _write() -> sqlite3.Connection:
    """Open a writable connection. Only the write tools below call this."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _today() -> str:
    """The shop's working date, which drives every overdue check."""
    rows = _query("SELECT date_today FROM desk LIMIT 1")
    return rows[0]["date_today"] if rows else ""


# --------------------------------------------------------------------------
# Tables this server adds to the working database
#
# The original schema has nowhere to put a prepared purchase order, a drafted
# customer message, or a human's approval of a payment. Rather than overload an
# existing table (or let an agent pretend a draft is a completed purchase),
# the server creates three small tables of its own the first time it starts.
# The original data/campus_customs.db is never touched.
# --------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS approvals (
    id              INTEGER PRIMARY KEY,
    kind            TEXT NOT NULL,
    ref_id          INTEGER,
    amount          REAL NOT NULL,
    account         TEXT NOT NULL,
    approved_by     TEXT NOT NULL,
    approved_at     TEXT NOT NULL,
    used_payment_id INTEGER
);

CREATE TABLE IF NOT EXISTS prepared_requests (
    id           INTEGER PRIMARY KEY,
    kind         TEXT NOT NULL,
    ref_id       INTEGER,
    ticket_id    INTEGER,
    vendor_id    INTEGER,
    sku          TEXT,
    size         TEXT,
    qty          INTEGER,
    amount       REAL,
    status       TEXT NOT NULL,
    details      TEXT,
    prepared_by  TEXT NOT NULL,
    prepared_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS message_drafts (
    id          INTEGER PRIMARY KEY,
    ticket_id   INTEGER,
    recipient   TEXT NOT NULL,
    subject     TEXT NOT NULL,
    body        TEXT NOT NULL,
    status      TEXT NOT NULL,
    drafted_by  TEXT NOT NULL,
    drafted_at  TEXT NOT NULL
);
"""


def init_db() -> None:
    conn = _write()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


# ==========================================================================
# READ TOOLS  (read-only connection)
# ==========================================================================


@mcp.tool()
def get_today() -> dict[str, Any]:
    """Return the shop's working date from the desk table.

    This is "today" for every deadline question: whether an invoice is overdue,
    how close the rent due date is, and what date a vendor ETA counts forward
    from. Do not use your own idea of the current date; use this.

    Returns:
        date_today and the desk notes.
    """
    rows = _query("SELECT date_today, notes FROM desk LIMIT 1")
    if not rows:
        return {"found": False, "message": "The desk table is empty."}
    return {"found": True, "date_today": rows[0]["date_today"], "notes": rows[0]["notes"]}


@mcp.tool()
def list_open_tickets() -> dict[str, Any]:
    """List every ticket whose status is still 'open'.

    The Boss's starting point: this is the day's work queue.

    Returns:
        count and a list of tickets with their linking fields (sku, size, qty,
        lease_id, invoice_id) so each one can be traced to the table it needs.
    """
    rows = _query(
        "SELECT id, type, requester, subject, sku, size, qty, lease_id, "
        "invoice_id, status, notes, created_at FROM tickets "
        "WHERE status = 'open' ORDER BY id"
    )
    return {"found": True, "count": len(rows), "tickets": [dict(r) for r in rows]}


@mcp.tool()
def list_tickets(status: str = "") -> dict[str, Any]:
    """List every ticket on the board, open and resolved alike.

    `list_open_tickets` is the Boss's work queue and deliberately hides
    finished work. This one shows the whole board, which is what a dashboard
    needs in order to say "resolved" rather than silently dropping a ticket.

    Args:
        status: Optional filter, e.g. "open" or "resolved". Empty returns all.

    Returns:
        count and a list of tickets with every field, newest id last.
    """
    sql = (
        "SELECT id, type, requester, subject, sku, size, qty, lease_id, "
        "invoice_id, status, notes, created_at FROM tickets"
    )
    params: tuple = ()
    if status:
        sql += " WHERE status = ?"
        params = (status,)
    rows = _query(sql + " ORDER BY id", params)
    return {"found": True, "count": len(rows), "tickets": [dict(r) for r in rows]}


@mcp.tool()
def get_ticket(ticket_id: int) -> dict[str, Any]:
    """Return one ticket by id, with every field including its links.

    Args:
        ticket_id: Ticket primary key, e.g. 101.

    Returns:
        The full ticket row, or found=False if there is no such ticket.
    """
    rows = _query(
        "SELECT id, type, requester, subject, sku, size, qty, lease_id, "
        "invoice_id, status, notes, created_at FROM tickets WHERE id = ?",
        (ticket_id,),
    )
    if not rows:
        return {"found": False, "ticket_id": ticket_id, "message": f"No ticket {ticket_id}."}
    return {"found": True, **dict(rows[0])}


@mcp.tool()
def check_stock(sku: str, size: str) -> dict[str, Any]:
    """Return on-hand quantity for one SKU in one size.

    Inventory is keyed by sku AND size together, so both are required; a SKU on
    its own does not identify a shelf position. qty is the whole truth about
    what is on the shelf. qty = 0 means a genuine stockout, not "check again".

    Args:
        sku: Inventory SKU, e.g. "CC-TEE-WHITE".
        size: Size code as stored, e.g. "S", "M", "L", "XL", "OS".

    Returns:
        sku, name, size, qty, location -- or found=False if that pair is not in
        the inventory table.
    """
    rows = _query(
        "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ? AND size = ?",
        (sku, size),
    )
    if not rows:
        return {
            "found": False,
            "sku": sku,
            "size": size,
            "message": f"No inventory row for SKU {sku} in size {size}.",
        }
    return {"found": True, **dict(rows[0])}


@mcp.tool()
def get_lease_terms(lease_id: int) -> dict[str, Any]:
    """Return the rent amount and next due date for one lease.

    Used to confirm what a landlord's rent notice actually obliges the shop to
    pay, and when -- rather than trusting the amount quoted in the notice.

    Args:
        lease_id: Primary key of the lease, e.g. 1.

    Returns:
        id, space_name, landlord, monthly_rent, next_due, notes -- or
        found=False if no lease has that id.
    """
    rows = _query(
        "SELECT id, space_name, landlord, monthly_rent, next_due, notes "
        "FROM leases WHERE id = ?",
        (lease_id,),
    )
    if not rows:
        return {"found": False, "lease_id": lease_id, "message": f"No lease with id {lease_id}."}
    return {"found": True, **dict(rows[0])}


@mcp.tool()
def get_margin(sku: str) -> dict[str, Any]:
    """Return unit cost, list price, and margin for one SKU.

    margin_per_unit and margin_pct are arithmetic on the two stored values --
    no assumed costs and no discount applied. Used to see how much room a
    discount request leaves before the shop sells below cost.

    Args:
        sku: SKU to price, e.g. "CC-HOOD-NAVY".

    Returns:
        sku, unit_cost, list_price, margin_per_unit, margin_pct -- or
        found=False if the SKU is not in the pricing table.
    """
    rows = _query("SELECT sku, unit_cost, list_price FROM pricing WHERE sku = ?", (sku,))
    if not rows:
        return {"found": False, "sku": sku, "message": f"No pricing row for SKU {sku}."}
    unit_cost = rows[0]["unit_cost"]
    list_price = rows[0]["list_price"]
    margin = list_price - unit_cost
    return {
        "found": True,
        "sku": rows[0]["sku"],
        "unit_cost": unit_cost,
        "list_price": list_price,
        "margin_per_unit": round(margin, 2),
        "margin_pct": round(margin / list_price * 100, 1) if list_price else None,
    }


@mcp.tool()
def get_invoice(invoice_id: int) -> dict[str, Any]:
    """Return one invoice, its status, and whether it is overdue today.

    overdue compares due_date against desk.date_today. status 'open' means the
    vendor has not been paid -- which is what blocks that vendor from shipping.

    Args:
        invoice_id: Invoice primary key, e.g. 501.

    Returns:
        id, vendor_id, vendor_name, amount, due_date, status, description,
        plus is_open, overdue and date_today -- or found=False.
    """
    rows = _query(
        "SELECT i.id, i.vendor_id, v.name AS vendor_name, i.amount, i.due_date, "
        "i.status, i.description FROM invoices i "
        "LEFT JOIN vendors v ON v.id = i.vendor_id WHERE i.id = ?",
        (invoice_id,),
    )
    if not rows:
        return {"found": False, "invoice_id": invoice_id, "message": f"No invoice {invoice_id}."}
    row = dict(rows[0])
    today = _today()
    row["is_open"] = row["status"] == "open"
    row["overdue"] = bool(row["is_open"] and today and row["due_date"] < today)
    row["date_today"] = today
    return {"found": True, **row}


@mcp.tool()
def list_vendor_invoices(vendor_id: int, only_open: bool = True) -> dict[str, Any]:
    """List a vendor's invoices, by default only the unpaid ones.

    Use this before promising a restock. A vendor with an open invoice will not
    ship, so an empty list here is what clears a vendor to supply.

    Args:
        vendor_id: Vendor primary key.
        only_open: True (default) returns just status='open' invoices.

    Returns:
        count, a list of invoices, and blocks_shipping -- True when the vendor
        has at least one open invoice.
    """
    sql = "SELECT id, vendor_id, amount, due_date, status, description FROM invoices WHERE vendor_id = ?"
    if only_open:
        sql += " AND status = 'open'"
    rows = _query(sql + " ORDER BY due_date", (vendor_id,))
    open_count = sum(1 for r in rows if r["status"] == "open")
    return {
        "found": True,
        "vendor_id": vendor_id,
        "count": len(rows),
        "invoices": [dict(r) for r in rows],
        "blocks_shipping": open_count > 0,
    }


@mcp.tool()
def get_vendor(vendor_id: int) -> dict[str, Any]:
    """Return one vendor's name, specialty, and lead_days.

    lead_days is the vendor's quoted lead time and is the only basis for an
    ETA. Do not shorten it to sound reassuring.

    Args:
        vendor_id: Vendor primary key, e.g. 1.

    Returns:
        id, name, specialty, lead_days -- or found=False.
    """
    rows = _query("SELECT id, name, specialty, lead_days FROM vendors WHERE id = ?", (vendor_id,))
    if not rows:
        return {"found": False, "vendor_id": vendor_id, "message": f"No vendor {vendor_id}."}
    return {"found": True, **dict(rows[0])}


@mcp.tool()
def find_vendors(specialty: str = "") -> dict[str, Any]:
    """Find vendors whose specialty matches, or list them all.

    Match is case-insensitive and partial, so "apparel" finds "apparel
    reprint". Call with no argument to see every vendor and pick the one whose
    specialty actually covers the item.

    Args:
        specialty: Text to look for in the specialty column. Empty lists all.

    Returns:
        count and a list of vendors with id, name, specialty, lead_days.
    """
    if specialty:
        rows = _query(
            "SELECT id, name, specialty, lead_days FROM vendors "
            "WHERE LOWER(specialty) LIKE ? ORDER BY lead_days",
            (f"%{specialty.lower()}%",),
        )
    else:
        rows = _query("SELECT id, name, specialty, lead_days FROM vendors ORDER BY id")
    return {"found": True, "count": len(rows), "vendors": [dict(r) for r in rows]}


@mcp.tool()
def get_cash_balance(account: str = "checking") -> dict[str, Any]:
    """Return the current balance of one cash account.

    This is the shop's hard spending limit. No revenue is modelled, so this
    number only ever goes down; money spent on one thing is not available for
    another. Check it before committing to any sequence of payments.

    Args:
        account: Account name, e.g. "checking".

    Returns:
        name, balance, date -- or found=False.
    """
    rows = _query("SELECT name, balance, date FROM cash_accounts WHERE name = ?", (account,))
    if not rows:
        return {"found": False, "account": account, "message": f"No cash account named {account}."}
    return {"found": True, **dict(rows[0])}


@mcp.tool()
def list_approvals(unused_only: bool = True) -> dict[str, Any]:
    """List the human approvals on file for payments.

    An approval is a human's written go-ahead for one specific payment. Agents
    cannot create these -- a person records them outside the agent run. Check
    here to see whether a payment you want to make is actually cleared.

    Args:
        unused_only: True (default) hides approvals already spent on a payment.

    Returns:
        count and the approvals, each with kind, ref_id, amount, account,
        approved_by, and used_payment_id (null while still unspent).
    """
    sql = (
        "SELECT id, kind, ref_id, amount, account, approved_by, approved_at, "
        "used_payment_id FROM approvals"
    )
    if unused_only:
        sql += " WHERE used_payment_id IS NULL"
    rows = _query(sql + " ORDER BY id")
    return {"found": True, "count": len(rows), "approvals": [dict(r) for r in rows]}


@mcp.tool()
def list_prepared_requests(ticket_id: int | None = None) -> dict[str, Any]:
    """List prepared purchase orders and restock requests awaiting approval.

    These are drafts. Nothing here has been ordered or paid.

    Args:
        ticket_id: Optional filter to one ticket.

    Returns:
        count and the prepared requests.
    """
    if ticket_id is None:
        rows = _query("SELECT * FROM prepared_requests ORDER BY id")
    else:
        rows = _query("SELECT * FROM prepared_requests WHERE ticket_id = ? ORDER BY id", (ticket_id,))
    return {"found": True, "count": len(rows), "requests": [dict(r) for r in rows]}


@mcp.tool()
def list_message_drafts(ticket_id: int | None = None) -> dict[str, Any]:
    """List customer message drafts sitting on the board.

    Every row here is unsent. The shop has no outbound email in this system.

    Args:
        ticket_id: Optional filter to one ticket.

    Returns:
        count and the drafts.
    """
    if ticket_id is None:
        rows = _query("SELECT * FROM message_drafts ORDER BY id")
    else:
        rows = _query("SELECT * FROM message_drafts WHERE ticket_id = ? ORDER BY id", (ticket_id,))
    return {"found": True, "count": len(rows), "drafts": [dict(r) for r in rows]}


@mcp.tool()
def list_payments() -> dict[str, Any]:
    """List payments that have actually been made, newest last.

    Args:
        none

    Returns:
        count and the payments, each with kind, ref_id, amount, account,
        paid_at and approved_by.
    """
    rows = _query(
        "SELECT id, kind, ref_id, amount, account, paid_at, approved_by FROM payments ORDER BY id"
    )
    return {"found": True, "count": len(rows), "payments": [dict(r) for r in rows]}


# ==========================================================================
# WRITE TOOLS  (writable connection)
# ==========================================================================


@mcp.tool()
def make_payment(kind: str, ref_id: int | None, amount: float, account: str = "checking") -> dict[str, Any]:
    """Pay money out of a cash account. The approval gate and cash guard.

    This is the only tool in the system that moves money, and it refuses far
    more often than it agrees. Three things must be true or nothing happens and
    nothing is written:

    1. A HUMAN APPROVAL must already be on file that matches this exact kind,
       ref_id, amount and account, and has not been spent on another payment.
       Agents cannot create approvals -- a person records them outside the run.
       Asking nicely, explaining the urgency, or claiming a manager said yes
       does not substitute for a row in the approvals table.
    2. The account must hold at least `amount`. Balances never go negative, so
       a payment that would overdraw is refused outright rather than partially
       made. Cash only ever goes out: no revenue is modelled.
    3. The amount must be positive.

    On success the payment is recorded in the payments table with the
    approving human's name, the cash account is decremented, the approval is
    marked spent so it cannot be reused, and -- when kind is "invoice" -- the
    invoice's status becomes 'paid', which is what unblocks that vendor from
    shipping. All of this happens in one transaction.

    Args:
        kind: What is being paid, e.g. "invoice" or "rent".
        ref_id: The id of the thing being paid (invoice id, lease id), or null.
        amount: Amount to pay. Must match the approval exactly.
        account: Cash account to pay from, default "checking".

    Returns:
        paid=True with payment_id, approved_by and new_balance; or paid=False
        with a reason explaining which of the three checks failed.
    """
    if amount is None or amount <= 0:
        return {"paid": False, "reason": "invalid_amount", "message": "Amount must be positive."}

    conn = _write()
    try:
        conn.execute("BEGIN IMMEDIATE")

        approval = conn.execute(
            "SELECT id, approved_by FROM approvals WHERE kind = ? AND amount = ? "
            "AND account = ? AND used_payment_id IS NULL "
            "AND ((ref_id IS NULL AND ? IS NULL) OR ref_id = ?) LIMIT 1",
            (kind, amount, account, ref_id, ref_id),
        ).fetchone()
        if approval is None:
            conn.rollback()
            return {
                "paid": False,
                "reason": "no_human_approval",
                "message": (
                    f"No unused human approval on file for {kind} ref {ref_id} of "
                    f"{amount} from {account}. A person must approve this exact "
                    "payment before it can be made. Nothing was paid."
                ),
            }

        cash = conn.execute(
            "SELECT balance FROM cash_accounts WHERE name = ?", (account,)
        ).fetchone()
        if cash is None:
            conn.rollback()
            return {
                "paid": False,
                "reason": "no_such_account",
                "message": f"No cash account named {account}. Nothing was paid.",
            }

        balance = cash["balance"]
        if balance < amount:
            conn.rollback()
            return {
                "paid": False,
                "reason": "insufficient_funds",
                "message": (
                    f"{account} holds {balance:.2f} but the payment is {amount:.2f}. "
                    "Balances never go negative, so this payment is refused. "
                    "Nothing was paid."
                ),
                "balance": balance,
                "shortfall": round(amount - balance, 2),
            }

        paid_at = _now()
        cur = conn.execute(
            "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (kind, ref_id, amount, account, paid_at, approval["approved_by"]),
        )
        payment_id = cur.lastrowid
        new_balance = round(balance - amount, 2)
        conn.execute(
            "UPDATE cash_accounts SET balance = ? WHERE name = ?", (new_balance, account)
        )
        conn.execute(
            "UPDATE approvals SET used_payment_id = ? WHERE id = ?", (payment_id, approval["id"])
        )

        invoice_closed = False
        if kind == "invoice" and ref_id is not None:
            res = conn.execute(
                "UPDATE invoices SET status = 'paid' WHERE id = ? AND status = 'open'", (ref_id,)
            )
            invoice_closed = res.rowcount > 0

        # Close out the prepared request this payment settles. Without this a
        # request stays 'awaiting_approval' even after it has been paid, and
        # every later agent reads the board as "this is still outstanding" --
        # which is wrong, and keeps a finished ticket from ever being resolved.
        settled = conn.execute(
            "SELECT id FROM prepared_requests WHERE status = 'awaiting_approval' "
            "AND amount = ? AND (ref_id = ? OR ref_id IS NULL) ORDER BY id LIMIT 1",
            (amount, ref_id),
        ).fetchone()
        request_settled = None
        if settled is not None:
            conn.execute(
                "UPDATE prepared_requests SET status = 'approved_and_paid' WHERE id = ?",
                (settled["id"],),
            )
            request_settled = settled["id"]

        conn.commit()
        return {
            "paid": True,
            "payment_id": payment_id,
            "kind": kind,
            "ref_id": ref_id,
            "amount": amount,
            "account": account,
            "approved_by": approval["approved_by"],
            "paid_at": paid_at,
            "previous_balance": balance,
            "new_balance": new_balance,
            "invoice_marked_paid": invoice_closed,
            "prepared_request_settled": request_settled,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@mcp.tool()
def prepare_purchase_request(
    kind: str,
    prepared_by: str,
    details: str,
    ref_id: int | None = None,
    ticket_id: int | None = None,
    vendor_id: int | None = None,
    sku: str = "",
    size: str = "",
    qty: int | None = None,
    amount: float | None = None,
) -> dict[str, Any]:
    """Write down a purchase order or restock request as a DRAFT for approval.

    Nothing is ordered and no money moves. This records what someone is asking
    a human to approve, and its status is always 'awaiting_approval'. Use it to
    hand a restock or a payment request to a person; never describe the result
    as a placed order or a completed purchase.

    One obligation, one request. The shop owes invoice 501 once, even if three
    different tickets run into it. So this tool will not create a second draft
    for something already waiting: if a matching request is already on the
    desk it returns that one with duplicate=True, and no new row is written.
    Matching is on `ref_id` plus `kind` when a ref_id is given -- which is why
    a payment draft should always carry the id of the invoice or lease it
    settles -- and otherwise on the item, quantity, and amount.

    Args:
        kind: What is being prepared, e.g. "restock_po", "invoice_payment",
            "rent_payment".
        prepared_by: Which agent prepared it, e.g. "inventory".
        details: Plain words covering what, why, how much, and what it unblocks.
        ref_id: The id of the thing being settled -- the invoice id for an
            invoice payment, the lease id for rent. Give this whenever one
            exists; it is what stops the same bill being drafted twice.
        ticket_id: Ticket this serves, if any.
        vendor_id: Vendor this would go to, if any.
        sku: SKU to restock, if any.
        size: Size to restock, if any.
        qty: Units to order, if any.
        amount: Money involved, if known.

    Returns:
        recorded=True with request_id and status 'awaiting_approval'; or
        duplicate=True with the existing request_id when this obligation is
        already on the desk.
    """
    conn = _write()
    try:
        if ref_id is not None:
            existing = conn.execute(
                "SELECT id, ticket_id, prepared_by, amount FROM prepared_requests "
                "WHERE status = 'awaiting_approval' AND kind = ? AND ref_id = ? LIMIT 1",
                (kind, ref_id),
            ).fetchone()
        else:
            existing = conn.execute(
                "SELECT id, ticket_id, prepared_by, amount FROM prepared_requests "
                "WHERE status = 'awaiting_approval' AND kind = ? AND ref_id IS NULL "
                "AND IFNULL(sku,'') = ? AND IFNULL(size,'') = ? "
                "AND IFNULL(qty,-1) = ? AND IFNULL(amount,-1) = ? LIMIT 1",
                (kind, sku or "", size or "", qty if qty is not None else -1,
                 amount if amount is not None else -1),
            ).fetchone()

        if existing is not None:
            return {
                "recorded": False,
                "duplicate": True,
                "request_id": existing["id"],
                "kind": kind,
                "ref_id": ref_id,
                "amount": existing["amount"],
                "status": "awaiting_approval",
                "ticket_id": existing["ticket_id"],
                "prepared_by": existing["prepared_by"],
                "note": (
                    f"Request #{existing['id']} already covers this and is waiting for "
                    f"approval (first raised on ticket {existing['ticket_id']} by "
                    f"{existing['prepared_by']}). Nothing new was written. Refer to that "
                    "request rather than preparing a second one."
                ),
            }

        prepared_at = _now()
        cur = conn.execute(
            "INSERT INTO prepared_requests (kind, ref_id, ticket_id, vendor_id, sku, size, "
            "qty, amount, status, details, prepared_by, prepared_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'awaiting_approval', ?, ?, ?)",
            (kind, ref_id, ticket_id, vendor_id, sku or None, size or None, qty, amount,
             details, prepared_by, prepared_at),
        )
        conn.commit()
        return {
            "recorded": True,
            "duplicate": False,
            "request_id": cur.lastrowid,
            "kind": kind,
            "ref_id": ref_id,
            "amount": amount,
            "status": "awaiting_approval",
            "ticket_id": ticket_id,
            "prepared_by": prepared_by,
            "prepared_at": prepared_at,
            "note": "Draft only. Nothing has been ordered and no money has moved.",
        }
    finally:
        conn.close()


@mcp.tool()
def update_ticket(ticket_id: int, status: str = "", notes: str = "") -> dict[str, Any]:
    """Update a ticket's status and/or append to its notes.

    Notes are appended, never overwritten, so the history of a ticket survives.
    Leave an argument empty to leave that field alone.

    Args:
        ticket_id: Ticket to update.
        status: New status, e.g. "in_progress", "blocked", "resolved". Empty
            leaves the status unchanged.
        notes: Text to append to the existing notes. Empty appends nothing.

    Returns:
        updated=True with the ticket's new status and notes, or found=False.
    """
    conn = _write()
    try:
        row = conn.execute(
            "SELECT id, status, notes FROM tickets WHERE id = ?", (ticket_id,)
        ).fetchone()
        if row is None:
            return {"found": False, "ticket_id": ticket_id, "message": f"No ticket {ticket_id}."}

        new_status = status or row["status"]
        new_notes = row["notes"] or ""
        if notes:
            stamp = _now()
            new_notes = (new_notes + f"\n[{stamp}] {notes}").strip()

        conn.execute(
            "UPDATE tickets SET status = ?, notes = ? WHERE id = ?",
            (new_status, new_notes, ticket_id),
        )
        conn.commit()
        return {
            "found": True,
            "updated": True,
            "ticket_id": ticket_id,
            "status": new_status,
            "notes": new_notes,
        }
    finally:
        conn.close()


@mcp.tool()
def record_customer_message(
    recipient: str,
    subject: str,
    body: str,
    drafted_by: str,
    ticket_id: int | None = None,
) -> dict[str, Any]:
    """Pin a drafted customer message to the board. It is NOT sent.

    This system has no outbound email and no way to contact a vendor or a
    customer. Recording a draft here is the end of the line: a person reads it
    and decides whether to send it. Never tell anyone the message went out.

    Args:
        recipient: Who the message is addressed to, e.g. "Tauhid Zaman".
        subject: Subject line.
        body: The message itself, in plain words.
        drafted_by: Which agent wrote it, e.g. "customer_service".
        ticket_id: Ticket this message belongs to, if any.

    Returns:
        recorded=True with draft_id and status 'draft'.
    """
    conn = _write()
    try:
        drafted_at = _now()
        cur = conn.execute(
            "INSERT INTO message_drafts (ticket_id, recipient, subject, body, status, "
            "drafted_by, drafted_at) VALUES (?, ?, ?, ?, 'draft', ?, ?)",
            (ticket_id, recipient, subject, body, drafted_by, drafted_at),
        )
        conn.commit()
        return {
            "recorded": True,
            "draft_id": cur.lastrowid,
            "status": "draft",
            "recipient": recipient,
            "ticket_id": ticket_id,
            "drafted_at": drafted_at,
            "note": "Draft only. This message has not been sent to anyone.",
        }
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    mcp.run()
