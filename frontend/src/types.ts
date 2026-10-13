/** Shapes returned by the Campus Customs backend (backend/main.py). */

export type AgentId =
  | "boss"
  | "inventory"
  | "accounting"
  | "facilities"
  | "customer_service";

export interface Ticket {
  id: number;
  type: string;
  requester: string;
  subject: string;
  status: string;
  is_open: boolean;
  is_resolved: boolean;
  sku: string | null;
  size: string | null;
  qty: number | null;
  lease_id: number | null;
  invoice_id: number | null;
  notes: string | null;
  created_at: string;
}

export interface AgentEvent {
  timestamp: string;
  run_id: string;
  step: number;
  agent: AgentId;
  depth: number;
  kind: "tool_call" | "delegation" | "agent_result";
  tool_name: string;
  tool_args: string;
  tool_result: string;
  delegated_to: string;
  delegated_task: string;
  stop_reason: string;
}

export interface EventsResponse {
  count: number;
  total: number;
  runs: string[];
  latest_run: string | null;
  events: AgentEvent[];
}

export interface TicketDecision {
  ticket_id: number;
  subject: string;
  assigned_to: AgentId[];
  priority: number;
  decision: string;
  money_involved: number | null;
  awaiting_human: boolean;
  status_set: string;
}

export interface DayPlan {
  date_today: string;
  opening_cash: number;
  decisions: TicketDecision[];
  cash_plan: string;
  awaiting_human_approval: string[];
  notes: string;
}

export interface RunResponse {
  ticket_id: number;
  run_id: string;
  steps_recorded: number;
  plan: DayPlan;
}

export interface CashResponse {
  found: boolean;
  name: string;
  balance: number;
  date: string;
}

export interface ApprovalResponse {
  approved: boolean;
  approval: { approval_id: number; approved_by: string; amount: number };
  paid: boolean;
  payment: {
    paid?: boolean;
    reason?: string;
    message?: string;
    payment_id?: number;
    new_balance?: number;
    shortfall?: number;
  };
  balance: number;
  note: string;
}

/**
 * A prepared request recovered from the audit trail.
 *
 * The agents can only *prepare* spending; a human has to approve it. The
 * backend has no route that lists prepared requests, but every one of them
 * shows up in the event stream as a `prepare_purchase_request` tool call whose
 * result carries the request id, kind, ref, and amount. That is what the
 * approval card is built from.
 */
export interface PendingRequest {
  request_id: number;
  kind: string;
  ref_id: number | null;
  amount: number | null;
  ticket_id: number | null;
  prepared_by: AgentId;
  details: string;
}
