# Changelog

All notable changes to this repository's skills are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning: [SemVer](https://semver.org) on the plugin manifest
(breaking skill-interface change → major, new skill → minor, fix → patch).

## [Unreleased]

## [0.2.0] - 2026-09-24

Two new skills (`diagram-animate`, `diagram-design-system`), six themes, the
architecture and pipeline-explainer compilers, standard sizes, inline figures,
and delegation to diagram-design for the types these skills do not draw.

### Added

- v6, standard sizes and generic samples:
  - Canvas presets are the three delivery standards: `social` 1200×627,
    `square` 1080×1080, `wide` 1920×1080 (was 1200×630 / 1600×900).
    `build_svg.py --canvas` overrides the spec. On a square canvas, cards try a
    larger type unit first and keep the first layout that fits. They also get
    square layouts: a vertical timeline, tall flow cards, stack rows that fill
    the height, compare/tiers as full-width row cards, and titles wrapped at
    full size.
  - `--canvas` on `arch_svg.py`, `pipeline_svg.py` and `render_themed.py`
    centres a finished diagram on a preset (shared `design_tokens.fit_canvas`)
    and warns when its smallest text falls under 12 px there.
    `animate.py --canvas` pads GIF/MP4 to the preset, and the pipeline camera
    takes the canvas shape.
  - Every shipped sample tells a generic GraphQL / API-platform story: the
    matrix, the architecture, and the pipeline explainer (query → gateway →
    plan → resolvers → dashboard). The README gallery was regenerated from them.

- Types this repo does not draw (swimlane, org chart, Venn, funnel, treemap,
  heatmap, charts, Gantt, Sankey, fishbone, Wardley, kanban, journey, …) are
  routed to diagram-design in the active theme: `diagram-design-system`'s new
  `to_diagram_design.py` exports a theme as a diagram-design profile (+ the
  project marker that selects it); `diagram-brief` routes there instead of
  bending a missing type into a near archetype.
- v5, animations cross-checked against a reference explainer video and Emil
  Kowalski's animation rubric:
  - `pipeline_svg.py`: the pipeline explainer — columns of labelled code/JSON
    panels with syntax colour and bracket callouts to coloured notes,
    processor boxes with latency captions, a rendered mini-dashboard, arrows,
    and a stacked timing bar; `--sample` recreates the instant-dashboard video.
  - `animate.py`: code types line by line (at most 3 s per panel) and later
    steps wait for it; callouts play one at a time (token tint, leader draw,
    note fade); dashboards build part by part; on an explainer the camera
    makes one move per stage (650–1100 ms, `cubic-bezier(0.65, 0, 0.35, 1)`)
    after a 1.5 s reading hold, finished stages dim to 28 % and stay back so
    the summary owns the ending; `--reduced-motion` capture; reduced motion
    fades whole code panels and draws
    and cuts the camera instead of freezing; pops start at 0.96 without
    overshoot; the default entrance curve is `cubic-bezier(0.23, 1, 0.32, 1)`;
    only `reveal` compresses to `max-seconds`; the build no longer pauses
    before its first layer.
  - `deck.py --preset auto` recognises wide pipelines; each MP4 slide stays up
    max(7 s, 0.22 s per word), capped at 14 s.
  - Tokens `series-1` … `series-4` (chart and callout tones) in every theme.
- v4, after new coral references (private slides and a PowerPoint build video),
  two independent model proposals (Claude Fable 5.1, GPT-6 Astra via acpx) and
  a cross-review:
  - `coral` is now the slide language (navy type, accessible red `#C52D1C`
    lede/badges/row headers, square white cards with a soft shadow, warm-grey
    bands, mono labels, coral icons, disc arrows); the salmon look is kept as
    `coral-blocks`.
  - New tokens `color.lede`, `color.tag`/`tag-ink`, `color.icon` (each follows
    its older token unless set), `type.small-family` (`mono`),
    `shape.badge-shape` (`square`), `shape.flow-connector` (`disc`), and
    `elevation.style: soft` (one broad shadow; the lint bounds it).
  - `build_svg.py`: `matrix` archetype (row headers × cells), tiered `compare`
    (per-column `badge` and `eyebrow`, a `scale` complexity mosaic),
    `takeaway` bar, item `chips`, square bullets.
  - `animate.py --preset build`: the PowerPoint build — layers wait as ghosts
    and come into focus in order, connectors arrive with their later endpoint,
    the camera frames the active layers and settles on the whole; `--beat-ms`.
  - `deck.py`: diagrams → one offline HTML slide deck that replays each build,
    and optionally one 1080p MP4 of every slide.
  - `arch_svg.py`: cards inside a coloured layer are surface-coloured (white
    cards on warm-grey layers), notes avoid step badges, `data-id`/`data-group`
    /`data-from`/`data-to` attributes for the animator.
