# Design system: Coral

An editorial slide language: white canvas, deep navy type, a coral subtitle,
square white cards with a soft broad shadow, warm grey bands, coral row
headers and square step badges, mono identifiers, coral outline icons, and one
navy card as the highlight. Synthesised from two independent model proposals
that converged on the same palette; the salmon-block look lives on as
`coral-blocks`.

```design-tokens
{
  "name": "coral",
  "extends": "default",
  "color": {
    "canvas": "#FFFFFF", "surface": "#FFFFFF", "tile": "#EEEDE9",
    "ink": "#0B2026", "muted": "#3F535B", "line": "#0B2026",
    "border": "#D6DADC", "subtle": "#E4E1DB",
    "group": "#FCDCD3", "group-border": "#FCDCD3",
    "accent": "#0B2026", "accent-ink": "#FFFFFF", "accent-muted": "#B7C4C9",
    "note": "#FFFFFF", "note-border": "#D6DADC",
    "pill": "#FFD7D1", "pill-ink": "#0B2026",
    "badge": "#C52D1C", "badge-ink": "#FFFFFF", "signal": "#FF3621",
    "lede": "#C52D1C", "tag": "#C52D1C", "tag-ink": "#FFFFFF", "icon": "#C52D1C",
    "series-1": "#0B2026", "series-2": "#C52D1C", "series-3": "#6E3A8C", "series-4": "#C4643A"
  },
  "type": {
    "sans": "'DM Sans', Manrope, Inter, 'Helvetica Neue', Helvetica, Arial, sans-serif",
    "mono": "'DM Mono', 'JetBrains Mono', 'SF Mono', Menlo, Consolas, monospace",
    "title-size": 44, "title-weight": 700, "title-tracking": -0.025,
    "label-weight": 700, "section-weight": 700, "section-tracking": 0.04,
    "small-family": "mono"
  },
  "shape": {
    "radius": 0, "radius-small": 0, "card-border": "none",
    "connector": "orthogonal", "corner": 6, "arrow": "open",
    "badge-shape": "square", "flow-connector": "disc"
  },
  "elevation": {
    "style": "soft",
    "dark": { "dx": 0, "dy": 8, "blur": 24, "color": "#0B2026", "opacity": 0.07 }
  },
  "icon": { "style": "line", "stroke": 1.6, "tile": false },
  "motion": { "stagger-ms": 140, "enter-ms": 360, "type-ms": 0, "hold-ms": 2800, "max-seconds": 40 }
}
```

## The language

- **Type.** Navy titles, bold, tight; the subtitle (lede) in accessible coral
  `#C52D1C` (5.6:1 on white — the slides' `#FF3621` is only 3.6:1, so it is
  kept for decorative marks as `signal`). Identifiers, step numbers, dates and
  kickers are mono.
- **Cards.** Square, white, no border, a soft one-sided shadow (8 px down,
  24 px blur, 7 %). Warm grey `#EEEDE9` is a structural band behind white cells.
- **Coral does the pointing.** Row headers, square step badges, tag pills,
  outline icons and the subtitle are coral; card fills never are.
- **One navy card** carries the takeaway (white text, 16.8:1).
- **Arrows between stages** are navy discs with a white arrow; architecture
  connectors stay thin navy elbows.
