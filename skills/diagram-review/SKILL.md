---
name: diagram-review
description: Reviews a diagram - Mermaid, DOT, SVG, or PNG - with lints (syntax, caps, contrast, overlap), a render, and an analyze-then-judge checklist, returning PASS, FIX, REDRAW, or INCOMPLETE. Use when the user asks to review, critique, check, rate, compare, or fix a diagram, or whether it is readable, neat, or too busy. Not for drawing, choosing a format, icon or UI reviews, or code review.
license: MIT
argument-hint: <diagram path(s), optionally --brief <path>>
---

# diagram-review

Judge diagrams by what a reader sees, in a fixed order. A diagram can compile,
render, and look polished while inverting a dependency or inventing a service —
and a model asked "is this good?" tends to answer from the source instead of
the pixels. So this skill runs deterministic lints first, refuses to render
anything unsafe, renders at delivery and feed size, then forces the
analyze-then-judge checklist: transcribe and count before any verdict. The
output is PASS, FIX (with the exact edits), REDRAW (with the split), or
INCOMPLETE (what could not be checked).

## When NOT to use

- Creating a diagram → `mermaid-draw` or `illustration-draw` (they call this
  skill within their own budget).
- Choosing a format or writing a brief → `diagram-brief`.
- HTML pages, app icons (`icon-critique`), data charts, page UX, or code.

## Workflow

1. **Identify the input and the reference.** Inputs: Mermaid (`.mmd`, or the
   fenced blocks of a `.md`), DOT, SVG, PNG/JPG. Reference: the brief path you
   were given, else the source code or expected relations, else none — then
   say fidelity cannot be checked.
2. **Lint** (stdlib, exit 1 on errors):

   ```bash
   python3 "${CLAUDE_SKILL_DIR}/scripts/mermaid_lint.py" diagram.mmd      # or README.md (all fences)
   python3 "${CLAUDE_SKILL_DIR}/scripts/svg_lint.py" illustration.svg
   ```

   **Security gate:** an SVG with `<script>`, `<image>`, `<foreignObject>`,
   external `href`, or an event handler is rejected here — do not render it,
   report the finding and stop. Mermaid types maid validates can also run
   `npx -y @probelabs/maid@0.0.29 diagram.mmd` (one pinned download); report
   ER, gantt and other pass-through types as "unvalidated". DOT: `dot -Tsvg
   in.dot -o in.svg` validates and converts when installed, else "unvalidated".
   PNG has no lint — say so.
3. **Render** what has a source: a Mermaid fence goes to a `.mmd` file first;
   DOT after `dot -Tsvg`; SVG directly. PNG is read as is.

   ```bash
   python3 "${CLAUDE_SKILL_DIR}/scripts/render.py" <file> --out diagram-design/renders/<stem>
   ```

   `render.py` autodetects rsvg-convert, resvg, cairosvg, ImageMagick,
   Inkscape, headless Chrome with network blocked, or macOS qlmanage; Mermaid
   needs `mmdc` or `--allow-download`. If nothing can render, relay the install
   hints and the verdict is **INCOMPLETE** — never judge markup.
4. **Read both PNGs** (delivery width and half width) with the Read tool.
5. **Analyze, then judge**, per `references/checklist.md`: Pass A transcribes
   every text run and counts elements and connectors; Pass B checks fidelity
   against the reference (missing, extra, reversed, wrong level, claim); Pass C
   is the checklist, split into mandatory items and advisory items. Every
   finding cites a visible fact ("'Deploy' overlaps the arrow at 600 px").
6. **Verdict** by the rules in the checklist: any mandatory failure or lint
   ERROR → FIX with the exact edits (REDRAW when fidelity is off by more than
   one edge or label, or the takeaway is not visible); ≥ 3 advisory findings →
   REDRAW recommended; a missing render or reference → INCOMPLETE with what was
   checked; otherwise PASS with residual advisory findings.
7. **Fix only when asked.** "Review", "rate", "compare" end at the verdict.
   When asked to fix, edit non-destructively: `<name>-r1.svg` / `-r1.mmd` next
   to the original (for compiled illustrations, edit the spec and rebuild), then
   re-run steps 2–4 before presenting. **Hard cap: three fix iterations.**
8. **Second opinion (optional).** For anything going public, or when several
   candidates exist, ask a different model to run Pass A and C on the PNG and to
   *rank* candidates; the command and the "did it see the pixels" check are in
   the checklist. Rankings are advisory; the human picks. Never auto-promote,
   headless included.

## Output spec

- Lint output (or "no lint for this type"), security-gate result, renderer
  used, render paths.
- Findings grounded in visible facts, grouped as fidelity / mandatory / advisory.
- Verdict: PASS | FIX (edits listed) | REDRAW (split or archetype named) |
  INCOMPLETE (what was and was not checked).

## Gotchas

- **Self-review bias.** When you drew the diagram, prefer the second opinion for
  the final pass and ground every finding in a pixel fact.
- **The lint's text metrics are approximate** (character counts); an overlap
  flag needs the render to confirm, and a clean lint never means a clean render.
- **Ask judges for findings and rankings, never a number.** Absolute scores
  from a vision model carry wide, uninformative intervals (see the checklist's
  reference); a 7/10 is not a finding.
- **Compiles ≠ correct.** A green parser only closes the syntax question; the
  fidelity pass is the only defence against a diagram that describes a system
  that does not exist.
- maid passes ER, gantt and journey diagrams through as valid — do not report
  them as validated.
- Rendering runs local subprocesses (Chrome, mmdc). The security gate in step 2
  exists because a renderer is an execution surface; it is not a style check.