- `diagram-design-system` — one `design-system.md` (tokens + prose) styles every
  renderer, the lint, and the animator; resolution `--design-system` →
  `$DIAGRAM_DESIGN_SYSTEM` → `./design-system.md` → built-in Studio. Ships
  Studio (default, from the moodboard's draw.io board), `paper-line`, and
  `coral`; `scripts/design_tokens.py` (strict schema, `extends`, WCAG checks on
  every text/surface pair) and `scripts/derive_palette.py` (moodboard sampling
  via ffmpeg). The loader is vendored byte-identical; `scripts/test_vendored.py`
  guards drift.
- `diagram-animate` — `scripts/animate.py` adds CSS keyframes in reading order
  (fade/rise, connector draw with late arrowheads, badge pop, typing, highlighter
  last, `pipeline` camera pan with a pinned title); `scripts/capture.mjs`
  captures deterministic frames in the system Chrome (puppeteer-core, pinned
  lockfile, `npm ci --ignore-scripts` on `--allow-install`) for GIF and MP4.
- `illustration-draw` — `scripts/arch_svg.py` (Graphviz-laid architecture
  diagrams: groups, icon cards, pills, sticky notes, orthogonal connectors,
  numbered badges + legend), `scripts/icons.py` (35 outline icons, flat or
  isometric line), `scripts/gemini_icon.py` (optional Nano Banana icons behind
  `--allow-network`), a `timeline` archetype, per-item icons, `data-step` on
  every element.
- `mermaid-draw` — `scripts/render_themed.py` + `render_mermaid.mjs`:
  beautiful-mermaid 1.1.3 exports themed from the design system (no web-font
  fetch, rasterized in Chrome), Graphviz with design-system defaults, and
  `--config` for GitHub-rendered Mermaid.
- `diagram-brief` — routes architecture, timelines, exported Mermaid, and
  animation; a "Reference styles" catalog section for diagram-design, archify
  (light) and drawio-skill with how to feed each the design system.

- Themes resolve by name everywhere (`--design-system coral`,
  `DIAGRAM_DESIGN_SYSTEM=midnight`, `"extends": "paper-line"`), from `./themes/`,
  `$DIAGRAM_THEMES`, `~/.config/diagram-skills/themes/` and the shipped set;
  `design_tokens.py --list-themes`. New themes `midnight` (dark) and `studio-ink`
  (six-line custom-theme example). New token `accent-muted`.
- Card redesign after a hallmark audit, a frontend-slides exploration and an
  advise-max council: shared card lockup (number top-left, icon top-right,
  bottom-anchored label + detail, one label size per row), `eyebrow` and
  `numbered` spec keys, a `bus` layout for `hub`, a table-like `compare`, a
  one-card `stack` with a clipped highlight row, drawn `grid` axes, and a
  single-track `timeline` (solid done / dashed planned, highlight pill,
  alternating callouts from 7 milestones).
- `gemini_icon.py --kind illustration` for 16:9 hero visuals; handles the
  current Interactions API response shape (JPEG only).
- Animated GIF/MP4 start with a poster frame (the final state), so feed and
  README thumbnails show the diagram instead of an empty canvas.

### Changed

- v7, inline figures: `build_svg.py`, `arch_svg.py` and `pipeline_svg.py` no
  longer draw a slide-style title. The title (still required: it is the
  takeaway) becomes the SVG `<title>`/alt text; `show_title: true` or
  `--show-title` draws title, subtitle, eyebrow and footer for slides and
  social cards (decks use it). Without a `canvas`, an inline card is as tall
  as its content plus the margins (`data-inline="1"`, which the lint accepts);
  an explicit `--canvas` keeps the preset size. The architecture legend
  aligns with the diagram. The diagram-design profile asks for title-less,
  inline figures too.
- README gallery restructured by what each diagram explains (architecture,
  cards, explainers and animation, diagrams as code, sizes, delegated types,
  themes), each shown in its best-designed theme as picked by an
  `/advise-max` council (GPT-6 Astra, Gemini 3.8) and two image-reading
  reviews (GPT-6 Astra, Opus 5.5); `coral-blocks` stays out of the gallery.
- Highlights per theme: paper-line and coral no longer use yellow (1.06:1 and
  1.28:1 against their canvases) — paper-line inverts the card to ink, coral
  fills it navy; Studio keeps the pale-yellow card.
- `svg_lint.py` reloads the theme named in `data-design-system`, ignores
  clip-path/marker geometry for contrast, handles end-anchored rotated labels,
  and warns on feed text below 16 px (was 18 px) at 1200 wide.
- `build_svg.py` is token-driven: the spec's `theme` is gone (use a design
  system), `accent` is now an optional override that must pass contrast as a
  fill behind ink, and the accent is a highlighter fill rather than a coloured
  outline. The hub centre uses the badge colours.
