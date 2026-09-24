---
name: illustration-draw
description: Draws a minimalist visual from a brief as one SVG in the active design system - architecture diagram with numbered steps, timeline, social card, hero, infographic-style graphic, slide visual - compiled from a JSON spec, then reviewed. Use when the user asks for a visual, illustration, graphic, architecture diagram, timeline, or LinkedIn or X image. Not for Mermaid in Markdown, app icons, or decks.
license: MIT
argument-hint: <brief path, or one-line idea + destination>
---

# illustration-draw

Produce a visual that reads as designed: one takeaway, specific elements,
one highlighter, in the active design system. Free-hand SVG from a language model collides once
it has more than a handful of elements, and the popular "no Mermaid slop"
skills turn out to have the model hand-place every coordinate — so here the
model does not write geometry. It writes a **JSON spec** and a compiler
places it: `build_svg.py` puts cards (`flow`, `stack`, `hub`, `grid`,
`compare`, `timeline`, `matrix`) on a fixed grid with capacity checks;
`arch_svg.py` lets Graphviz lay out an **architecture diagram** (groups,
cards with outline icons, pill tags, sticky notes, orthogonal connectors,
numbered step badges plus a legend) and paints it. Both read the design
system (`--design-system`, `$DIAGRAM_DESIGN_SYSTEM`, `./design-system.md`,
else the built-in Studio look; see `diagram-design-system`) and tag every
element with `data-step`, so `diagram-animate` can turn the result into a GIF.
The render is still inspected, because fonts vary by machine. This skill runs
inside one fixed budget.

## When NOT to use

- The destination is a README, docs page, or PR → `mermaid-draw`.
- The idea has no format yet → `diagram-brief` (it routes here when the
  destination is a feed, article, or slide).
