# Campus Customs Operations Desk — design notes

What I chose for the dashboard, and why. The short version: the screen is a
*room*, not a table of JSON. You are the shop owner standing at the head of it,
and the agents are staff you can see working.

---

## The core idea: a room you stand at the head of

The obvious way to show a multi-agent run is a log and a status table. That is
accurate and completely unreadable — you cannot tell at a glance who is busy,
who is stuck, or who is waiting on whom.

So the layout is literal. The Boss sits at the head of the room, bigger than
everyone and wearing a crown, at the top of the page. The four specialists sit
in a line below, facing you. You read the hierarchy before you read a single
word, because it is a seating chart.

The room has a floor. A dark floorboard gradient runs across the bottom, and a
warm pool of light falls from above the Boss's desk, which is why the top of the
screen feels like the front of a room rather than the top of a scroll. The
background is Yale Blue, deepening toward the edges, so the whole thing reads as
a collegiate office after hours.

## The bulldogs

Every character is drawn from scratch as SVG — my own bulldog, not a copy of any
real mascot or logo. The proportions are chosen to read as *bulldog* at 200
pixels wide, where detail disappears:

- a low, wide skull rather than a round one
- **three** brow wrinkles, which is the single strongest bulldog cue
- rose ears folded back and set low
- a broad flat muzzle set low on the face, with a big upturned nose
- a modest underbite with two visible bottom teeth
- heavy jowls that hang past the jawline

They are the same dog five times, deliberately. A team should look like a team.
What separates them is the apron.

### How the agents read differently from each other

Four things distinguish them, and they stack, so you never depend on just one:

1. **Apron colour**, pulled from Yale's palette but chosen for maximum
   separation — green (Inventory), rust (Accounting), medium blue (Facilities),
   plum (Customer Service). I specifically avoided four shades of navy, which
   would have been on-brand and useless. The Boss keeps Yale Blue itself, so the
   senior colour stays with the senior dog.
2. **A brass-topped name tag** on the front of each desk, with the agent's name
   in a serif face. The tag plate widens and the lettering shrinks for longer
   names, so "Customer Service" sits inside its plate instead of spilling out of
   it.
3. **Position**. The seating never changes, so after a minute you stop reading
   the tags and just know that Accounting is second from the left.
4. **The crown and the scale**. The Boss is about 25% larger and wears a gold
   crown. You never have to ask who makes the call.

Each desk also carries a mug in the agent's own apron colour, a pen cup, and a
drawer — small props that make five identical dogs feel like five different
desks.

## Showing the work: speech bubbles over tool names

Each bulldog has a speech bubble above it carrying what it is doing *right now*,
in plain words. The raw event says `check_stock`; the bubble says **"Counting
what's on the shelf"** and then shows `check_stock` underneath as a small
monospace chip, plus the actual answer pulled out of the result — "none left in
S", "$2,400 due 2026-09-02", "vendor won't ship yet".

That ordering matters. The plain sentence is for understanding the shop; the
tool chip is for trusting the system. You get the story first and the evidence
second, rather than being asked to decode `get_lease_terms` yourself.

The dogs also *look* at whoever they are talking to — the pupils shift a few
pixels toward the agent being delegated to — and the active speaker leans
gently. Tiny touches, but they make the room feel staffed rather than rendered.

Bubbles are lifted out of the layout flow and anchored above each dog, so a long
report cannot shove its own bulldog out of the line of desks.

## The wires, and the thing I got wrong first

Every pair of agents is connected — all ten lines, because the team really is
fully connected — drawn as faint dashed wires behind the desks. When two agents
are actually talking, their wire lights up in a crawling rainbow.

My first version lit the wire for a fixed four seconds when a delegation
appeared. Watching a real run, the wires were almost always dark: a delegation
takes ten to thirty seconds, because the other agent has to go and *do* the
work. The timer was measuring the wrong thing.

