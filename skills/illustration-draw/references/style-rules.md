# House style for minimalist technical illustrations

The rules the drawer must follow and the reviewer checks. They exist because the
default output of every image and code model converges on the same look — and
readers now recognise it as machine-made. Facts below were verified against
primary sources on 2026-09-14.

## One idea

- The **title is the takeaway**, written as a sentence a reader can disagree with
  ("One artifact moves through three gates"), not a topic label ("CI pipeline").
- **Inline by default.** A figure in an article sits under the article's own
  heading, so the title is *not drawn*: it becomes the SVG `<title>` (and the
  alt text / caption you hand over). Draw it only for a slide, deck or social
  card (`show_title: true` / `--show-title`), where the image travels alone.
- If the brief contains two ideas, draw the one in the takeaway and say what was
  left out. Two ideas on one card is the most common reason a visual fails.
- Everything on the card either supports the takeaway or is deleted.

## Fewest, most specific elements

- 3–6 primary elements (boxes, columns, layers). The compiler caps: flow 2–6,
  stack 2–5, hub 3–6 spokes, grid exactly 4, compare 2–3 columns × 1–5 rows.
- Labels name a concrete thing or action: "immutable image", "one endpoint,
  typed schema". Never "data", "flow", "system", "process", "connects to",
  "uses", "interacts". If a label could sit on any diagram, it is wrong.
- No numbers that are not in the brief. Missing information stays missing; a
  fabricated statistic is worse than a gap.
- No colour legends: label the element directly (the one exception is the
  architecture step legend, which maps numbered badges to verbs) (Tufte's data-ink rule — remove
  everything that does not carry information; chartjunk is decoration that
  distracts, https://en.wikipedia.org/wiki/Chartjunk).

## What an archetype can say

| Archetype | Relation it expresses | Cannot express |
| --- | --- | --- |
| `flow` | order: A before B before C (2–6 steps) | branches, loops, labeled edges |
| `stack` | layering / tiers (2–5) | dependencies between non-adjacent layers |
| `hub` | one center, 3–6 satellites (undirected); `layout: "bus"` draws the center as a bar | direction or payload per spoke |
| `grid` | position on two named axes (exactly 4) | anything not a 2×2 |
| `compare` | membership: which trait belongs to which option (2–3 × 1–5) | relations between options |
| `timeline` | order in time: 3–12 milestones on one track (dashed after the highlight = planned) | durations, overlaps, branches, dates to scale |
| pipeline explainer (`pipeline_svg.py`) | data moving through stages: artifacts in, a processor, artifacts out, with callouts and latencies | branching flows, more than ~8 stages |
| architecture (`arch_svg.py`) | systems in boundaries, labelled calls, an ordered flow (badges 1..n + legend), notes; ≤ 24 cards | a data chart; anything a 3-card flow already says |

If the takeaway depends on a relation an archetype cannot express, the brief
belongs in `mermaid-draw` (or two cards), not in a stretched archetype. An
entity the brief lists but the takeaway does not need may be left out; say so
in the delivery. An entity the takeaway needs may not.

## Palette, type, shape — from the design system

The look is not decided here. Every compiler reads the active design system
(`--design-system`, `$DIAGRAM_DESIGN_SYSTEM`, `./design-system.md`, else the
built-in Studio look — see the `diagram-design-system` skill): canvas, ink,
muted, surfaces, the one accent, fonts, radius, borders, the subtle neumorphic
lift, icon style, motion. What stays fixed whatever the theme:

- **One highlighter.** The accent goes on exactly one element — the one that
  carries the takeaway — as a fill behind ink, never as text or a line.
- No gradients, glows, textures, emoji, stock or coloured icons. The only
  effect is the design system's two-sided lift on panels and top-level cards.
- Icons only from `icons.py` (one stroke, one family), one per card, and only
  when they name a real thing; no icon beats a generic icon.
- Contrast is a hard gate: WCAG 2.2 SC 1.4.3 requires 4.5:1 for text and 3:1 for
  large text (≥ 24 px, or ≥ 18.66 px bold); SC 1.4.11 requires 3:1 for graphical
  objects (https://www.w3.org/TR/WCAG22/). The token checker and the lint compute it.
- Fonts are system stacks declared on the `<svg>` root: nothing is fetched,
  non-Latin text never becomes tofu.
- Sizes on a 1200-wide card: title ≈ 40–48 px, labels 20–28 px, detail
  17–19 px. Floors the lint enforces on cards: **error below 1.15 % of the
  canvas width, warning below 1.5 %** — a feed shows the card at roughly half
  size. Architecture diagrams are read full size: `svg_lint.py --diagram`
  switches to an 11 px floor.
- One line at a smaller size beats two lines at a larger size.

## Canvas presets (delivery sizes)

| Preset | Pixels | Source |
| --- | --- | --- |
| `social` | 1200 × 627 (1.91:1) | Facebook: "at least 1200 x 630 pixels", "as close to 1.91:1 as possible" (developers.facebook.com/docs/sharing/webmasters/images/); LinkedIn: minimum 1200 × 627, ratio 1.91:1 (linkedin.com/help/linkedin/answer/a521928) |
| `wide` | 1920 × 1080 (16:9) | talk slides, video, 16:9 cards |
| `square` | 1080 × 1080 | feeds that crop to square; cards try a larger type unit first, the timeline runs vertically, compare/tiers become row cards (matrix stays a grid — prefer `social` for it) |

Cards reflow natively to every preset. Architecture and pipeline diagrams are laid out
at their natural size; `--canvas` centres them on a preset and warns when the smallest
text falls under 12 px there — then keep the natural size or animate with a camera
(`diagram-animate --canvas` pads GIF/MP4 to the same presets).

X (Twitter) large-image cards are widely described as 2:1; the primary page
could not be fetched, so `social` (1.91:1) is the safe default there too.

## The anti-slop tells (what reviewers actually flag)

| Tell | Do instead |
| --- | --- |
| Purple or pastel gradient, heavy drop shadows, glow | the design system's surfaces and its one subtle lift |
| Three identical cards in a row with a decorative icon each | only as many elements as the takeaway needs; an icon only when it names the thing |
| Labels like "Data", "Process", "Connects to" | the specific noun or verb from the brief |
| Arrow soup: every element linked to every other | the one path that matters; drop the rest or split the visual |
| Legend + colour coding | direct labels, one accent |
| A title that is a topic ("Architecture overview") | a sentence with a claim |
| Numbers without a source | delete them |

## Why the constraints live in the compiler, not the prompt

The drawer prompt is short and the compiler (`build_svg.py`) rejects what breaks
the rules. Two findings motivate this: format-restricted generation measurably
degrades model reasoning ("Let Me Speak Freely?", arXiv 2408.02442), so the
prompt asks for content, not compliance; and vision-language judges rank
candidates reliably but produce unreliable absolute scores ("VLM Judges Can Rank
but Cannot Score", arXiv 2604.25235), so the review step is a binary checklist
plus deterministic lints rather than a 1–10 score.
