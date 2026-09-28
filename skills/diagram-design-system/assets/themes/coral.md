# Design system: Coral

An editorial red-line language: a white page, flat square cards bounded by a
hairline, no shadow. Red is structural (square step numbers, icons, bullets,
row rules), navy is ink and the only fill (the highlight), and connectors are
plain open arrows. Chosen in v8 over a warm-paper and a warm-ground variant;
the salmon-block look lives on as `coral-blocks`.

```design-tokens
{
  "name": "coral",
  "extends": "default",
  "color": {
    "canvas": "#FFFFFF", "surface": "#FFFFFF", "tile": "#F7F2EF",
    "ink": "#0B2026", "muted": "#46585E", "line": "#3F535B",
    "border": "#7E8A8F", "subtle": "#E6DEDA",
    "group": "#FFF4F0", "group-border": "#F2DCD4",
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
    "radius": 0, "radius-small": 0, "card-border": "hairline",
    "connector": "orthogonal", "corner": 6, "arrow": "open",
    "badge-shape": "square", "flow-connector": "line"
  },
  "elevation": { "style": "flat" },
  "icon": { "style": "line", "stroke": 1.6, "tile": false },
  "motion": { "stagger-ms": 140, "enter-ms": 360, "type-ms": 0, "hold-ms": 2800, "max-seconds": 40 }
}
```

## The language

- **Page and cards.** White page, white square cards bounded by a 1 px hairline
  (`#7E8A8F`, 3:1), no shadow. Warm `#F7F2EF` / `#FFF4F0` only where a band or a
  group means something.
- **Red is structural.** Square step numbers, outline icons, bullets and the
  lede are accessible coral `#C52D1C` (5.6:1 on white; the brand `#FF3621` is
  only 3.6:1, so it stays a decorative `signal`).
- **One navy fill** carries the takeaway (white text, 16.8:1); nothing else is
  filled dark.
- **Connectors** are plain open arrows in slate `#3F535B`; no discs.
- **Type.** Bold navy labels; identifiers, step numbers, dates and kickers are
  mono.
