# Campus Customs — a five-agent shop desk

A small merch shop run by five PydanticAI agents, all on `gpt-6-luna` through
Portkey, all able to delegate to each other. They read and change the shop's
data **only** through an MCP server, they prepare payments but can never make
one, and a React board shows them working at their desks in real time.

Three open tickets sit on the board:

| Ticket | What it is |
|---|---|
| **101** | A customer wants a white tee in size S. There are none, and the vendor who could reprint them will not ship while an overdue invoice is outstanding. |
| **102** | The landlord says rent is due. The lease record is the thing to trust, not the email. |
| **103** | A student org wants 20 hoodies at a bulk discount. Only 8 are on the shelf. |

The shop starts with **$3,400.00** and has no income, so the day is really a
sequencing problem: the three tickets together ask for more than the shop has.

---

## What's in here

```
hw5/
├── AI_prompts.md          every prompt used to build this, by problem
├── requirements.txt       Python dependencies
├── .env.example           copy to .env and add your key
├── .mcp.json / mcp.json   MCP connection config (same content, see note below)
├── README.md
├── data/
│   ├── campus_customs.db       pristine original — never written to
│   └── campus_customs_new.db   the working copy the agents change
├── mcp_server/
│   ├── server.py          the MCP server: 20 tools over the working database
│   ├── approve_cli.py     the human approval desk (deliberately NOT an MCP tool)
│   └── README.md
├── backend/
│   ├── main.py            FastAPI app the board calls
│   ├── team.py            the five agents, delegation, usage limits
│   ├── shop.py            the backend's only route to shop data (MCP client)
│   ├── audit.py           append-only audit trail
│   ├── models.py          shared data types
│   └── prompts/           one prompt file per agent
│       ├── boss.md
│       ├── inventory.md
│       ├── accounting.md
│       ├── facilities.md
│       └── customer_service.md
├── frontend/              React + Vite + TypeScript board
└── output/
    ├── harness.md             full write-up: tables, tools, agents, routes, safety
    ├── design.md              why the dashboard looks the way it does
    ├── desk_tickets.html      Expected vs Actual per ticket, cash, reflection
    ├── resolved_board.html    screenshots of the board for each resolved ticket
    ├── resolved_tickets.json  machine-readable record of the canonical run
    ├── mcp_smoke.json         MCP tool smoke test evidence
    ├── audit_trail.json       every agent step, appended across runs
    └── github_url.txt
```

Both `mcp.json` and `.mcp.json` are present with identical content:
`mcp.json` is what `backend/` reads, and `.mcp.json` is the filename Claude Code
loads. Paths inside them are **relative to this folder**, so they work after a
clone on any machine.

---

## Setup

Needs Python 3.11+ and Node 18+.

### 1. Clone and enter the project

```bash
git clone <this repo url>
cd hw5
```

### 2. Create the Python environment and install dependencies

```bash
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
```

`requirements.txt` is pinned to the versions this project was verified against.
That matters: installing unpinned pulls a newer `cryptography` that has no
prebuilt wheel on some platforms and tries to build from Rust source, which
fails. The pins avoid that.

Everything below calls `.venv/bin/python` directly, so there is no need to
activate the virtualenv.

### 3. Add your API key

```bash
cp .env.example .env
```

Then open `.env` and set `PORTKEY_API_KEY` to your own key. Nothing else needs
changing — `MODEL_NAME` defaults to `gpt-6-luna`. `.env` is gitignored.

### 4. Install the frontend dependencies

```bash
npm install --prefix frontend
```

---

## Running it

### Start from a clean board

The agents write to `data/campus_customs_new.db`. `data/campus_customs.db` is
the pristine original and is never written to, so a clean run is just a copy:

```bash
cp data/campus_customs.db data/campus_customs_new.db
```

