<p align="center">
  <img src="assets/icon.svg" alt="diagram-skills icon" width="128"/>
</p>

# Diagram Skills

Agent skills that turn a title, a few notes, or a hot take into a minimalist technical diagram — the right format for the destination, no AI slop, checked before it reaches you.

[![CI](https://github.com/Paldom/diagram-skills/actions/workflows/ci.yml/badge.svg)](https://github.com/Paldom/diagram-skills/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![skills.sh](https://skills.sh/b/Paldom/diagram-skills)](https://skills.sh/Paldom/diagram-skills)

## Demo

<p align="center">
  <img src="assets/demo.gif" alt="Terminal recording: /diagram-brief run headless writes a brief that routes a LinkedIn ask to a compiled SVG card" width="900"/>
</p>

The recording above is a real headless run of the routing step (source: `assets/demo.tape`, regenerate with `vhs assets/demo.tape`): one ask in, a one-page brief out — the takeaway, the entities and relations, and the format decision with its reason.

What a real headless `/illustrate` run returned for the ask in the tape above (verdict PASS, second opinion from a different model included). The model wrote the title, the subtitle and six labels; the grid, sizes, and contrast came from the compiler:

<p align="center">
  <img src="assets/demo-card.png" alt="Compiled social card: Your gateway should only do three things" width="600"/>
</p>

## Quick start

```bash
npx skills add Paldom/diagram-skills
```

Then either give your agent the whole job:

```text
/illustrate LinkedIn visual: gateways should only do auth, rate limiting and routing
```

or ask for one step in plain English and the matching skill activates on its description:

```text
which diagram format fits explaining our event-driven order pipeline?
add a mermaid flowchart of the deploy pipeline to the README
make a social card for my article on cache invalidation
is docs/architecture.svg readable, or too busy?
```

What you need on the machine: Python 3 (the scripts are stdlib-only). Optional, used
when present: an SVG rasterizer (`rsvg-convert`, `resvg`, Chrome, or macOS
QuickLook) to look at renders, `mmdc` for Mermaid renders, and
[`acpx`](https://github.com/openclaw/acpx) with a logged-in Claude Code or Codex
to draw in a separate model session. Nothing is downloaded silently; nothing is
sent to hosted renderers.

### Other ways to install

```bash
npx skills add Paldom/diagram-skills -a codex -a pi   # target specific agents
gh skill install Paldom/diagram-skills                # GitHub CLI >= 2.90
```

```text
/plugin marketplace add Paldom/diagram-skills
/plugin install diagram-skills@diagram-skills
```

## Skills

| Skill | Ask it when | Invoke |
| --- | --- | --- |
| [illustrate](skills/illustrate/) | You have an idea and want the finished visual: brief → format → drawn in a subagent → reviewed | `/illustrate <idea>` |
| [diagram-brief](skills/diagram-brief/) | "which diagram format fits…", "should this be mermaid or an illustration?", "brief a visual for…" | `/diagram-brief` |
| [mermaid-draw](skills/mermaid-draw/) | "add a flowchart to the README", "sequence diagram of the login flow", "DOT graph of the dependencies" | `/mermaid-draw` |
| [illustration-draw](skills/illustration-draw/) | "social card for my article", "slide visual of the three layers", "LinkedIn image comparing REST and gRPC" | `/illustration-draw` |
| [diagram-review](skills/diagram-review/) | "is this diagram readable?", "critique docs/arch.svg", "does this look like AI slop?" | `/diagram-review` |

## How they compose

`/illustrate` runs the engines in order; each also works alone.

1. **[Required]** `diagram-brief` writes the takeaway, the few entities, and the
   route: Markdown destinations get Mermaid, feeds and slides get a compiled
   SVG, illustration-grade work is handed to Claude Design or FigJam.
2. **[Required]** `mermaid-draw` or `illustration-draw` produces the artifact.
   Mermaid gets a pinned config, quoted labels, a node cap, and a
   lint → parser → render loop. Illustrations are compiled from a small JSON
   spec onto a fixed grid, so the model never places a coordinate.
3. **[Required]** `diagram-review` lints, renders at delivery and feed size, and
   runs an analyze-then-judge checklist against the brief. It returns PASS,
   FIX with the exact edits, or REDRAW with the split — never a score.
4. **[Optional]** A second model reviews through `acpx`, ranking candidates
   rather than scoring them.

A paste-ready `/goal` that runs the pipeline over a batch of ideas is in
[docs/setup-prompt.md](docs/setup-prompt.md).

## Repository structure

```
skills/                  # distributed skills, one folder per skill (SKILL.md + evals/ + scripts/ + references/)
docs/                    # authoring guide, eval methodology, README standard, deployment, setup prompt
scripts/                 # the gate: validator, eval scorer, self-checks
skills.sh.json           # skills.sh repo-page customization (groupings)
.claude/                 # agentic dev setup: hooks + bundled add-skill / publish-repo skills
.claude-plugin/          # plugin + marketplace manifests (makes this repo installable)
.local/                  # gitignored working area: sources, research, PROMPT.md
```

## Working on this repo with an agent

This repo is agent-native: canonical agent instructions live in
[AGENTS.md](AGENTS.md) (CLAUDE.md imports it), hooks validate and lint every write,
`make check` runs the full gate, and CI enforces the same on every PR. The bundled
`add-skill` skill walks the eval-first authoring workflow in
[docs/skill-authoring.md](docs/skill-authoring.md); the README shape is
[docs/readme-standard.md](docs/readme-standard.md). `make hooks` installs the
commit-time layer. Maintainers drive sessions with their own gitignored
`.local/PROMPT.md`.

## Contributing

Contributions welcome — see [CONTRIBUTING.md](CONTRIBUTING.md) for the skill-proposal
process, the authoring workflow, and the PR checklist. Please note the
[Code of Conduct](CODE_OF_CONDUCT.md).

## Support

Questions, ideas, or something not working? Start with [SUPPORT.md](SUPPORT.md) —
bugs and skill proposals have [issue templates](../../issues/new/choose), and
security concerns go through [SECURITY.md](SECURITY.md) (never a public issue).

## License

[MIT](LICENSE) © 2026 Paldom

<!-- attribution:start -->
---

[![Built with skillskit](https://img.shields.io/badge/built%20with-skillskit-F5A623)](https://github.com/Paldom/skillskit)

Scaffolded with [skillskit](https://github.com/Paldom/skillskit) — eval-first Agent
Skills tooling. This line is yours to delete; nothing checks for it.
<!-- attribution:end -->
