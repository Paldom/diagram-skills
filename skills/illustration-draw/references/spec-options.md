# Spec options, card anatomy, and generated visuals

Loaded on demand from `SKILL.md`. Everything here is optional; `build_svg.py --schema` prints the exact shape.

## Card anatomy and spec options

Every card uses one lockup: step number top-left (a badge on icon-less themes),
icon top-right, label and detail anchored bottom-left, one label size per row.
Figures are always inline: `title` and `subtitle` become `<title>`/`<desc>`,
never drawn (top-level `eyebrow`, `footer` and `show_title` are rejected).
Optional spec keys: `numbered` (step numbers, default on for `flow`), `layout: "bus"` for `hub`
(a horizontal bar with stops above and below — use it for buses, queues,
platforms), `takeaway` (a full-width ink bar stating the conclusion), item
`chips` (up to 3 mono identifiers such as `main` or `dev → stg → prod`).
Tiered comparisons: per column `badge` (S/M/L) and `eyebrow` ("Ships in
days"). `matrix` is a ruled table: 2–4 `rows`, each a `header` and 1–4
`cells` (`label`, `detail`, one `accent` fill; no card chrome). The highlight
is whatever the design system says: a yellow card in Studio, an inverted card
in paper-line, coral and studio-ink.

## Relation-first archetypes (v8)

Pick by the relation the takeaway states. `build_svg.py --sample` is not
needed: every shape below has a working sample in `SAMPLES` (print one with
`python3 -c 'import build_svg, json; print(json.dumps(build_svg.SAMPLES["cycle"]))'`).

| Archetype | Shape of the spec |
| --- | --- |
| `cycle` | `items` 3–6 (`label`, `detail`, one `accent`), optional `center`; arcs run clockwise and the last returns to the first |
| `before_after` | `before` / `after` headings, `pairs` 2–6 `{before, after, before_detail?, after_detail?, accent?}` — old cards quiet, new cards on the surface |
| `swimlane` | `lanes` 2–4 names, `steps` 3–8 in order `{label, lane, detail?, accent?}` — same lane moves right, a hand-off drops in the same column |
| `decision` | `root` `{question, branches: [{label, to}]}` down to leaves `{answer, detail?, accent?}` (≤ 4 levels, ≤ 7 answers) |
| `tree` | `root` `{label, detail?, accent?, children}` (≤ 4 levels, ≤ 5 children each, ≤ 7 leaves) |
| `quadrant` | `axes {x: [low, high], y: [low, high]}`, optional `quadrants` (4 corner names), `points` 3–10 `{label, x, y, accent?}` with x, y in 0–1 |
| `metrics` | `kpis` 1–4 `{label, value, delta?, accent?}` and/or `bars.items` 2–8 `{label, value, display?, accent?}` — only numbers the brief supplies |
| `layers` | `items` 2–5, outermost first; a highlighted ring fills only its label band |

## Icons and visuals beyond the built-in set

`icons.py` is the consistency guarantee: same stroke, same grid, recoloured by
the design system. For a subject it lacks, or for a hero image,
`scripts/gemini_icon.py` asks a Gemini image model (`gemini-3-pro-image`, Nano
Banana Pro), prompting with the design system's ink, canvas, accent and icon
style:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/gemini_icon.py" "a vector database" --out db.jpg --allow-network
python3 "${CLAUDE_SKILL_DIR}/scripts/gemini_icon.py" "requests flowing through one gateway" \
  --kind illustration --out hero.jpg --allow-network --design-system paper-line
```

It needs `GEMINI_API_KEY` (create one at aistudio.google.com/apikey, `export`
it in the shell profile, never commit it; a key set in `~/.zshrc` is visible to
`zsh -ic '...'`), sends only the prompt, and returns a SynthID-watermarked JPEG
(the API's only image format). Use the output in HTML, slides or posts — the
static-SVG lint rejects raster images — and prefer procedural icons inside
cards: generated icons are richer but less uniform at 28 px.
