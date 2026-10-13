/** Thin client for the Campus Customs backend. */

import type {
  ApprovalResponse,
  CashResponse,
  EventsResponse,
  RunResponse,
  Ticket,
} from "./types";

const BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

async function get<T>(path: string): Promise<T> {
  // no-store: the balance and the ticket list change underneath us, and a
  // cached 200 would show the owner money that has already been spent.
  const res = await fetch(`${BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(await describe(res));
  return res.json() as Promise<T>;
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(await describe(res));
  return res.json() as Promise<T>;
}

async function describe(res: Response): Promise<string> {
  try {
    const data = await res.json();
    if (typeof data?.detail === "string") return data.detail;
    if (Array.isArray(data?.detail)) {
      return data.detail.map((d: { msg?: string }) => d.msg ?? "invalid").join("; ");
    }
    return `${res.status} ${res.statusText}`;
  } catch {
    return `${res.status} ${res.statusText}`;
  }
}

export const api = {
  tickets: () => get<Ticket[]>("/api/tickets"),
  cash: () => get<CashResponse>("/api/cash"),
  events: (limit = 300, runId?: string) =>
    get<EventsResponse>(
      `/api/events?limit=${limit}${runId ? `&run_id=${encodeURIComponent(runId)}` : ""}`,
    ),
  runTicket: (id: number) => post<RunResponse>(`/api/tickets/${id}/run`),
  reset: () => post<{ reset: boolean; balance: number }>("/api/reset"),
  approve: (body: {
    kind: string;
    amount: number;
    approved_by: string;
    ref_id: number | null;
    account?: string;
  }) => post<ApprovalResponse>("/api/approvals", body),
};

export { BASE as API_BASE };
