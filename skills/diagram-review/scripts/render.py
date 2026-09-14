#!/usr/bin/env python3
"""render.py — rasterize a diagram to PNG so it can be looked at, on any machine.

Input: an .svg or .html file, or a .mmd Mermaid file (rendered to SVG first).
Autodetects a rasterizer — rsvg-convert → resvg → cairosvg → ImageMagick →
inkscape → headless Chrome/Chromium (network blocked) → macOS qlmanage — and
renders at the delivery width plus a feed-size width, because a label that is
fine at 1200 px is what dies at 600 px. Validates every PNG's real dimensions.
Pure stdlib; exits non-zero with install hints when no renderer exists.

Mermaid needs `mmdc` (`@mermaid-js/mermaid-cli`); if it is not on PATH the
script only downloads the pinned version through npx when `--allow-download`
is given — nothing is fetched silently. Nothing is ever sent to kroki.io.

Usage:
    python3 render.py FILE.svg|FILE.html|FILE.mmd [--widths 1200,600] [--out DIR]
        [--renderer NAME] [--allow-download]

Output lines: `RENDERED <w>x<h> <path>` per file, then `OK:`/`FAIL:`.
"""

from __future__ import annotations

import argparse
import platform
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

MERMAID_CLI_PIN = "@mermaid-js/mermaid-cli@11.17.0"  # verified on npm 2026-09-14
CHROME_CANDIDATES = (
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
    "chrome",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
)
INSTALL_HINTS = (
    ("rsvg-convert", "brew install librsvg          # or: apt install librsvg2-bin"),
    ("resvg", "cargo install resvg           # or: brew install resvg"),
    ("cairosvg", "pip install cairosvg          # needs system cairo"),
    ("magick", "brew install imagemagick      # or: apt install imagemagick"),
    ("inkscape", "brew install --cask inkscape  # or: apt install inkscape"),
    ("chrome", "any Chrome/Chromium/Edge install (headless screenshot)"),
    ("qlmanage", "built into macOS (fallback; used automatically)"),
)
TIMEOUT = 180


def png_size(path: Path) -> tuple[int, int] | None:
    try:
        with open(path, "rb") as fh:
            head = fh.read(24)
    except OSError:
        return None
    if len(head) < 24 or head[:8] != b"\x89PNG\r\n\x1a\n" or head[12:16] != b"IHDR":
        return None
    return struct.unpack(">II", head[16:24])


def run(cmd: list[str], cwd: Path | None = None) -> bool:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT, cwd=cwd)
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"  note: {cmd[0]} failed to run: {exc}", file=sys.stderr)
        return False
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()
        print(
            f"  note: {cmd[0]} exited {proc.returncode}: {tail[-1] if tail else ''}",
            file=sys.stderr,
        )
        return False
    return True


def svg_aspect(svg: Path) -> float:
    """height/width from viewBox (or width/height attrs); 0.525 (1200x630) if unknown."""
    head = svg.read_text(encoding="utf-8", errors="replace")[:4000]
    m = re.search(r"<svg\b[^>]*>", head, re.S)
    tag = m.group(0) if m else ""
    vb = re.search(r'viewBox\s*=\s*"([^"]+)"', tag)
    if vb:
        nums = re.findall(r"[-+]?\d*\.?\d+", vb.group(1))
        if len(nums) >= 4 and float(nums[2]) > 0:
            return float(nums[3]) / float(nums[2])
    w = re.search(r'\bwidth\s*=\s*"([\d.]+)', tag)
    h = re.search(r'\bheight\s*=\s*"([\d.]+)', tag)
    if w and h and float(w.group(1)) > 0:
        return float(h.group(1)) / float(w.group(1))
    return 0.525


def find_chrome() -> str | None:
    for c in CHROME_CANDIDATES:
        if c.startswith("/"):
            if Path(c).is_file():
                return c
        elif shutil.which(c):
            return c
    return None


