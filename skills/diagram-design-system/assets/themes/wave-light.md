# Design system: Wave light

The light, product-marketing sibling of Wave: a pale periwinkle page, white
rounded cards floating on a soft shadow, pale-lavender groups, sky-blue pills
and one deep indigo highlight card with white text. Lavender is the accent
family; everything is Manrope, black ink, generous radii.

```design-tokens
{
  "name": "wave-light",
  "extends": "default",
  "color": {
    "canvas": "#F1F4FF", "surface": "#FFFFFF", "tile": "#EEF3FF",
    "ink": "#111118", "muted": "#4A4A55", "line": "#2B2B30",
    "border": "#8E8AB8", "subtle": "#D3E2FF",
    "group": "#E6EEFF", "group-border": "#D3E2FF",
    "accent": "#463D87", "accent-ink": "#FFFFFF", "accent-muted": "#E0DAFE",
    "note": "#FCF6E1", "note-border": "#F5E5AF",
    "pill": "#A9DBFC", "pill-ink": "#111118",
    "badge": "#463D87", "badge-ink": "#FFFFFF", "signal": "#907AFF",
    "lede": "#463D87", "tag": "#463D87", "tag-ink": "#FFFFFF", "icon": "#5A4BC2",
    "series-1": "#463D87", "series-2": "#3F6BAD", "series-3": "#23767B", "series-4": "#907AFF"
  },
  "type": {
    "sans": "Manrope, Inter, 'Helvetica Neue', Helvetica, Arial, sans-serif",
    "title-weight": 700, "title-tracking": -0.02,
    "label-weight": 600, "section-weight": 700, "section-tracking": 0.06,
    "small-family": "sans"
  },
  "shape": { "radius": 20, "radius-small": 12, "card-border": "none", "connector": "orthogonal", "corner": 12, "arrow": "open" },
  "elevation": {
    "style": "soft",
    "dark": { "dx": 0, "dy": 4, "blur": 16, "color": "#282878", "opacity": 0.12 }
  },
  "icon": { "style": "line", "tile": true }
}
```

## The language

- **Page and cards.** A pale periwinkle page; white cards with 20 px corners
  lifted by one soft indigo-tinted shadow; groups are pale-lavender panels.
- **Lavender family.** Deep indigo `#463D87` carries the highlight card (white
  text, 10:1), step badges, tags and the lede; icons are violet `#5A4BC2`;
  bright lavender `#907AFF` is decorative only (the `signal` and the last
  chart series) because it is 3.4:1 as text.
- **Soft chips.** Pills are sky blue with black text; sticky notes are cream.
- **Type.** Manrope throughout — no mono — with bold titles at −2 % tracking
  and caps section labels.
