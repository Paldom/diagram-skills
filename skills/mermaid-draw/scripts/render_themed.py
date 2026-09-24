#!/usr/bin/env python3
"""render_themed.py — render Mermaid or DOT in the active design system.

    .mmd  -> beautiful-mermaid SVG (+ PNG via the system Chrome with --png)
    .dot  -> Graphviz with the design system's -G/-N/-E defaults (SVG or PNG)
    --config  prints the Mermaid `config:` frontmatter for README embeds, so
              GitHub's own Mermaid matches the same palette and font

The design system resolves as everywhere else: --design-system PATH,
$DIAGRAM_DESIGN_SYSTEM, ./design-system.md, then the built-in studio look.

Usage:
    python3 render_themed.py diagram.mmd [--out diagram.svg] [--png] [--allow-install]
    python3 render_themed.py graph.dot [--out graph.svg|graph.png]
    python3 render_themed.py --config
    python3 render_themed.py --self-test

beautiful-mermaid and puppeteer-core are pinned in assets/package-lock.json and
installed into ~/.cache/diagram-skills/ only with --allow-install
(`npm ci --ignore-scripts`). Exit 1 on any failure.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import design_tokens as dt  # noqa: E402

CHROME = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
)
EDGE_LABEL = re.compile(r"(->|--)[^\n;]*\blabel\s*=", re.I)


def find_chrome() -> str | None:
    for c in CHROME:
        hit = c if c.startswith("/") and Path(c).is_file() else shutil.which(c)
        if hit:
            return hit
    return None


def node_env(allow_install: bool) -> Path:
    lock = HERE.parent / "assets" / "package-lock.json"
    digest = hashlib.sha256(lock.read_bytes()).hexdigest()[:12]
    base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    cache = base / "diagram-skills" / f"mermaid-draw-{digest}"
    if (cache / "node_modules" / "beautiful-mermaid").is_dir():
        return cache
    if not allow_install:
        raise RuntimeError(
            "beautiful-mermaid is not installed yet; re-run with --allow-install to run "
            f"`npm ci --ignore-scripts` (pinned lockfile) into {cache}"
        )
    if not shutil.which("npm"):
        raise RuntimeError("npm not found — install Node.js >= 22.12")
    cache.mkdir(parents=True, exist_ok=True)
    for f in ("package.json", "package-lock.json"):
        shutil.copy(HERE.parent / "assets" / f, cache / f)
    r = subprocess.run(
        ["npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund"],
        cwd=cache,
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(f"npm ci failed: {r.stderr.strip()[-400:]}")
    return cache


def render_mermaid(src: Path, out: Path, t: dict, png: bool, allow_install: bool) -> list[Path]:
    env = node_env(allow_install)
    script = env / "render_mermaid.mjs"
    shutil.copy(HERE / "render_mermaid.mjs", script)
    opts = dt.beautiful_options(t) | {
        "padding": t["space"]["margin"],
        "nodeSpacing": t["space"]["gap"],
        "layerSpacing": round(t["space"]["gap"] * 1.6),
        "post": {
            "font": t["type"]["sans"],
            "radius": t["shape"]["radius"],
            "radiusSmall": t["shape"]["radius-small"],
            # a card the colour of its canvas needs an edge: a hairline, unless a shadow lifts it
            "border": t["shape"]["card-border"] == "hairline"
            or (
                t["elevation"]["style"] == "flat"
                and dt.contrast(t["color"]["surface"], t["color"]["canvas"]) < 1.1
            ),
            "stroke": t["shape"]["stroke"],
            "lift": {
                "neumorph": [t["elevation"]["light"], t["elevation"]["dark"]],
                "soft": [t["elevation"]["dark"]],  # one broad, faint drop shadow
            }.get(t["elevation"]["style"]),
            "liftKind": t["elevation"]["style"],
        },
    }
    cmd = ["node", str(script), str(src.resolve()), str(out.resolve()), json.dumps(opts)]
    made = [out]
    if png:
        chrome = find_chrome()
        if not chrome:
            raise RuntimeError(
                "Chrome/Chromium not found — needed for --png (the SVG uses CSS color-mix)"
            )
        pngp = out.with_suffix(".png")
        cmd += ["--png", str(pngp.resolve()), "--chrome", chrome]
        made.append(pngp)
    r = subprocess.run(cmd, cwd=env, capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip()[-400:])
    return made


def rasterize(svg: Path, png: Path, allow_install: bool) -> None:
    """PNG of an existing SVG in Chrome (beautiful-mermaid output needs CSS color-mix)."""
    chrome = find_chrome()
    if not chrome:
        raise RuntimeError(
            "Chrome/Chromium not found — needed to rasterize (the SVG uses CSS color-mix)"
        )
    env = node_env(allow_install)
    script = env / "render_mermaid.mjs"
    shutil.copy(HERE / "render_mermaid.mjs", script)
    cmd = [
        "node",
        str(script),
        str(svg.resolve()),
        str(svg.resolve()),
        "{}",
        "--png",
        str(png.resolve()),
        "--chrome",
        chrome,
    ]
    r = subprocess.run(cmd, cwd=env, capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip()[-400:])


def render_dot(src: Path, out: Path, t: dict) -> list[Path]:
    if not shutil.which("dot"):
        raise RuntimeError(
            "Graphviz `dot` not found — brew install graphviz / apt-get install graphviz"
        )
    args = dt.dot_args(t)
    # ortho routing drops edge labels; fall back to curved splines when edges carry one
    if "-Gsplines=ortho" in args and EDGE_LABEL.search(src.read_text(encoding="utf-8")):
        args[args.index("-Gsplines=ortho")] = "-Gsplines=true"
    fmt = "png" if out.suffix == ".png" else "svg"
    extra = ["-Gdpi=192"] if fmt == "png" else []
    r = subprocess.run(
        ["dot", f"-T{fmt}", *args, *extra, str(src), "-o", str(out)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip()[-400:])
    return [out]


def self_test() -> int:
    t = dt.load(None)
    cfg = dt.mermaid_config(t)
    assert cfg.startswith("---\nconfig:") and t["color"]["ink"] in cfg
    assert EDGE_LABEL.search('a -> b [label="calls"]') and not EDGE_LABEL.search('a [label="x"]')
    if shutil.which("dot"):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "g.dot"
            p.write_text('digraph { a -> b [label="calls"] }')
            (o,) = render_dot(p, p.with_suffix(".svg"), t)
            svg = o.read_text()
            assert t["color"]["canvas"].lower() in svg.lower() and "calls" in svg
    print("OK: self-test passed")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("src", nargs="?", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument(
        "--png", action="store_true", help="also rasterize a Mermaid render (needs Chrome)"
    )
    ap.add_argument("--design-system", default=None)
    ap.add_argument(
        "--config", action="store_true", help="print the Mermaid config frontmatter and exit"
    )
    ap.add_argument("--allow-install", action="store_true")
    ap.add_argument(
        "--canvas",
        choices=sorted(dt.CANVASES),
        help="fit onto a standard canvas: social 1200x627, square 1080x1080, wide 1920x1080",
    )
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    try:
        t = dt.load(a.design_system)
        if a.config:
            print(dt.mermaid_config(t))
            return 0
        if not a.src:
            ap.error("a .mmd or .dot file is required")
        out = a.out or a.src.with_suffix(".svg")
        out.parent.mkdir(parents=True, exist_ok=True)
        if a.src.suffix == ".dot" or a.src.suffix == ".gv":
            made = render_dot(a.src, out, t)
        else:
            made = render_mermaid(a.src, out, t, a.png, a.allow_install)
    except (RuntimeError, OSError, dt.TokenError, subprocess.TimeoutExpired) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    try:
        for p in made if a.canvas else []:
            if p.suffix != ".svg":
                continue
            svg, small = dt.fit_canvas(
                p.read_text(encoding="utf-8"), a.canvas, t["color"]["canvas"]
            )
            p.write_text(svg, encoding="utf-8")
            if small < dt.READABLE_PX:
                print(
                    f"WARN: on {a.canvas} the smallest text is {small:.1f}px (< {dt.READABLE_PX})",
                    file=sys.stderr,
                )
            if (
                p.with_suffix(".png") in made
            ):  # re-rasterize the fitted SVG: only a browser gets its CSS right
                rasterize(p, p.with_suffix(".png"), a.allow_install)
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"OK: {', '.join(map(str, made))} (design system: {t['name']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