def render_chrome(chrome: str, src: Path, width: int, height: int, out: Path) -> bool:
    """Screenshot a local file with network resolution blocked. HTML or SVG (wrapped)."""
    with tempfile.TemporaryDirectory() as td:
        if src.suffix.lower() == ".svg":
            page = Path(td) / "wrap.html"
            page.write_text(
                "<!doctype html><meta charset='utf-8'>"
                "<style>html,body{margin:0;padding:0;background:#fff;overflow:hidden}img{display:block}</style>"
                f'<img src="{src.resolve().as_uri()}" width="{width}" height="{height}">',
                encoding="utf-8",
            )
        else:
            page = src.resolve()
        cmd = [
            chrome,
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            "--host-resolver-rules=MAP * ~NOTFOUND",  # nothing leaves the machine
            "--no-first-run",
            "--no-default-browser-check",
            f"--window-size={width},{height}",
            f"--screenshot={out}",
            page.as_uri(),
        ]
        return run(cmd) and out.is_file()


def render_qlmanage(src: Path, width: int, out: Path) -> bool:
    with tempfile.TemporaryDirectory() as td:
        if not run(["qlmanage", "-t", "-s", str(width), "-o", td, str(src)]):
            return False
        produced = Path(td) / (src.name + ".png")
        if not produced.is_file():
            return False
        shutil.move(str(produced), out)
    return True


def detect(prefer: str | None, html: bool) -> tuple[str, object] | None:
    order = ["rsvg-convert", "resvg", "cairosvg", "magick", "inkscape", "chrome", "qlmanage"]
    if html:
        order = ["chrome"]
    if prefer:
        order = [prefer]
    for tool in order:
        if tool == "chrome":
            chrome = find_chrome()
            if chrome:
                return "chrome", chrome
        elif tool == "cairosvg":
            if shutil.which("cairosvg"):
                return tool, "cairosvg"
            try:
                import cairosvg  # noqa: F401

                return "cairosvg-module", sys.executable
            except ImportError:
                continue
        elif tool == "qlmanage":
            if platform.system() == "Darwin" and shutil.which("qlmanage"):
                return tool, "qlmanage"
        elif shutil.which(tool):
            return tool, tool
    return None


def rasterize(tool: str, exe: str, src: Path, width: int, height: int, out: Path) -> bool:
    if tool == "rsvg-convert":
        return run([exe, "-w", str(width), "-h", str(height), "-o", str(out), str(src)])
    if tool == "resvg":
        return run([exe, "-w", str(width), "-h", str(height), str(src), str(out)])
    if tool == "cairosvg":
        return run(
            [
                exe,
                str(src),
                "-o",
                str(out),
                "--output-width",
                str(width),
                "--output-height",
                str(height),
            ]
        )
    if tool == "cairosvg-module":
        return run(
            [
                exe,
                "-m",
                "cairosvg",
                str(src),
                "-o",
                str(out),
                "--output-width",
                str(width),
                "--output-height",
                str(height),
            ]
        )
    if tool == "magick":
        return run(
            [
                exe,
                "-background",
                "none",
                "-density",
                "96",
                str(src),
                "-resize",
                f"{width}x{height}!",
                str(out),
            ]
        )
    if tool == "inkscape":
        return run(
            [
                exe,
                "--export-type=png",
                f"--export-filename={out}",
                f"--export-width={width}",
                f"--export-height={height}",
                str(src),
            ]
        )
    if tool == "chrome":
        return render_chrome(exe, src, width, height, out)
    if tool == "qlmanage":
        return render_qlmanage(src, width, out)
    raise ValueError(tool)


