#!/usr/bin/env python3
"""spawn_drawer.py — ask a frontier model for the illustration *spec*, not the SVG.

Builds a self-contained prompt (brief + house rules + the JSON schema from
build_svg.py), runs it through `acpx` — the local Agent Client Protocol CLI
that drives an installed Claude Code or Codex session — with every permission
denied, and extracts the JSON spec from the reply. The drawer never writes
files and never touches the repo; this script (the parent) validates the spec
with build_svg.py and writes the SVG. Only the prompt text leaves the machine,
to the provider of the chosen agent.

If `acpx` is not installed the script prints the prompt path and exits 3 so
the calling agent can run the same prompt itself (in-harness subagent).

Usage:
    python3 spawn_drawer.py --brief BRIEF.md --out-dir DIR --name SLUG
        [--agent claude|codex] [--model ID] [--timeout 600] [--dry-run]

The agent session runs with `--cwd` set to an empty temporary directory, so no
project files or repo instructions are loaded into it.

Output: `SPEC <path>` and `SVG <path>` lines, then `OK:`; exit 1 on a bad spec.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = HERE / "build_svg.py"
RULES = HERE.parent / "references" / "style-rules.md"

PROMPT = """You are drawing ONE minimalist technical illustration for the brief below.
You do not write SVG. You return a JSON spec that a deterministic script compiles
to SVG on a fixed grid. Your whole job is the content: the one takeaway as the
title, the fewest specific labels that explain it, one accent on the element
that carries the point, the archetype that matches the idea's shape.

Rules (non-negotiable):
- One idea per visual. If the brief has two, pick the one in the takeaway.
- Labels are specific ("one endpoint, typed schema"), never generic ("data", "flow", "connects").
- Fewest elements that still explain it. Capacity limits are in the schema; stay well under them.
- Exactly one element carries the accent. No emoji, no ASCII art, no markdown in strings.
- No numbers you did not get from the brief. Missing information stays missing.

Archetype guide:
- flow: steps or stages in order (2-6)     - stack: layers, tiers, levels (2-5)
- hub: one center with satellites (3-6)     - grid: 2x2 tradeoff or quadrant (exactly 4)
- compare: 2-3 options side by side, 1-5 short rows each

Spec schema (JSON):
{schema}

{rules}

Brief:
---
{brief}
---

Reply with ONLY a ```json fenced block containing the spec. No prose before or after.
"""


def extract_json(text: str) -> dict | None:
    m = re.search(r"```json\s*(\{.*?\})\s*```", text, re.S)
    candidates = [m.group(1)] if m else []
    start = text.find("{")
    if start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    candidates.append(text[start : i + 1])
                    break
    for c in candidates:
        try:
            obj = json.loads(c)
            if isinstance(obj, dict):
                return obj
        except ValueError:
            continue
    return None


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--brief", type=Path, required=True, help="brief file (markdown or text)")
    ap.add_argument("--out-dir", type=Path, default=Path("diagram-design"))
    ap.add_argument("--agent", choices=["claude", "codex"], default="claude")
    ap.add_argument("--model", help="agent model id (acpx --model)")
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--name", default="illustration", help="output file stem")
    ap.add_argument("--dry-run", action="store_true", help="write the prompt, do not call acpx")
    args = ap.parse_args()

    if not args.brief.is_file():
        print(f"ERROR: no such brief: {args.brief}", file=sys.stderr)
        return 1
    schema = subprocess.run(
        [sys.executable, str(BUILD), "--schema"], capture_output=True, text=True, check=False
    )
    if schema.returncode != 0:
        print("ERROR: build_svg.py --schema failed", file=sys.stderr)
        return 1
    rules = RULES.read_text(encoding="utf-8") if RULES.is_file() else ""
    prompt = PROMPT.format(
        schema=schema.stdout.strip(), rules=rules, brief=args.brief.read_text(encoding="utf-8")
    )
    args.out_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = args.out_dir / f"{args.name}.prompt.md"
    prompt_path.write_text(prompt, encoding="utf-8")
    print(f"PROMPT {prompt_path}")
    if args.dry_run:
        return 0

    acpx = shutil.which("acpx")
    if not acpx:
        print(
            "NOTE: acpx is not installed (npm i -g acpx); run the prompt above in a subagent yourself, "
            "save its JSON as <name>.spec.json, then: python3 build_svg.py <name>.spec.json --out <name>.svg",
            file=sys.stderr,
        )
        return 3
    with tempfile.TemporaryDirectory(prefix="drawer-") as empty:
        cmd = [
            acpx,
            "--deny-all",
            "--cwd",
            empty,  # an empty directory: no project context reaches the drawer
            "--timeout",
            str(args.timeout),
            "--format",
            "text",
        ]
        if args.model:
            cmd += ["--model", args.model]
        cmd += [args.agent, "exec", "-f", str(prompt_path.resolve())]
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=args.timeout + 60, check=False
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            print(f"ERROR: acpx failed: {exc}", file=sys.stderr)
            return 1
    reply = proc.stdout
    (args.out_dir / f"{args.name}.reply.txt").write_text(
        reply + "\n--- stderr ---\n" + proc.stderr, encoding="utf-8"
    )
    spec = extract_json(reply)
    if spec is None:
        print(
            f"ERROR: no JSON spec in the {args.agent} reply (saved next to the prompt); re-run or draw in-harness",
            file=sys.stderr,
        )
        return 1
    spec_path = args.out_dir / f"{args.name}.spec.json"
    spec_path.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"SPEC {spec_path}")
    svg_path = args.out_dir / f"{args.name}.svg"
    built = subprocess.run(
        [sys.executable, str(BUILD), str(spec_path), "--out", str(svg_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if built.returncode != 0:
        sys.stderr.write(built.stderr)
        print(
            "FAIL: spec rejected by build_svg.py — feed the errors back to the drawer and retry (max 3)"
        )
        return 1
    print(f"SVG {svg_path}")
    print("OK: spec compiled; next run diagram-review on the SVG")
    return 0


if __name__ == "__main__":
    sys.exit(main())
