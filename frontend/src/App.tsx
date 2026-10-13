import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "./api";
import {
  AGENTS,
  AGENT_BY_ID,
  LINKS,
  extractSummary,
  kindLabel,
  linkKey,
  paymentKind,
  pendingFromEvents,
  resultGist,
  speechFor,
} from "./agents";
import Bulldog from "./Bulldog";
import type {
  AgentEvent,
  AgentId,
  CashResponse,
  DayPlan,
  PendingRequest,
  Ticket,
} from "./types";
import "./App.css";

const POLL_MS = 1100;
/** How long a delegation keeps its wire lit after the event lands. */
const WIRE_MS = 4200;

interface Flash {
  key: string;
  at: number;
}

export default function App() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [cash, setCash] = useState<CashResponse | null>(null);
  const [cashBump, setCashBump] = useState(false);
  const [selected, setSelected] = useState<number | null>(null);

  const [running, setRunning] = useState(false);
  const [runTicket, setRunTicket] = useState<number | null>(null);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [plan, setPlan] = useState<DayPlan | null>(null);
  const [finishedTickets, setFinishedTickets] = useState<Set<number>>(new Set());
  const [wires, setWires] = useState<Flash[]>([]);
  const [banner, setBanner] = useState<{ tone: "ok" | "bad"; text: string } | null>(null);

  const [approving, setApproving] = useState<PendingRequest | null>(null);
  const [approver, setApprover] = useState("Shop Owner");
  const [approveAmount, setApproveAmount] = useState("");
  const [approveBusy, setApproveBusy] = useState(false);
  const [paidRequests, setPaidRequests] = useState<Set<number>>(new Set());

  const baselineRun = useRef<string | null>(null);
  const activeRun = useRef<string | null>(null);
  const seenSteps = useRef<Set<number>>(new Set());
  const feedRef = useRef<HTMLDivElement | null>(null);

  // ---------------------------------------------------------------- loading

  const loadTickets = useCallback(async () => {
    try {
      setTickets(await api.tickets());
    } catch (e) {
      setBanner({ tone: "bad", text: `Could not load tickets: ${(e as Error).message}` });
    }
  }, []);

  // The previous reading is kept in a ref rather than read inside a setState
  // updater: queueing another state change from inside an updater is not safe,
  // and doing so was silently dropping the new balance altogether.
  const lastBalance = useRef<number | null>(null);

  const loadCash = useCallback(async (bump = false) => {
    try {
      const next = await api.cash();
      const prev = lastBalance.current;
      lastBalance.current = next.balance;
      setCash(next);
      if (bump && prev !== null && next.balance < prev) {
        setCashBump(true);
        setTimeout(() => setCashBump(false), 1800);
      }
    } catch {
      /* the ledger just keeps its last reading */
    }
  }, []);

  useEffect(() => {
    loadTickets();
    loadCash();
  }, [loadTickets, loadCash]);

  // ------------------------------------------------------------------ wires

  /**
   * A wire is lit for as long as the two agents are actually mid-conversation.
   *
   * The trail records a delegation twice: once as `in_progress` when the work
   * is handed over, and once as `completed` (or `delegation_refused`) when the
   * answer comes back. Replaying those in order gives the delegations that are
   * still open right now — which is usually tens of seconds, not the few
   * seconds a fixed timer would have given. Recently-closed delegations keep a
   * short afterglow so a fast exchange still registers.
   */
  const openLinks = useMemo(() => {
    const depth = new Map<string, number>();
    for (const e of events) {
      if (e.kind !== "delegation" || !e.delegated_to) continue;
      const k = linkKey(e.agent, e.delegated_to);
      const d = depth.get(k) ?? 0;
      depth.set(k, e.stop_reason === "in_progress" ? d + 1 : Math.max(0, d - 1));
    }
    return new Set([...depth].filter(([, n]) => n > 0).map(([k]) => k));
  }, [events]);

  const litWires = useMemo(() => {
    const now = Date.now();
    const lit = new Set(openLinks);
    for (const w of wires) if (now - w.at < WIRE_MS) lit.add(w.key);
    return lit;
  }, [openLinks, wires]);

  // Keep the lit set decaying even when no new events arrive.
  useEffect(() => {
    if (!wires.length) return;
    const t = setInterval(() => setWires((w) => w.filter((x) => Date.now() - x.at < WIRE_MS)), 700);
    return () => clearInterval(t);
  }, [wires.length]);

  // ------------------------------------------------------------------- feed

  const absorb = useCallback((incoming: AgentEvent[]) => {
    const fresh = incoming.filter((e) => !seenSteps.current.has(e.step));
    if (!fresh.length) return;
    fresh.forEach((e) => seenSteps.current.add(e.step));

    setEvents((prev) => [...prev, ...fresh].sort((a, b) => a.step - b.step));

    const newWires = fresh
      .filter((e) => e.kind === "delegation" && e.delegated_to && e.stop_reason !== "in_progress")
      .map((e) => ({ key: linkKey(e.agent, e.delegated_to), at: Date.now() }));
    if (newWires.length) setWires((w) => [...w, ...newWires]);
  }, []);

  // ------------------------------------------------------------------- run

  async function startRun(id: number) {
    if (running) return;
    setRunning(true);
    setRunTicket(id);
    setPlan(null);
    setEvents([]);
    setWires([]);
    setBanner(null);
    seenSteps.current = new Set();
    activeRun.current = null;

    try {
      baselineRun.current = (await api.events(1)).latest_run;
    } catch {
      baselineRun.current = null;
    }

    // The run request is long-lived; the board watches the trail meanwhile.
    const runPromise = api.runTicket(id);

    const poll = setInterval(async () => {
      try {
        if (!activeRun.current) {
          const peek = await api.events(1);
          if (peek.latest_run && peek.latest_run !== baselineRun.current) {
            activeRun.current = peek.latest_run;
          } else {
            return;
          }
        }
        const data = await api.events(400, activeRun.current!);
        absorb(data.events);
      } catch {
        /* a dropped poll is harmless; the next one catches up */
      }
    }, POLL_MS);

    try {
      const result = await runPromise;
      activeRun.current = result.run_id;
      // Final sweep so no tail events are missed between polls.
      try {
        absorb((await api.events(400, result.run_id)).events);
      } catch {
        /* ignore */
      }
      setPlan(result.plan);
      setFinishedTickets((s) => new Set(s).add(id));
      setBanner({
        tone: "ok",
        text: `Ticket ${id} worked through in ${result.steps_recorded} steps.`,
      });
    } catch (e) {
      setBanner({ tone: "bad", text: `Run failed: ${(e as Error).message}` });
    } finally {
      clearInterval(poll);
      setRunning(false);
      setWires([]);
      loadTickets();
      loadCash();
    }
  }

  async function doReset() {
    if (running) return;
    try {
      await api.reset();
      setEvents([]);
      setPlan(null);
      setWires([]);
      setFinishedTickets(new Set());
      setPaidRequests(new Set());
      setRunTicket(null);
      setSelected(null);
      seenSteps.current = new Set();
      await Promise.all([loadTickets(), loadCash()]);
      setBanner({ tone: "ok", text: "Board cleared. Back to the original values." });
    } catch (e) {
      setBanner({ tone: "bad", text: `Reset failed: ${(e as Error).message}` });
    }
  }

  async function submitApproval() {
    if (!approving) return;
    const amount = Number(approveAmount);
    if (!Number.isFinite(amount) || amount <= 0) {
      setBanner({ tone: "bad", text: "Enter an amount greater than zero." });
      return;
    }
    setApproveBusy(true);
    try {
      const res = await api.approve({
        kind: paymentKind(approving.kind),
        amount,
        approved_by: approver.trim() || "Shop Owner",
        ref_id: approving.ref_id,
      });
      if (res.paid) {
        setPaidRequests((s) => new Set(s).add(approving.request_id));
        // Take the new balance straight from the approval response rather than
        // re-reading it: the backend has already applied the payment and
        // returns the figure, so the drawer updates the instant it is true.
        const after = res.payment.new_balance ?? res.balance;
        if (typeof after === "number") {
          lastBalance.current = after;
          setCash((prev) => (prev ? { ...prev, balance: after } : prev));
          setCashBump(true);
          setTimeout(() => setCashBump(false), 1800);
        }
        setBanner({
          tone: "ok",
          text: `Approved and paid $${amount.toLocaleString()}. ${typeof after === "number" ? `Checking now $${after.toLocaleString()}.` : ""}`,
        });
      } else {
        setBanner({
          tone: "bad",
          text: `Approval recorded but nothing was paid — ${res.payment.reason}. ${res.payment.message ?? ""}`,
        });
      }
      setApproving(null);
      await loadCash();
    } catch (e) {
      setBanner({ tone: "bad", text: `Approval failed: ${(e as Error).message}` });
    } finally {
      setApproveBusy(false);
    }
  }

  // --------------------------------------------------------------- derived

  const latestByAgent = useMemo(() => {
    const m = new Map<AgentId, AgentEvent>();
    for (const e of events) m.set(e.agent, e);
    return m;
  }, [events]);

  const speakingAgent = events.length ? events[events.length - 1].agent : null;

  const perAgentSummary = useMemo(() => {
    const m = new Map<AgentId, { tools: string[]; result: string }>();
    for (const e of events) {
      const cur = m.get(e.agent) ?? { tools: [], result: "" };
      if (e.kind === "tool_call" && e.tool_name && !cur.tools.includes(e.tool_name)) {
        cur.tools.push(e.tool_name);
      }
      if (e.kind === "agent_result" && e.tool_result) {
        const summary = extractSummary(e.tool_result);
        if (summary) cur.result = summary;
      }
      m.set(e.agent, cur);
    }
    return m;
  }, [events]);

  const pending = useMemo(
    () => pendingFromEvents(events).filter((p) => !paidRequests.has(p.request_id)),
    [events, paidRequests],
  );

  useEffect(() => {
    if (feedRef.current) feedRef.current.scrollTop = feedRef.current.scrollHeight;
  }, [events.length]);

  const gazeFor = (id: AgentId): "left" | "right" | "center" => {
    const last = latestByAgent.get(id);
    if (!last || last.kind !== "delegation" || !last.delegated_to) return "center";
    const me = AGENT_BY_ID[id];
    const them = AGENT_BY_ID[last.delegated_to as AgentId];
    if (!me || !them) return "center";
    return them.x < me.x ? "left" : "right";
  };

  // ----------------------------------------------------------------- render

  return (
    <div className="shell">
      <header className="masthead">
        <div className="crest" aria-hidden="true">
          <span>CC</span>
        </div>
        <div className="masthead-text">
          <h1>Campus Customs — Operations Desk</h1>
          <p>Five bulldogs, one shop, and a cash drawer that only ever goes down.</p>
        </div>

        <div className={`ledger ${cashBump ? "bump" : ""}`}>
          <div className="ledger-label">Checking</div>
          <div className="ledger-amount">
            {cash ? `$${cash.balance.toLocaleString(undefined, { minimumFractionDigits: 2 })}` : "—"}
          </div>
          <div className="ledger-foot">as of {cash?.date ?? "…"}</div>
          <div className="ledger-slot" aria-hidden="true" />
        </div>
      </header>

      {banner && (
        <div className={`banner ${banner.tone}`} role="status">
          {banner.text}
          <button className="banner-x" onClick={() => setBanner(null)} aria-label="Dismiss">
            ×
          </button>
        </div>
      )}

      <div className="columns">
        {/* ------------------------------ left rail ------------------------------ */}
        <aside className="rail">
          <div className="rail-head">
            <h2>Today's tickets</h2>
            <button className="reset" onClick={doReset} disabled={running} title="Clear the board">
              Reset board
            </button>
          </div>

          {tickets.map((t) => {
            const done = finishedTickets.has(t.id);
            const isRunning = running && runTicket === t.id;
            return (
              <button
                key={t.id}
                className={`ticket ${selected === t.id ? "sel" : ""} ${done ? "done" : ""}`}
                onClick={() => setSelected(t.id)}
                disabled={running}
              >
                <div className="ticket-top">
                  <span className="ticket-id">#{t.id}</span>
                  {done ? (
                    <span className="chip resolved">Resolved</span>
                  ) : isRunning ? (
                    <span className="chip working">Working…</span>
                  ) : (
                    <span className="chip open">{t.status}</span>
                  )}
                </div>
                <div className="ticket-subject">{t.subject}</div>
                <div className="ticket-meta">
                  {t.requester}
                  {t.sku ? ` · ${t.sku}${t.size ? ` / ${t.size}` : ""}` : ""}
                  {t.qty ? ` × ${t.qty}` : ""}
                </div>
                {done && t.status !== "resolved" && (
                  <div className="ticket-note">agents left it “{t.status}”</div>
                )}
              </button>
            );
          })}

          <button
            className="run"
            disabled={selected === null || running}
            onClick={() => selected !== null && startRun(selected)}
          >
            {running ? "Team is working…" : selected ? `Send the team in on #${selected}` : "Pick a ticket"}
          </button>

          {pending.length > 0 && (
            <div className="pending">
              <h3>Waiting on you</h3>
              {pending.map((p) => (
                <div className="pending-card" key={p.request_id}>
                  <div className="pending-kind">{kindLabel(p.kind)}</div>
                  <div className="pending-amt">
                    {p.amount !== null ? `$${p.amount.toLocaleString()}` : "amount not set"}
                  </div>
                  <div className="pending-meta">
                    request #{p.request_id}
                    {p.ticket_id ? ` · ticket ${p.ticket_id}` : ""} · from {AGENT_BY_ID[p.prepared_by]?.label ?? p.prepared_by}
                  </div>
                  <button
                    className="approve"
                    onClick={() => {
                      setApproving(p);
                      setApproveAmount(p.amount !== null ? String(p.amount) : "");
                    }}
                  >
                    Review &amp; approve
                  </button>
                </div>
              ))}
            </div>
          )}
        </aside>

        {/* -------------------------------- room -------------------------------- */}
        <main className="room">
          <svg className="wires" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
            <defs>
              {/* userSpaceOnUse: an objectBoundingBox gradient collapses on the
                  horizontal desk-to-desk wires, whose bounding box has no
                  height, and the rainbow would not paint at all. */}
              <linearGradient
                id="rainbow"
                gradientUnits="userSpaceOnUse"
                spreadMethod="repeat"
                x1="0"
                y1="0"
                x2="26"
                y2="26"
              >
                <stop offset="0%" stopColor="#E8503A" />
                <stop offset="20%" stopColor="#E8A33A" />
                <stop offset="40%" stopColor="#64B45E" />
                <stop offset="60%" stopColor="#3FB0C8" />
                <stop offset="80%" stopColor="#4A6FD0" />
                <stop offset="100%" stopColor="#A455C8" />
              </linearGradient>
            </defs>
            {LINKS.map(([a, b]) => {
              const A = AGENT_BY_ID[a];
              const B = AGENT_BY_ID[b];
              const key = linkKey(a, b);
              const lit = litWires.has(key);
              return (
                <line
                  key={key}
                  x1={A.x}
                  y1={A.y}
                  x2={B.x}
                  y2={B.y}
                  className={`wire ${lit ? "lit" : ""}`}
                  vectorEffect="non-scaling-stroke"
                />
              );
            })}
          </svg>

          {AGENTS.map((a) => {
            const ev = latestByAgent.get(a.id);
            const gist = ev ? resultGist(ev) : "";
            const isSpeaking = speakingAgent === a.id && running;
            const sum = perAgentSummary.get(a.id);
            return (
              <div
                key={a.id}
                className={`seat ${a.id === "boss" ? "boss" : ""} ${isSpeaking ? "active" : ""}`}
                style={{ left: `${a.x}%`, top: `${a.y}%` }}
              >
                {(ev || (plan && sum)) && (
                  <div className={`bubble ${isSpeaking ? "live" : ""}`}>
                    {ev && (
                      <>
                        <div className="bubble-say">{speechFor(ev)}</div>
                        {ev.kind === "tool_call" && (
                          <div className="bubble-tool">
                            <code>{ev.tool_name}</code>
                            {gist && <span className="gist">{gist}</span>}
                          </div>
                        )}
                      </>
                    )}
                    {plan && sum?.result && (
                      <div className="bubble-summary">
                        <span className="sum-label">On this ticket</span>
                        {sum.result}
                        {sum.tools.length > 0 && (
                          <span className="sum-tools">{sum.tools.join(" · ")}</span>
                        )}
                      </div>
                    )}
                  </div>
                )}

                <Bulldog
                  apron={a.apron}
                  apronDark={a.apronDark}
                  name={a.label}
                  crown={a.id === "boss"}
                  gaze={gazeFor(a.id)}
                  speaking={isSpeaking}
                />
                <div className="seat-role">{a.role}</div>
              </div>
            );
          })}
        </main>
      </div>

      {/* ------------------------------ run feed ------------------------------ */}
      <section className="feed-wrap">
        <h2>
          Run log
          {running && <span className="pulse" aria-label="running" />}
          <span className="feed-count">{events.length} steps</span>
        </h2>
        <div className="feed" ref={feedRef}>
          {events.length === 0 && (
            <p className="feed-empty">
              Pick a ticket and send the team in. Everything they do shows up here as it happens.
            </p>
          )}
          {events.map((e) => (
            <div className={`feed-row ${e.kind}`} key={`${e.run_id}-${e.step}`}>
              <span className="feed-step">{e.step}</span>
              <span className="feed-dog" style={{ background: AGENT_BY_ID[e.agent]?.apron }}>
                {AGENT_BY_ID[e.agent]?.label ?? e.agent}
              </span>
              <span className="feed-say">{speechFor(e)}</span>
              {e.kind === "tool_call" && <code className="feed-tool">{e.tool_name}</code>}
              {resultGist(e) && <span className="feed-gist">{resultGist(e)}</span>}
            </div>
          ))}
        </div>
      </section>

      {plan && (
        <section className="plan">
          <h2>The Boss's call</h2>
          {plan.decisions.map((d) => (
            <div className="decision" key={d.ticket_id}>
              <div className="decision-head">
                <strong>Ticket {d.ticket_id}</strong> · {d.subject}
                {d.awaiting_human && <span className="chip waiting">awaiting a human</span>}
                {d.money_involved !== null && (
                  <span className="chip money">${d.money_involved.toLocaleString()}</span>
                )}
              </div>
              <p>{d.decision}</p>
              <div className="decision-who">
                {d.assigned_to.map((id) => (
                  <span key={id} className="who" style={{ background: AGENT_BY_ID[id]?.apron }}>
                    {AGENT_BY_ID[id]?.label ?? id}
                  </span>
                ))}
              </div>
            </div>
          ))}
          <div className="cashplan">
            <h3>Cash</h3>
            <p>{plan.cash_plan}</p>
          </div>
        </section>
      )}

      {/* ----------------------------- approval modal ----------------------------- */}
      {approving && (
        <div className="scrim" onClick={() => !approveBusy && setApproving(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
            <h2>Approve {kindLabel(approving.kind).toLowerCase()}?</h2>
            <p className="modal-detail">{approving.details || "No further detail was recorded."}</p>

            <label className="field">
              <span>Amount</span>
              <input
                type="number"
                step="0.01"
                value={approveAmount}
                onChange={(e) => setApproveAmount(e.target.value)}
                autoFocus
              />
            </label>
            <label className="field">
              <span>Approved by</span>
              <input value={approver} onChange={(e) => setApprover(e.target.value)} />
            </label>

            <p className="modal-warn">
              This is the only thing in the shop that actually moves money. The agents cannot
              do it, and it will still be refused if the drawer can't cover it.
            </p>

            <div className="modal-row">
              <button className="ghost" onClick={() => setApproving(null)} disabled={approveBusy}>
                Not yet
              </button>
              <button className="approve big" onClick={submitApproval} disabled={approveBusy}>
                {approveBusy ? "Paying…" : "Approve & pay"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
