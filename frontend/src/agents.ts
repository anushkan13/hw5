/** Who sits where, in which apron, and how to read their events. */

import type { AgentEvent, AgentId, PendingRequest } from "./types";

export interface AgentMeta {
  id: AgentId;
  label: string;
  role: string;
  apron: string;
  apronDark: string;
  /** Position in the room, as a percentage of the floor box. */
  x: number;
  y: number;
}

/**
 * Apron colours are pulled from Yale's palette and chosen so no two specialists
 * share a hue — green, rust, blue, plum — rather than four shades of navy that
 * would be impossible to tell apart at a glance. The Boss keeps Yale Blue
 * itself, which is why the crown reads as the senior colour.
 */
export const AGENTS: AgentMeta[] = [
  {
    id: "boss",
    label: "Boss",
    role: "Reads every ticket, decides who works it, sequences the day against cash.",
    apron: "#00356B",
    apronDark: "#00254A",
    x: 50,
    y: 23,
  },
  {
    id: "inventory",
    label: "Inventory",
    role: "Stock by SKU and size, shortfalls, vendors and lead times.",
    apron: "#5F712D",
    apronDark: "#44521F",
    x: 13.5,
    y: 68,
  },
  {
    id: "accounting",
    label: "Accounting",
    role: "Cash, invoices, margins. Prepares payments for a human.",
    apron: "#BD5319",
    apronDark: "#8E3D11",
    x: 37.8,
    y: 68,
  },
  {
    id: "facilities",
    label: "Facilities",
    role: "The shop space: leases, rent, due dates.",
    apron: "#286DC0",
    apronDark: "#1B4F8F",
    x: 62.2,
    y: 68,
  },
  {
    id: "customer_service",
    label: "Customer Service",
    role: "Drafts messages to customers. Never sends them.",
    apron: "#7D5BA6",
    apronDark: "#5C4080",
    x: 86.5,
    y: 68,
  },
];

export const AGENT_BY_ID: Record<AgentId, AgentMeta> = Object.fromEntries(
  AGENTS.map((a) => [a.id, a]),
) as Record<AgentId, AgentMeta>;

/** Every pair, because the team is fully connected. */
export const LINKS: Array<[AgentId, AgentId]> = (() => {
  const out: Array<[AgentId, AgentId]> = [];
  for (let i = 0; i < AGENTS.length; i++) {
    for (let j = i + 1; j < AGENTS.length; j++) {
      out.push([AGENTS[i].id, AGENTS[j].id]);
    }
  }
  return out;
})();

export const linkKey = (a: string, b: string) => [a, b].sort().join("~");

/** Tool name -> what a person would say the dog is doing. */
const TOOL_SPEECH: Record<string, string> = {
  get_today: "Checking what day it is on the shop calendar",
  list_open_tickets: "Reading the open tickets",
  list_tickets: "Looking over the whole board",
  get_ticket: "Reading the ticket",
  check_stock: "Counting what's on the shelf",
  get_lease_terms: "Pulling the lease out of the file",
  get_margin: "Working out the margin",
  get_invoice: "Checking the invoice",
  list_vendor_invoices: "Seeing what we still owe this vendor",
  get_vendor: "Looking up the vendor",
  find_vendors: "Finding a supplier who can make this",
  get_cash_balance: "Checking the cash drawer",
  list_approvals: "Seeing what's been approved",
  list_prepared_requests: "Checking what's already on the desk",
  list_message_drafts: "Reading the drafts on the board",
  list_payments: "Going through the payments ledger",
  make_payment: "Trying to pay",
  prepare_purchase_request: "Writing this up for a human to approve",
  update_ticket: "Writing the outcome on the ticket",
  record_customer_message: "Drafting a note to the customer",
};

export function speechFor(ev: AgentEvent): string {
  if (ev.kind === "delegation") {
    const to = AGENT_BY_ID[ev.delegated_to as AgentId]?.label ?? ev.delegated_to;
    if (ev.stop_reason === "delegation_refused") return `Can't hand that to ${to}`;
    if (ev.stop_reason === "completed") return `Got ${to}'s answer back`;
    return `Asking ${to} to help`;
  }
  if (ev.kind === "agent_result") {
    return ev.stop_reason === "completed" ? "Done — reporting back" : "Stopped early";
  }
  return TOOL_SPEECH[ev.tool_name] ?? `Using ${ev.tool_name}`;
}

