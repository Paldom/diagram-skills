---
name: mermaid-draw
description: Draws diagrams-as-code - Mermaid flowchart, sequence, state, ER, class and Graphviz DOT - pinned config, quoted labels, a node cap, a lint-render loop, and one review. Use when the user asks for a mermaid diagram, flowchart, sequence diagram, state machine, ER diagram, or a diagram for a README, docs, or PR. Not for SVG social cards or slide visuals, reviewing a diagram, or picking a format.
license: MIT
argument-hint: <what to diagram, or a brief path>
---

# mermaid-draw

Write Mermaid (and DOT) that renders on the first try and still reads as a
diagram, not as arrow soup. LLM Mermaid fails in two separate ways: the parser
rejects it (unquoted punctuation, a lowercase `end`, `->` arrows), or it
renders fine and nobody can read it (25 nodes, generic labels, a theme that
changed under Mermaid 12). This skill fixes both with constraints on the source
and a deterministic loop around it, inside one fixed budget.

## When NOT to use

- The idea has no format yet and the destination is a feed, article, or slide →
  `diagram-brief` first (it may route to `illustration-draw`).
- Reviewing or fixing a diagram someone else wrote → `diagram-review`.
- Editable draw.io/FigJam output, C4 modelling, or a deck → the handoffs in
  `diagram-brief`'s catalog.

## Budget (the whole skill runs inside it)

- **Three mutations** of the source per request — a lint repair, a parser-error
  repair, and a regeneration from the brief all count.
- **One review pass**, plus at most one re-check after its FIX or REDRAW.
- **Every mutation is followed by the lint and, when available, the render.**
  Nothing is delivered on the strength of an earlier check.
- At the cap, deliver what exists with its residual findings; do not loop.

## Workflow

1. **Brief.** Use the brief path you were given. Without one, read
   `diagram-design/brief.md` only if its takeaway matches the request;
   otherwise write a 3-line quick brief (takeaway, destination, entities ≤ 12)
   into `diagram-design/<slug>/brief.md`. Entities come from the code or text
   you were given — never invented.
2. **Pick the type** by the idea's shape: steps → `flowchart LR`; parties
   exchanging messages over time → `sequenceDiagram` (≤ 7 participants);
   states → `stateDiagram-v2`; tables → `erDiagram`; a dependency tree → DOT
   (see `references/mermaid-gotchas.md`). Layers → `flowchart TB` with subgraphs.
3. **Write the source** from the template in `references/mermaid-gotchas.md`:
   the `config:` frontmatter pin (`theme: base`, `look: classic`, `layout: dagre`,
   and the design system's `themeVariables` — print them with
   `python3 "${CLAUDE_SKILL_DIR}/scripts/render_themed.py" --config`, so
   GitHub's own renderer matches the exported images), `accTitle`/`accDescr`, alphanumeric ids, every
   label with punctuation in double quotes, specific edge labels (verb +
   payload), ≤ 12 nodes / 20 edges, one `classDef accent` on the element that
   carries the takeaway. Split into two diagrams rather than exceed the cap.
4. **Lint** (milliseconds, no install):

   ```bash
   python3 "${CLAUDE_SKILL_DIR}/../diagram-review/scripts/mermaid_lint.py" diagram.mmd
   ```

   If the script is missing, install the sibling: `npx skills add
   Paldom/diagram-skills --skill diagram-review`. Fix every ERROR; keep or
   justify each WARN.
5. **Validate with a real parser** when the type is flowchart, sequence, pie,
   class, or state: `npx -y @probelabs/maid@0.0.29 diagram.mmd` (browser-free,
   exit 1 on errors, `--fix` for safe auto-fixes). ER, gantt and other types
   pass through maid unvalidated — say "unvalidated" for them. Running npx
   downloads the pinned package once; skip it if the user has not allowed
   network access.
6. **Render in the design system and look.** For an exported image (docs site,
   slide, post) render with beautiful-mermaid (flowchart, state, sequence,
   class, ER) — cleaner than mmdc, themed from the design system (palette,
   font, radius, border, lift), no web-font fetch; DOT goes through Graphviz
   with the design system's defaults (rounded borderless cards, muted edge
   labels, orthogonal routing unless edges carry labels):

   ```bash
   python3 "${CLAUDE_SKILL_DIR}/scripts/render_themed.py" diagram.mmd --png [--design-system design-system.md]
   python3 "${CLAUDE_SKILL_DIR}/scripts/render_themed.py" graph.dot --out graph.png
   ```

   `--canvas social|square|wide` centres the SVG on 1200×627, 1080×1080 or
   1920×1080 and warns when text drops under 12 px there.

   The first Mermaid render needs `--allow-install` (pinned `npm ci
   --ignore-scripts` of beautiful-mermaid + puppeteer-core into
   `~/.cache/diagram-skills/`; ask first). The SVG styles itself with CSS
   variables, so the PNG is rasterized in the system Chrome. For a README that
   GitHub renders, the check is still `mmdc` via
   `"${CLAUDE_SKILL_DIR}/../diagram-review/scripts/render.py" diagram.mmd`.
   Read the PNG at both widths. Feed exact parser errors back and fix, counting
   each fix against the budget.
7. **Review.** Invoke `diagram-review` on the source (and PNG if any) with the
   brief path, so fidelity — missing, extra, reversed, wrong level — is checked
   against what the diagram was supposed to say. On FIX apply the edits, on
   REDRAW rebuild from step 2 with the reviewer's split; either way re-run
   steps 4–6, then one re-check at most.
8. **Deliver** the fenced ```` ```mermaid ```` block in the target file (or a
   `.mmd` next to it), the validation status per step, the verdict, and
   anything the cap left unresolved. Never commit or push.

## Output spec

- A Mermaid block that passes `mermaid_lint.py` with 0 errors, with the config
  pin and `accTitle`/`accDescr`, ≤ 12 nodes per diagram.
- The maid/mmdc result (or "unvalidated" with the reason) and the review verdict.
- For DOT: the `.dot` source and, when `dot` exists, the rendered SVG/PNG in
  the design system.
- For exported Mermaid: the beautiful-mermaid SVG and PNG (`data-design-system`
  is not set on them; lint them visually, not with `svg_lint.py`).
- Want it animated? Hand the SVG to `diagram-animate`.

## Gotchas

- Mermaid 12 (2026-09) changed the default layout to ELK and the look to `neo`;
  an unpinned diagram renders differently on every host. Always pin.
- GitHub bundles its own Mermaid version: avoid the newest diagram types in a
  README, and never paste private diagrams into hosted editors or kroki.io
  (they keep nothing under your access controls).
- Several bundled themes fail WCAG AA contrast (open issue #3691) — `theme:
  base` with the design system's variables is the safe baseline (the token
  checker has already verified their contrast).
- beautiful-mermaid ignores the `config:` frontmatter (the renderer strips it)
  and does not support gantt, pie, mindmap or C4 — render those with mmdc.
- `->` is invalid in a flowchart but valid in a sequence diagram; the lint knows
  the difference, so trust its type-specific errors, not a generic rule.
- A clean render proves syntax, not truth. The reviewer's fidelity pass is the
  only step that catches a reversed dependency or an invented service.
- If the lint script cannot run, fail closed: label the diagram UNVALIDATED and
  say so; do not present it as checked.
