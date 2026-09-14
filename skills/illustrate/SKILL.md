---
name: illustrate
description: Draws a minimalist technical illustration from a title, notes, or a brief, end to end - brief, format choice, drawing in a subagent, one review.
license: MIT
argument-hint: <title, notes, brief path, or "from this repo">
disable-model-invocation: true
context: fork
agent: general-purpose
---

# illustrate

The one entry point: `/illustrate <idea>`. Runs the three engines in order and
reports. It holds no rules of its own — the brief, the drawing constraints, and
the checklist live in `diagram-brief`, `mermaid-draw` / `illustration-draw`, and
`diagram-review`. This skill runs in a forked subagent, so `$ARGUMENTS` must
carry everything: the idea, the destination if known, the personal take, and
any file paths. If a skill is missing here, install all of them first:
`npx skills add Paldom/diagram-skills`.

## Steps

1. **Brief.** Run `diagram-brief` on `$ARGUMENTS`. If the input is only a title,
   let it declare assumptions rather than stall. It writes
   `diagram-design/<slug>/brief.md`; pass that path explicitly to the next
   step — never let a draw skill pick up an older brief by default.
2. **Draw.** Run the routed skill — `mermaid-draw` for Markdown destinations,
   `illustration-draw` for feeds, articles, slides — with the brief path. That
   skill owns the whole mutation budget (three repairs, regenerations included)
   and the review (one pass, plus at most one re-check after a FIX or REDRAW,
   always followed by a fresh lint and render). Do not review again here.
   If the route is a handoff (`/design`, FigJam, draw.io), output the brief
   verbatim with the handoff instruction from the router and stop.
3. **Report** in one block: the takeaway and assumptions, the artifact paths
   (source, SVG, PNGs), the review verdict with residual findings, and what was
   left out. Never commit or push.

## From other harnesses or with another model

The same pipeline runs headless through `acpx` (the Agent Client Protocol CLI;
global flags go before the agent name). Write the ask to a file and pass it
with `-f` — never splice user text into a quoted shell string. Run it in a
throwaway directory: non-interactive sessions cannot prompt for permissions,
so writes need `--approve-all`, which is only acceptable where there is
nothing to damage.

```bash
mkdir -p /tmp/illustrate && cd /tmp/illustrate
printf '%s\n' '/illustrate <idea, destination, take>' > ask.md
acpx --approve-all --timeout 1200 claude exec -f ask.md
```

What leaves the machine: the ask, the files the session reads in that
directory, and whatever the adapter attaches on its own (its session metadata;
project context if you run it inside a repo, which is why the directory is empty).

## Gotchas

- Forks do not inherit the conversation. Anything said earlier and not in
  `$ARGUMENTS` does not exist for this run.
- One controller per request: this skill orchestrates; the draw skill mutates
  and reviews within its budget; nothing here re-opens the loop.
- A handoff is a valid outcome, not a failure — say so plainly.
