# Design system: Paper Line

Warm editorial variant from the same moodboard: greige paper, black ink,
hairline cards, curved connectors, solid black dots for milestones, and a neon
highlighter swipe used once. Only the tokens that differ from the default
(studio) are listed; the rest are inherited.

```design-tokens
{
  "name": "paper-line",
  "extends": "default",
  "color": {
    "canvas": "#EEEDE8", "surface": "#F6F5F1", "tile": "#F6F5F1",
    "ink": "#141414", "muted": "#6B6A65", "line": "#141414",
    "border": "#85847E", "subtle": "#D9D8D2",
    "group": "#F6F5F1", "group-border": "#85847E",
    "accent": "#141414", "accent-ink": "#F6F5F1", "accent-muted": "#A8A59E",
    "note": "#F6F5F1", "note-border": "#85847E",
    "pill": "#141414", "pill-ink": "#F6F5F1",
    "badge": "#141414", "badge-ink": "#F6F5F1", "signal": "#E0263F",
    "series-1": "#141414", "series-2": "#4D4C48", "series-3": "#6B6A65", "series-4": "#86847D"
  },
  "type": {
    "sans": "Inter, 'Helvetica Neue', Helvetica, Arial, sans-serif",
    "title-size": 46, "title-weight": 500, "title-tracking": -0.02,
    "section-weight": 600, "section-tracking": 0.12
  },
  "shape": { "radius": 14, "stroke": 1.25, "card-border": "hairline", "connector": "curve", "arrow": "open", "corner": 24 },
  "space": { "margin": 64, "gap": 40, "padding": 20 },
  "elevation": { "style": "flat" },
  "icon": { "style": "isometric-line", "stroke": 1.3, "tile": false }
}
```

## Differences from Studio

- Connectors are curves, not elbows, with small open arrowheads (a review
  showed direction was ambiguous without them).
- Milestones are solid ink dots on the line with the label beside the dot.
- Cards have a hairline border and no lift; the page stays flat like print.
- The highlight is an **ink-inverted card**: black fill, paper text, used
  once. Paper-line has no hue, so inversion is the only emphasis that survives
  grayscale and thumbnails (the old neon was 1.06:1 against the paper).
- Icons are isometric line drawings, not flat line icons.
