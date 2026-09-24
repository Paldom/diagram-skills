#!/usr/bin/env python3
"""derive_palette.py — measure a moodboard so the design system starts from data.

Samples every image (png, jpg, webp, gif, and the first frame of mp4/mov/webm)
in a folder with ffmpeg, downsampled to 96 px, and reports what a person
squinting at the board would see: how many images are monochrome, the paper
(light, dominant) colours, the ink (dark, frequent) colours, and the few
saturated accents — each with how many images use it. Prints a starter
`color` block you then refine by looking at the images. Stdlib + ffmpeg.

Usage:
    python3 derive_palette.py MOODBOARD_DIR [--json]
    python3 derive_palette.py --self-test
Exit 1 when ffmpeg is missing or no image could be read.
"""

from __future__ import annotations

import argparse
import colorsys
import json
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import design_tokens as dt  # noqa: E402

EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".mp4", ".mov", ".webm", ".m4v"}
SIDE = 96


def pixels(path: Path) -> list[tuple[int, int, int]]:
    r = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-frames:v", "1",
         "-vf", f"scale={SIDE}:{SIDE}:flags=area", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True, timeout=60,
    )  # fmt: skip
    b = r.stdout
    if r.returncode != 0 or len(b) < 3:
        return []
    return [(b[i], b[i + 1], b[i + 2]) for i in range(0, len(b) - 2, 3)]


def quant(c: tuple[int, int, int], step: int = 12) -> tuple[int, int, int]:
    return tuple(min(255, round(v / step) * step) for v in c)  # type: ignore[return-value]


def hexc(c) -> str:
    return "#{:02X}{:02X}{:02X}".format(*c)


def analyse(images: dict[str, list[tuple[int, int, int]]]) -> dict:
    papers, inks, accents = Counter(), Counter(), Counter()
    used_by: dict[str, set[str]] = {}
    mono = 0
    for name, px in images.items():
        counts = Counter(quant(p) for p in px)
        total = len(px)
        sat_share = 0
        for c, n in counts.items():
            _h, s, v = colorsys.rgb_to_hsv(*(x / 255 for x in c))
            share = n / total
            if s > 0.35 and v > 0.35:
                sat_share += share
                if share > 0.004:
                    accents[c] += n
                    used_by.setdefault(hexc(c), set()).add(name)
            elif v > 0.82 and share > 0.05:
                papers[c] += n
                used_by.setdefault(hexc(c), set()).add(name)
            elif v < 0.35 and share > 0.01:
                inks[c] += n
                used_by.setdefault(hexc(c), set()).add(name)
        mono += sat_share < 0.02

    def top(counter, k):
        return [
            {
                "hex": hexc(c),
                "images": len(used_by.get(hexc(c), ())),
                "share": round(n / sum(counter.values()), 3),
            }
            for c, n in counter.most_common(k)
        ]

    out = {
        "images": len(images),
        "monochrome": mono,
        "paper": top(papers, 5),
        "ink": top(inks, 5),
        "accents": top(accents, 6),
    }
    paper = out["paper"][0]["hex"] if out["paper"] else "#F5F5F2"
    ink = out["ink"][0]["hex"] if out["ink"] else "#1A1A1A"
    starter = {"canvas": paper, "ink": ink}
    if out["accents"]:
        starter["accent"] = out["accents"][0]["hex"]
    starter_ratio = dt.contrast(ink, paper)
    out["starter"] = {"color": starter, "ink_on_canvas": round(starter_ratio, 2)}
    return out


def self_test() -> int:
    paper, ink, neon = (244, 244, 240), (20, 20, 20), (240, 240, 0)
    imgs = {
        "a.png": [paper] * 900 + [ink] * 100,
        "b.png": [paper] * 800 + [ink] * 150 + [neon] * 50,
    }
    r = analyse(imgs)
    assert r["images"] == 2 and r["monochrome"] == 1, r
    assert r["paper"][0]["hex"] == hexc(quant(paper)) and r["ink"][0]["hex"] == hexc(quant(ink))
    assert r["accents"] and r["accents"][0]["images"] == 1
    assert r["starter"]["ink_on_canvas"] > 10
    print("OK: self-test passed")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("folder", nargs="?", type=Path)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if not a.folder or not a.folder.is_dir():
        ap.error("a moodboard folder is required")
    if not shutil.which("ffmpeg"):
        print(
            "ERROR: ffmpeg not found — brew install ffmpeg / apt-get install ffmpeg",
            file=sys.stderr,
        )
        return 1
    files = sorted(p for p in a.folder.rglob("*") if p.suffix.lower() in EXT)
    images = {p.name: px for p in files if (px := pixels(p))}
    if not images:
        print(f"ERROR: no readable images in {a.folder}", file=sys.stderr)
        return 1
    r = analyse(images)
    if a.json:
        print(json.dumps(r, indent=2))
        return 0
    print(
        f"{r['images']} images read, {r['monochrome']} monochrome (skipped: {len(files) - len(images)})"
    )
    for key in ("paper", "ink", "accents"):
        row = ", ".join(f"{e['hex']} ({e['images']} img)" for e in r[key]) or "none"
        print(f"{key:8} {row}")
    print(
        f"starter  {json.dumps(r['starter']['color'])}  ink/canvas {r['starter']['ink_on_canvas']}:1"
    )
    print("Now LOOK at the images: shapes, borders, radius, icon style and type are not in pixels.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