The audit trail already records a delegation twice — `in_progress` when the work
is handed over, `completed` when the answer comes back — so the board now
replays those and lights the wire for the entire life of the conversation. When
the Boss hands ticket 101 to Inventory, that wire stays lit while Inventory goes
and talks to Accounting, and you can watch a whole chain hold at once. Recently
closed delegations keep a short afterglow so a fast exchange still registers.

(The rainbow itself is a repeating gradient in user space. An object-bounding-box
gradient silently refuses to paint on the horizontal desk-to-desk wires, whose
bounding box has no height.)

## Resolved tickets

A ticket card turns green and gets a **Resolved** badge when its run finishes.

But the agents usually do not literally mark a ticket `resolved` — they mark it
`blocked` or `in_progress`, because the honest state of ticket 101 is "waiting
on a human to approve $840". So the card shows both: the green badge for *the
team has worked this*, and a small italic line underneath — *agents left it
"blocked"* — for what the shop's own records say. Hiding that difference would
be the easy design and the dishonest one.

When the run ends, each bubble also keeps a short per-agent summary of what that
dog did on that ticket, with the list of tools it touched underneath. The Boss's
full decision, the cash sequencing, and everything awaiting a human land in a
parchment card below the room.

## Cash: a drawer, not a number

The balance lives in the masthead as a cream-and-brass ledger plate with a slot
across the bottom, styled like the front of a cash drawer. It uses a serif face
and tabular numerals so the figure reads as money rather than as a metric.

When an approved payment goes through, the plate physically *jolts* — a short
drop-and-settle animation, like a drawer being shoved shut — and the number
falls. That is the only moment in the whole interface where anything moves
weightily, which is the point: it is the only moment where real money left the
shop.

This is also where the most stubborn bug lived. The drawer kept showing the old
balance after a successful payment. The board was re-reading `GET /api/cash`
after approving, and the browser was happy to serve that from cache. The fix was
to stop asking: the approve response already carries the post-payment balance,
so the drawer now updates from the thing that actually moved the money, with
`cache: "no-store"` on the reads as a second line of defence.

## The approval prompt

Anything the agents prepare shows up under **"Waiting on you"** in the left
rail, as a cream card with a gold left edge — the only warm-coloured thing in a
blue interface, so it pulls your eye.

Clicking through opens a modal that states what is being approved, in the
agent's own words, with the amount pre-filled but editable, and a field for who
is approving. It carries one line of plain warning:

> This is the only thing in the shop that actually moves money. The agents
> cannot do it, and it will still be refused if the drawer can't cover it.

That sentence is the whole safety model of the assignment in twenty-six words,
placed exactly where a person is about to spend money. If the payment is
refused — not enough cash, no matching approval — the banner says so plainly and
reports that the approval is still on file, unspent, rather than quietly
succeeding.

## Live updates

The run request is long-lived, so the board does not wait on it. It notes the
latest run id before starting, fires the request, and then polls the events route
roughly once a second, picking up the new run as soon as it appears and
streaming its steps in. When the request finally returns, it does one last sweep
so no tail events are lost between polls.

Below the room, a **run log** shows every step with its number, a colour-coded
agent pill in that dog's apron colour, the plain-language action, the tool, and
the result — and auto-scrolls as it grows. The room is for watching; the log is
for checking.

## Reset

A small "Reset board" control sits next to the ticket heading — understated on
purpose, since it throws work away. It restores the database to its original
values, clears the run, the drafts and the resolved badges, and puts the drawer
back to $3,400 so the whole thing can be demonstrated again from a clean start.

## What makes it enjoyable

Mostly that it is *legible without effort*. You can glance at it from across a
desk and know that the green dog is busy, the rust dog is waiting, a gold card
wants your signature, and there is $3,400 in the drawer.

And partly that it has some warmth. The dogs look at each other. The one that is
talking leans in. The mugs match the aprons. The Boss has a crown with a little
blue stone in it. None of that is necessary — but a tool you sit in front of all
day should feel like somewhere you do not mind sitting, and a shop staffed by
bulldogs in aprons is a more pleasant place to spend an afternoon than a table of
JSON.