/** Pull the headline number or answer out of a tool result for the bubble. */
export function resultGist(ev: AgentEvent): string {
  if (ev.kind !== "tool_call" || !ev.tool_result) return "";
  const r = parseLoose(ev.tool_result);
  if (!r) return "";

  if (ev.tool_name === "check_stock" && typeof r.qty === "number") {
    return r.qty === 0 ? `none left in ${r.size}` : `${r.qty} in ${r.size}`;
  }
  if (ev.tool_name === "get_cash_balance" && typeof r.balance === "number") {
    return `$${r.balance.toLocaleString()}`;
  }
  if (ev.tool_name === "get_margin" && typeof r.margin_per_unit === "number") {
    return `$${r.margin_per_unit} room (${r.margin_pct}%)`;
  }
  if (ev.tool_name === "get_lease_terms" && typeof r.monthly_rent === "number") {
    return `$${r.monthly_rent.toLocaleString()} due ${r.next_due}`;
  }
  if (ev.tool_name === "get_invoice" && r.status) {
    return `#${r.id} ${r.status}${r.overdue ? " · overdue" : ""}`;
  }
  if (ev.tool_name === "list_vendor_invoices") {
    return r.blocks_shipping ? "vendor won't ship yet" : "vendor is clear";
  }
  if (ev.tool_name === "get_vendor" && r.name) return `${r.name}, ${r.lead_days}d lead`;
  if (ev.tool_name === "find_vendors" && Array.isArray(r.vendors)) {
    return r.vendors[0]?.name ? `${r.vendors[0].name}` : `${r.count} found`;
  }
  if (ev.tool_name === "prepare_purchase_request") {
    if (r.duplicate) return `already on the desk (#${r.request_id})`;
    return `request #${r.request_id} awaiting approval`;
  }
  if (ev.tool_name === "record_customer_message") return `draft #${r.draft_id}, not sent`;
  if (ev.tool_name === "update_ticket" && r.status) return `marked ${r.status}`;
  if (ev.tool_name === "make_payment") {
    return r.paid ? `paid, $${r.new_balance} left` : `refused: ${r.reason}`;
  }
  return "";
}

/** The audit trail stores results as a JSON string, sometimes truncated. */
function parseLoose(text: string): Record<string, any> | null {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

/**
 * Pull an agent's `summary` out of its report.
 *
 * Agent reports are capped at 900 characters in the audit trail to keep token
 * use down, so the JSON is often cut mid-field and will not parse. The trail
 * is a log rather than an API, so rather than loosen that cap we read it
 * tolerantly: try real JSON first, and otherwise lift the summary field out
 * directly, since it is written near the front of the report and survives the
 * truncation.
 */
export function extractField(text: string, field: string): string {
  if (!text) return "";
  const parsed = parseLoose(text);
  if (parsed && typeof parsed[field] === "string") return parsed[field];

  const m = text.match(new RegExp(`"${field}"\\s*:\\s*"((?:[^"\\\\]|\\\\.)*)"`));
  if (!m) return "";
  try {
    return JSON.parse(`"${m[1]}"`);
  } catch {
    return m[1].replace(/\\"/g, '"').replace(/\\n/g, " ");
  }
}

export function extractSummary(text: string): string {
  if (!text) return "";
  const parsed = parseLoose(text);
  if (parsed && typeof parsed.summary === "string") return parsed.summary;

  const m = text.match(/"summary"\s*:\s*"((?:[^"\\]|\\.)*)"/);
  if (!m) return "";
  try {
    return JSON.parse(`"${m[1]}"`);
  } catch {
    return m[1].replace(/\\"/g, '"').replace(/\\n/g, " ");
  }
}

/**
 * Recover the prepared requests from the run's events.
 *
 * Each `prepare_purchase_request` call records its result in the trail, and
 * that result carries the request id, kind, ref and amount — everything the
 * approval card needs. Duplicates collapse onto the same request id, which is
 * exactly what the server's own deduplication intends.
 */
export function pendingFromEvents(events: AgentEvent[]): PendingRequest[] {
  const byId = new Map<number, PendingRequest>();
  for (const ev of events) {
    if (ev.tool_name !== "prepare_purchase_request") continue;
    const r = parseLoose(ev.tool_result);
    if (!r || typeof r.request_id !== "number") continue;
    // tool_args is capped in the trail and usually cut mid-`details`, so read
    // the field tolerantly rather than requiring the whole blob to parse.
    const details = extractField(ev.tool_args, "details");
    byId.set(r.request_id, {
      request_id: r.request_id,
      kind: String(r.kind ?? "payment"),
      ref_id: typeof r.ref_id === "number" ? r.ref_id : null,
      amount: typeof r.amount === "number" ? r.amount : null,
      ticket_id: typeof r.ticket_id === "number" ? r.ticket_id : null,
      prepared_by: (r.prepared_by ?? ev.agent) as AgentId,
      details: details.slice(0, 400),
    });
  }
  return [...byId.values()].sort((a, b) => a.request_id - b.request_id);
}

/**
 * Map a prepared-request kind onto the kind `make_payment` understands.
 *
 * The agents name their drafts things like `invoice_payment`; the payment tool
 * keys invoice-closing off the bare word `invoice`. Translating here keeps the
 * approval and the payment matching each other.
 */
export function paymentKind(preparedKind: string): string {
  if (preparedKind.startsWith("invoice")) return "invoice";
  if (preparedKind.startsWith("rent")) return "rent";
  return preparedKind;
}

export function kindLabel(kind: string): string {
  return kind
    .replace(/_/g, " ")
    .replace(/\bpo\b/i, "purchase order")
    .replace(/^\w/, (c) => c.toUpperCase());
}