- `svg_lint.py` allows only the design system's `<filter data-ds="neumorph">`
  lift (blur ≤ 5 px), errors when the accent is used as text or a line, skips
  icon transforms, checks the palette against the design system, and has a
  `--diagram` mode for full-size architecture diagrams.
- Trigger descriptions retuned for the two new skills (evals green).
- After an independent visual review (Codex, GPT-6 Astra): `compare` heading
  bands use the card surface plus a divider (the tile colour can equal the
  canvas), `paper-line` gets open arrowheads, and the `pipeline` animation ends
  by pulling back to an overview of the whole diagram; foreign SVGs (Mermaid,
  Graphviz) now animate in positional reading order with drawn connectors.

### Removed

- The `scale` complexity mosaic above tiered `compare` cards (a moodboard
  illustration, not a diagram element); a spec that still sets it fails with a
  fix-it message. Badges and eyebrows carry the tiers.

### Fixed

- `render_themed.py --canvas --png` rasterizes the *fitted* SVG in Chrome (it
  needs CSS `color-mix`; rsvg drew black boxes and dropped lines), creates the
  output folder, and message/edge labels get a canvas-coloured halo so
  lifelines no longer strike through them.
- `pipeline_svg.py`: timing-bar labels of short segments no longer collide;
  callout leaders leave from the end of the code line instead of striking
  through it.
- `arch_svg.py`: a note with no free spot fails with a fix-it message instead
  of being drawn over a card; a title wider than the diagram widens the canvas.
- `pipeline_svg.py`: a callout note wider than its panel is rejected; the
  footer widens the canvas instead of touching its edge.
- `animate.py`: a pipeline stage dims only once the next stage is lit (no
  all-dim frame), and the take ends on the payoff and the summary together
  when both fit the frame. `bbox()` no longer reads `H`/`V` path values as
  coordinates.

## [0.1.0] - 2026-09-15

### Added
- `illustrate` — user-invoked entry point (`/illustrate <idea>`): brief → route →
  draw in a forked subagent → one review; documents the headless `acpx` path for
  other harnesses.
- `diagram-brief` — title/notes/take → one-page brief with the takeaway, ≤ 9
  entities, and the format decision; `references/format-router.md` (destination
  → medium, precedence rules, handoffs to Claude Design, FigJam, draw.io) and
  `references/skill-catalog.md` (15 third-party skills/tools verified 2026-09-14
  with licenses, network behaviour, and install commands).
- `mermaid-draw` — Mermaid/DOT with a pinned `config:` frontmatter, quoted
  labels, node caps, a lint → maid → mmdc loop capped at three repairs, and one
  review; `references/mermaid-gotchas.md`.
- `illustration-draw` — slide-like SVG from a JSON spec: `scripts/build_svg.py`
  compiles five archetypes (flow, stack, hub, grid, compare) onto a fixed grid
  with capacity checks; `scripts/spawn_drawer.py` asks a Claude or Codex session
  through `acpx --deny-all` for the spec only; `references/style-rules.md`.
- `diagram-review` — `scripts/mermaid_lint.py` (parser-crash idioms, caps,
  config pin, accessibility, one accent), `scripts/svg_lint.py` (safe static
  subset, WCAG 2.2 contrast, text overlap/overflow, palette, font floors),
  `scripts/render.py` (renderer autodetect incl. network-blocked headless
  Chrome; pinned mermaid-cli via `--allow-download`), and
  `references/checklist.md` (analyze → fidelity → mandatory/advisory checklist →
  PASS / FIX / REDRAW / INCOMPLETE; a security gate before rendering; border
  contrast per WCAG 2.2 SC 1.4.11).
- Repository scaffolded from the skills template.
