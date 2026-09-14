# Setup prompt: run the pipeline on a batch of ideas

Paste this as a `/goal` in Claude Code (or as the prompt of a headless `acpx`
session) after installing the skills. Fill the bracketed parts. Under 4000
characters; nothing in it commits or pushes.

```text
/goal Produce one reviewed visual for each idea below, using the diagram-skills pipeline, until every idea has a PASS verdict or a documented handoff. Never git commit or push; leave files in the working tree.

Install first if any skill is missing: `npx skills add Paldom/diagram-skills`.

Ideas (one per line; destination in brackets):
- [LinkedIn] <takeaway or title>
- [README] <what to diagram>
- [slide] <takeaway or title>

For each idea:
1. Run `diagram-brief` on the line. If only a title is given, declare assumptions at the top of the brief instead of asking. Save `diagram-design/<slug>/brief.md`.
2. Draw with the skill the brief names: `mermaid-draw` for README/docs/PR destinations, `illustration-draw` for LinkedIn/X/article/slide destinations. The draw skill owns its lint/repair loop (max 3 rounds) and runs `diagram-review` exactly once. Do not review twice.
3. If the brief routes to a handoff (Claude Design `/design`, FigJam, draw.io), write the brief verbatim into `diagram-design/<slug>/handoff.md` with the tool named, and move on.
4. Record in `diagram-design/SUMMARY.md`: slug, destination, format, artifact paths (source, SVG, PNG), verdict, residual findings, assumptions.

Rules:
- One takeaway per visual; split ideas that need two.
- Mermaid: pinned config frontmatter, quoted labels, ≤ 12 nodes, accTitle/accDescr.
- SVG: from the JSON spec only; fix by editing the spec and recompiling.
- Never send diagrams to hosted renderers (kroki.io, live editors).
- Use the render at half width to judge legibility before calling anything done.

Definition of Done: every idea has a row in SUMMARY.md with PASS or a handoff; every SVG passes `svg_lint.py` with 0 errors; every Mermaid block passes `mermaid_lint.py` with 0 errors; zero commits.
```

Verified commands in this prompt: `npx skills add Paldom/diagram-skills`
installs all five skills (skills CLI 1.5.19); the skill names match the folders
under `skills/`; `svg_lint.py` and `mermaid_lint.py` are the scripts
`diagram-review` runs (see its SKILL.md for the invocation).
