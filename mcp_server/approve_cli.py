"""Human approval desk for Campus Customs payments.

This script is the person in "human approval". It is deliberately NOT an MCP
tool: no agent can reach it, so no agent can approve its own spending. A human
runs it from a terminal to record that they have authorised one specific
payment, and `make_payment` then finds that row and lets the money move.

An approval is matched on kind + ref_id + amount + account, and is spent by the
first payment that matches it, so one approval can never fund two payments.

Usage, from the HW 5 folder:

    .venv/bin/python mcp_server/approve_cli.py pending
        Show the prepared requests that are waiting on a human.

    .venv/bin/python mcp_server/approve_cli.py list
        Show approvals already on file, spent and unspent.

    .venv/bin/python mcp_server/approve_cli.py approve \\
        --kind invoice --ref 501 --amount 840 --by "Anushka Nair"
        Record one approval. --account defaults to checking.

    .venv/bin/python mcp_server/approve_cli.py revoke --id 3
        Remove an unspent approval.
"""

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "campus_customs_new.db"


APPROVALS_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS approvals ("
    "id INTEGER PRIMARY KEY, kind TEXT NOT NULL, ref_id INTEGER, "
    "amount REAL NOT NULL, account TEXT NOT NULL, approved_by TEXT NOT NULL, "
    "approved_at TEXT NOT NULL, used_payment_id INTEGER)"
)


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


class ApprovalError(RuntimeError):
    """Raised when an approval cannot be recorded."""


def record_approval(
    kind: str,
    amount: float,
    approved_by: str,
    ref_id: int | None = None,
    account: str = "checking",
) -> dict:
    """Record one human approval for one specific payment.

    This is THE human path. It writes the row that `make_payment` looks for,
    and it is deliberately not an MCP tool, so no agent can reach it and no
    agent can authorise its own spending. The FastAPI approve route calls this
    same function, so there is exactly one implementation of "a person said
    yes" rather than two that could drift apart.

    Raises:
        ApprovalError: if the approver is unnamed, the amount is not positive,
            or the cash account does not exist.
    """
    if not approved_by or not approved_by.strip():
        raise ApprovalError("An approval must name the human doing the approving.")
    if amount is None or amount <= 0:
        raise ApprovalError("The approved amount must be positive.")

    conn = connect()
    try:
        conn.execute(APPROVALS_SCHEMA)
        row = conn.execute(
            "SELECT balance FROM cash_accounts WHERE name = ?", (account,)
        ).fetchone()
        if row is None:
            raise ApprovalError(f"No cash account named {account}.")

        approved_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        cur = conn.execute(
            "INSERT INTO approvals (kind, ref_id, amount, account, approved_by, "
            "approved_at, used_payment_id) VALUES (?, ?, ?, ?, ?, ?, NULL)",
            (kind, ref_id, amount, account, approved_by.strip(), approved_at),
        )
        conn.commit()
        return {
            "approval_id": cur.lastrowid,
            "kind": kind,
            "ref_id": ref_id,
            "amount": amount,
            "account": account,
            "approved_by": approved_by.strip(),
            "approved_at": approved_at,
            "balance_at_approval": row["balance"],
            # Recording an approval does not move money. make_payment still
            # refuses if the balance will not cover it.
            "covers_balance": row["balance"] >= amount,
        }
    finally:
        conn.close()


def cmd_pending(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        "SELECT id, kind, ticket_id, vendor_id, sku, size, qty, amount, details, "
        "prepared_by, prepared_at FROM prepared_requests "
        "WHERE status = 'awaiting_approval' ORDER BY id"
    ).fetchall()
    if not rows:
        print("Nothing is waiting for approval.")
        return
    print(f"{len(rows)} request(s) awaiting approval:\n")
    for r in rows:
        amount = f"{r['amount']:.2f}" if r["amount"] is not None else "-"
        print(f"  request #{r['id']}  {r['kind']}  amount {amount}  "
              f"ticket {r['ticket_id']}  prepared by {r['prepared_by']}")
        print(f"      {r['details']}")
        print()


def cmd_list(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        "SELECT id, kind, ref_id, amount, account, approved_by, approved_at, "
        "used_payment_id FROM approvals ORDER BY id"
    ).fetchall()
    if not rows:
        print("No approvals on file.")
        return
    for r in rows:
        state = f"spent on payment {r['used_payment_id']}" if r["used_payment_id"] else "UNSPENT"
        print(f"  approval #{r['id']}  {r['kind']} ref={r['ref_id']}  "
              f"{r['amount']:.2f} from {r['account']}  by {r['approved_by']}  [{state}]")


def cmd_approve(conn: sqlite3.Connection, args: argparse.Namespace) -> int:
    try:
        result = record_approval(
            kind=args.kind,
            amount=args.amount,
            approved_by=args.by,
            ref_id=args.ref,
            account=args.account,
        )
    except ApprovalError as exc:
        print(f"Refusing: {exc}", file=sys.stderr)
        return 1

    if not result["covers_balance"]:
        print(f"Warning: {result['account']} holds {result['balance_at_approval']:.2f}, "
              f"which is less than {result['amount']:.2f}. make_payment will refuse "
              f"this until the balance covers it.")
    print(f"Approval #{result['approval_id']} recorded: {result['kind']} "
          f"ref={result['ref_id']} {result['amount']:.2f} from {result['account']}, "
          f"approved by {result['approved_by']}.")
    return 0


def cmd_revoke(conn: sqlite3.Connection, args: argparse.Namespace) -> int:
    row = conn.execute("SELECT used_payment_id FROM approvals WHERE id = ?", (args.id,)).fetchone()
    if row is None:
        print(f"No approval #{args.id}.", file=sys.stderr)
        return 1
    if row["used_payment_id"] is not None:
        print(f"Approval #{args.id} was already spent on payment "
              f"{row['used_payment_id']} and cannot be revoked.", file=sys.stderr)
        return 1
    conn.execute("DELETE FROM approvals WHERE id = ?", (args.id,))
    conn.commit()
    print(f"Approval #{args.id} revoked.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Human approval desk for Campus Customs payments.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("pending", help="show prepared requests awaiting a human")
    sub.add_parser("list", help="show approvals already on file")

    ap = sub.add_parser("approve", help="record one human approval")
    ap.add_argument("--kind", required=True, help='what is being paid, e.g. "invoice" or "rent"')
    ap.add_argument("--ref", type=int, default=None, help="invoice id, lease id, etc.")
    ap.add_argument("--amount", type=float, required=True, help="exact amount approved")
    ap.add_argument("--account", default="checking", help="cash account, default checking")
    ap.add_argument("--by", required=True, help="name of the human approving")

    rv = sub.add_parser("revoke", help="remove an unspent approval")
    rv.add_argument("--id", type=int, required=True)

    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH}.", file=sys.stderr)
        return 1

    conn = connect()
    try:
        conn.executescript(APPROVALS_SCHEMA)
        if args.cmd == "pending":
            cmd_pending(conn)
            return 0
        if args.cmd == "list":
            cmd_list(conn)
            return 0
        if args.cmd == "approve":
            return cmd_approve(conn, args)
        if args.cmd == "revoke":
            return cmd_revoke(conn, args)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
