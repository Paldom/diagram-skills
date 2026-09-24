# Token schema

Every key the ```` ```design-tokens ```` block accepts. Unknown keys are errors.
Colours are 6-digit hex. Numbers are px unless noted. Defaults are Studio's.

## color

| Token | Default | Paints | Checked |
| --- | --- | --- | --- |
| `canvas` | #EEEFF4 | the background | — |
| `surface` | #FFFFFF | cards on the canvas | ink ≥ 4.5, muted ≥ 4.5 |
| `tile` | #EEEFF4 | cards inside a group, icon tiles, heading bands | ink ≥ 4.5, muted ≥ 4.5 |
| `ink` | #232F3E | titles, labels, icons | ≥ 4.5 on canvas, surface, tile, group, note |
| `muted` | #5B6472 | subtitles, details, edge labels | ≥ 4.5 on canvas, surface, tile |
| `line` | #3D4756 | connectors, timeline track | warn < 3 on canvas |
| `border` | #8E95A2 | hairline card borders | warn < 3 when `card-border` is hairline |
| `subtle` | #D0D3D2 | dividers, inactive dots | — |
| `group` / `group-border` | #FFFFFF / #D0D3D2 | group panels | ink ≥ 4.5 on group |
| `accent` / `accent-ink` / `accent-muted` | #FFE27A / #232F3E / #454E5C | the one highlight fill, its text, its secondary text | ≥ 4.5 each; warn accent < 3 on canvas. A dark accent (paper-line, coral) makes an inverted highlight card |
| `note` / `note-border` | #FFF2CC / #D6B656 | sticky notes | ink ≥ 4.5 |
| `pill` / `pill-ink` | #D0D3D2 / #232F3E | status and tier tags | ≥ 4.5 |
| `badge` / `badge-ink` | #232F3E / #FFFFFF | numbered step badges, hub centre | ≥ 4.5 |
| `signal` | #E8563F | a single alert dot or decorative mark, used sparingly | — |
| `lede` | follows `muted` | the subtitle under the title (coral red in `coral`) | ≥ 4.5 on canvas |
| `tag` / `tag-ink` | follow `badge` / `badge-ink` | filled kicker pills and matrix row headers | ≥ 4.5 |
| `series-1` … `series-4` | #2F5FA8 · #2E7A3F · #5B4AAE · #B7791F | chart lines and bars, callout tones, timing-bar segments | 1–3 ≥ 4.5 on canvas (they are also note text); 4 ≥ 3 on surface |
| `icon` | follows `ink` | outline icons (coral red in `coral`) | ≥ 3 on surface (graphical, SC 1.4.11) |

## type

`sans`, `mono`, `serif` (CSS font stacks, end with a generic family);
`title-size` (40 at 1200 px — cards scale titles by `title-size / 40`),
`body-size`, `label-size`, `small-size`; `title-weight`, `label-weight`,
`section-weight`; `title-tracking`, `section-tracking` (em);
`section-case` ∈ `upper` | `none`; `small-family` ∈ `sans` | `mono` — the voice of
step numbers, dates, eyebrows, chips and axis labels.

## shape

`radius`, `radius-small`, `stroke`, `stroke-strong`, `card-border` ∈ `none` |
`hairline`, `connector` ∈ `orthogonal` | `curve` | `straight`, `corner`
(elbow rounding), `arrow` ∈ `open` | `filled` | `none`, `dot-radius`,
`badge-radius`, `badge-shape` ∈ `circle` | `square` (S/M/L-style square badges and
square bullets), `flow-connector` ∈ `line` | `disc` (a filled disc with a white
arrow between flow steps).

## space

`margin`, `gap`, `padding`, `card-width`, `card-height` (architecture cards;
Mermaid spacing derives from `gap`).

## elevation

`style` ∈ `neumorph` | `soft` | `flat`; `light` and `dark` shadows, each `{dx, dy,
blur, color, opacity}`. `soft` uses only `dark` as one broad drop shadow
(slide cards; the lint allows ≤ 24 px blur and ≤ 15 % opacity). Applied only to groups and top-level cards as
`<filter id="ds-lift" data-ds="neumorph|soft">` — the only filters `svg_lint.py`
accepts (neumorph: two shadows, blur ≤ 5 px).

## icon

`style` ∈ `line` | `isometric-line` | `none`; `stroke`; `size`; `tile`
(draw the icon on a tile-coloured square).

## motion

`easing` (cubic-bezier array), `stagger-ms` (between steps), `enter-ms`,
`draw-ms` (connector draw), `type-ms` (per character), `hold-ms` (last
frame), `fps`, `gif-fps`, `max-seconds` (the stagger compresses to fit).

## Top level

`name` (shown in `data-design-system` on every SVG; the lint reloads the theme
by this name), `version`, `extends` (`studio`/`default`, a theme name, or a
path relative to this file).

## Follow rules

`lede`, `tag`, `tag-ink` and `icon` are newer than most themes. When a theme
sets the older token but not the newer one, the newer one follows it (a theme
that changes `muted` gets the same subtitle colour) — so old themes keep
working unchanged.
