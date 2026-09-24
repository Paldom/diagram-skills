# Design system: Studio

The default look for every diagram, card, icon and animation these skills
produce. Derived from a moodboard of 17 stills, one draw.io architecture board
and one pipeline animation (2026-09-23): white borderless cards on a cool grey
canvas, outline icons in tiles, grey pill tags, yellow sticky notes,
numbered step badges, thin orthogonal connectors, and a pale-yellow
highlighter used once.

**To restyle everything:** copy this file (or one of `themes/`), edit it, and
point the skills at it — `--design-system path/to/design-system.md`,
`DIAGRAM_DESIGN_SYSTEM=path`, or a `./design-system.md` in the working
directory. A theme file only needs the tokens it changes (`"extends":
"default"` is implied); everything else comes from the block below. Outputs
bake the tokens at generation time, so switching themes means regenerating.

The ```design-tokens``` block is what the scripts read. The prose after it is
what the drawing model reads. Keep both in step.

```design-tokens
{
  "name": "studio",
  "version": 1,
  "color": {
    "canvas": "#EEEFF4",
    "surface": "#FFFFFF",
    "tile": "#EEEFF4",
    "ink": "#232F3E",
    "muted": "#5B6472",
    "line": "#3D4756",
    "border": "#8E95A2",
    "subtle": "#D0D3D2",
    "group": "#FFFFFF",
    "group-border": "#D0D3D2",
    "accent": "#FFE27A",
    "accent-ink": "#232F3E",
    "accent-muted": "#454E5C",
    "note": "#FFFFFF",
    "note-border": "#C9CDD4",
    "pill": "#D0D3D2",
    "pill-ink": "#232F3E",
    "badge": "#232F3E",
    "badge-ink": "#FFFFFF",
    "signal": "#E8563F",
    "lede": "#5B6472",
    "tag": "#232F3E",
    "tag-ink": "#FFFFFF",
    "icon": "#232F3E",
    "series-1": "#2F5FA8",
    "series-2": "#2E7A3F",
    "series-3": "#5B4AAE",
    "series-4": "#B7791F"
  },
  "type": {
    "sans": "Manrope, Inter, 'Helvetica Neue', Helvetica, Arial, sans-serif",
    "mono": "'JetBrains Mono', 'SF Mono', Menlo, Consolas, monospace",
    "serif": "'Instrument Serif', 'Times New Roman', Georgia, serif",
    "title-size": 40,
    "body-size": 15,
    "label-size": 13,
    "small-size": 11,
    "title-weight": 700,
    "label-weight": 500,
    "section-weight": 800,
    "title-tracking": -0.01,
    "section-case": "upper",
    "section-tracking": 0.02,
    "small-family": "sans"
  },
  "shape": {
    "radius": 10,
    "radius-small": 6,
    "stroke": 1.5,
    "stroke-strong": 2,
    "card-border": "none",
    "connector": "orthogonal",
    "corner": 8,
    "arrow": "open",
    "dot-radius": 6,
    "badge-radius": 11,
    "badge-shape": "circle",
    "flow-connector": "line"
  },
  "space": { "margin": 48, "gap": 28, "padding": 16, "card-width": 116, "card-height": 96 },
  "elevation": {
    "style": "neumorph",
    "light": { "dx": -2, "dy": -2, "blur": 3, "color": "#FFFFFF", "opacity": 0.9 },
    "dark": { "dx": 2, "dy": 3, "blur": 5, "color": "#1C2433", "opacity": 0.07 }
  },
  "icon": { "style": "line", "stroke": 1.6, "size": 30, "tile": true },
  "motion": {
    "easing": [0.23, 1, 0.32, 1],
    "stagger-ms": 160,
    "enter-ms": 480,
    "draw-ms": 700,
    "type-ms": 26,
    "hold-ms": 1800,
    "fps": 24,
    "gif-fps": 20,
    "max-seconds": 12
  }
}
```

## Vocabulary

| Element | Use it for | Look |
| --- | --- | --- |
| **Group** | a system boundary or layer ("Gateway services") | white panel, 10 px radius, uppercase bold section title top-left, faint lift |
| **Card** | one component | icon above a 1–2 line label, centred; tile fill inside a group, white on the canvas; no border |
| **Pill** | a status, tier or cross-cutting concern ("Health", "Scaling", "Raw") | grey capsule overlapping the top edge of the card or group it qualifies |
| **Layer header** | the columns of a layered architecture | accent-yellow capsule spanning the column, centred title |
| **Note** | a fact that needs a sentence | white sticky with a folded corner and a grey edge (never yellow — that is the highlight's colour), 11 px text, placed next to what it explains, never covering a connector |
| **Badge** | the order of a flow | ink circle with a white number on the connector; a legend row at the bottom maps numbers to verbs |
| **Connector** | a dependency or a call | 1.5 px ink line, orthogonal with 8 px rounded corners, open arrowhead; label in muted small text beside it |
| **Code block** | a config or payload the reader must see | dashed group with mono text |

## Principles

1. **Quiet surfaces, loud structure.** Colour is almost absent: grey canvas,
   white panels, grey tiles. Structure comes from grouping, alignment and
   whitespace, not boxes-in-boxes-in-boxes. Maximum two levels of nesting.
2. **One highlighter.** The yellow accent marks at most one element — the one
   that carries the takeaway — as a fill behind ink. Layer headers and sticky
   notes are the only other yellow, and they are pale.
3. **Icons are line art of real things.** One outline icon per card, same
   stroke weight everywhere, no colour. No icon beats a generic icon.
4. **Numbers tell the story.** When a flow has an order, badge the connectors
   1..n and add the legend; the reader should be able to narrate the diagram
   from the legend alone.
5. **A bit of neumorphism, never more.** Groups and top-level cards get a soft
   two-sided lift (light top-left, dark bottom-right, blur ≤ 5 px, ≤ 7 %
   opacity). Tiles inside groups are flat. If the lift is visible at feed
   size, it is too strong.
6. **Motion is explanation.** Animations reveal in reading order: groups fade
   up, cards land in them, connectors draw along their route, badges pop in
   step order, notes appear last, the highlighter goes on the takeaway at the
   end. Ease-out, no bounce, and hold the final frame.

## Do / don't

| Do | Don't |
| --- | --- |
| a sentence as the title ("Keep the gateway thin") | a topic as the title ("Architecture") |
| specific labels from the brief | "Data", "Process", "Connects to", invented numbers |
| one icon family, one stroke | emoji, coloured stock icons, mixed styles |
| numbered badges + legend for an ordered flow | arrows that cross when a reorder would avoid it |
| a sticky note for a sentence | paragraphs inside cards |
| the soft lift on panels | drop shadows, glows, gradients, 3D extrusions |

## Accessibility floor

Text 4.5:1 against its background (WCAG 2.2 SC 1.4.3), connectors 3:1
(SC 1.4.11). Measured for this file: ink on canvas 11.8:1, muted on canvas
5.2:1, line on canvas 8.2:1, ink on note 13.6:1, badge numbers 13.6:1, ink on
the accent 10.6:1. `design_tokens.py --check` recomputes this for any theme.