def mermaid_to_svg(src: Path, out_dir: Path, allow_download: bool) -> Path | None:
    out = out_dir / (src.stem + ".svg")
    if shutil.which("mmdc"):
        cmd = ["mmdc", "-i", str(src), "-o", str(out)]
    elif allow_download and shutil.which("npx"):
        print(
            f"note: mmdc not on PATH — running pinned {MERMAID_CLI_PIN} via npx (downloads Chromium once)",
            file=sys.stderr,
        )
        cmd = ["npx", "-y", "-p", MERMAID_CLI_PIN, "mmdc", "-i", str(src), "-o", str(out)]
    else:
        print(
            "ERROR: no `mmdc` on PATH. Install `npm i -g @mermaid-js/mermaid-cli@11.17.0`, or re-run with "
            "--allow-download to use the pinned npx build (no silent downloads).",
            file=sys.stderr,
        )
        return None
    if not run(cmd):
        print(
            "ERROR: Mermaid render failed — the parser errors above are the thing to fix",
            file=sys.stderr,
        )
        return None
    return out if out.is_file() else None


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("file", type=Path)
    ap.add_argument(
        "--widths",
        default="auto",
        help="comma-separated px widths (auto = native and half, min 400)",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=None,
        help="output dir (default: diagram-design/renders/<stem>/)",
    )
    ap.add_argument(
        "--renderer", choices=[t for t, _ in INSTALL_HINTS] + ["cairosvg-module"], default=None
    )
    ap.add_argument(
        "--allow-download", action="store_true", help="permit the pinned mermaid-cli via npx"
    )
    args = ap.parse_args()

    src: Path = args.file
    if not src.is_file():
        print(f"ERROR: no such file: {src}", file=sys.stderr)
        return 1
    out_dir = args.out or Path("diagram-design/renders") / src.stem
    out_dir.mkdir(parents=True, exist_ok=True)

    if src.suffix.lower() in (".mmd", ".mermaid"):
        svg = mermaid_to_svg(src, out_dir, args.allow_download)
        if svg is None:
            return 1
        print(f"SVG {svg}")
        src = svg
    html = src.suffix.lower() in (".html", ".htm")

    found = detect(args.renderer, html)
    if found is None:
        print(
            "ERROR: no renderer found"
            + (" (HTML needs Chrome/Chromium/Edge)" if html else "")
            + ". Install one of:",
            file=sys.stderr,
        )
        for tool, hint in INSTALL_HINTS:
            print(f"  {tool:13s} {hint}", file=sys.stderr)
        return 2
    tool, exe = found

    aspect = 0.5625 if html else svg_aspect(src)
    if args.widths == "auto":
        native = 1200
        if not html:
            head = src.read_text(encoding="utf-8", errors="replace")[:4000]
            m = re.search(r'viewBox\s*=\s*"[^"]*?([\d.]+)\s+[\d.]+"\s*', head) or re.search(
                r'\bwidth\s*=\s*"([\d.]+)', head
            )
            if m:
                native = int(float(m.group(1)))
        widths = [native, max(400, native // 2)]
    else:
        try:
            widths = [int(w) for w in args.widths.split(",") if w.strip()]
        except ValueError:
            print(f"ERROR: bad --widths value: {args.widths!r}", file=sys.stderr)
            return 1

    failures = 0
    for width in widths:
        height = max(1, round(width * aspect))
        out = out_dir / f"{src.stem}-{width}.png"
        if not rasterize(tool, exe, src, width, height, out):
            print(f"ERROR: {tool} failed to render {src} at {width}px", file=sys.stderr)
            failures += 1
            continue
        dims = png_size(out)
        if dims is None:
            print(f"ERROR: {out} is not a valid PNG", file=sys.stderr)
            failures += 1
            continue
        if tool != "qlmanage" and abs(dims[0] - width) > 2:
            print(f"ERROR: {out} is {dims[0]}x{dims[1]}, expected width {width}", file=sys.stderr)
            failures += 1
            continue
        print(f"RENDERED {dims[0]}x{dims[1]} {out}")
    if tool == "qlmanage":
        print(
            "note: qlmanage fallback — fine for review; install librsvg or resvg for exact sizes",
            file=sys.stderr,
        )
    if failures:
        print(f"FAIL: {failures} of {len(widths)} renders failed (renderer: {tool})")
        return 1
    print(f"OK: {len(widths)} file(s) in {out_dir} (renderer: {tool})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
