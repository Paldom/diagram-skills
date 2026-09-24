# Spec options, card anatomy, and generated visuals

Loaded on demand from `SKILL.md`. Everything here is optional; `build_svg.py --schema` prints the exact shape.

## Card anatomy and spec options

Every card uses one lockup: step number top-left (a badge on icon-less themes),
icon top-right, label and detail anchored bottom-left, one label size per row.
Optional spec keys: `show_title` (draw `title`/`subtitle`/`eyebrow` — off by
default so the figure sits inline in an article; turn it on for slides and
social cards, or pass `--show-title`), `eyebrow` (small uppercase kicker above the title),
`numbered` (step numbers, default on for `flow`), `layout: "bus"` for `hub`
(a horizontal bar with stops above and below — use it for buses, queues,
platforms), `takeaway` (a full-width ink bar stating the conclusion), item
`chips` (up to 3 mono identifiers such as `main` or `dev → stg → prod`).
Tiered comparisons: per column `badge` (S/M/L) and `eyebrow` ("Ships in
days"). `matrix` is the row-header layout: 2–4 `rows`, each a `header` and
1–4 `cells` (`label`, `detail`, mono `eyebrow`, one `accent`). The highlight is whatever the design system says: a yellow card
in Studio, an inverted card in paper-line, coral and studio-ink.

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
