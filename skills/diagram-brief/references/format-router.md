# Format router: which medium for which idea

The destination decides the medium; the idea's shape decides the type. Facts
verified against primary sources on 2026-09-14.

## Precedence (read first)

1. **Operation words outrank format words.** "Review / critique / check / rate /
   fix" → `diagram-review`, whatever the diagram is.
2. **An explicit requirement wins over the destination.** "must be mermaid",
   "a flowchart", "sequence diagram", "DOT" → `mermaid-draw`; "an SVG", "social
   card", "hero image", "slide visual" → `illustration-draw`. Note the tradeoff
   if the destination cannot show it.
3. **Otherwise route by destination**, table below. An *inferred* preference
   (a prettier engine, a richer tool) never beats the destination.
4. **Relation first, shape second.** Name the one relation the takeaway
   states, then take the row below. Specificity wins: branches beat `flow`,
   two or more actors beat `flow`, a return to the start is a `cycle`, numbers
   that are the point are `metrics`. `flow` needs an explicit order in the
   takeaway and `compare` explicit alternatives. The brief names **two
   candidate types and why the runner-up lost**, and across one article no type
   appears more than twice unless the brief says why.
5. **Native when it fits, delegate when it doesn't — in the same theme.** The
   compilers draw the native column; `mermaid-draw` the Mermaid column; the
   rest goes to **diagram-design** (`npx skills add cathrynlavery/diagram-design`,
   41 types) after exporting the theme with `to_diagram_design.py --design-system
   <theme> --write --marker .` (in `diagram-design-system`; ask before it writes
   `~/.diagram-design/profiles/` and the project marker). Editable output goes to
   drawio-skill, an explorable architecture to archify. Never bend a missing
   type into a near archetype.
6. **Complexity gate:** more than ~12 entities never fits one view. Split by
   level (context → container → component, the C4 idea) or by phase, and say so
   in the brief. No layout engine keeps 25 nodes readable.

## Destination → medium

| Destination | Medium | Skill / tool | Why |
| --- | --- | --- | --- |
| README, docs page, PR or issue body, wiki, Notion, Obsidian | Mermaid diagram-as-code | `mermaid-draw` | Renders natively in GitHub, GitLab, Notion, Obsidian, VS Code; diffable text in the same PR; validated before it ships |
| Dependency tree, package graph, anything with many nodes and one direction | Graphviz DOT | `mermaid-draw` (DOT section) | Graphviz owns the layout entirely; needs `dot` installed, else fall back to a ≤ 12-node Mermaid flowchart |
| LinkedIn / X post, article hero, newsletter, talk slide, one-pager | Slide-like SVG → PNG | `illustration-draw` | Mermaid's default look reads as "Mermaid slop" outside Markdown; a compiled SVG on a fixed grid with one accent reads as designed |
| Architecture for a post, slide or docs image: boundaries, cards with icons, an ordered flow | Architecture SVG → PNG | `illustration-draw` (`arch_svg.py`) | Graphviz lays it out, the design system paints it; numbered badges + legend tell the order |
| Exported Mermaid image (docs site, slide) rather than a Markdown embed | beautiful-mermaid SVG/PNG | `mermaid-draw` (`render_themed.py`) | Same source, design-system look, no "Mermaid slop" |
| Any of the above as a GIF or video (explainer, feed post) | Animated SVG + GIF/MP4 | draw first, then `diagram-animate` | Reveal in reading order; `pipeline` pans across a wide diagram |
| Editable diagram a team will keep changing in a tool | Handoff | drawio-skill, FigJam, or Claude Design (see below) | Ownership of layout moves to the tool; regeneration would destroy manual edits |
| Interactive architecture a reader explores | Handoff | archify (light) | Zoom, trace, search in one HTML file; heavy for a README |
| Editorial figure where the typography is the look | Handoff | diagram-design | Most editorial result; fact-check every label |
| A diagram type this repo does not draw (see precedence 5) | Delegate | diagram-design, with the theme exported as its profile | 41 types; the profile keeps the palette, fonts and one accent; fact-check every label |
| Characters, scenes, brand illustration, photos, a full deck | Handoff | Claude Design `/design`, or a deck skill | Outside a minimalist technical diagram; do not fake it with boxes |

## Relation → diagram type

