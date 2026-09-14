# Icon brief: diagram-skills
Assumptions: autonomous run — no clarifying questions asked. Audience and category taken from the README; the accent color is the skills' house blue (#2563EB) in case one accent is used.
Product: agent skills that turn a title or brief into a minimalist, reviewed technical diagram (Mermaid or slide-like SVG) — a router picks the format, a lint and a render-then-checklist review keep it neat  ·  Audience: developers and technical writers who publish READMEs, articles and social posts  ·  Category neighbors: Mermaid (mermaid), Lucidchart (interlocking shapes), draw.io (boxes joined by arrows), Excalidraw (pencil / hand-drawn box), Miro (letter M), Figma (letter F), Graphviz (node graph)

## Concepts

### 1. Keystone  (axis: vertical)
Depicts: a keystone
Metaphor: the one wedge that makes the arch stand — the router picks the single element that carries the takeaway and drops the rest.
Gestalt device: closure — the wedge's top and bottom edges are arcs, so the viewer completes the arch that is not drawn.
16px risk: the arcs flatten and it reads as a trapezoid; keep the arc sag ≥ 6% of the width.
Distinct from: no diagram tool uses a stone or a wedge; boxes-and-arrows, node graphs and pencils all differ in silhouette.
Not a UI glyph: checked against upload/eject (triangle on a bar) — a wedge with curved edges and no bar; not a bucket (narrow side up).

### 2. Sieve  (axis: vertical)
Depicts: a sieve
Metaphor: what goes in is a brief with everything in it; what stays is the few elements that explain the idea — the slop falls through.
Gestalt device: figure-ground — the holes are background-colored knockouts cut out of one filled bowl.
16px risk: the holes fill in; the bowl still reads as a bowl, so the mark degrades to "a dish", not to noise. Use ≤ 7 holes, each ≥ 56 units.
Distinct from: nothing in the category is a vessel; the filter glyph is a funnel (open triangle), this is a bowl with a rim.
Not a UI glyph: checked against filter (funnel) and settings gear (toothed ring) — neither shares the bowl silhouette.

### 3. Protractor  (axis: vertical)
Depicts: a protractor
Metaphor: the review — every angle measured before it ships; neat means checked, not just tidy.
Gestalt device: closure — a half-disc with a knockout half-ring and short tick knockouts; the viewer completes the scale.
16px risk: ticks die first and the inner ring becomes a thin gap; keep the ring ≥ 40 units so it survives as a "D" shape.
Distinct from: rulers and compasses are the drafting clichés, both linework; a filled half-disc is a different silhouette.
Not a UI glyph: checked against the gauge/speedometer glyph (half-ring with a needle) — no needle, solid mass, flat base; and against "half circle" progress indicators (thin ring, no base).

### 4. Stamp  (axis: vertical)
Depicts: a rubber stamp
Metaphor: the verdict — PASS goes on the visual only after lint, render and checklist; a stamp is the mark of a decision.
Gestalt device: proximity — knob, neck and base are three stacked masses that read as one object.
16px risk: the neck vanishes and knob merges into base; it reads as a mushroom. Keep the neck ≥ 70 units wide.
Distinct from: no diagram or design tool uses a stamp; the closest is the "verified" badge (scalloped disc with a check), a different silhouette.
Not a UI glyph: checked against download/upload (arrow on a tray) and the hamburger — a stamp has a knob, not an arrow or bars.

## Palette
Background #2A2A2E · Glyph #E8E8EA · Accent none (optional #2563EB on the keystone only)

## Recommendation
Keystone first: it names the product's actual job — choose the one element that holds the idea — with a solid silhouette and no category collision. Sieve second (strongest mass, clearest metaphor for "no slop"); Protractor and Stamp are review metaphors and read as tools, not as this product. Next: `icon-draw` for 3 candidates (keystone, sieve, protractor).
