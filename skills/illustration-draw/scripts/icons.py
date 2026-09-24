#!/usr/bin/env python3
"""icons.py — procedural line-art icons for diagrams, styled by design tokens.

Two families, both drawn from code so every icon in a set shares one stroke,
one grid and one colour (the consistency no image model guarantees):

* `line` — flat outline icons on a 24-unit grid, round caps and joins.
* `isometric-line` — 3D outline objects on a 30° isometric grid (cube,
  database, server, document, laptop, phone, layers, monitor, package); names
  without an isometric drawing fall back to the flat icon.

`icon_svg(name, x, y, size, color, stroke, style, fill)` returns an SVG `<g>`
fragment positioned at (x, y) with the given size; `--sheet` writes a contact
sheet of every icon for review. Unknown names raise KeyError with the list of
known names, so a spec can never silently get a wrong icon. Pure stdlib.

Usage:
    python3 icons.py --list
    python3 icons.py --sheet out.svg [--style line|isometric-line] [--design-system PATH]
    python3 icons.py --self-test
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path

# --- flat line icons: 24x24 grid, primitives as (tag, attrs) -------------------
P = "path"
C = "circle"
R = "rect"
L = "line"

LINE: dict[str, list[tuple[str, dict]]] = {
    "user": [(C, {"cx": 12, "cy": 8, "r": 4}), (P, {"d": "M4 21c0-4.4 3.6-7 8-7s8 2.6 8 7"})],
    "users": [
        (C, {"cx": 9, "cy": 8, "r": 3.5}),
        (P, {"d": "M2.5 20c0-3.8 2.9-6 6.5-6s6.5 2.2 6.5 6"}),
        (P, {"d": "M16 4.6a3.5 3.5 0 0 1 0 6.8M18 14.3c2.1.7 3.5 2.6 3.5 5.7"}),
    ],
    "key": [
        (C, {"cx": 7.5, "cy": 12, "r": 4}),
        (P, {"d": "M11.5 12H21M18 12v3M21 12v2"}),
    ],
    "lock": [
        (R, {"x": 5, "y": 10.5, "width": 14, "height": 10, "rx": 2}),
        (P, {"d": "M8 10.5V7a4 4 0 0 1 8 0v3.5M12 14.5v2"}),
    ],
    "shield": [
        (P, {"d": "M12 3l7.5 3v5.5c0 4.6-3.1 8.2-7.5 9.5-4.4-1.3-7.5-4.9-7.5-9.5V6z"}),
        (P, {"d": "M8.8 12l2.2 2.2 4.2-4.4"}),
    ],
    "database": [
        (
            P,
            {
                "d": "M4.5 5.5c0-1.7 3.4-2.8 7.5-2.8s7.5 1.1 7.5 2.8-3.4 2.8-7.5 2.8-7.5-1.1-7.5-2.8z"
            },
        ),
        (
            P,
            {
                "d": "M4.5 5.5v13c0 1.7 3.4 2.8 7.5 2.8s7.5-1.1 7.5-2.8v-13M4.5 12c0 1.7 3.4 2.8 7.5 2.8s7.5-1.1 7.5-2.8"
            },
        ),
    ],
    "server": [
        (R, {"x": 3.5, "y": 4, "width": 17, "height": 7, "rx": 1.8}),
        (R, {"x": 3.5, "y": 13, "width": 17, "height": 7, "rx": 1.8}),
        (P, {"d": "M7 7.5h.01M7 16.5h.01M11 7.5h6M11 16.5h6"}),
    ],
    "document": [
        (P, {"d": "M6 2.8h8l4.5 4.5v13.9H6z"}),
        (P, {"d": "M14 2.8v4.5h4.5M9 12h6M9 15.5h6M9 8.5h2"}),
    ],
    "folder": [
        (
            P,
            {
                "d": "M3 6.5a1.5 1.5 0 0 1 1.5-1.5h4.3l2 2.2h8.7A1.5 1.5 0 0 1 21 8.7v9.8a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 18.5z"
            },
        )
    ],
    "layers": [
        (P, {"d": "M12 3l9 4.8-9 4.8-9-4.8z"}),
        (P, {"d": "M3 12.2l9 4.8 9-4.8M3 16.6l9 4.8 9-4.8"}),
    ],
    "gear": [
        (C, {"cx": 12, "cy": 12, "r": 3.2}),
        (
            P,
            {
                "d": "M12 2.8l1.6 2.6 3-.6.9 2.9 2.8 1.2-1 2.9 1.9 2.4-2.4 1.9.2 3-3 .3-1.4 2.7-2.6-1.5-2.6 1.5-1.4-2.7-3-.3.2-3L2.8 14l1.9-2.4-1-2.9 2.8-1.2.9-2.9 3 .6z"
            },
        ),
    ],
    "chip": [
        (R, {"x": 6, "y": 6, "width": 12, "height": 12, "rx": 2}),
        (R, {"x": 9.5, "y": 9.5, "width": 5, "height": 5, "rx": 0.8}),
        (P, {"d": "M9 2.5V6M15 2.5V6M9 18v3.5M15 18v3.5M2.5 9H6M2.5 15H6M18 9h3.5M18 15h3.5"}),
    ],
    "cloud": [(P, {"d": "M7 18.5a4.5 4.5 0 0 1-.6-9 6 6 0 0 1 11.4 1.4A3.8 3.8 0 0 1 17.5 18.5z"})],
    "globe": [
        (C, {"cx": 12, "cy": 12, "r": 9}),
        (
            P,
            {
                "d": "M3 12h18M12 3c2.6 2.6 3.8 5.6 3.8 9s-1.2 6.4-3.8 9c-2.6-2.6-3.8-5.6-3.8-9S9.4 5.6 12 3z"
            },
        ),
    ],
    "phone": [
        (R, {"x": 7, "y": 2.8, "width": 10, "height": 18.4, "rx": 2.2}),
        (P, {"d": "M11 17.8h2"}),
    ],
    "laptop": [
        (R, {"x": 4.5, "y": 5, "width": 15, "height": 10, "rx": 1.4}),
        (P, {"d": "M2.5 19h19"}),
    ],
    "monitor": [
        (R, {"x": 3, "y": 4, "width": 18, "height": 12, "rx": 1.6}),
        (P, {"d": "M9 20h6M12 16v4"}),
    ],
    "code": [(P, {"d": "M8.5 7.5L4 12l4.5 4.5M15.5 7.5L20 12l-4.5 4.5M13.5 5l-3 14"})],
    "api": [
        (
            P,
            {
                "d": "M7 4.5c-2 0-3 1-3 3v2c0 1.2-.8 2.5-2 2.5 1.2 0 2 1.3 2 2.5v2c0 2 1 3 3 3M17 4.5c2 0 3 1 3 3v2c0 1.2.8 2.5 2 2.5-1.2 0-2 1.3-2 2.5v2c0 2-1 3-3 3"
            },
        ),
        (P, {"d": "M9 12h.01M12 12h.01M15 12h.01"}),
    ],
    "queue": [
        (R, {"x": 3, "y": 8, "width": 18, "height": 8, "rx": 1.6}),
        (P, {"d": "M7.5 8v8M12 8v8M16.5 8v8"}),
    ],
    "table": [
        (R, {"x": 3.5, "y": 4.5, "width": 17, "height": 15, "rx": 1.6}),
        (P, {"d": "M3.5 9.5h17M3.5 14.5h17M9.5 9.5v10"}),
    ],
    "chart": [(P, {"d": "M4 20V4M4 20h16"}), (P, {"d": "M8 16v-4M12 16V8M16 16v-6"})],
    "search": [(C, {"cx": 10.5, "cy": 10.5, "r": 6.5}), (P, {"d": "M15.5 15.5L20.5 20.5"})],
    "eye": [
        (P, {"d": "M2.5 12s3.5-6.5 9.5-6.5 9.5 6.5 9.5 6.5-3.5 6.5-9.5 6.5S2.5 12 2.5 12z"}),
        (C, {"cx": 12, "cy": 12, "r": 2.8}),
    ],
    "chat": [
        (P, {"d": "M4 5.5h16v10H10l-4.5 3.5v-3.5H4z"}),
        (P, {"d": "M8 10.5h.01M12 10.5h.01M16 10.5h.01"}),
    ],
    "bolt": [(P, {"d": "M13 2.8L5 13.5h6l-1 7.7 8-10.7h-6z"})],
    "package": [
        (P, {"d": "M12 2.8l8.5 4.6v9.2L12 21.2l-8.5-4.6V7.4z"}),
        (P, {"d": "M3.5 7.4L12 12l8.5-4.6M12 12v9.2M7.8 5.1l8.5 4.6"}),
    ],
    "branch": [
        (C, {"cx": 6.5, "cy": 5.5, "r": 2.3}),
        (C, {"cx": 6.5, "cy": 18.5, "r": 2.3}),
        (C, {"cx": 17.5, "cy": 8.5, "r": 2.3}),
        (P, {"d": "M6.5 7.8v8.4M17.5 10.8c0 3.5-3 4.2-8.5 5.8"}),
    ],
    "sparkle": [
        (P, {"d": "M12 3l1.8 5.4L19 10.2l-5.2 1.8L12 17.4l-1.8-5.4L5 10.2l5.2-1.8z"}),
        (P, {"d": "M18.5 16v4M16.5 18h4"}),
    ],
    "bell": [(P, {"d": "M6 16.5V11a6 6 0 0 1 12 0v5.5l1.5 2H4.5zM10 20.5a2 2 0 0 0 4 0"})],
    "clock": [(C, {"cx": 12, "cy": 12, "r": 9}), (P, {"d": "M12 7v5l3.2 2"})],
    "check": [(C, {"cx": 12, "cy": 12, "r": 9}), (P, {"d": "M8 12.2l2.8 2.8L16.2 9.5"})],
    "mail": [
        (R, {"x": 3, "y": 5.5, "width": 18, "height": 13, "rx": 1.8}),
        (P, {"d": "M3.5 7l8.5 6 8.5-6"}),
    ],
    "card": [
        (R, {"x": 2.8, "y": 5.5, "width": 18.4, "height": 13, "rx": 1.8}),
        (P, {"d": "M2.8 9.5h18.4M6.5 15h4"}),
    ],
    "flow": [
        (C, {"cx": 5, "cy": 12, "r": 2.2}),
        (C, {"cx": 19, "cy": 6, "r": 2.2}),
        (C, {"cx": 19, "cy": 18, "r": 2.2}),
        (
            P,
            {
                "d": "M7.2 12h4.3a2 2 0 0 0 2-2V8a2 2 0 0 1 2-2h1.3M11.5 12a2 2 0 0 1 2 2v2a2 2 0 0 0 2 2h1.3"
            },
        ),
    ],
}

# --- isometric line art: unit vectors of a 30° isometric projection -----------
COS30 = math.cos(math.radians(30))


def _iso(x: float, y: float, z: float) -> tuple[float, float]:
    """World (x right-back, y left-back, z up) -> screen, unit = 1."""
    return ((x - y) * COS30, (x + y) * 0.5 - z)


def _poly(pts: list[tuple[float, float, float]]) -> str:
    return "M" + " L".join(f"{a:.2f} {b:.2f}" for a, b in (_iso(*p) for p in pts)) + " Z"


def _box(x, y, z, w, d, h) -> list[str]:
    """Three visible faces of a box (top, left, right) as closed paths."""
    top = _poly([(x, y, z + h), (x + w, y, z + h), (x + w, y + d, z + h), (x, y + d, z + h)])
    left = _poly([(x, y + d, z), (x + w, y + d, z), (x + w, y + d, z + h), (x, y + d, z + h)])
    right = _poly([(x + w, y, z), (x + w, y + d, z), (x + w, y + d, z + h), (x + w, y, z + h)])
    return [top, left, right]


def _ellipse_iso(cx, cy, z, r, steps=36) -> list[tuple[float, float]]:
    return [
        _iso(cx + r * math.cos(t), cy + r * math.sin(t), z)
        for t in (2 * math.pi * i / steps for i in range(steps + 1))
    ]


def _cylinder(r, h, bands=0) -> list[str]:
    top = _ellipse_iso(0, 0, h, r)
    bot = _ellipse_iso(0, 0, 0, r)
    # silhouette: leftmost/rightmost points of the ellipse in screen x
    lx = min(top, key=lambda p: p[0])
    rx = max(top, key=lambda p: p[0])
    lb = min(bot, key=lambda p: p[0])
    rb = max(bot, key=lambda p: p[0])
    front = [p for p in bot if p[1] >= (lb[1] + rb[1]) / 2 - 1e-6]
    front.sort(key=lambda p: p[0])
    body = (
        f"M{lx[0]:.2f} {lx[1]:.2f} L{lb[0]:.2f} {lb[1]:.2f} "
        + " ".join(f"L{a:.2f} {b:.2f}" for a, b in front)
        + f" L{rb[0]:.2f} {rb[1]:.2f} L{rx[0]:.2f} {rx[1]:.2f}"
    )
    paths = [body + " Z", "M" + " L".join(f"{a:.2f} {b:.2f}" for a, b in top) + " Z"]
    for k in range(1, bands + 1):
        band = _ellipse_iso(0, 0, h * k / (bands + 1), r)
        fr = sorted(
            (p for p in band if p[1] >= (band[0][1] + band[len(band) // 2][1]) / 2 - 1e-6),
            key=lambda p: p[0],
        )
        paths.append("M" + " L".join(f"{a:.2f} {b:.2f}" for a, b in fr))
    return paths


def _iso_shapes(name: str) -> list[str] | None:
    """Back-to-front closed paths; the viewer looks from +x,+y, so back = low x+y."""
    if name in ("package", "cube"):
        return [
            *_box(-1, -1, 0, 2, 2, 2),
            _line3([(-1, 0, 2), (1, 0, 2)]),
            _line3([(0, 1, 0), (0, 1, 2)]),
        ]
    if name == "database":
        return _cylinder(1.25, 2.4, bands=2)
    if name == "server":
        out: list[str] = []
        for i in range(3):
            out += _box(-1.3, -0.9, i * 0.8, 2.6, 1.8, 0.62)
            out.append(_line3([(0.35, 0.9, i * 0.8 + 0.31), (1.0, 0.9, i * 0.8 + 0.31)]))
        return out
    if name == "document":
        sheet = _box(-1.2, -1.5, 0, 2.4, 3.0, 0.06)
        lines = [_line3([(-0.8, y, 0.07), (0.8, y, 0.07)]) for y in (-0.9, -0.4, 0.1, 0.6)]
        return [*sheet, *lines]
    if name == "layers":
        out = []
        for i in range(3):
            out += _box(-1.4, -1.4, i * 0.55, 2.8, 2.8, 0.18)
        return out
    if name == "laptop":
        base = _box(-1.5, -1.1, 0, 3, 2.2, 0.14)
        screen = _box(-1.5, -1.2, 0.14, 3, 0.1, 1.9)
        keys = [_line3([(-1.1, y, 0.15), (1.1, y, 0.15)]) for y in (-0.6, -0.2, 0.2)]
        return [*screen, *base, *keys]
    if name == "phone":
        body = _box(-0.8, -1.5, 0, 1.6, 3.0, 0.14)
        face = _poly(
            [(-0.62, -1.25, 0.15), (0.62, -1.25, 0.15), (0.62, 1.2, 0.15), (-0.62, 1.2, 0.15)]
        )
        return [*body, face]
    if name == "monitor":
        foot = _box(-0.7, -0.5, 0, 1.4, 1.0, 0.08)
        neck = _box(-0.12, -0.35, 0.08, 0.24, 0.2, 0.8)
        panel = _box(-1.7, -0.5, 0.88, 3.4, 0.12, 2.0)
        return [*foot, *neck, *panel]
    return None


def _line3(pts: list[tuple[float, float, float]]) -> str:
    return "M" + " L".join(f"{a:.2f} {b:.2f}" for a, b in (_iso(*q) for q in pts))


def _bounds(paths: list[str]) -> tuple[float, float, float, float]:
    nums = [float(v) for d in paths for v in re.findall(r"-?\d+\.?\d*", d)]
    xs, ys = nums[0::2], nums[1::2]
    return min(xs), min(ys), max(xs), max(ys)


def _attrs(d: dict) -> str:
    return " ".join(f'{k.replace("_", "-")}="{v}"' for k, v in d.items())


def names() -> list[str]:
    return sorted(LINE)


def icon_svg(
    name: str,
    x: float,
    y: float,
    size: float,
    color: str,
    stroke: float = 1.6,
    style: str = "line",
    fill: str = "none",
) -> str:
    """SVG <g> for icon `name`, top-left at (x, y), square `size` px."""
    if name not in LINE:
        raise KeyError(f"unknown icon {name!r}; known: {', '.join(names())}")
    if style == "isometric-line":
        shapes = _iso_shapes(name)
        if shapes:
            x0, y0, x1, y1 = _bounds(shapes)
            scale = size / max(x1 - x0, y1 - y0)
            ox = x + size / 2 - (x0 + x1) / 2 * scale
            oy = y + size / 2 - (y0 + y1) / 2 * scale
            body = "".join(
                f'<path d="{d}" fill="{fill if d.endswith("Z") else "none"}"/>' for d in shapes
            )
            sw = stroke / scale
            return (
                f'<g class="icon" transform="translate({ox:.2f},{oy:.2f}) scale({scale:.3f})" '
                f'stroke="{color}" stroke-width="{sw:.3f}" stroke-linejoin="round" stroke-linecap="round">{body}</g>'
            )
    scale = size / 24
    parts = "".join(f"<{tag} {_attrs(a)}/>" for tag, a in LINE[name])
    sw = stroke / scale
    return (
        f'<g class="icon" transform="translate({x:.2f},{y:.2f}) scale({scale:.3f})" fill="none" '
        f'stroke="{color}" stroke-width="{sw:.3f}" stroke-linecap="round" stroke-linejoin="round">{parts}</g>'
    )


def sheet(style: str, color: str, bg: str, fill: str) -> str:
    cols, cell, size = 8, 120, 48
    items = names()
    rows = (len(items) + cols - 1) // cols
    w, h = cols * cell, rows * cell
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" font-family="Inter, Helvetica, Arial, sans-serif">'
    ]
    out.append(f"<title>Icon sheet ({style})</title><desc>Every procedural icon</desc>")
    out.append(f'<rect width="{w}" height="{h}" fill="{bg}"/>')
    for i, n in enumerate(items):
        cx, cy = (i % cols) * cell, (i // cols) * cell
        out.append(icon_svg(n, cx + (cell - size) / 2, cy + 22, size, color, 1.6, style, fill))
        out.append(
            f'<text x="{cx + cell / 2}" y="{cy + 104}" font-size="13" fill="{color}" text-anchor="middle">{n}</text>'
        )
    out.append("</svg>")
    return "\n".join(out)


def self_test() -> int:
    import xml.etree.ElementTree as ET

    for n in names():
        for st in ("line", "isometric-line"):
            frag = icon_svg(n, 0, 0, 32, "#111111", 1.6, st, "#FFFFFF")
            ET.fromstring(f'<svg xmlns="http://www.w3.org/2000/svg">{frag}</svg>')  # noqa: S314 - own markup
    try:
        icon_svg("nope", 0, 0, 24, "#000000")
        raise AssertionError("unknown icon accepted")
    except KeyError:
        pass
    assert len(names()) >= 30
    print(f"OK: self-test passed ({len(names())} icons)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--sheet", type=Path)
    ap.add_argument("--style", default=None, choices=["line", "isometric-line"])
    ap.add_argument("--design-system", default=None)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if args.list:
        print("\n".join(names()))
        return 0
    if args.sheet:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import design_tokens as dt

        t = dt.load(args.design_system)
        style = args.style or (t["icon"]["style"] if t["icon"]["style"] != "none" else "line")
        c = t["color"]
        args.sheet.write_text(sheet(style, c["ink"], c["canvas"], c["surface"]), encoding="utf-8")
        print(f"OK: wrote {args.sheet}")
        return 0
    ap.error("choose --list, --sheet or --self-test")
    return 2


if __name__ == "__main__":
    sys.exit(main())
