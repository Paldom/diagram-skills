# Design system: Wave

A calm, engineered look from a deep-water palette: a warm near-white page,
soft grey cards without borders, very dark green ink, and one bright green
highlight card with dark text — the only saturated colour on the page.
Headings are Manrope, identifiers and step numbers are mono, section labels
are ExtraBold caps. Flat: the cards separate by tone, not by shadow.

```design-tokens
{
  "name": "wave",
  "extends": "default",
  "color": {
    "canvas": "#FFFDFC", "surface": "#F7F7FA", "tile": "#EEEFF4",
    "ink": "#062220", "muted": "#5B5A60", "line": "#2B2B30",
    "border": "#76757C", "subtle": "#DDDDE2",
    "group": "#FFFFFF", "group-border": "#DDDDE2",
    "accent": "#42FF94", "accent-ink": "#062220", "accent-muted": "#1D5C38",
    "note": "#FCEAE1", "note-border": "#FFC2B6",
    "pill": "#D6FEE8", "pill-ink": "#062220",
    "badge": "#062220", "badge-ink": "#FFFFFF", "signal": "#F25E48",
    "lede": "#5B5A60", "tag": "#062220", "tag-ink": "#FFFFFF", "icon": "#062220",
    "series-1": "#0E7B7B", "series-2": "#217D48", "series-3": "#D82F15", "series-4": "#F25E48"
  },
  "type": {
    "sans": "Manrope, 'IBM Plex Sans', 'Helvetica Neue', Helvetica, Arial, sans-serif",
    "mono": "'IBM Plex Mono', 'JetBrains Mono', 'SF Mono', Menlo, Consolas, monospace",
    "title-weight": 600, "title-tracking": -0.02,
    "label-weight": 600, "section-weight": 800, "section-tracking": 0.05,
    "small-family": "mono"
  },
  "shape": { "radius": 12, "radius-small": 8, "card-border": "none", "connector": "orthogonal", "corner": 10, "arrow": "open" },
  "elevation": { "style": "flat" },
  "icon": { "style": "line", "tile": true }
}
```

## The language

- **Page and cards.** Warm near-white page; cards are soft grey `#F7F7FA` with
  no border and no shadow; icons sit in slightly darker `#EEEFF4` tiles.
- **One bright highlight.** The takeaway is a bright green `#42FF94` card with
  very dark green text (12.7:1). Bright green is never text on the light page
  (1.3:1) — only this one fill.
- **Ink, not black.** Titles, labels, badges and tags are very dark green
  `#062220`; connectors are near-black `#2B2B30`, plain open arrows.
- **Quiet accents.** Pills are pale mint, sticky notes pale peach; coral
  appears only as the `signal` dot and the last chart series.
- **Type.** Manrope SemiBold titles with slight negative tracking; step
  numbers, dates and chips in mono; section labels ExtraBold caps with wide
  tracking.
