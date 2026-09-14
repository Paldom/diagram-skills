# Catalog of third-party diagram skills and tools

Reference, not an install list. Every row was checked on GitHub, npm, or
skills.sh on **2026-09-14**; stars and dates move, licenses and network behaviour
rarely do. Install nothing without showing the user the command and the caveat —
a 2026 Snyk audit found roughly a third of scanned agent skills carried at least
one security flaw, and a skill runs with the user's permissions.

**Rule of thumb:** prefer tools that run locally with pinned dependencies and no
network; avoid unpinned `npx -y`, runtime `npm install`, and anything that sends
the diagram to a hosted service.

## Mermaid: syntax help

| Skill | Install | What it adds | Caveats |
| --- | --- | --- | --- |
| `WH-2099/mermaid-skill` (MIT, 277★, commit 2026-08-11) | `npx skills add WH-2099/mermaid-skill` | 80-line prompt skill + per-type syntax references for 23 diagram types | prompt-only; no validation |
| `K-Dense-AI/scientific-agent-skills` → `markdown-mermaid-writing` (MIT, 44.9k★ monorepo, v2.69.0 2026-09-11) | `npx skills add K-Dense-AI/scientific-agent-skills --skill markdown-mermaid-writing` | Mermaid-in-Markdown writing guidance, 24 diagram types, accessibility notes | prompt-only; large monorepo (165 skills) |

## Mermaid: validation and rendering

| Tool | Command | What it adds | Caveats |
| --- | --- | --- | --- |
| `@probelabs/maid` (ISC, npm 0.0.29, 2026-03-18) | `npx -y @probelabs/maid@0.0.29 diagram.mmd` (or `--fix`, `--format json`) | browser-free Mermaid linter/auto-fixer; exit 0 = clean, 1 = errors; MCP server `npx -y @probelabs/maid@0.0.29 mcp` | validates flowchart, sequence, pie, class, state; **ER, gantt, journey pass through**; `render` is experimental |
| `@mermaid-js/mermaid-cli` (npm 11.17.0, 2026-09-02) | `mmdc -i in.mmd -o out.svg` | the reference renderer | Puppeteer + Chromium download; pin the version |
| `imxv/Pretty-mermaid-skills` → `pretty-mermaid` (MIT, 1.2k★, 3.9k skills.sh installs) | `npx skills add imxv/Pretty-mermaid-skills` | Mermaid → SVG/PNG/ASCII with 15 themes, no browser (beautiful-mermaid + resvg) | needs `npm install` inside the skill dir; skills.sh shows Socket and Snyk *Warn* badges |
| `veelenga/claude-mermaid` (MIT, 206★, npm 1.6.5) | `npm i -g claude-mermaid && claude mcp add --scope user mermaid claude-mermaid` | live-reload preview MCP (`mermaid_preview`, `mermaid_save`) | mermaid-cli/Chromium underneath; the bundled skill is useless without the MCP |
| `intellectronica/agent-skills` → `beautiful-mermaid` (CC0) | `npx skills add intellectronica/agent-skills --skill beautiful-mermaid` | Mermaid → SVG via the beautiful-mermaid library | **runs an unpinned `npm install` at runtime** — avoid in CI |
| `mgranberry/mermaid-diagram-skill` | — | writing guide + render | no license, unpinned `npx --yes mmdc`, hard-coded path — **avoid** |

## Editorial SVG / HTML illustrations

| Skill | Install | What it adds | Caveats |
| --- | --- | --- | --- |
| `cathrynlavery/diagram-design` (MIT, 39.6k★, commit 2026-09-10, 5.7k installs) | `npx skills add cathrynlavery/diagram-design` | 38 editorial diagram types as standalone HTML + inline SVG; brand extraction; optional `verify-geometry.py` | **no layout engine — the model hand-places every coordinate**; 587-line body; output loads Geist from fonts.googleapis.com |
| `tt-a1i/archify` (MIT, 61.6k★, v2.16.0 2026-08-30) | `npx skills add tt-a1i/archify` | schema-validated JSON → standalone HTML+SVG architecture diagrams; accepts Mermaid flowchart/sequence/state input; zero npm deps | **phones home**: `scripts/check-update.mjs` fetches `tt-a1i.github.io/archify/skill-updates/...` (read-only); raster export spawns local Chrome |

## Editable tools and architecture-as-code

| Skill / tool | Install | What it adds | Caveats |
| --- | --- | --- | --- |
| `Agents365-ai/drawio-skill` (MIT, 9.3k★, v3.4.0 2026-09-14) | `npx skills add Agents365-ai/drawio-skill` | editable `.drawio` from text, IR JSON, Terraform, K8s, SQL, OpenAPI; `python3 scripts/diagramctl.py`; optional MCP | PNG/SVG export needs a local draw.io CLI; icon fetchers use the network only when opted in (`references/security.md`) |
| `likec4/likec4` → `likec4-dsl` (MIT, 5.7k★, v1.59.3) | `npx skills add likec4/likec4 --skill likec4-dsl` | architecture-as-code `.c4` DSL, interactive C4 views; MCP `@likec4/mcp` | a modelling commitment, not a one-off drawing |
| Structurizr MCP (docs.structurizr.com/ai/mcp) | Docker `structurizr/mcp` or Java 21 | C4 DSL validate/parse/inspect, Mermaid and PlantUML export | the hosted `mcp.structurizr.com` instance is a third party — self-host for private models |
| `@excalidraw/mermaid-to-excalidraw` (MIT, npm 2.1.1) | library only | Mermaid → Excalidraw elements in the browser | not a skill or CLI |

## Adjacent

- **Icons**: `Paldom/icon-designer-skills` (MIT, v0.4.0) — `icon-brief`, `icon-draw`, `icon-critique`, `icon-export`; `npx skills add Paldom/icon-designer-skills`.
- **Anthropic's own catalog** (`anthropics/skills`, 176k★): no diagram, Mermaid, or SVG skill as of 2026-09-10 — `pptx`, `docx`, `canvas-design`, `frontend-design` and others only.
- **Slide decks** are out of scope for this repo; search skills.sh for Marp or Slidev skills and vet them with the rule of thumb above.
