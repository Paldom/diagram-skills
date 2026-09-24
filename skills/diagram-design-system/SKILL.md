---
name: diagram-design-system
description: Creates and checks the design-system.md that styles every diagram - palette, fonts, radius, borders, a subtle neumorphic lift, icon style, motion - and can derive the tokens from moodboard or reference images, a brand, or a theme. Use when the user wants diagrams on-brand, restyled, themed, or consistent. Not for web or app design systems, UI kits, or drawing a diagram.
license: MIT
argument-hint: <moodboard folder, brand notes, or a theme to switch to>
---

# diagram-design-system

One file decides how every diagram looks. `design-system.md` holds a
```` ```design-tokens ```` JSON block the scripts read and prose (vocabulary,
principles, do/don't) the drawing model reads. Every renderer —
`illustration-draw` (cards, architecture, timelines, icons), `mermaid-draw`
(beautiful-mermaid, Graphviz, the Mermaid config), `diagram-animate`, and
`diagram-review`'s lint — loads it the same way, so pointing at another file
restyles everything on the next render.

**Resolution order** (first hit wins): `--design-system PATH-or-NAME` →
`$DIAGRAM_DESIGN_SYSTEM` → `./design-system.md` → the built-in Studio look
(`assets/design-system.md`). A **name** (`coral`) is looked up as `<name>.md`
in `./themes/`, each folder of `$DIAGRAM_THEMES`,
`~/.config/diagram-skills/themes/`, then the shipped `assets/themes/`;
`design_tokens.py --list-themes` shows what resolves. A theme file lists only
what it changes and inherits the rest (`"extends"` takes a name or a path). Outputs bake the tokens at generation time: switching themes
means regenerating, never editing SVGs.

Shipped: `studio` (`assets/design-system.md` — cool grey canvas, white
borderless cards, outline icons in tiles, pale-yellow highlight card, soft
lift), and in `assets/themes/`: `studio-ink` (Studio with an ink highlight —
the six-line custom-theme example), `paper-line` (warm paper, hairlines,
isometric icons, ink-inverted highlight), `coral` (the slide language: navy
type, red lede, square white cards with a soft shadow, warm-grey bands, coral
row headers, square badges, disc arrows, mono labels, coral icons, one navy
highlight), `coral-blocks` (solid salmon blocks in a peach group, navy
highlight), `midnight` (dark, hairline cards, periwinkle highlight). Every
token is documented in `references/token-schema.md`.

## When NOT to use

- Drawing a diagram → `illustration-draw` or `mermaid-draw` (they read the file).
- A design system for a web app, a Tailwind/shadcn theme, or a UI kit — this
  file styles diagrams only.
- Reviewing one diagram → `diagram-review`.

## Workflow

1. **Start from the closest shipped file.** Copy `assets/design-system.md` or a
   theme to the project as `design-system.md` (or next to the brief). For a
   brand given as a few values, write a partial file with just those tokens.
2. **From a moodboard, measure before choosing:**

   ```bash
   python3 "${CLAUDE_SKILL_DIR}/scripts/derive_palette.py" path/to/moodboard
   ```

   It samples every image and the first frame of every video: how many are
   monochrome, the paper and ink colours, the rare accents and how many images
   use each. Then **look at the images** (and read any `.drawio` XML for its
   `fillColor`, `arcSize`, `fontFamily`, `strokeWidth`): radius, borders, icon
   style, type and density are not in pixels. Weight what the user says is
   best over the frequency count.
3. **Write the tokens.** Pick the highlight by the palette, not by habit: a
   light marker (yellow) only works where it contrasts with the cards; on a
   hueless or saturated palette invert a card instead (dark `accent`, light
   `accent-ink` and `accent-muted`) — check it at 300 px in grayscale.
   Rules the checker enforces: text 4.5:1 on every
   surface it sits on (canvas, card, tile, group, note, pill, badge, accent);
   connectors 3:1; the accent is a **fill behind ink**, never text or a line;
   neumorph blur ≤ 5 px. Keep the prose in step: vocabulary table, 4–6
   principles, do/don't, measured ratios.
4. **Check** — hard errors exit 1 with the failing pair and ratio:

   ```bash
   python3 "${CLAUDE_SKILL_DIR}/scripts/design_tokens.py" --check design-system.md
   ```

5. **Prove the switch.** Render one sample in the default and in the new file
   (e.g. `arch_svg.py --sample` and a `build_svg.py` card from
   `illustration-draw`, each with `--design-system design-system.md`), look at
   both PNGs side by side, and adjust tokens until the new one reads as the
   moodboard. Report the file path and the three ways to apply it.

## Output spec

- `design-system.md` that passes `--check`, with prose matching its tokens.
- One before/after render pair and the measured contrast ratios.

## Gotchas

- `design_tokens.py` is vendored byte-identical into each skill that needs it
  (skills install independently); the repo's `make test` fails on drift.
- Colour is almost never the moodboard's point — spacing, radius, borders and
  restraint are. A board of 15 monochrome stills wants one accent, not five.
- Unknown keys are errors, on purpose: a typo like `"acent"` would otherwise
  silently fall back to the default.
- Fonts are system stacks; list a fallback chain ending in a generic family.
  Web fonts are never fetched (the renderers strip `@import`).
- Mermaid rendered by GitHub cannot load the file — `mermaid-draw`'s
  `render_themed.py --config` prints the equivalent `config:` frontmatter.
- Types this repo does not draw go to diagram-design; keep them in the theme
  with `scripts/to_diagram_design.py --design-system <theme> [--write --marker .]`
  — it prints (or, after the user agrees, writes) a diagram-design profile and
  the project marker that selects it.
