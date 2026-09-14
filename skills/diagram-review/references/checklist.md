# Review checklist: analyze, then judge

Vision-language judges rank candidates far more reliably than they score them:
absolute scores come with wide, uninformative intervals while pairwise rankings
hold up ("VLM Judges Can Rank but Cannot Score", arXiv 2604.25235). So this
review never asks for a score. It is three passes in a fixed order, and the
verdict is derived from the passes. That the checklist itself catches more than
free-form review is this repo's design heuristic, not a measured result.

## Pass A — Analyze (no opinions yet)

Write these down from the render, not from the source:

1. Every visible text run, transcribed verbatim (this catches clipped or
   overlapping labels and the "continvoucly morged" class of garbled text).
2. Count of primary elements (boxes / nodes / columns / lifelines) and of
   connectors (arrows / edges / messages).
3. Colors in use; which element carries the accent.
4. The title, and whether it states a claim or names a topic.
5. What the diagram is *about* in one sentence — written before reading the brief.

## Pass B — Fidelity (only when a brief, source, or expected relations exist)

Compare Pass A against the brief. A diagram can compile, render, and look
polished while describing something that does not exist, so each of these is a
separate check:

| Check | Fails when |
| --- | --- |
| Missing | an entity or relation the takeaway requires is absent (an entity the brief lists but the takeaway does not need may be left out, if the delivery says so) |
| Extra | an entity, edge, or number appears that the brief does not contain |
| Direction | an arrow or dependency points the wrong way, a lifeline is inverted |
| Level | abstraction levels mix (a deployment host inside a logical component view; a database engine on a context diagram) |
| Claim | the title's claim is not what the elements show |

One wrong edge or label → **FIX**; anything more → **REDRAW**.

## Pass C — Checklist

Answer yes/no; each "no" is a finding with the visible fact that caused it.

**Mandatory (any "no" → FIX)**
- [ ] The takeaway is visible at feed size (the half-width render).
- [ ] Every text run is legible in the half-width render and passes the lint's size floor.
- [ ] No overlapping labels, nothing clipped, no text outside the canvas.
- [ ] Contrast ≥ 4.5:1 for text, 3:1 for large text and graphics (the lint computes it; on a PNG, judge by eye and say so).
- [ ] Accessibility metadata present: SVG `<title>` and `<desc>`; Mermaid `accTitle` and `accDescr`.
- [ ] Labels name concrete things or actions — no "data", "flow", "connects to", "uses".
- [ ] No numbers without a source in the brief.

**Advisory (≥ 3 "no"s → recommend REDRAW; otherwise listed as residual)**
- [ ] ≤ 9 primary elements (Mermaid: ≤ 12 nodes / 7 lifelines).
- [ ] No crossing connectors that could be avoided.
- [ ] The title is a sentence with a claim, not a topic label.
- [ ] One accent, on the element that carries the takeaway; neutrals elsewhere.
- [ ] No gradients, shadows, 3D, decorative icons, emoji, legends, or unused shapes.
- [ ] One font family; ≤ 2 stroke widths.

## Verdict rules

| Condition | Verdict |
| --- | --- |
| No render possible, or no reference when fidelity was requested | **INCOMPLETE** — list what was and was not checked |
| Lint ERROR, a mandatory "no", or a one-edge fidelity miss | **FIX** — list the targeted edits |
| Fidelity off by more than one edge/label, the takeaway not visible, or ≥ 3 advisory "no"s | **REDRAW** — say which archetype/split would work |
| Otherwise | **PASS** — list residual advisory findings and what the reviewer could not check |

Hard cap: three fix iterations. Report what remains rather than looping.

## What each input type allows

| Input | Deterministic checks | Render | Notes |
| --- | --- | --- | --- |
| Mermaid source (`.mmd`, fenced in `.md`) | `mermaid_lint.py`; `@probelabs/maid` validates flowchart, sequence, pie, class, state — ER, gantt, journey and others are **pass-through** (say "unvalidated: erDiagram") | write the fence to a `.mmd`, then `render.py` via `mmdc` (needs `--allow-download` if not installed) | maid: exit 0 = no errors, 1 = errors; `--fix` applies safe fixes (`->` → `-->`, inner quotes) |
| Graphviz DOT | `dot -Tsvg in.dot -o in.svg` validates when installed, else "unvalidated" | the produced SVG through `render.py` | |
| SVG | `svg_lint.py` (safe subset, geometry, contrast, palette); a safe-subset ERROR stops the review before rendering | `render.py` | text metrics are approximate; the render decides |
| PNG/JPG | none | read directly | say plainly that only Passes A–C ran |
| HTML | out of scope | — | no lint exists for it here; render it yourself and submit the PNG |

## Second opinion (optional, different model)

Reviewing your own drawing is unreliable. When `acpx` is installed, ask a
different model to run Pass A and Pass C on the PNG and to **rank** candidates
if there are several — never to score them. Reads must be allowed or the model
cannot open the image; nothing else is permitted:

```bash
acpx --approve-reads --timeout 300 --format text codex exec \
  "Open <path.png>. First transcribe every text run and count the boxes and arrows. \
   Then answer yes/no for each line of this checklist: <paste Pass C>. \
   Return findings only, each tied to a visible fact."
```

Accept the reply only if its transcription matches the render — a reply with no
transcription did not see the pixels. The image and the checklist leave the
machine, to the provider of that agent.
