#!/usr/bin/env python3
"""build_svg.py — compile a small JSON spec into a minimalist illustration SVG.

The model decides *what* goes on the card (archetype, title, labels, the one
accent); this script decides *where* — every coordinate comes from a fixed
grid, so nothing can overlap by construction. Capacity is enforced: too many
items or labels that would not fit at the minimum font size are rejected with
a message that says what to cut. Text is XML-escaped. Pure stdlib.

Spec (JSON, see --schema):
    {"archetype": "flow|compare|stack|hub|grid", "canvas": "social|wide|square",
     "theme": "light|dark", "accent": "#2563EB", "title": "...", "subtitle": "...",
     "footer": "...", "items": [{"label": "...", "detail": "...", "accent": true}],
     "center": "..." (hub), "columns": [{"heading": "...", "rows": ["..."]}] (compare),
     "axes": {"x": ["left", "right"], "y": ["bottom", "top"]} (grid)}

Usage:
    python3 build_svg.py SPEC.json [--out FILE.svg]     # or - for stdin
    python3 build_svg.py --schema
    python3 build_svg.py --self-test

Exit 1 with `ERROR:` lines when the spec is invalid or over capacity.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.sax.saxutils import escape

CANVASES = {"social": (1200, 630), "wide": (1600, 900), "square": (1080, 1080)}
THEMES = {
    "light": {
        "bg": "#F7F7F5",
        "ink": "#1A1A1F",
        "muted": "#6B6B75",
        "box": "#FFFFFF",
        "line": "#7C7C86",
        "accent_text": "#FFFFFF",
    },
    "dark": {
        "bg": "#1E1E23",
        "ink": "#F0F0F2",
        "muted": "#A0A0A8",
        "box": "#2A2A30",
        "line": "#8A8A94",
        "accent_text": "#FFFFFF",
    },
}
DEFAULT_ACCENT = "#2563EB"
FONT = "Inter, -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
CAPACITY = {"flow": (2, 6), "stack": (2, 5), "hub": (3, 6), "grid": (4, 4), "compare": (2, 3)}
LIMITS = {
    "title": 70,
    "subtitle": 110,
    "footer": 60,
    "label": 26,
    "detail": 60,
    "heading": 20,
    "row": 34,
    "center": 20,
}
HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
CHAR_W = 0.55  # em per glyph, regular
CHAR_WB = 0.6  # bold

errors: list[str] = []


def err(msg: str) -> None:
    errors.append(f"ERROR: {msg}")


def text_w(s: str, size: float, bold: bool = False) -> float:
    return len(s) * size * (CHAR_WB if bold else CHAR_W)


def wrap(
    s: str, size: float, max_w: float, bold: bool = False, max_lines: int = 2
) -> list[str] | None:
    """Greedy word wrap by estimated width; None if it does not fit in max_lines."""
    words, lines, cur = s.split(), [], ""
    for w in words:
        cand = f"{cur} {w}".strip()
        if text_w(cand, size, bold) <= max_w:
            cur = cand
        else:
            if not cur or text_w(w, size, bold) > max_w:
                return None
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines if len(lines) <= max_lines else None


def fit(s: str, sizes: list[float], max_w: float, bold: bool = False, max_lines: int = 2):
    """Largest size at which `s` fits on ONE line; else the largest size that wraps into
    max_lines. (size, lines) or None. One line at 44px beats two lines at 48px."""
    for allowed in range(1, max_lines + 1):
        for size in sizes:
            lines = wrap(s, size, max_w, bold, allowed)
            if lines:
                return size, lines
    return None


def t(
    x: float,
    y: float,
    lines: list[str],
    size: float,
    fill: str,
    anchor: str = "start",
    bold: bool = False,
) -> str:
    weight = ' font-weight="700"' if bold else ""
    lh = size * 1.25
    if len(lines) == 1:
        return f'<text x="{x:.0f}" y="{y:.0f}" font-size="{size:.0f}" fill="{fill}" text-anchor="{anchor}"{weight}>{escape(lines[0])}</text>'
    spans = "".join(
        f'<tspan x="{x:.0f}" y="{y + i * lh:.0f}">{escape(ln)}</tspan>'
        for i, ln in enumerate(lines)
    )
    return (
        f'<text font-size="{size:.0f}" fill="{fill}" text-anchor="{anchor}"{weight}>{spans}</text>'
    )


def box(x: float, y: float, w: float, h: float, th: dict, accent: str | None) -> str:
    stroke = accent if accent else th["line"]
    sw = 3 if accent else 2
    return f'<rect x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="{h:.0f}" rx="10" fill="{th["box"]}" stroke="{stroke}" stroke-width="{sw}"/>'


def arrow(x1: float, y1: float, x2: float, y2: float, color: str) -> str:
    return f'<line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" stroke="{color}" stroke-width="2" marker-end="url(#arrow)"/>'


def validate(spec: dict) -> tuple[dict, dict, tuple[int, int], str] | None:
    if not isinstance(spec, dict):
        err("spec must be a JSON object")
        return None
    arch = spec.get("archetype")
    if arch not in CAPACITY:
        err(f"archetype must be one of {sorted(CAPACITY)}, got {arch!r}")
        return None
    canvas = spec.get("canvas", "social")
    if isinstance(canvas, dict):
        try:
            size = (int(canvas["w"]), int(canvas["h"]))
        except (KeyError, TypeError, ValueError):
            err("canvas object needs integer w and h")
            return None
    elif canvas in CANVASES:
        size = CANVASES[canvas]
    else:
        err(f"canvas must be one of {sorted(CANVASES)} or {{w,h}}, got {canvas!r}")
        return None
    theme = spec.get("theme", "light")
    if theme not in THEMES:
        err(f"theme must be light or dark, got {theme!r}")
        return None
    accent = spec.get("accent", DEFAULT_ACCENT)
    if not HEX_RE.match(str(accent)):
        err(f"accent must be a 6-digit hex color, got {accent!r}")
        return None
    for key in ("title", "subtitle", "footer", "center"):
        v = spec.get(key)
        if v is not None and not isinstance(v, str):
            err(f"{key} must be a string")
            return None
        if isinstance(v, str) and len(v) > LIMITS[key if key != "center" else "center"]:
            err(
                f"{key} is {len(v)} chars (max {LIMITS[key]}) — cut it; the visual carries the detail"
            )
        if isinstance(v, str) and re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", v):
            err(f"{key} contains control characters")
    if not spec.get("title"):
        err("title is required — it states the one takeaway")
    lo, hi = CAPACITY[arch]
    if arch == "compare":
        cols = spec.get("columns")
        if not isinstance(cols, list) or not lo <= len(cols) <= hi:
            err(f"compare needs {lo}-{hi} columns")
            return None
        for i, c in enumerate(cols):
            if (
                not isinstance(c, dict)
                or not isinstance(c.get("heading"), str)
                or not isinstance(c.get("rows"), list)
            ):
                err(f"columns[{i}] needs a heading string and a rows list")
                return None
            if len(c["heading"]) > LIMITS["heading"]:
                err(f"columns[{i}].heading is {len(c['heading'])} chars (max {LIMITS['heading']})")
            if not 1 <= len(c["rows"]) <= 5:
                err(f"columns[{i}] needs 1-5 rows")
            for j, r in enumerate(c["rows"]):
                if not isinstance(r, str) or len(r) > LIMITS["row"]:
                    err(f"columns[{i}].rows[{j}] must be a string of at most {LIMITS['row']} chars")
    else:
        items = spec.get("items")
        if not isinstance(items, list) or not lo <= len(items) <= hi:
            err(
                f"{arch} needs {lo}-{hi} items, got {len(items) if isinstance(items, list) else 'none'} — cut to what the takeaway needs"
            )
            return None
        accents = 0
        for i, it in enumerate(items):
            if (
                not isinstance(it, dict)
                or not isinstance(it.get("label"), str)
                or not it["label"].strip()
            ):
                err(f"items[{i}] needs a non-empty label")
                continue
            if len(it["label"]) > LIMITS["label"]:
                err(f"items[{i}].label is {len(it['label'])} chars (max {LIMITS['label']})")
            d = it.get("detail")
            if d is not None and (not isinstance(d, str) or len(d) > LIMITS["detail"]):
                err(f"items[{i}].detail must be a string of at most {LIMITS['detail']} chars")
            accents += 1 if it.get("accent") else 0
        if accents > 1:
            err(
                f"{accents} items marked accent — exactly one element carries the accent (the takeaway)"
            )
        if arch == "hub" and not isinstance(spec.get("center"), str):
            err("hub needs a center label")
        if arch == "grid":
            axes = spec.get("axes")
            if axes is not None and not (
                isinstance(axes, dict)
                and all(isinstance(axes.get(k), list) and len(axes[k]) == 2 for k in ("x", "y"))
            ):
                err('grid axes must be {"x": [left, right], "y": [bottom, top]}')
    if errors:
        return None
    return spec, THEMES[theme], size, accent


def header(spec: dict, th: dict, W: int, H: int, m: float) -> tuple[list[str], float]:
    """Title + subtitle; returns (svg parts, y where content may start)."""
    parts = []
    scale = W / 1200
    title_sizes = [int(48 * scale), int(44 * scale), int(40 * scale), int(36 * scale)]
    ft = fit(spec["title"], title_sizes, W - 2 * m, bold=True, max_lines=2)
    if ft is None:
        err("title does not fit in two lines even at the smallest size — shorten it")
        return parts, 0
    size, lines = ft
    y = m + size
    parts.append(t(m, y, lines, size, th["ink"], bold=True))
    y += (len(lines) - 1) * size * 1.25
    if spec.get("subtitle"):
        sub = fit(spec["subtitle"], [int(24 * scale), int(22 * scale)], W - 2 * m, max_lines=2)
        if sub is None:
            err("subtitle does not fit — shorten it")
            return parts, 0
        ssize, slines = sub
        y += ssize * 1.6
        parts.append(t(m, y, slines, ssize, th["muted"]))
        y += (len(slines) - 1) * ssize * 1.25
    return parts, y + 24 * scale


def footer(spec: dict, th: dict, W: int, H: int, m: float) -> tuple[list[str], float]:
    if not spec.get("footer"):
        return [], H - m
    size = max(18, int(18 * W / 1200))
    return [
        t(W - m, H - m + size * 0.2, [spec["footer"]], size, th["muted"], anchor="end")
    ], H - m - size * 1.4


def item_box(
    x: float, y: float, w: float, h: float, it: dict, th: dict, accent: str, W: int
) -> list[str] | None:
    """A box with a bold label and optional detail, centered; None if the text cannot fit."""
    scale = W / 1200
    pad = 16 * scale
    color = accent if it.get("accent") else None
    label = fit(
        it["label"],
        [int(28 * scale), int(24 * scale), int(20 * scale)],
        w - 2 * pad,
        bold=True,
        max_lines=2,
    )
    if label is None:
        return None
    lsize, llines = label
    parts = [box(x, y, w, h, th, color)]
    detail = None
    if it.get("detail"):
        detail = fit(it["detail"], [int(19 * scale), int(17 * scale)], w - 2 * pad, max_lines=2)
        if detail is None:
            return None
    block_h = len(llines) * lsize * 1.25 + (
        len(detail[1]) * detail[0] * 1.25 + 8 * scale if detail else 0
    )
    if block_h > h - 2 * pad:
        return None
    cy = y + (h - block_h) / 2 + lsize
    parts.append(
        t(x + w / 2, cy, llines, lsize, accent if color else th["ink"], anchor="middle", bold=True)
    )
    if detail:
        dy = cy + (len(llines) - 1) * lsize * 1.25 + 8 * scale + detail[0] * 1.1
        parts.append(t(x + w / 2, dy, detail[1], detail[0], th["muted"], anchor="middle"))
    return parts


def build(spec: dict, th: dict, size: tuple[int, int], accent: str) -> str | None:
    W, H = size
    m = 60 * W / 1200
    scale = W / 1200
    top_parts, y0 = header(spec, th, W, H, m)
    foot_parts, y1 = footer(spec, th, W, H, m)
    if errors:
        return None
    body: list[str] = []
    arch = spec["archetype"]
    items = spec.get("items", [])
    gap = 36 * scale
    ch = y1 - y0
    if arch == "flow":
        n = len(items)
        bw = (W - 2 * m - (n - 1) * gap) / n
        bh = min(160 * scale, ch)
        by = y0 + (ch - bh) / 2
        for i, it in enumerate(items):
            bx = m + i * (bw + gap)
            parts = item_box(bx, by, bw, bh, it, th, accent, W)
            if parts is None:
                err(
                    f"items[{i}] {it['label']!r} does not fit a {n}-step flow — shorten it or use fewer steps"
                )
                return None
            body += parts
            if i < n - 1:
                body.append(
                    arrow(bx + bw + 4, by + bh / 2, bx + bw + gap - 4, by + bh / 2, th["muted"])
                )
    elif arch == "stack":
        n = len(items)
        g = gap * 0.5
        cap = (170 if any(it.get("detail") for it in items) else 120) * scale
        bh = min(cap, (ch - (n - 1) * g) / n)
        top = y0 + (ch - (n * bh + (n - 1) * g)) / 2
        for i, it in enumerate(items):
            by = top + i * (bh + g)
            parts = item_box(m, by, W - 2 * m, bh, it, th, accent, W)
            if parts is None:
                err(
                    f"items[{i}] {it['label']!r} does not fit a {n}-layer stack — shorten it or drop a layer"
                )
                return None
            body += parts
    elif arch == "hub":
        n = len(items)
        cx, cy = W / 2, y0 + ch / 2
        bw, bh = 250 * scale, 96 * scale
        rx, ry = (W - 2 * m - bw) / 2, (ch - bh) / 2
        if ry < bh * 1.2:
            err("hub needs more vertical room — remove the subtitle or footer")
            return None
        cw, chh = 220 * scale, 110 * scale
        import math

        for i, it in enumerate(items):
            ang = -math.pi / 2 + i * 2 * math.pi / n
            px_, py_ = cx + rx * math.cos(ang), cy + ry * math.sin(ang)
            body.append(
                arrow(
                    cx + (px_ - cx) * 0.32,
                    cy + (py_ - cy) * 0.32,
                    cx + (px_ - cx) * 0.72,
                    cy + (py_ - cy) * 0.72,
                    th["muted"],
                )
            )
            parts = item_box(px_ - bw / 2, py_ - bh / 2, bw, bh, it, th, accent, W)
            if parts is None:
                err(f"items[{i}] {it['label']!r} does not fit a hub spoke — shorten it")
                return None
            body += parts
        center = item_box(
            cx - cw / 2,
            cy - chh / 2,
            cw,
            chh,
            {"label": spec["center"], "accent": True},
            th,
            accent,
            W,
        )
        if center is None:
            err("center label does not fit — shorten it")
            return None
        body += center
    elif arch == "grid":
        axes = spec.get("axes")
        s = max(18, int(18 * scale))
        ax = max(text_w(lbl, s) for lbl in axes["y"]) + 20 * scale if axes else 0
        gw, gh = (W - 2 * m - ax - gap) / 2, (ch - (s * 1.6 if axes else 0) - gap) / 2
        x0 = m + ax
        for i, it in enumerate(items):
            col, row = i % 2, i // 2
            bx, by = x0 + col * (gw + gap), y0 + row * (gh + gap)
            parts = item_box(bx, by, gw, gh, it, th, accent, W)
            if parts is None:
                err(f"items[{i}] {it['label']!r} does not fit a quadrant — shorten it")
                return None
            body += parts
        if axes:
            gy = y0 + 2 * gh + gap + s * 1.3
            body.append(t(x0, gy, [axes["x"][0]], s, th["muted"]))
            body.append(t(W - m, gy, [axes["x"][1]], s, th["muted"], anchor="end"))
            body.append(t(m, y0 + 2 * gh + gap - s * 0.3, [axes["y"][0]], s, th["muted"]))
            body.append(t(m, y0 + s, [axes["y"][1]], s, th["muted"]))
    elif arch == "compare":
        cols = spec["columns"]
        n = len(cols)
        cw = (W - 2 * m - (n - 1) * gap) / n
        hsize = int(26 * scale)
        rsize = int(23 * scale)
        max_rows = max(len(c["rows"]) for c in cols)
        need = 24 * scale + hsize + 30 * scale + max_rows * rsize * 1.5 + rsize * 1.25 + 28 * scale
        col_h = min(ch, max(need, 0.45 * ch))
        y0 = y0 + (ch - col_h) / 2
        ch = col_h
        for i, c in enumerate(cols):
            cx0 = m + i * (cw + gap)
            is_accent = bool(c.get("accent"))
            body.append(box(cx0, y0, cw, ch, th, accent if is_accent else None))
            bar = accent if is_accent else th["line"]
            body.append(
                f'<rect x="{cx0:.0f}" y="{y0:.0f}" width="{cw:.0f}" height="{6 * scale:.0f}" rx="3" fill="{bar}"/>'
            )
            hl = wrap(c["heading"], hsize, cw - 32 * scale, bold=True, max_lines=1)
            if hl is None:
                err(f"columns[{i}].heading does not fit — shorten it")
                return None
            body.append(
                t(
                    cx0 + cw / 2,
                    y0 + 24 * scale + hsize,
                    hl,
                    hsize,
                    accent if is_accent else th["ink"],
                    anchor="middle",
                    bold=True,
                )
            )
            ry = y0 + 24 * scale + hsize + 30 * scale
            for j, r in enumerate(c["rows"]):
                rl = wrap(r, rsize, cw - 56 * scale, max_lines=2)
                if rl is None:
                    err(f"columns[{i}].rows[{j}] does not fit — shorten it")
                    return None
                ry += rsize * 1.5
                body.append(
                    f'<circle cx="{cx0 + 24 * scale:.0f}" cy="{ry - rsize * 0.35:.0f}" r="{4 * scale:.1f}" fill="{th["muted"]}"/>'
                )
                body.append(t(cx0 + 40 * scale, ry, rl, rsize, th["ink"]))
                ry += (len(rl) - 1) * rsize * 1.25
                if ry > y0 + ch - rsize:
                    err(f"columns[{i}] has too many rows for the canvas — cut to fewer rows")
                    return None
    title = escape(spec["title"])
    desc = escape(spec.get("subtitle") or spec["title"])
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="{FONT}">',
        f"<title>{title}</title><desc>{desc}</desc>",
        f'<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{th["muted"]}"/></marker></defs>',
        f'<rect width="{W}" height="{H}" fill="{th["bg"]}"/>',
        *top_parts,
        *body,
        *foot_parts,
        "</svg>",
    ]
    return "\n".join(parts) + "\n"


SCHEMA = {
    "archetype": "flow | compare | stack | hub | grid",
    "canvas": 'social (1200x630) | wide (1600x900) | square (1080x1080) | {"w": int, "h": int}',
    "theme": "light | dark (default light)",
    "accent": "#RRGGBB (default #2563EB); exactly one item/column may set accent: true",
    "title": f"required, <= {LIMITS['title']} chars, the one takeaway as a sentence",
    "subtitle": f"optional, <= {LIMITS['subtitle']} chars",
    "footer": f"optional, <= {LIMITS['footer']} chars (handle, source)",
    "items": f"flow 2-6 | stack 2-5 | hub 3-6 | grid exactly 4: [{{label <= {LIMITS['label']}, detail <= {LIMITS['detail']} (optional), accent: bool}}]",
    "center": f"hub only, <= {LIMITS['center']} chars",
    "columns": f"compare only, 2-3: [{{heading <= {LIMITS['heading']}, rows: 1-5 strings <= {LIMITS['row']}, accent: bool}}]",
    "axes": "grid only, optional: {x: [left, right], y: [bottom, top]}",
}

SAMPLES = {
    "flow": {
        "archetype": "flow",
        "title": "One artifact moves through three gates",
        "subtitle": "Build once, promote the same bytes",
        "footer": "@handle",
        "items": [
            {"label": "Commit", "detail": "main branch only"},
            {"label": "Build once", "detail": "immutable image", "accent": True},
            {"label": "Deploy", "detail": "promote, never rebuild"},
        ],
    },
    "stack": {
        "archetype": "stack",
        "title": "What an API gateway should own",
        "items": [
            {"label": "Auth"},
            {"label": "Rate limiting", "accent": True},
            {"label": "Routing"},
        ],
    },
    "hub": {
        "archetype": "hub",
        "title": "Everything routes through the event bus",
        "center": "Event bus",
        "items": [
            {"label": "Orders"},
            {"label": "Billing", "accent": True},
            {"label": "Inventory"},
            {"label": "Notifications"},
            {"label": "Analytics"},
        ],
    },
    "grid": {
        "archetype": "grid",
        "title": "Pick the store by access pattern",
        "axes": {
            "x": ["low write volume", "high write volume"],
            "y": ["simple queries", "complex queries"],
        },
        "items": [
            {"label": "Postgres", "detail": "default choice", "accent": True},
            {"label": "Kafka + views"},
            {"label": "SQLite"},
            {"label": "Cassandra"},
        ],
    },
    "compare": {
        "archetype": "compare",
        "title": "Three ways to talk to a service",
        "columns": [
            {"heading": "REST", "rows": ["Resources and verbs", "Caches well", "Over-fetching"]},
            {
                "heading": "GraphQL",
                "rows": ["One endpoint", "Typed schema", "N+1 risk"],
                "accent": True,
            },
            {
                "heading": "gRPC",
                "rows": ["Binary, fast", "Streaming", "Needs a proxy for browsers"],
            },
        ],
    },
}


def self_test() -> int:
    global errors
    for name, sample in SAMPLES.items():
        for canvas in CANVASES:
            errors = []
            spec = dict(sample, canvas=canvas)
            v = validate(spec)
            assert v is not None, (name, canvas, errors)
            svg = build(*v)
            assert svg and not errors, (name, canvas, errors)
            ET.fromstring(svg)  # noqa: S314 - our own generated markup, no DOCTYPE/entities possible
            assert "<title>" in svg and 'font-family="' in svg
    errors = []
    bad = dict(SAMPLES["flow"], items=SAMPLES["flow"]["items"] * 3)
    assert validate(bad) is None and any("needs 2-6 items" in e for e in errors), errors
    errors = []
    bad = dict(
        SAMPLES["flow"], items=[{"label": "x", "accent": True}, {"label": "y", "accent": True}]
    )
    assert validate(bad) is None and any(
        "exactly one element carries the accent" in e for e in errors
    ), errors
    errors = []
    bad = dict(SAMPLES["flow"], title="<script>alert(1)</script>")
    v = validate(bad)
    assert v is not None
    svg = build(*v)
    assert svg and "<script>" not in svg and "&lt;script&gt;" in svg
    errors = []
    bad = dict(
        SAMPLES["flow"], items=[{"label": "a very long label that cannot fit"} for _ in range(6)]
    )
    v = validate(bad)
    assert v is None and any("max 26" in e for e in errors), errors
    print("OK: self-test passed")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("spec", nargs="?", help="spec JSON file, or - for stdin")
    ap.add_argument("--out", type=Path, help="write the SVG here (default: stdout)")
    ap.add_argument("--schema", action="store_true", help="print the spec shape as JSON")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.schema:
        print(json.dumps(SCHEMA, indent=2))
        return 0
    if args.self_test:
        return self_test()
    if not args.spec:
        ap.error("spec is required (or --schema / --self-test)")
    try:
        raw = sys.stdin.read() if args.spec == "-" else Path(args.spec).read_text(encoding="utf-8")
        spec = json.loads(raw)
    except (OSError, ValueError) as exc:
        print(f"ERROR: cannot read spec: {exc}", file=sys.stderr)
        return 1
    v = validate(spec)
    svg = build(*v) if v else None
    if svg is None or errors:
        for line in errors:
            print(line, file=sys.stderr)
        print(f"FAIL: {len(errors)} error(s)")
        return 1
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(svg, encoding="utf-8")
        print(f"OK: wrote {args.out}")
    else:
        sys.stdout.write(svg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