- The takeaway depends on labeled, directed edges between more than three
  entities — the archetypes cannot express them (see "What an archetype can
  say" in `references/style-rules.md`) → `mermaid-draw` or a handoff.
- Reviewing or fixing an existing image → `diagram-review`.
- App icons → `icon-draw` (icon-designer-skills); decks, charts, characters,
  brand scenes → the handoffs in `diagram-brief`.

## Budget (the whole skill runs inside it)

- **Three mutations** of the spec per request — a capacity fix, a lint fix,
  and a regeneration by the drawer all count.
- **One review pass**, plus at most one re-check after its FIX or REDRAW.
- **Every mutation is followed by compile, lint, and render** before anything
  is delivered. At the cap, deliver with residual findings; do not loop.

## Workflow

1. **Brief.** Use the brief path you were given. Without one, read
   `diagram-design/brief.md` only if its takeaway matches the request;
   otherwise write a 5-line quick brief (takeaway, audience, destination,
   entities, archetype) to `diagram-design/<slug>/brief.md`. Never draw without
   a stated takeaway.
2. **Choose** the archetype by the idea's shape — `flow` (steps), `stack`
   (layers), `hub` (one center, satellites), `grid` (2×2 tradeoff), `compare`
   (2–3 options), `timeline` (3–12 dated milestones on one left-to-right
   track; solid up to the highlight, dashed after) — or an
   **architecture** spec when the takeaway needs systems, boundaries and an
   ordered flow between them (`arch_svg.py --sample` prints a working one).
   Pick the canvas (`social` 1200×627 for LinkedIn/X/OG, `square` 1080×1080,
   `wide` 1920×1080 for slides — or `--canvas` to override; `{"w","h"}` for a
   wide panorama to camera-pan; `arch_svg.py`/`pipeline_svg.py --canvas` fit a
   finished diagram and warn under 12 px). Figures are inline by default: the
   title is the SVG `<title>`/alt text, not drawn — add `--show-title` for a
   slide or social card. Pick an `icon` per card from `icons.py --list` (35
   outline icons, line or isometric-line by the design system). Read
   `references/style-rules.md` once per session; it is what the drawer and the
   reviewer both follow. If the brief's
   required entities exceed the archetype's capacity, split the brief or route
   to `mermaid-draw` — dropping a required entity is a fidelity failure, not a
   fix.
3. **Get the spec from a drawer** — an in-harness subagent, or a separate
   session through `acpx` (an installed Claude Code or Codex; useful for a
   different model or another harness). The acpx path, every permission
   denied, run from an empty temp directory so no project context is loaded:

   ```bash
   python3 "${CLAUDE_SKILL_DIR}/scripts/spawn_drawer.py" --brief diagram-design/<slug>/brief.md \
     --out-dir diagram-design/<slug> --name <slug> --agent claude      # or --agent codex
   ```

   It writes `<slug>.prompt.md`, `<slug>.spec.json`, and compiles `<slug>.svg`.
   Exit 3 means `acpx` is not installed: give the prompt file to a subagent (or
   answer it yourself), save the JSON as `<slug>.spec.json`, then compile:

   ```bash
   python3 "${CLAUDE_SKILL_DIR}/scripts/build_svg.py" diagram-design/<slug>/<slug>.spec.json --out diagram-design/<slug>/<slug>.svg
   ```

   Architecture specs compile with `arch_svg.py SPEC.json --out X.svg` (needs
   Graphviz `dot`). Add `--design-system PATH` to either compiler to restyle.
   How a system works, step by step (question → model → answers → query → spec
   → rendered result), is a **pipeline explainer**: `pipeline_svg.py SPEC.json
   --out X.svg` lays columns of labelled code/JSON panels (with bracket
   callouts to coloured notes), tall processor boxes with latency captions, a
   rendered mini-dashboard and a timing bar left to right —
   `pipeline_svg.py --sample` prints one; animate it with `diagram-animate
   --preset pipeline`. Lint it with `--diagram --max-words 400` (it is read
   over time).
   A capacity ERROR ("does not fit", "needs 2-6 items") means shorten labels or
   remove elements the takeaway does not need; never shrink text.
4. **Lint and render** with the sibling review scripts (install with
   `npx skills add Paldom/diagram-skills --skill diagram-review` if missing):

   ```bash
   python3 "${CLAUDE_SKILL_DIR}/../diagram-review/scripts/svg_lint.py" diagram-design/<slug>/<slug>.svg  # --diagram for architecture
   python3 "${CLAUDE_SKILL_DIR}/../diagram-review/scripts/render.py" diagram-design/<slug>/<slug>.svg
   ```

   Read both PNGs (delivery size and half size). Fix by editing the **spec** and
   recompiling — never the SVG — counting each fix against the budget.
5. **Review.** Invoke `diagram-review` with the SVG, the PNGs, and the brief
   path. On FIX edit the spec, on REDRAW change archetype or cut content and
   return to step 3; either way recompile, lint, render, then one re-check at
   most.
6. **Deliver** (and offer `diagram-animate` for a GIF/MP4) the SVG and the delivery-size PNG paths (feeds want PNG; LinkedIn
   and X do not accept SVG), the spec, the verdict, and anything left out of the
   brief. Never commit or push.

## Output spec

- `diagram-design/<slug>/<slug>.svg` — one file, `viewBox` at a preset size,
  root `font-family`, `<title>` and `<desc>`, passes `svg_lint.py` with 0 errors.
- `diagram-design/<slug>/renders/<slug>/<slug>-<w>.png` at two widths.
- `diagram-design/<slug>/<slug>.spec.json` — the editable source of truth.
- The review verdict and residual warnings, in one short block.

## Spec options and generated visuals

Card anatomy, every optional spec key (`eyebrow`, `numbered`, `takeaway`,
item `chips`, the hub `bus` layout, tiered `compare` with S/M/L badges and a
complexity `scale`, the `matrix` archetype) and the Gemini icon/hero workflow
(`scripts/gemini_icon.py`, needs `GEMINI_API_KEY` and `--allow-network`) are in
`references/spec-options.md` — read it when the brief needs one of them.

## Gotchas

- **The spec is the artifact.** Editing the SVG by hand reintroduces the failure
  the compiler removed; regenerate from the spec.
- **Capacity errors usually mean the brief carries more than one point.** Split
  into two cards when cutting would drop something the takeaway needs.
- `acpx` global flags go before the agent name (`acpx --deny-all ... claude exec`);
  `spawn_drawer.py` already does this and uses `--cwd` on an empty directory.
  The adapters must be installed and logged in; nothing is downloaded here.
  What leaves the machine: the prompt file plus whatever the adapter attaches
  on its own (session metadata) — to that agent's provider.
- The drawer prompt asks for content, not compliance — rules live in the compiler
  and the lint, because format-restricted prompts measurably degrade reasoning
  (reference in `references/style-rules.md`).
- The neumorph lift is the one filter allowed (`<filter data-ds="neumorph">`);
  the accent is a fill behind ink — the lint errors if it becomes text or a line.
- Fonts are a system stack declared on the root; no CDN fonts, so text metrics
  differ slightly between machines. The lint's fitting is approximate; the
  half-size render is the check that counts.
- Drawing the spec yourself is fine — the compiler and the reviewer, not the
  drawer's identity, are the gate.