| The takeaway's relation | Native archetype (`illustration-draw`) | Mermaid (`mermaid-draw`) | Delegate |
| --- | --- | --- | --- |
| order: steps in sequence | `flow` | `flowchart LR` | — |
| loop: the last step feeds the first | `cycle` | — | — |
| change: old → new, migration | `before_after` | — | — |
| branch: if / otherwise, choose-when | `decision` | `flowchart TD` with a diamond | — |
| ownership: hand-offs between actors | `swimlane` (≤ 4 lanes, ≤ 8 steps) | — | diagram-design swimlane when bigger |
| hierarchy: breaks down into | `tree` (≤ 15 nodes) | — | diagram-design org chart / tree when bigger |
| containment: runs inside, wraps | `layers` | — | diagram-design Venn for overlaps |
| tiers / levels | `stack` | `flowchart TB` + subgraphs | diagram-design pyramid |
| one center, satellites | `hub` (`layout: bus` for a bus or queue) | `flowchart` | — |
| alternatives side by side | `compare` (tiers with badges) | — | — |
| groups × items | `matrix` (ruled table) | — | — |
| position on two axes | `grid` (exactly 2×2) or `quadrant` (3–10 points) | — | — |
| magnitude: the numbers are the point | `metrics` (KPI tiles, ranked bars) | — | diagram-design bar / line / waterfall / heatmap for real data |
| time: dated milestones | `timeline` | `timeline` | diagram-design Gantt / roadmap for durations and lanes |
| reduction: counts shrink stage by stage | — | — | diagram-design funnel |
| flow volume between parts | — | — | diagram-design Sankey |
| messages between parties over time | — | `sequenceDiagram` (≤ 7 participants) | — |
| named states and transitions | — | `stateDiagram-v2` | — |
| tables, keys, cardinality | — | `erDiagram` | diagram-design DB schema |
| data through stages, with payloads and latencies | pipeline explainer (`pipeline_svg.py`) | — | — |
| systems, boundaries, ordered calls | architecture (`arch_svg.py`) | `flowchart LR` + subgraphs | archify (explorable), drawio (editable) |
| a dependency graph with many nodes | — | DOT (`digraph`) | — |
| causes, maps, boards: fishbone, Wardley, kanban, journey, radar | — | — | diagram-design |

## Handoff targets (verified 2026-09-14)

- **Claude Design** (Anthropic Labs, launched 2026-04-17): designs, prototypes,
  slides, one-pagers. In Claude Code: the built-in `/design <brief>` skill
  (v2.1.234+) drafts artboards and publishes a canvas artifact; the MCP server is
  `claude mcp add --scope user --transport http claude-design
  https://api.anthropic.com/v1/design/mcp`, with `/design-login` and
  `/design-sync`. Sources: anthropic.com/news/claude-design-anthropic-labs,
  code.claude.com/docs/en/artifacts. Hand over the brief verbatim; the pick stays
  with the human.
- **FigJam via the Figma connector** (`figma-generate-diagram` skill): takes
  Mermaid, supports flowchart, sequence, state, gantt, ER only; no emoji/HTML in
  labels; in Claude Code it returns a FigJam *link*, edits happen in FigJam
  (help.figma.com/hc/en-us/articles/37883260397975).
- **Reference styles** — diagram-design (editorial), archify (light,
  interactive), drawio-skill (editable): install commands, how to feed each
  one `design-system.md`, and the measured caveats are in the catalog's
  "Reference styles" section. Hand over the brief and the design system
  verbatim; review what comes back.

## Evidence behind the routing

- Layout is the model's weak spot, not syntax: on PlanarBench the number of edges
  predicts failure far better than the number of vertices (r = −0.85 vs −0.47,
  arXiv 2606.02010). Delegate placement to Dagre/ELK (Mermaid), Graphviz (DOT),
  or the fixed grid (illustration compiler); never ask for coordinates.
- "Mermaid slop": syntactically valid Mermaid whose auto-routed edges cross,
  hierarchy is flat, and labels are generic — the reason presentation surfaces
  route to the illustration skill (explainx.ai/blog/what-is-mermaid-slop-ai-diagram-explained-2026).
- Mermaid 12.0.0 (npm, 2026-09-10) changed the defaults to the ELK layout and the
  `neo` look; unpinned diagrams re-render differently across hosts — hence the
  config pin in `mermaid-draw`.
- D2 lays out more cleanly but GitHub does not render it ("D2 is better, but it's
  not supported by GitHub. Go where your users are", news.ycombinator.com/item?id=45713312).