Do this before a full three-ticket run. You can also do it from the board's
**Reset board** button, or with `curl -X POST http://localhost:8000/api/reset`,
both of which perform exactly this copy and then let the MCP server rebuild the
three tables it owns.

After a reset the board reads: checking **$3,400.00**, shop date **2026-08-31**,
tickets 101, 102 and 103 all `open`.

### Start the MCP server

The backend and the agent team both spawn this automatically, so you usually do
**not** need to start it by hand. To run it on its own, for example to poke at
the tools directly:

```bash
.venv/bin/python mcp_server/server.py
```

It speaks MCP over stdio and creates its own three tables (`approvals`,
`prepared_requests`, `message_drafts`) on first start if they are missing.

### Start the FastAPI backend

From the `backend/` folder, on port 8000:

```bash
cd backend
../.venv/bin/python -m uvicorn main:app --reload --port 8000
```

Check it is up:

```bash
curl -s http://localhost:8000/api/health
```

### Start the React board

In a second terminal, from the project root:

```bash
npm run dev --prefix frontend
```

Then open **http://localhost:5173**. CORS on the backend already allows that
origin.

---

## A full three-ticket run

1. Reset to a clean board — the **Reset board** button, or
   `cp data/campus_customs.db data/campus_customs_new.db`.
2. Pick a ticket in the left rail and press **Send the team in on #…**.
   Watch the bulldogs: the wires light while two agents are talking, each
   speech bubble shows what that agent is doing and which tool it used, and the
   run log fills in below.
3. When the team prepares a payment, a gold **Waiting on you** card appears.
   Approving it is the only thing in the whole system that moves money — the
   cash drawer in the top right drops.
4. Repeat for the other two tickets.

Ticket **101** is the most interesting to watch: Boss → Inventory → Accounting,
when Inventory finds the restock is blocked by the unpaid invoice.

The canonical run is already recorded in `output/` if you would rather read it
than run it: `desk_tickets.html` has Expected vs Actual per ticket plus the
itemised cash, and `resolved_board.html` has screenshots.

### Approving from the command line instead

The approval desk is a CLI as well as a button. It is deliberately **not** an
MCP tool, so no agent can reach it and no agent can authorise its own spending:

```bash
.venv/bin/python mcp_server/approve_cli.py pending
.venv/bin/python mcp_server/approve_cli.py approve --kind invoice --ref 501 \
    --amount 840 --by "Your Name"
.venv/bin/python mcp_server/approve_cli.py list
```

### Running the team without the board

```bash
.venv/bin/python backend/run_team.py
.venv/bin/python backend/run_team.py --task "Work ticket 101 only."
```

---

## How the money is protected

`make_payment` is the only tool that moves cash, and it refuses unless **all**
of these hold, in one transaction that rolls back on any failure:

- a **human approval** is already on file matching the exact kind, ref, amount
  and account, and has not been spent — no agent has any tool that writes to
  that table;
- the **balance covers it**; balances never go negative, and a payment that
  would overdraw is refused outright rather than partially made;
- the amount is positive.

No revenue is modelled anywhere, so cash only ever goes down. Drafted customer
messages are never sent — there is no outbound email in the system at all.
Read tools open the database in SQLite read-only mode, so a read tool cannot
change data even if it is buggy.

`output/harness.md` has the full picture: every table, all 20 MCP tools, the
five agents, the API routes, the dashboard, and the safety and token limits.

---

## Troubleshooting

**`PORTKEY_API_KEY is not set`** — copy `.env.example` to `.env` in the project
root and put your key in it.

**The board shows no tickets and the drawer reads `—`** — the backend is not
running, or not on port 8000. Check `curl http://localhost:8000/api/health`.

**An agent run returns 409** — only one run happens at a time on purpose. Wait
for the current one to finish.

**You want to start over completely** — `cp data/campus_customs.db
data/campus_customs_new.db`. `output/audit_trail.json` is deliberately left
alone by every reset, because it is append-only across runs.
