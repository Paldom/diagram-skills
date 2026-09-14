# Changelog

All notable changes to this repository's skills are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning: [SemVer](https://semver.org) on the plugin manifest
(breaking skill-interface change → major, new skill → minor, fix → patch).

## [Unreleased]

## [0.1.0] - 2026-09-15

### Added
- `illustrate` — user-invoked entry point (`/illustrate <idea>`): brief → route →
  draw in a forked subagent → one review; documents the headless `acpx` path for
  other harnesses.
- `diagram-brief` — title/notes/take → one-page brief with the takeaway, ≤ 9
  entities, and the format decision; `references/format-router.md` (destination
  → medium, precedence rules, handoffs to Claude Design, FigJam, draw.io) and
  `references/skill-catalog.md` (15 third-party skills/tools verified 2026-09-14
  with licenses, network behaviour, and install commands).
- `mermaid-draw` — Mermaid/DOT with a pinned `config:` frontmatter, quoted
  labels, node caps, a lint → maid → mmdc loop capped at three repairs, and one
  review; `references/mermaid-gotchas.md`.
- `illustration-draw` — slide-like SVG from a JSON spec: `scripts/build_svg.py`
  compiles five archetypes (flow, stack, hub, grid, compare) onto a fixed grid
  with capacity checks; `scripts/spawn_drawer.py` asks a Claude or Codex session
  through `acpx --deny-all` for the spec only; `references/style-rules.md`.
- `diagram-review` — `scripts/mermaid_lint.py` (parser-crash idioms, caps,
  config pin, accessibility, one accent), `scripts/svg_lint.py` (safe static
  subset, WCAG 2.2 contrast, text overlap/overflow, palette, font floors),
  `scripts/render.py` (renderer autodetect incl. network-blocked headless
  Chrome; pinned mermaid-cli via `--allow-download`), and
  `references/checklist.md` (analyze → fidelity → mandatory/advisory checklist →
  PASS / FIX / REDRAW / INCOMPLETE; a security gate before rendering; border
  contrast per WCAG 2.2 SC 1.4.11).
- Repository scaffolded from the skills template.
