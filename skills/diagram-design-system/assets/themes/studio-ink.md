# Design system: Studio ink

Studio with an ink-inverted highlight instead of the pale-yellow one: the
takeaway card turns navy-black with white text. Everything else is Studio.
This file is also the smallest example of a custom theme — it only lists what
changes.

```design-tokens
{
  "name": "studio-ink",
  "extends": "studio",
  "color": { "accent": "#232F3E", "accent-ink": "#FFFFFF", "accent-muted": "#C1C5C9" }
}
```

## Differences from Studio

- The highlight is an ink card (white text, 13.6:1), the hallmark audit's
  recommendation; the yellow stays for sticky notes only.
