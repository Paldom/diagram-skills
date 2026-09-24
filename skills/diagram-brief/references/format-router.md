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
4. **Relations decide the ceiling of the illustration archetypes:** they express
   order (flow), layering (stack), a center with satellites (hub), position on
   two axes (grid), membership (compare) and time (timeline). Labeled, directed
   edges between systems go to the **architecture** compiler in
   `illustration-draw` when the destination is visual (post, slide, docs
   image), to Mermaid when it is Markdown.
5. **A type this repo does not draw goes to diagram-design, in the same theme.**
   The compilers cover flow, stack, hub, grid, compare/tiers, matrix, timeline,
   architecture and the pipeline explainer; `mermaid-draw` covers flowchart,
   sequence, state, ER, class and DOT. Everything else in the table below
   (swimlane, org chart, tree, Venn, pyramid/funnel, treemap, heatmap, charts,
   Gantt, Sankey, fishbone, Wardley map, kanban, journey, radar, loop/flywheel,
   deployment, DB schema, story map) → **diagram-design**
   (`npx skills add cathrynlavery/diagram-design`). Export the active theme first:
   `to_diagram_design.py --design-system <theme> --write --marker .` (in
   `diagram-design-system`; it writes `~/.diagram-design/profiles/ds-<theme>.md`
   and the project's `.diagram-design` marker — ask before running it). Never
   bend a missing type into a near archetype.
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

## Idea shape → diagram type

| The idea is… | Mermaid | Illustration archetype |
| --- | --- | --- |
| steps or stages in order | `flowchart LR` | `flow` |
| parties exchanging messages over time | `sequenceDiagram` (≤ 7 participants) | `flow` of the phases, or Mermaid |
| named states and transitions | `stateDiagram-v2` | — (keep it Mermaid) |
| tables, keys, cardinality | `erDiagram` (note: maid passes it through unvalidated; render to check) | — |
| layers, tiers, levels | `flowchart TB` with subgraphs | `stack` |
| one thing everything depends on | `flowchart` | `hub` |
| a 2×2 tradeoff or quadrant | — | `grid` |
| 2–3 options side by side | — | `compare` |
| milestones in time | `timeline` or `gantt` | `timeline` |
| data moving through stages: an explainer of how a system answers, with payloads and latencies | — | pipeline explainer (`pipeline_svg.py`), animated with `--preset pipeline` |
| systems, boundaries, ordered calls between them | `flowchart LR` with subgraphs | architecture (`arch_svg.py`) |
| a tree or dependency graph | DOT (`digraph`, `rankdir=LR`) | — |
| lanes of responsibility, an org chart, Venn, funnel, treemap, heatmap, a chart (bar, line, scatter, waterfall), Gantt, Sankey, fishbone, Wardley map, kanban, journey, radar, flywheel, deployment, DB schema | — | — → **diagram-design** in the exported theme |

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
