# Design system: Midnight

A dark variant for slides and dark-mode docs: near-black canvas, raised slate
cards, soft white ink, and a periwinkle highlight card with dark text. Flat —
a neumorphic lift does not read on dark surfaces, so the cards separate by
tone instead. Only the tokens that differ from Studio are listed.

```design-tokens
{
  "name": "midnight",
  "extends": "default",
  "color": {
    "canvas": "#0E1117", "surface": "#171B24", "tile": "#222837",
    "ink": "#E8EBF2", "muted": "#A1A9B8", "line": "#8C95A6",
    "border": "#343B4A", "subtle": "#2A303D",
    "group": "#131720", "group-border": "#2A303D",
    "accent": "#8FA8FF", "accent-ink": "#0E1117", "accent-muted": "#243056",
    "note": "#1C2130", "note-border": "#3A4152",
    "pill": "#2A303D", "pill-ink": "#E8EBF2",
    "badge": "#E8EBF2", "badge-ink": "#0E1117", "signal": "#FF7A6B",
    "series-1": "#7AB6F5", "series-2": "#7ED39A", "series-3": "#C4A8FF", "series-4": "#F2B866"
  },
  "type": { "title-weight": 600 },
  "shape": { "card-border": "hairline" },
  "elevation": { "style": "flat" },
  "icon": { "style": "line", "tile": true }
}
```

## Differences from Studio

- Dark canvas, cards one step lighter with a hairline border; no lift.
- The highlight is a periwinkle card with near-black text (the only
  saturated colour on the page); icons sit in slightly lighter tiles.
- Sticky notes are a neutral raised slate, so the periwinkle highlight stays the only hue.
