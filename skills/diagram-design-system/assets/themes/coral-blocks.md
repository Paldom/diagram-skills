# Design system: Coral blocks

The earlier coral look, kept as its own theme: solid salmon component blocks in
a pale peach group, after the coral architecture boards and the skill diagram:
white canvas, solid coral component blocks with a bold title and a regular
subtitle, a peach-tinted shared core, thin navy elbow connectors, and red
numbered badges with a legend. Only the tokens that differ from the default
(studio) are listed.

```design-tokens
{
  "name": "coral-blocks",
  "extends": "default",
  "color": {
    "canvas": "#FFFFFF", "surface": "#F47A63", "tile": "#F47A63",
    "ink": "#1B1B1B", "muted": "#1B3139", "line": "#1B3139",
    "border": "#E8452C", "subtle": "#F7C9BF",
    "group": "#FCEAE5", "group-border": "#FCEAE5",
    "accent": "#1B3139", "accent-ink": "#FFFFFF", "accent-muted": "#B9C4C8",
    "note": "#FFF6F3", "note-border": "#E8452C",
    "pill": "#1B3139", "pill-ink": "#FFFFFF",
    "badge": "#C7321C", "badge-ink": "#FFFFFF", "signal": "#C7321C",
    "series-1": "#1B3139", "series-2": "#7A1E12", "series-3": "#3A2622", "series-4": "#5C1A10"
  },
  "type": { "title-size": 38, "label-weight": 700 },
  "shape": { "radius": 8, "connector": "orthogonal", "corner": 12, "arrow": "open" },
  "elevation": { "style": "flat" },
  "icon": { "style": "line", "tile": false, "stroke": 1.6 }
}
```

## Differences from Studio

- Components are solid coral blocks; the label is bold, the one-line role
  below it regular; one ink outline icon per block, no tile.
- The shared layer is a peach-tinted group without a border.
- Step badges are red with white numbers, and a legend row explains them.
- The highlight is a **navy card with white text** — the connectors' navy,
  13.6:1 on the white canvas and 5.1:1 against the coral blocks. Yellow was
  the least visible card on this page (1.28:1 on white). Secondary text on
  coral is navy too, so hierarchy comes from size and weight.
