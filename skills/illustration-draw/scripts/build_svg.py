#!/usr/bin/env python3
"""build_svg.py — compile a small JSON spec into a minimalist illustration SVG.

The model decides *what* goes on the card (archetype, title, labels, the one
accent); this script decides *where* — every coordinate comes from a fixed
grid, so nothing can overlap by construction — and the design system decides
*how it looks* (palette, fonts, radius, borders, elevation, icon style).
Capacity is enforced: too many items or labels that would not fit at the
minimum font size are rejected with a message that says what to cut. Text is
XML-escaped. Every element carries `data-step` so diagram-animate can reveal
it in reading order. Pure stdlib.

Spec (JSON, see --schema):
    {"archetype": "flow|compare|stack|hub|grid|timeline",
     "canvas": "social|wide|square", "title": "...", "subtitle": "...",
     "footer": "...", "accent": "#RRGGBB" (optional override of the design system),
     "items": [{"label": "...", "detail": "...", "icon": "database", "accent": true}],
     "center": "..." (hub), "columns": [{"heading": "...", "rows": ["..."]}] (compare),
     "axes": {"x": ["left", "right"], "y": ["bottom", "top"]} (grid)}

The look comes from the design system: --design-system PATH,
$DIAGRAM_DESIGN_SYSTEM, ./design-system.md, else the built-in studio look.

Usage:
    python3 build_svg.py SPEC.json [--out FILE.svg] [--design-system PATH]   # - for stdin
    python3 build_svg.py --schema
    python3 build_svg.py --self-test

Exit 1 with `ERROR:` lines when the spec is invalid or over capacity.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import design_tokens as dt  # noqa: E402
import icons  # noqa: E402
from arch_svg import svg_defs  # noqa: E402

CANVASES = dt.CANVASES  # social 1200x627, square 1080x1080, wide 1920x1080
CAPACITY = {
    "flow": (2, 6),
    "stack": (2, 5),
    "hub": (3, 6),
    "grid": (4, 4),
    "compare": (2, 3),
    "timeline": (3, 12),
    "matrix": (2, 4),
}
LIMITS = {
    "title": 70,
    "subtitle": 110,
    "footer": 60,
    "label": 26,
    "detail": 60,
    "heading": 20,
    "row": 34,
    "center": 20,
    "eyebrow": 40,
}
HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
CHAR_W = 0.55  # em per glyph, regular
CHAR_WB = 0.6  # bold

errors: list[str] = []
SMALL_FAMILY: str | None = None  # set per build from type.small-family


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


class Style:
    """The design tokens, resolved into what this compiler paints with."""

    def __init__(self, tok: dict, accent: str | None = None):
        self.tok = tok
        c = tok["color"]
        self.c = dict(c, accent=accent or c["accent"])
        self.ty, self.sh = tok["type"], tok["shape"]
        self.lift = ' filter="url(#ds-lift)"' if tok["elevation"]["style"] != "flat" else ""
        self.mono = tok["type"]["small-family"] == "mono"
        self.marker = ' marker-end="url(#ds-arrow)"' if self.sh["arrow"] != "none" else ""
        self.bold = max(600, self.ty["label-weight"])
        self.k = self.ty["title-size"] / 40  # a theme's title scale
        self.u = 1.0  # set per canvas in build()
        self.square = False


def t(
    x: float,
    y: float,
    lines: list[str],
    size: float,
    fill: str,
    anchor: str = "start",
    weight: int = 400,
    track: float = 0.0,
    lh: float = 1.25,
) -> str:
    fw = f' font-weight="{weight}"' if weight != 400 else ""
    if (
        track >= 0.05 and SMALL_FAMILY
    ):  # tracked small labels take the mono voice (mono needs no tracking)
        ls = f' font-family="{escape(SMALL_FAMILY, {chr(34): "&quot;"})}"'
    else:
        ls = f' letter-spacing="{track * size:.2f}"' if track else ""
    step_y = size * lh
    if len(lines) == 1:
        return f'<text x="{x:.0f}" y="{y:.0f}" font-size="{size:.0f}" fill="{fill}" text-anchor="{anchor}"{fw}{ls}>{escape(lines[0])}</text>'
    spans = "".join(
        f'<tspan x="{x:.0f}" y="{y + i * step_y:.0f}">{escape(ln)}</tspan>'
        for i, ln in enumerate(lines)
    )
    return (
        f'<text font-size="{size:.0f}" fill="{fill}" text-anchor="{anchor}"{fw}{ls}>{spans}</text>'
    )


def box(x: float, y: float, w: float, h: float, st: Style, accent: bool) -> str:
    fill = st.c["accent"] if accent else st.c["surface"]
    border = (
        f' stroke="{st.c["border"]}" stroke-width="1"' if st.sh["card-border"] == "hairline" else ""
    )
    acc = ' data-accent="1"' if accent else ""
    return f'<rect x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="{h:.0f}" rx="{st.sh["radius"]}" fill="{fill}"{border}{st.lift}{acc}/>'


def arrow(x1: float, y1: float, x2: float, y2: float, st: Style) -> str:
    return (
        f'<path d="M{x1:.0f},{y1:.0f} L{x2:.0f},{y2:.0f}" fill="none" stroke="{st.c["line"]}" '
        f'stroke-width="{st.sh["stroke-strong"]}" stroke-linecap="round"{st.marker} data-draw="1"/>'
    )


def rim(cx: float, cy: float, w: float, h: float, tx: float, ty: float, pad: float):
    """Point where the ray from a box centre towards (tx, ty) leaves the box, plus pad."""
    dx, dy = tx - cx, ty - cy
    k = min(w / 2 / abs(dx) if dx else math.inf, h / 2 / abs(dy) if dy else math.inf)
    d = math.hypot(dx, dy)
    return cx + dx * k + dx / d * pad, cy + dy * k + dy / d * pad


def step(n: int, kind: str, parts: list[str]) -> str:
    return f'<g data-step="{n}" data-kind="{kind}">' + "".join(parts) + "</g>"


def validate(spec: dict, tok: dict) -> tuple[dict, Style, tuple[int, int]] | None:
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
    if spec.get("theme", "light") != "light":
        err(
            "theme is set by the design system now — point --design-system at a dark "
            "design-system.md instead of theme: dark"
        )
        return None
    accent = spec.get("accent")
    if accent is not None:
        if not HEX_RE.match(str(accent)):
            err(f"accent must be a 6-digit hex color, got {accent!r}")
            return None
        if dt.contrast(tok["color"]["accent-ink"], accent) < 4.5:
            err(
                f"accent {accent} is a fill behind {tok['color']['accent-ink']} text and "
                f"reaches only {dt.contrast(tok['color']['accent-ink'], accent):.1f}:1 (need 4.5)"
            )
            return None
    tk = spec.get("takeaway")
    if tk is not None and (not isinstance(tk, str) or len(tk) > 80):
        err("takeaway must be a sentence of at most 80 chars")
    if "scale" in spec:
        err(
            "scale (the complexity mosaic) was removed — drop it; badges and eyebrows carry the tiers"
        )
    for key in ("title", "subtitle", "footer", "center", "eyebrow"):
        v = spec.get(key)
        if v is not None and not isinstance(v, str):
            err(f"{key} must be a string")
            return None
        if isinstance(v, str) and len(v) > LIMITS[key]:
            err(
                f"{key} is {len(v)} chars (max {LIMITS[key]}) — cut it; the visual carries the detail"
            )
        if isinstance(v, str) and re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", v):
            err(f"{key} contains control characters")
    if not spec.get("title"):
        err(
            "title is required — it states the one takeaway (the SVG's accessible name and alt text)"
        )
    if not isinstance(spec.get("show_title", False), bool):
        err("show_title must be true or false")
    lo, hi = CAPACITY[arch]
    if arch == "matrix":
        rows = spec.get("rows")
        if not isinstance(rows, list) or not lo <= len(rows) <= hi:
            err(f"matrix needs {lo}-{hi} rows")
            return None
        accents = 0
        for i, r in enumerate(rows):
            if (
                not isinstance(r, dict)
                or not isinstance(r.get("header"), str)
                or not isinstance(r.get("cells"), list)
            ):
                err(f"rows[{i}] needs a header string and a cells list")
                return None
            if len(r["header"]) > LIMITS["heading"]:
                err(f"rows[{i}].header is {len(r['header'])} chars (max {LIMITS['heading']})")
            if not 1 <= len(r["cells"]) <= 4:
                err(f"rows[{i}] needs 1-4 cells")
            for j, cell in enumerate(r["cells"]):
                if not isinstance(cell, dict) or not isinstance(cell.get("label"), str):
                    err(f"rows[{i}].cells[{j}] needs a label")
                    continue
                for key in ("label", "detail", "eyebrow"):
                    v = cell.get(key)
                    lim = LIMITS["eyebrow" if key == "eyebrow" else key]
                    if v is not None and (not isinstance(v, str) or len(v) > lim):
                        err(f"rows[{i}].cells[{j}].{key} must be a string of at most {lim} chars")
                accents += bool(cell.get("accent"))
        if accents > 1:
            err("more than one cell marked accent — exactly one element carries the accent")
    elif arch == "compare":
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
            if c.get("badge") is not None and (
                not isinstance(c["badge"], str) or not 1 <= len(c["badge"]) <= 2
            ):
                err(f"columns[{i}].badge must be 1-2 characters (S, M, L, 1, 2…)")
            if c.get("eyebrow") is not None and (
                not isinstance(c["eyebrow"], str) or len(c["eyebrow"]) > 24
            ):
                err(f"columns[{i}].eyebrow must be a string of at most 24 chars")
            if not 1 <= len(c["rows"]) <= 5:
                err(f"columns[{i}] needs 1-5 rows")
            for j, r in enumerate(c["rows"]):
                if not isinstance(r, str) or len(r) > LIMITS["row"]:
                    err(f"columns[{i}].rows[{j}] must be a string of at most {LIMITS['row']} chars")
        if sum(bool(c.get("accent")) for c in cols) > 1:
            err("more than one column marked accent — exactly one element carries the accent")
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
            chips = it.get("chips")
            if chips is not None and not (
                isinstance(chips, list)
                and len(chips) <= 3
                and all(isinstance(v, str) and 0 < len(v) <= 24 for v in chips)
            ):
                err(f"items[{i}].chips must be up to 3 short strings (<= 24 chars)")
            ic = it.get("icon")
            if ic is not None and ic not in icons.LINE:
                err(f"items[{i}].icon {ic!r} is unknown; known: {', '.join(icons.names())}")
            accents += 1 if it.get("accent") else 0
        if accents > 1:
            err(
                f"{accents} items marked accent — exactly one element carries the accent (the takeaway)"
            )
        if arch == "hub" and not isinstance(spec.get("center"), str):
            err("hub needs a center label")
        if spec.get("layout", "radial") not in ("radial", "bus"):
            err('layout must be "radial" or "bus" (hub only)')
        if arch == "grid":
            axes = spec.get("axes")
            if axes is not None and not (
                isinstance(axes, dict)
                and all(isinstance(axes.get(k), list) and len(axes[k]) == 2 for k in ("x", "y"))
            ):
                err('grid axes must be {"x": [left, right], "y": [bottom, top]}')
    if errors:
        return None
    return spec, Style(tok, accent), size


def header(spec: dict, st: Style, W: int, m: float) -> tuple[list[str], float]:
    """Eyebrow + title + subtitle; returns (svg parts, y where the body may start)."""
    u, c, ty = st.u, st.c, st.ty
    parts: list[str] = []
    y = 56 * u
    if spec.get("eyebrow"):
        es = 16 * u
        parts.append(t(m, y + es, [spec["eyebrow"].upper()], es, c["muted"], weight=600, track=0.1))
        y += es + 16 * u
    sizes = [int(v * u * st.k) for v in (46, 44, 40, 36)]
    ft = fit(spec["title"], sizes, W - 2 * m, bold=True, max_lines=2)
    if st.square:  # a square has height to spare: the largest size that wraps into two lines
        ft = next((f for z in sizes if (f := fit(spec["title"], [z], W - 2 * m, True, 2))), ft)
    if ft is None:
        err("title does not fit in two lines even at the smallest size — shorten it")
        return parts, 0
    size, lines = ft
    y += size * 0.9
    parts.append(
        t(
            m,
            y,
            lines,
            size,
            c["ink"],
            weight=ty["title-weight"],
            track=ty["title-tracking"],
            lh=1.12,
        )
    )
    y += (len(lines) - 1) * size * 1.12
    if spec.get("subtitle"):
        sub = fit(spec["subtitle"], [int(21 * u), int(19 * u)], W - 2 * m, max_lines=2)
        if sub is None:
            err("subtitle does not fit — shorten it")
            return parts, 0
        ssize, slines = sub
        y += ssize * 1.75
        parts.append(t(m, y, slines, ssize, c["lede"], lh=1.35))
        y += (len(slines) - 1) * ssize * 1.35
    return parts, y + 40 * u


def footer(spec: dict, st: Style, W: int, H: int, m: float) -> tuple[list[str], float]:
    u = st.u
    if not spec.get("footer") or not spec.get("show_title"):  # a handle/source is a slide device
        return [], H - 48 * u
    size = 16 * u
    return [
        t(W - m, H - 40 * u, [spec["footer"]], size, st.c["muted"], anchor="end", weight=500)
    ], H - 40 * u - size * 2.2


def mix(a: str, b: str, k: float) -> str:
    """Solid blend of hex a toward hex b by k (0..1) — no translucency for the lint to guess at."""
    ca = [int(a[i : i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i : i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * k):02X}" for x, y in zip(ca, cb, strict=True))


def inverted(st: Style) -> bool:
    """True when the highlight is a dark card (paper-line, coral) rather than a light marker."""
    return dt.luminance(st.c["accent"]) < 0.2


LABEL_SIZES = (28, 26, 24, 22, 20, 18)
DETAIL_SIZES = (18, 17, 16, 15, 14)


def card_pad(w: float, u: float) -> float:
    return (28 if w >= 300 * u else 24 if w >= 200 * u else 16) * u


def card(
    x: float,
    y: float,
    w: float,
    h: float,
    it: dict,
    st: Style,
    num: int | None,
    label_px: float | None = None,
    detail_px: float | None = None,
) -> list[str] | None:
    """The shared card lockup: step number top-left, icon (in a tile when the design
    system says so) top-right, label and detail anchored to the bottom-left.
    None if the content cannot fit."""
    u, c = st.u, st.c
    acc = bool(it.get("accent"))
    ink = c["accent-ink"] if acc else c["ink"]
    mut = c["accent-muted"] if acc else c["muted"]
    pad = card_pad(w, u)
    parts = [box(x, y, w, h, st, acc)]
    style = st.tok["icon"]["style"]
    icon = it.get("icon") if style != "none" else None
    ns = 16 * u
    top = y + pad
    used = top
    if num and st.sh["badge-shape"] == "square":  # S/M/L-style square badge
        bs = 30 * u
        parts.append(
            f'<rect x="{x + pad:.0f}" y="{top:.0f}" width="{bs:.0f}" height="{bs:.0f}" fill="{c["badge"]}"'
            f"{' stroke=' + chr(34) + c['accent-ink'] + chr(34) + ' stroke-width=' + chr(34) + '1.5' + chr(34) if acc and c['badge'].upper() == c['accent'].upper() else ''}/>"
        )
        parts.append(
            t(
                x + pad + bs / 2,
                top + bs / 2 + ns * 0.36,
                [str(num)],
                ns,
                c["badge-ink"],
                "middle",
                700,
            )
        )
        used = top + bs
    elif num and style == "none":  # no icons (coral): the number becomes a badge with a halo
        r = 14 * u
        parts.append(
            f'<circle cx="{x + pad + r:.0f}" cy="{top + r:.0f}" r="{r:.1f}" fill="{c["badge"]}" '
            f'stroke="{c["accent-ink"] if acc else c["canvas"]}" stroke-width="{2 * u:.1f}"/>'
        )
        parts.append(
            t(x + pad + r, top + r + ns * 0.34, [str(num)], ns, c["badge-ink"], "middle", 700)
        )
        used = top + 2 * r
    elif num:
        parts.append(t(x + pad, top + ns, [f"{num:02d}"], ns, mut, weight=600, track=0.08))
        used = top + ns
    if icon:
        tiled = style == "line" and st.tok["icon"]["tile"]
        ts = (48 if tiled else 44) * u
        tx0 = x + w - pad - ts
        if tiled and not (acc and inverted(st)):
            tile, op = (mix(c["accent"], "#FFFFFF", 0.5), "") if acc else (c["tile"], "")
            if not acc and tile.upper() == c["surface"].upper():
                tile = c["subtle"]
            parts.append(
                f'<rect x="{tx0:.0f}" y="{top:.0f}" width="{ts:.0f}" height="{ts:.0f}" '
                f'rx="{st.sh["radius-small"]}" fill="{tile}"{op}/>'
            )
        isz = 28 * u if tiled else ts
        parts.append(
            icons.icon_svg(
                icon,
                tx0 + (ts - isz) / 2,
                top + (ts - isz) / 2,
                isz,
                ink if acc else c["icon"],
                st.tok["icon"]["stroke"],
                "line" if tiled else style,
                c["accent"] if acc else c["surface"],
            )
        )
        used = top + ts
    inner = w - 2 * pad
    sizes = [label_px] if label_px else [int(v * u) for v in LABEL_SIZES]
    lab = fit(it["label"], sizes, inner, bold=True)
    if lab is None:
        return None
    ls, llines = lab
    det = None
    if it.get("detail"):
        dsizes = [detail_px] if detail_px else [int(v * u) for v in DETAIL_SIZES]
        det = fit(it["detail"], dsizes, inner, max_lines=3)
        if det is None:
            return None
    block = len(llines) * ls * 1.15 + (8 * u + len(det[1]) * det[0] * 1.4 if det else 0)
    bottom = y + h - pad
    if it.get("chips"):  # mono identifier chips along the bottom edge
        cs, chh = 16 * u, 28 * u
        cx_ = x + pad
        for chip in it["chips"]:
            cw_ = text_w(chip, cs) + 16 * u
            if cx_ + cw_ > x + w - pad:
                return None
            parts.append(
                f'<rect x="{cx_:.0f}" y="{bottom - chh:.0f}" width="{cw_:.0f}" height="{chh:.0f}" '
                f'rx="{min(4 * u, st.sh["radius-small"]):.0f}" fill="{mix(c["accent"], c["accent-ink"], 0.16) if acc else c["group"]}"/>'
            )
            parts.append(
                t(
                    cx_ + 8 * u,
                    bottom - chh / 2 + cs * 0.36,
                    [chip],
                    cs,
                    ink,
                    weight=500,
                    track=0.05,
                )
            )
            cx_ += cw_ + 6 * u
        bottom -= chh + 14 * u
    if used == top and not det:  # a bare label: centre it instead of stranding it at the bottom
        bottom = y + (h + block) / 2
    if bottom - block < used + 12 * u:
        return None
    ly = bottom - block + ls * 0.92
    parts.append(t(x + pad, ly, llines, ls, ink, weight=st.bold, track=-0.01, lh=1.15))
    if det:
        dy = ly + (len(llines) - 1) * ls * 1.15 + 8 * u + det[0] * 1.15
        parts.append(t(x + pad, dy, det[1], det[0], mut, lh=1.4))
    return parts


def pill_bg(cx: float, base: float, lines: list[str], size: float, st: Style) -> str:
    """Accent capsule behind a (possibly two-line) centred label whose first baseline is `base`."""
    w = max(text_w(ln, size, True) for ln in lines) + 28 * st.u
    h = size * 1.2 * len(lines) + 12 * st.u
    y = base - size * 0.95 - 6 * st.u
    rx = h / 2 if len(lines) == 1 else 12 * st.u
    return (
        f'<rect x="{cx - w / 2:.0f}" y="{y:.0f}" width="{w:.0f}" height="{h:.0f}" rx="{rx:.0f}" '
        f'fill="{st.c["accent"]}" data-accent="1"/>'
    )


def compare_square(spec: dict, st: Style, W: int, m: float, y0: float, y1: float) -> list[str]:
    """The square-canvas compare: each column becomes a full-width row card — its heading
    (badge, eyebrow) in a band on the left, its rows as a list on the right."""
    u, c = st.u, st.c
    cols = spec["columns"]
    n = len(cols)
    out: list[str] = []
    gap = 20 * u
    ch = min((y1 - y0 - (n - 1) * gap) / n, 230 * u)
    top = y0 + (y1 - y0 - n * ch - (n - 1) * gap) / 2
    lw = (W - 2 * m) * 0.36
    pad = 24 * u
    rsize = 22 * u
    heads = [
        fit(
            col["heading"], [int(v * u) for v in (30, 27, 24)], lw - 2 * pad, bold=True, max_lines=2
        )
        for col in cols
    ]
    head_size = min(h[0] for h in heads) if all(heads) else None  # one heading size for every row
    for i, col in enumerate(cols):
        y = top + i * (ch + gap)
        acc = bool(col.get("accent"))
        ink = c["accent-ink"] if acc else c["ink"]
        mut = c["accent-muted"] if acc else c["muted"]
        band = c["accent"] if acc else c["tile"]
        if band.upper() == c["surface"].upper() and not acc:
            band = c["subtle"] if dt.contrast(c["ink"], c["subtle"]) >= 4.5 else c["surface"]
        parts = [
            box(m, y, W - 2 * m, ch, st, acc),
            f'<rect x="{m:.0f}" y="{y:.0f}" width="{lw:.0f}" height="{ch:.0f}" fill="{band}"/>',
        ]
        hy = y + ch / 2
        if head_size is None:
            err(f"columns[{i}].heading does not fit — shorten it")
            return []
        hs, hl = head_size, wrap(col["heading"], head_size, lw - 2 * pad, True, 2)
        if col.get("badge") or col.get("eyebrow"):
            bits = []
            if col.get("badge"):
                bits.append(f"{col['badge']} ·")
            if col.get("eyebrow"):
                bits.append(col["eyebrow"])
            parts.append(
                t(m + pad, hy - hs * 0.9, [" ".join(bits)], 17 * u, mut, weight=600, track=0.06)
            )
            hy += hs * 0.5
        parts.append(
            t(
                m + pad,
                hy + hs * 0.36 - (len(hl) - 1) * hs * 0.6,
                hl,
                hs,
                ink,
                weight=st.bold,
                lh=1.2,
            )
        )
        rows = col["rows"]
        pitch = min(ch / (len(rows) + 0.6), 44 * u)
        ry = y + (ch - pitch * len(rows)) / 2
        rx = m + lw + pad
        rw = W - m - pad - rx
        for j, row in enumerate(rows):
            rl = fit(row, [rsize, rsize * 0.9, rsize * 0.8], rw - 22 * u, max_lines=1)
            if rl is None:
                err(f"columns[{i}].rows[{j}] does not fit — shorten it")
                return []
            mid = ry + j * pitch + pitch / 2
            parts.append(
                f'<rect x="{rx:.0f}" y="{mid - 4 * u:.0f}" width="{8 * u:.0f}" height="{8 * u:.0f}" '
                f'fill="{c["accent-ink"] if acc else c["badge"]}"/>'
            )
            parts.append(
                t(rx + 22 * u, mid + rl[0] * 0.35, rl[1], rl[0], c["ink"] if not acc else ink)
            )
        out.append(step(i + 1, "node", parts))
    return out


def timeline_vertical(
    items: list[dict], st: Style, W: int, m: float, y0: float, y1: float
) -> list[str]:
    """The square-canvas timeline: one top-to-bottom track, dates right-aligned to its left,
    labels to its right; solid up to the highlight, dashed after, arrowhead at the bottom."""
    u, c = st.u, st.c
    n = len(items)
    lx = m + 150 * u
    ya, yb = y0 + 24 * u, y1 - 36 * u
    pitch = (yb - ya) / max(n - 1, 1)
    hi = next((i for i, it in enumerate(items) if it.get("accent")), None)
    r = (9 if n <= 6 else 7) * u
    sw = st.sh["stroke-strong"]
    avail = W - m - (lx + 32 * u)
    lsz = [
        int(v * u) for v in ((34, 30, 28) if n <= 5 else (28, 26, 24) if n <= 8 else (22, 20, 18))
    ]
    lsz = [z for z in lsz if z <= pitch * 0.62] or [int(pitch * 0.55)]
    dsz = min(18 * u, pitch * 0.4)
    ys = [ya + i * pitch for i in range(n)]

    def seg(a_: float, b_: float, dashed: bool, marker: bool = False) -> str:
        dash = f' stroke-dasharray="{6 * u:.0f} {6 * u:.0f}"' if dashed else ' data-draw="1"'
        return (
            f'<path d="M{lx:.0f},{a_:.0f} V{b_:.0f}" fill="none" stroke="{c["line"]}" '
            f'stroke-width="{sw}" stroke-linecap="round"{dash}{st.marker if marker else ""}/>'
        )

    segs = []
    for i in range(1, n):
        segs.append(step(i + 1, "edge", [seg(ys[i - 1] + r, ys[i] - r, hi is not None and i > hi)]))
    segs.append(step(n, "edge", [seg(ys[-1] + r, y1 + 4 * u, hi is not None and hi < n - 1, True)]))
    nodes = []
    for i, (it, py) in enumerate(zip(items, ys, strict=True)):
        acc = i == hi
        rr = r * 1.55 if acc else r
        lab = fit(it["label"], lsz, avail, bold=True, max_lines=1)
        if lab is None:
            err(f"items[{i}] {it['label']!r} does not fit a square timeline — shorten it")
            return []
        size, lines = lab
        base = py + size * 0.36
        x = lx + 32 * u
        parts = [
            f'<circle cx="{lx:.0f}" cy="{py:.0f}" r="{rr:.1f}" fill="{c["accent"] if acc else c["surface"]}" '
            f'stroke="{c["ink"]}" stroke-width="{sw}"{" data-accent=" + chr(34) + "1" + chr(34) if acc else ""}/>'
        ]
        if it.get("detail"):
            parts.append(
                t(
                    lx - 28 * u,
                    py + dsz * 0.36,
                    [it["detail"].upper()],
                    dsz,
                    c["muted"],
                    "end",
                    600,
                    0.06,
                )
            )
        if acc:
            parts.append(pill_bg(x + text_w(lines[0], size, True) / 2, base, lines, size, st))
        parts.append(
            t(
                x,
                base,
                lines,
                size,
                c["accent-ink"] if acc else c["ink"],
                "start",
                700 if acc else st.bold,
                lh=1.2,
            )
        )
        nodes.append(step(i + 1, "node", parts))
    return segs + nodes


def timeline(items: list[dict], st: Style, W: int, m: float, y0: float, y1: float) -> list[str]:
    """One left-to-right track with an arrowhead: solid up to the highlighted milestone,
    dashed after it (done vs planned). 3-6 milestones put every label above the line;
    7-12 alternate above and below with short leaders. Equal pitch by index, not by date."""
    u, c = st.u, st.c
    n = len(items)
    alt = n > 6
    lsz = [
        int(v * u) for v in ((28, 26, 24) if n <= 4 else (24, 22, 20) if not alt else (21, 20, 18))
    ]
    # inset the ends by half the end labels so they never cross the margins
    half = [
        min(text_w(it["label"], lsz[0], True), 240 * u) / 2 + 6 * u for it in (items[0], items[-1])
    ]
    x0, x1 = m + max(44 * u, half[0]), W - m - max(44 * u, half[1])
    pitch = (x1 - x0) / (n - 1)
    ly = y0 + (y1 - y0) * (0.46 if alt else 0.42)  # sit closer to the title
    hi = next((i for i, it in enumerate(items) if it.get("accent")), None)
    r = (9 if n <= 4 else 7) * u
    sw = st.sh["stroke-strong"]
    slot = (2 * pitch if alt else pitch) - 20 * u
    dsz = 16 * u
    segs, nodes = [], []

    def seg(a: float, b: float, dashed: bool, marker: bool = False) -> str:
        dash = f' stroke-dasharray="{6 * u:.0f} {6 * u:.0f}"' if dashed else ' data-draw="1"'
        mk = st.marker if marker else ""
        return (
            f'<path d="M{a:.0f},{ly:.0f} H{b:.0f}" fill="none" stroke="{c["line"]}" '
            f'stroke-width="{sw}" stroke-linecap="round"{dash}{mk}/>'
        )

    xs = [x0 + i * pitch for i in range(n)]
    segs.append(step(1, "edge", [seg(m, xs[0] - r, False)]))
    for i in range(1, n):
        planned = hi is not None and i > hi
        segs.append(step(i + 1, "edge", [seg(xs[i - 1] + r, xs[i] - r, planned)]))
    segs.append(
        step(n, "edge", [seg(xs[-1] + r, W - m + 6 * u, hi is not None and hi < n - 1, True)])
    )
    for i, (it, px) in enumerate(zip(items, xs, strict=True)):
        acc = i == hi
        rr = r * 1.55 if acc else r
        dot = (
            f'<circle cx="{px:.0f}" cy="{ly:.0f}" r="{rr:.1f}" fill="{c["accent"] if acc else c["surface"]}" '
            f'stroke="{c["ink"]}" stroke-width="{sw}"{" data-accent=" + chr(34) + "1" + chr(34) if acc else ""}/>'
        )
        lab = fit(it["label"], lsz, slot, bold=True, max_lines=2)
        if lab is None:
            err(f"items[{i}] {it['label']!r} does not fit a {n}-milestone timeline — shorten it")
            return []
        size, lines = lab
        above = not alt or i % 2 == 0
        parts = [dot]
        weight = 700 if acc else st.bold
        ink = c["accent-ink"] if acc else c["ink"]
        gap = rr + (40 * u if alt else 18 * u)
        date = it.get("detail")
        if above:
            base = ly - gap - (len(lines) - 1) * size * 1.2
            if date:
                dy = base - size * 1.05 - (8 * u if acc else 0)  # clear the highlight pill
                parts.append(t(px, dy, [date.upper()], dsz, c["muted"], "middle", 600, 0.06))
            if acc:
                parts.append(pill_bg(px, base, lines, size, st))
            parts.append(t(px, base, lines, size, ink, "middle", weight, lh=1.2))
            if alt:
                parts.append(
                    f'<path d="M{px:.0f},{ly - rr - 4 * u:.0f} V{ly - gap + 8 * u:.0f}" stroke="{c["subtle"]}" stroke-width="1"/>'
                )
            top = base - size - (dsz * 1.6 if date else 0)
            if top < y0 - 4 * u:
                err(
                    "the timeline labels run into the title — use fewer milestones or shorter labels"
                )
                return []
        else:
            first = ly + gap + dsz
            if date:
                parts.append(t(px, first, [date.upper()], dsz, c["muted"], "middle", 600, 0.06))
                first += size * 1.3
            else:
                first += size - dsz
            if acc:
                parts.append(pill_bg(px, first, lines, size, st))
            parts.append(t(px, first, lines, size, ink, "middle", weight, lh=1.2))
            parts.append(
                f'<path d="M{px:.0f},{ly + rr + 4 * u:.0f} V{ly + gap - 8 * u:.0f}" stroke="{c["subtle"]}" stroke-width="1"/>'
            )
            if first + (len(lines) - 1) * size * 1.2 > y1 + 8 * u:
                err(
                    "the timeline labels run off the canvas — use fewer milestones or shorter labels"
                )
                return []
        if not alt and date:  # dates sit under the line when every label is above
            parts = [dot]
            if acc:
                parts.append(pill_bg(px, base, lines, size, st))
            parts.append(t(px, base, lines, size, ink, "middle", weight, lh=1.2))
            parts.append(
                t(px, ly + rr + 30 * u, [date.upper()], dsz, c["muted"], "middle", 600, 0.06)
            )
        nodes.append(step(i + 1, "node", parts))
    return segs + nodes


def build(spec: dict, st: Style, size: tuple[int, int]) -> str | None:
    """An inline figure (no drawn title, no canvas asked for) is as tall as its content plus
    the margins; a slide or an explicit canvas keeps the fixed preset size."""
    svg = build_fixed(spec, st, size)
    if not svg or spec.get("show_title") or "canvas" in spec:
        return svg
    W, H = size
    u = st.u
    box = content_box(svg, W, H)
    if box is None:
        return svg
    fit_h = int(box[3] - box[1] + 64 * u + 48 * u + 8 * u)
    if fit_h >= H - 8:
        return svg
    mark = len(errors)
    tight = _build(spec, st, (W, fit_h), u)
    if tight and len(errors) == mark:
        return tight.replace(
            "<svg ", '<svg data-inline="1" ', 1
        )  # lint: no delivery preset expected
    del errors[mark:]  # the layout needs the room: keep the preset height
    return svg


TRANSLATE = re.compile(r"translate\(\s*([-\d.]+)[ ,]+([-\d.]+)\s*\)(?:\s*scale\(\s*([\d.]+))?")


def content_box(svg: str, W: float, H: float) -> tuple[float, float, float, float] | None:
    """Rough extent of everything drawn except the full-canvas background."""
    ys: list[float] = []
    xs: list[float] = []

    def walk(e: ET.Element) -> None:
        tag = e.tag.rsplit("}", 1)[-1]
        if tag in ("defs", "clipPath", "title", "desc", "style"):
            return
        m_ = TRANSLATE.match(e.get("transform", ""))
        if m_:
            x, y, k = float(m_.group(1)), float(m_.group(2)), float(m_.group(3) or 1)
            xs.extend((x, x + 24 * k))
            ys.extend((y, y + 24 * k))
            return
        try:
            if tag == "rect" and not (
                float(e.get("width", 0)) >= W - 1 and float(e.get("height", 0)) >= H - 1
            ):
                x, y = float(e.get("x", 0)), float(e.get("y", 0))
                xs.extend((x, x + float(e.get("width", 0))))
                ys.extend((y, y + float(e.get("height", 0))))
            elif tag == "text":
                size = float(e.get("font-size", 14))
                ys.extend((float(e.get("y", 0)) - size, float(e.get("y", 0)) + size * 0.3))
            elif tag == "circle":
                cy, r = float(e.get("cy", 0)), float(e.get("r", 0))
                ys.extend((cy - r, cy + r))
            elif tag == "path" and not re.search(r"[a-zHV]", e.get("d", "")):
                nums = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", e.get("d", ""))]
                ys.extend(nums[1::2])
            elif tag == "path":  # H/V/relative paths: take the absolute y values we can read
                for mv in re.finditer(r"[MLV]\s*(-?[\d.]+)(?:[ ,](-?[\d.]+))?", e.get("d", "")):
                    if mv.group(0)[0] == "V":
                        ys.append(float(mv.group(1)))
                    elif mv.group(2):
                        ys.append(float(mv.group(2)))
        except ValueError:
            pass
        for k in e:
            walk(k)

    walk(ET.fromstring(svg))  # noqa: S314 - our own generated markup
    return (min(xs or [0]), min(ys), max(xs or [W]), max(ys)) if ys else None


def build_fixed(spec: dict, st: Style, size: tuple[int, int]) -> str | None:
    """Type/space unit = the tighter axis, so panoramas keep their scale. A square or portrait
    canvas has height to spare: try larger units first and keep the first that fits."""
    W, H = size
    for u in (W / 880, W / 1000) if H >= 0.9 * W else ():
        mark = len(errors)
        svg = _build(spec, st, size, u)
        if svg and len(errors) == mark:
            return svg
        del errors[mark:]
    return _build(spec, st, size, min(W / 1200, H / 630))


def _build(spec: dict, st: Style, size: tuple[int, int], unit: float) -> str | None:
    global SMALL_FAMILY
    SMALL_FAMILY = st.ty["mono"] if st.mono else None
    W, H = size
    st.u = unit
    st.square = H >= 0.9 * W
    u = st.u
    m = 64 * u
    c = st.c
    # inline by default: the article around the figure carries the heading, so the title and
    # subtitle only become <title>/<desc>; show_title draws them for a slide or a social card
    top_parts, y0 = header(spec, st, W, m) if spec.get("show_title") else ([], m)
    foot_parts, y1 = footer(spec, st, W, H, m)
    take_parts: list[str] = []
    if spec.get("takeaway"):  # a full-width ink bar that states the conclusion
        bar_h, ts_ = 48 * u, 19 * u
        by_ = y1 - bar_h
        y1 = by_ - 20 * u
        dark = dt.luminance(c["canvas"]) < 0.2  # an ink bar would glare on a dark canvas
        bar_fill, bar_ink = (c["tile"], c["ink"]) if dark else (c["ink"], c["canvas"])
        take_parts = [
            f'<rect x="{m:.0f}" y="{by_:.0f}" width="{W - 2 * m:.0f}" height="{bar_h:.0f}" '
            f'rx="{st.sh["radius-small"]}" fill="{bar_fill}"/>',
            t(
                m + 20 * u,
                by_ + bar_h / 2 + ts_ * 0.36,
                [spec["takeaway"]],
                ts_,
                bar_ink,
                weight=600,
            ),
        ]
    if errors:
        return None
    body: list[str] = []
    arch = spec["archetype"]
    items = spec.get("items", [])
    ch = y1 - y0
    numbered = spec.get("numbered", arch == "flow")
    if arch == "flow":
        n = len(items)
        disc = st.sh["flow-connector"] == "disc"
        gap = (56 if disc else 40 if n <= 4 else 28) * u
        bw = (W - 2 * m - (n - 1) * gap) / n
        rich = any(it.get("icon") or it.get("detail") for it in items)
        cap = (264 if n <= 3 else 250 if n == 4 else 230) if rich else 150
        bh = min(cap * u, ch)
        if H >= 0.9 * W:  # square: tall portrait cards use the height instead of a band
            bh = min(max(bh, ch * 0.62), ch)
        by = y0 + (ch - bh) / 2
        inner = bw - 2 * card_pad(bw, u)
        fits = [
            fit(it["label"], [int(v * u) for v in LABEL_SIZES], inner, bold=True) for it in items
        ]
        common = min(f[0] for f in fits) if all(fits) else None  # one label size per row
        dfits = [
            fit(it["detail"], [int(v * u) for v in DETAIL_SIZES], inner, max_lines=3)
            for it in items
            if it.get("detail")
        ]
        dcommon = min(f[0] for f in dfits) if dfits and all(dfits) else None  # and one detail size
        for i, it in enumerate(items):
            bx = m + i * (bw + gap)
            parts = card(bx, by, bw, bh, it, st, i + 1 if numbered else None, common, dcommon)
            if parts is None:
                err(
                    f"items[{i}] {it['label']!r} does not fit a {n}-step flow — shorten it or use fewer steps"
                )
                return None
            if i and st.sh["flow-connector"] == "disc":  # a filled disc with a white arrow
                r = min(gap / 2 - 2 * u, 20 * u)
                cx, cy = bx - gap / 2, by + bh / 2
                a = r * 0.42
                disc = (
                    f'<g data-kind="badge"><circle cx="{cx:.0f}" cy="{cy:.0f}" r="{r:.1f}" fill="{c["ink"]}"/>'
                    f'<path d="M{cx - a:.1f},{cy:.1f} H{cx + a:.1f} M{cx + a * 0.3:.1f},{cy - a * 0.7:.1f} '
                    f'L{cx + a:.1f},{cy:.1f} L{cx + a * 0.3:.1f},{cy + a * 0.7:.1f}" fill="none" '
                    f'stroke="{c["canvas"] if dt.contrast(c["canvas"], c["ink"]) >= 3 else c["surface"]}" '
                    f'stroke-width="{2 * u:.1f}" stroke-linecap="round" stroke-linejoin="round"/></g>'
                )
                body.append(step(i + 1, "edge", [disc]))
            elif i:
                body.append(
                    step(
                        i + 1,
                        "edge",
                        [arrow(bx - gap + 8 * u, by + bh / 2, bx - 9 * u, by + bh / 2, st)],
                    )
                )
            body.append(step(i + 1, "node", parts))
    elif arch == "stack":
        n = len(items)
        # one card with rows; the highlighted row is a fill clipped to the card's corners
        bh = min((92 if any(it.get("detail") for it in items) else 84) * u, ch / n)
        square = H >= 0.9 * W
        if square:  # taller rows fill the square instead of leaving its lower half empty
            bh = min(ch * 0.8 / n, 190 * u)
        total_h = n * bh
        titled = bool(spec.get("show_title"))  # under a title it sits high; inline it centres
        top = y0 + ((ch - total_h) / 2 if square or not titled else min((ch - total_h) / 2, 48 * u))
        bw = W - 2 * m
        clip = "ds-stack-clip"
        body.append(
            step(
                1,
                "group",
                [
                    f'<clipPath id="{clip}"><rect x="{m:.0f}" y="{top:.0f}" width="{bw:.0f}" '
                    f'height="{total_h:.0f}" rx="{st.sh["radius"]}"/></clipPath>',
                    box(m, top, bw, total_h, st, False),
                ],
            )
        )
        for i, it in enumerate(items):
            by = top + i * bh
            acc = bool(it.get("accent"))
            ink = c["accent-ink"] if acc else c["ink"]
            mut = c["accent-muted"] if acc else c["muted"]
            pad = 28 * u
            parts = (
                [
                    f'<rect x="{m:.0f}" y="{by:.0f}" width="{bw:.0f}" height="{bh:.0f}" '
                    f'fill="{c["accent"]}" clip-path="url(#{clip})" data-accent="1"/>'
                ]
                if acc
                else []
            )
            if i < n - 1 and not acc and not items[i + 1].get("accent"):
                parts.append(
                    f'<path d="M{m + pad:.0f},{by + bh:.0f} H{m + bw - pad:.0f}" '
                    f'stroke="{c["subtle"]}" stroke-width="1"/>'
                )
            ns = 16 * u
            parts.append(
                t(
                    m + pad,
                    by + bh / 2 + ns * 0.35,
                    [f"{i + 1:02d}"],
                    ns,
                    mut,
                    weight=600,
                    track=0.08,
                )
            )
            lx = m + pad + 48 * u
            lab = fit(
                it["label"],
                [int(v * u) for v in (26, 24, 22, 20)],
                bw * 0.45,
                bold=True,
                max_lines=1,
            )
            if lab is None:
                err(f"items[{i}] {it['label']!r} does not fit a stack bar — shorten it")
                return None
            ls, ll = lab
            parts.append(t(lx, by + bh / 2 + ls * 0.35, ll, ls, ink, weight=st.bold, track=-0.01))
            if it.get("detail"):
                det = fit(it["detail"], [int(v * u) for v in (18, 17, 16)], bw * 0.45, max_lines=1)
                if det is None:
                    err(f"items[{i}].detail does not fit a stack bar — shorten it")
                    return None
                parts.append(
                    t(m + bw - pad, by + bh / 2 + det[0] * 0.35, det[1], det[0], mut, anchor="end")
                )
            body.append(step(i + 1, "node", parts))
    elif arch == "hub" and spec.get("layout") == "bus":
        n = len(items)
        cy = y0 + ch / 2
        bar_h = 60 * u
        bw, bh = 210 * u, 76 * u
        reach = 56 * u
        if ch < bar_h + 2 * (bh + reach):
            err("bus hub needs more vertical room — remove the subtitle or footer")
            return None
        bar = [
            f'<rect x="{m:.0f}" y="{cy - bar_h / 2:.0f}" width="{W - 2 * m:.0f}" height="{bar_h:.0f}" '
            f'rx="{bar_h / 2 if st.sh["radius"] >= 12 else st.sh["radius"]:.0f}" fill="{c["surface"]}" '
            f'stroke="{c["line"]}" stroke-width="{st.sh["stroke"]}"{st.lift}/>'
        ]
        cl = fit(spec["center"], [int(v * u) for v in (24, 22, 20)], W / 3, bold=True, max_lines=1)
        if cl is None:
            err("center label does not fit — shorten it")
            return None
        bar.append(t(W / 2, cy + cl[0] * 0.35, cl[1], cl[0], c["ink"], "middle", 700, 0.02))
        body.append(step(1, "node", bar))
        k_top = (n + 1) // 2
        rows = [(items[:k_top], -1), (items[k_top:], 1)]
        idx = 0
        for row, side in rows:
            k = len(row)
            for j, it in enumerate(row):
                px_ = m + (W - 2 * m) * (j + 0.5) / k
                if side == 1 and k < k_top:  # bottom row sits between the top-row cards
                    px_ = m + (W - 2 * m) * (j + 1) / (k + 1)
                py_ = cy + side * (bar_h / 2 + reach + bh / 2)
                acc = bool(it.get("accent"))
                ink = c["accent-ink"] if acc else c["ink"]
                parts = [box(px_ - bw / 2, py_ - bh / 2, bw, bh, st, acc)]
                lab = fit(it["label"], [int(v * u) for v in (22, 20, 18)], bw - 28 * u, bold=True)
                if lab is None:
                    err(f"items[{idx}] {it['label']!r} does not fit a bus stop — shorten it")
                    return None
                ls, ll = lab
                parts.append(
                    t(
                        px_,
                        py_ + ls * 0.35 - (len(ll) - 1) * ls * 0.6,
                        ll,
                        ls,
                        ink,
                        "middle",
                        st.bold,
                        lh=1.2,
                    )
                )
                ya, yb = py_ - side * bh / 2, cy + side * bar_h / 2
                wire = (
                    f'<path d="M{px_:.0f},{yb:.0f} V{ya:.0f}" stroke="{c["line"]}" '
                    f'stroke-width="{st.sh["stroke"]}" data-draw="1"/>'
                )
                body.append(step(idx + 2, "edge", [wire]))
                body.append(step(idx + 2, "node", parts))
                idx += 1
    elif arch == "hub":
        n = len(items)
        cx, cy = W / 2, y0 + ch / 2
        bw, bh = 230 * u, 84 * u
        rx, ry = (W - 2 * m - bw) / 2, (ch - bh) / 2
        if ry < bh * 1.1:
            err("hub needs more vertical room — remove the subtitle or footer")
            return None
        cw, chh = 240 * u, 104 * u
        ctr = [
            f'<rect x="{cx - cw / 2:.0f}" y="{cy - chh / 2:.0f}" width="{cw:.0f}" height="{chh:.0f}" '
            f'rx="{st.sh["radius"]}" fill="{c["surface"]}" stroke="{c["line"]}" stroke-width="{st.sh["stroke-strong"]}"{st.lift}/>'
        ]
        cl = fit(spec["center"], [int(v * u) for v in (28, 26, 24, 22)], cw - 32 * u, bold=True)
        if cl is None:
            err("center label does not fit — shorten it")
            return None
        ctr.append(
            t(
                cx,
                cy + cl[0] * 0.35 - (len(cl[1]) - 1) * cl[0] * 0.6,
                cl[1],
                cl[0],
                c["ink"],
                "middle",
                700,
                lh=1.2,
            )
        )
        body.append(step(1, "node", ctr))
        for i, it in enumerate(items):
            ang = -math.pi / 2 + i * 2 * math.pi / n
            px_, py_ = cx + rx * math.cos(ang), cy + ry * math.sin(ang)
            ax_, ay_ = rim(cx, cy, cw, chh, px_, py_, 6 * u)
            bx_, by_ = rim(px_, py_, bw, bh, cx, cy, 6 * u)
            spoke = (
                f'<path d="M{ax_:.0f},{ay_:.0f} L{bx_:.0f},{by_:.0f}" stroke="{c["line"]}" '
                f'stroke-width="{st.sh["stroke"]}" stroke-opacity="0.55" data-draw="1"/>'
            )
            acc = bool(it.get("accent"))
            ink = c["accent-ink"] if acc else c["ink"]
            parts = [box(px_ - bw / 2, py_ - bh / 2, bw, bh, st, acc)]
            lab = fit(it["label"], [int(v * u) for v in (24, 22, 20, 18)], bw - 32 * u, bold=True)
            if lab is None:
                err(f"items[{i}] {it['label']!r} does not fit a hub spoke — shorten it")
                return None
            ls, ll = lab
            parts.append(
                t(
                    px_,
                    py_ + ls * 0.35 - (len(ll) - 1) * ls * 0.6,
                    ll,
                    ls,
                    ink,
                    "middle",
                    st.bold,
                    lh=1.2,
                )
            )
            body.append(step(i + 2, "edge", [spoke]))
            body.append(step(i + 2, "node", parts))
    elif arch == "grid":
        axes = spec.get("axes")
        s = 16 * u
        ax = 36 * u if axes else 0
        gap = 20 * u
        gw = (W - 2 * m - ax - gap) / 2
        gh = (ch - (ax + 12 * u if axes else 0) - gap) / 2
        x0 = m + ax
        for i, it in enumerate(items):
            col, row = i % 2, i // 2
            bx, by = x0 + col * (gw + gap), y0 + row * (gh + gap)
            parts = card(bx, by, gw, gh, it, st, None)
            if parts is None:
                err(f"items[{i}] {it['label']!r} does not fit a quadrant — shorten it")
                return None
            body.append(step(i + 1, "node", parts))
        if axes:
            base_y = y0 + 2 * gh + gap + 12 * u  # x-axis
            ax_x = x0 - 12 * u  # y-axis
            gy = base_y + 24 * u
            vx = m + 12 * u
            axis = f'stroke="{c["border"]}" stroke-width="{st.sh["stroke"]}"{st.marker}'
            body.append(
                step(
                    5,
                    "legend",
                    [
                        f'<path d="M{ax_x:.0f},{base_y:.0f} H{W - m:.0f}" fill="none" {axis}/>',
                        f'<path d="M{ax_x:.0f},{base_y:.0f} V{y0:.0f}" fill="none" {axis}/>',
                        t(x0, gy, [axes["x"][0].upper()], s, c["muted"], weight=600, track=0.08),
                        t(W - m, gy, [axes["x"][1].upper()], s, c["muted"], "end", 600, 0.08),
                        f'<text transform="translate({vx:.0f},{base_y:.0f}) rotate(-90)" font-size="{s:.0f}" font-weight="600" letter-spacing="{0.08 * s:.2f}" fill="{c["muted"]}">{escape(axes["y"][0].upper())}</text>',
                        f'<text transform="translate({vx:.0f},{y0:.0f}) rotate(-90)" font-size="{s:.0f}" font-weight="600" letter-spacing="{0.08 * s:.2f}" fill="{c["muted"]}" text-anchor="end">{escape(axes["y"][1].upper())}</text>',
                    ],
                )
            )
    elif arch == "compare" and st.square:
        body += compare_square(spec, st, W, m, y0, y1)
        if errors:
            return None
    elif arch == "compare":
        cols = spec["columns"]
        n = len(cols)
        gap = 24 * u
        cw = (W - 2 * m - (n - 1) * gap) / n
        hsize = 24 * u
        rsize = 18 * u
        pitch = 46 * u
        hb = 64 * u
        max_rows = max(len(col["rows"]) for col in cols)
        tiers = any(col.get("badge") or col.get("eyebrow") for col in cols)
        head_h = hsize * 1.9 if tiers else 0  # tiered columns: the heading sits under the band
        col_h = min(ch, hb + 12 * u + head_h + max_rows * pitch + 24 * u)
        y0 = y0 + (ch - col_h) / 2
        pad = 24 * u
        for i, col in enumerate(cols):
            cx0 = m + i * (cw + gap)
            acc = bool(col.get("accent"))
            ink = c["accent-ink"] if acc else c["ink"]
            mut = c["accent-muted"] if acc else c["muted"]
            parts = [box(cx0, y0, cw, col_h, st, acc)]
            r = st.sh["radius"]
            band = c["accent"] if acc else c["tile"]
            if band.upper() == c["surface"].upper() and not acc:
                band = c["subtle"] if dt.contrast(c["ink"], c["subtle"]) >= 4.5 else c["surface"]
            parts.append(
                f'<path d="M{cx0:.0f},{y0 + hb:.0f} V{y0 + r:.0f} Q{cx0:.0f},{y0:.0f} {cx0 + r:.0f},{y0:.0f} '
                f'H{cx0 + cw - r:.0f} Q{cx0 + cw:.0f},{y0:.0f} {cx0 + cw:.0f},{y0 + r:.0f} V{y0 + hb:.0f} Z" fill="{band}"/>'
            )
            parts.append(
                f'<path d="M{cx0:.0f},{y0 + hb:.0f} H{cx0 + cw:.0f}" stroke="{mut if acc else c["border"]}" stroke-width="1"/>'
            )
            hl = wrap(col["heading"], hsize, cw - 2 * pad, bold=True, max_lines=1)
            if hl is None:
                err(f"columns[{i}].heading does not fit — shorten it")
                return None
            if tiers:
                bx0, bsz = cx0 + pad, 32 * u
                if col.get("badge"):
                    shape = (
                        f'<rect x="{bx0:.0f}" y="{y0 + (hb - bsz) / 2:.0f}" width="{bsz:.0f}" height="{bsz:.0f}"'
                        if st.sh["badge-shape"] == "square"
                        else f'<circle cx="{bx0 + bsz / 2:.0f}" cy="{y0 + hb / 2:.0f}" r="{bsz / 2:.1f}"'
                    )
                    bfill, bink = c["badge"], c["badge-ink"]
                    parts.append(f'{shape} fill="{bfill}"/>')
                    parts.append(
                        t(
                            bx0 + bsz / 2,
                            y0 + hb / 2 + 8 * u,
                            [col["badge"]],
                            22 * u,
                            bink,
                            "middle",
                            700,
                        )
                    )
                    bx0 += bsz + 14 * u
                if col.get("eyebrow"):
                    parts.append(
                        t(
                            bx0,
                            y0 + hb / 2 + 6 * u,
                            [col["eyebrow"]],
                            17 * u,
                            ink,
                            weight=500,
                            track=0.06,
                        )
                    )
                parts.append(
                    t(
                        cx0 + pad,
                        y0 + hb + 12 * u + hsize * 1.1,
                        hl,
                        hsize,
                        ink,
                        weight=st.bold,
                        track=-0.01,
                    )
                )
            else:
                parts.append(
                    t(
                        cx0 + pad,
                        y0 + hb / 2 + hsize * 0.36,
                        hl,
                        hsize,
                        ink,
                        weight=st.bold,
                        track=-0.01,
                    )
                )
            ry = y0 + hb + 12 * u + head_h
            for j, row in enumerate(col["rows"]):
                rl = wrap(row, rsize, cw - 2 * pad, max_lines=1)
                if rl is None:
                    rl2 = wrap(row, rsize * 0.9, cw - 2 * pad, max_lines=2)
                    if rl2 is None:
                        err(f"columns[{i}].rows[{j}] does not fit — shorten it")
                        return None
                    rl, rs = rl2, rsize * 0.9
                else:
                    rs = rsize
                mid = ry + pitch / 2
                bx_ = cx0 + pad
                if st.sh["badge-shape"] == "square":  # square bullets, as on the slides
                    parts.append(
                        f'<rect x="{bx_:.0f}" y="{mid - 4 * u:.0f}" width="{8 * u:.0f}" height="{8 * u:.0f}" '
                        f'fill="{c["accent-ink"] if acc else c["badge"]}"/>'
                    )
                    bx_ += 20 * u
                parts.append(
                    t(
                        bx_,
                        mid + rs * 0.35 - (len(rl) - 1) * rs * 0.6,
                        rl,
                        rs,
                        ink,
                        lh=1.2,
                    )
                )
                if j < len(col["rows"]) - 1:
                    parts.append(
                        f'<path d="M{cx0 + pad:.0f},{ry + pitch:.0f} H{cx0 + cw - pad:.0f}" stroke="{mut if acc else c["subtle"]}" stroke-width="1" stroke-opacity="0.6"/>'
                    )
                ry += pitch
            body.append(step(i + 1, "node", parts))
    elif arch == "matrix":
        rows = spec["rows"]
        n = len(rows)
        g = 14 * u
        rh = min(118 * u, (ch - (n - 1) * g) / n)
        top = y0 + (ch - (n * rh + (n - 1) * g)) / 2
        hw = 200 * u  # row header width
        inset = 12 * u
        for i, row in enumerate(rows):
            ry = top + i * (rh + g)
            parts = [
                f'<rect x="{m:.0f}" y="{ry:.0f}" width="{W - 2 * m:.0f}" height="{rh:.0f}" '
                f'rx="{st.sh["radius-small"]}" fill="{c["tile"] if c["tile"].upper() not in (c["canvas"].upper(), c["surface"].upper()) else c["subtle"]}"/>',
                f'<rect x="{m + inset:.0f}" y="{ry + inset:.0f}" width="{hw:.0f}" height="{rh - 2 * inset:.0f}" '
                f'rx="{st.sh["radius-small"]}" fill="{c["tag"]}"/>',
            ]
            hl = fit(row["header"], [int(v * u) for v in (24, 22, 20)], hw - 28 * u, bold=True)
            if hl is None:
                err(f"rows[{i}].header does not fit — shorten it")
                return None
            parts.append(
                t(
                    m + inset + 14 * u,
                    ry + inset + 14 * u + hl[0],
                    hl[1],
                    hl[0],
                    c["tag-ink"],
                    weight=st.bold,
                    lh=1.15,
                )
            )
            cells = row["cells"]
            k = len(cells)
            cx0 = m + inset + hw + inset
            cw = (W - m - inset - cx0 - (k - 1) * inset) / k
            for j, cell in enumerate(cells):
                x0 = cx0 + j * (cw + inset)
                acc = bool(cell.get("accent"))
                ink = c["accent-ink"] if acc else c["ink"]
                mut = c["accent-muted"] if acc else c["muted"]
                parts.append(
                    f'<rect x="{x0:.0f}" y="{ry + inset:.0f}" width="{cw:.0f}" height="{rh - 2 * inset:.0f}" '
                    f'rx="{st.sh["radius-small"]}" fill="{c["accent"] if acc else c["surface"]}"'
                    f"{' data-accent=' + chr(34) + '1' + chr(34) if acc else ''}/>"
                )
                cy = ry + inset + 14 * u
                inner = cw - 28 * u
                if cell.get("eyebrow"):
                    ey = wrap(cell["eyebrow"], 15 * u, inner, max_lines=1)
                    if ey is None:
                        err(f"rows[{i}].cells[{j}].eyebrow does not fit — shorten it")
                        return None
                    cy += 15 * u
                    parts.append(
                        t(
                            x0 + 14 * u,
                            cy,
                            ey,
                            15 * u,
                            c["accent-ink"] if acc else c["lede"],
                            weight=500,
                            track=0.06,
                        )
                    )
                    cy += 6 * u
                lab = fit(cell["label"], [int(v * u) for v in (21, 20, 18, 17)], inner, bold=True)
                if lab is None:
                    err(f"rows[{i}].cells[{j}] {cell['label']!r} does not fit — shorten it")
                    return None
                cy += lab[0]
                parts.append(t(x0 + 14 * u, cy, lab[1], lab[0], ink, weight=st.bold, lh=1.15))
                cy += (len(lab[1]) - 1) * lab[0] * 1.15
                if cell.get("detail"):
                    det = fit(
                        cell["detail"], [int(v * u) for v in (16, 15, 14)], inner, max_lines=2
                    )
                    if det is None:
                        err(f"rows[{i}].cells[{j}].detail does not fit — shorten it")
                        return None
                    cy += det[0] * 1.35
                    parts.append(t(x0 + 14 * u, cy, det[1], det[0], mut, lh=1.3))
                    cy += (len(det[1]) - 1) * det[0] * 1.3
                if cy > ry + rh - inset + 2 * u:
                    err(f"rows[{i}] is too tall for {n} rows — cut a detail or a row")
                    return None
            body.append(step(i + 1, "node", parts))
    elif arch == "timeline":
        square = H >= 0.9 * W
        body += (timeline_vertical if square else timeline)(items, st, W, m, y0, y1)
        if errors:
            return None
    title = escape(spec["title"])
    desc = escape(spec.get("subtitle") or spec["title"])
    font = escape(st.ty["sans"], {'"': "&quot;"})
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
        f'font-family="{font}" data-design-system="{escape(st.tok["name"])}">',
        f"<title>{title}</title><desc>{desc}</desc>",
        f"<defs>{svg_defs(st.tok)}</defs>",
        f'<rect width="{W}" height="{H}" fill="{c["canvas"]}"/>',
        step(0, "title", top_parts),
        *body,
        *(
            [
                step(
                    max(map(int, re.findall(r'data-step="(\d+)"', "".join(body))), default=0) + 1,
                    "takeaway",
                    take_parts,
                )
            ]
            if take_parts
            else []
        ),
        *foot_parts,
        "</svg>",
    ]
    return "\n".join(parts) + "\n"


SCHEMA = {
    "archetype": "flow | compare | stack | hub | grid | timeline | matrix",
    "canvas": 'social (1200x627) | square (1080x1080) | wide (1920x1080) | {"w": int, "h": int}',
    "accent": "optional #RRGGBB override of the design system's highlighter; it is a fill behind ink, so it must reach 4.5:1 with accent-ink; exactly one item/column may set accent: true",
    "title": f"required, <= {LIMITS['title']} chars, the one takeaway as a sentence",
    "subtitle": f"optional, <= {LIMITS['subtitle']} chars",
    "footer": f"optional, <= {LIMITS['footer']} chars (handle, source)",
    "items": f"flow 2-6 | stack 2-5 | hub 3-6 | grid exactly 4 | timeline 3-12: [{{label <= {LIMITS['label']}, detail <= {LIMITS['detail']} (optional; a date on a timeline), icon (optional, flow/grid; see icons.py --list), accent: bool}}]",
    "center": f"hub only, <= {LIMITS['center']} chars",
    "layout": 'hub only: "radial" (default, centre with spokes) | "bus" (a horizontal bar, stops above and below)',
    "eyebrow": f"optional, <= {LIMITS['eyebrow']} chars, small uppercase kicker above the title",
    "numbered": "optional bool, step numbers on cards (default true for flow)",
    "columns": f"compare only, 2-3: [{{heading <= {LIMITS['heading']}, rows: 1-5 strings <= {LIMITS['row']}, accent: bool}}]",
    "axes": "grid only, optional: {x: [left, right], y: [bottom, top]}",
    "takeaway": "optional, <= 80 chars: a full-width ink bar under the diagram stating the conclusion",
    "chips": "per item, optional: up to 3 mono identifier chips (<= 24 chars) on the card",
    "rows": "matrix only, 2-4: [{header <= 20, cells: 1-4 [{label, detail?, eyebrow? (mono kicker), accent?}]}]",
    "column extras": "compare only, optional per column: badge (1-2 chars, e.g. S/M/L), eyebrow (<= 24 chars) — a tiered comparison",
}

SAMPLES = {
    "matrix": {
        "archetype": "matrix",
        "title": "Three layers keep a GraphQL API healthy",
        "rows": [
            {
                "header": "Schema",
                "cells": [
                    {"label": "SDL first", "eyebrow": "design", "detail": "reviewed like code"},
                    {
                        "label": "Federation",
                        "eyebrow": "subgraphs",
                        "detail": "one team per domain",
                    },
                    {
                        "label": "Persisted queries",
                        "eyebrow": "allow-list",
                        "detail": "only known operations",
                        "accent": True,
                    },
                ],
            },
            {
                "header": "Runtime",
                "cells": [
                    {"label": "DataLoader", "detail": "batches N+1 lookups"},
                    {"label": "Query cost", "detail": "depth and complexity limits"},
                    {"label": "Caching", "detail": "per-field cache hints"},
                ],
            },
            {
                "header": "Operations",
                "cells": [
                    {"label": "Tracing", "detail": "a span per resolver"},
                    {"label": "Schema checks", "detail": "breaking changes fail CI"},
                    {"label": "Usage stats", "detail": "retire unused fields"},
                ],
            },
        ],
    },
    "flow": {
        "archetype": "flow",
        "title": "One artifact moves through three gates",
        "subtitle": "Build once, promote the same bytes",
        "footer": "@handle",
        "items": [
            {"label": "Commit", "detail": "main branch only", "icon": "branch"},
            {"label": "Build once", "detail": "immutable image", "icon": "package", "accent": True},
            {"label": "Deploy", "detail": "promote, never rebuild", "icon": "cloud"},
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
    "timeline": {
        "archetype": "timeline",
        "title": "From prototype to general availability",
        "items": [
            {"label": "Prototype", "detail": "Jan"},
            {"label": "Design partners", "detail": "Mar"},
            {"label": "Private beta", "detail": "May"},
            {"label": "Public beta", "detail": "Jul"},
            {"label": "Pricing", "detail": "Aug"},
            {"label": "GA", "detail": "Oct", "accent": True},
            {"label": "EU region", "detail": "Dec"},
        ],
    },
}


def self_test() -> int:
    global errors
    tok = dt.load(None)
    for name, sample in SAMPLES.items():
        for canvas in CANVASES:
            errors = []
            spec = dict(sample, canvas=canvas)
            v = validate(spec, tok)
            assert v is not None, (name, canvas, errors)
            svg = build(*v)
            assert svg and not errors, (name, canvas, errors)
            ET.fromstring(svg)  # noqa: S314 - our own generated markup, no DOCTYPE/entities possible
            assert "<title>" in svg and 'font-family="' in svg and 'data-step="1"' in svg
            assert tok["color"]["canvas"] in svg
    errors = []
    bad = dict(SAMPLES["flow"], items=SAMPLES["flow"]["items"] * 3)
    assert validate(bad, tok) is None and any("needs 2-6 items" in e for e in errors), errors
    errors = []
    bad = dict(
        SAMPLES["flow"], items=[{"label": "x", "accent": True}, {"label": "y", "accent": True}]
    )
    assert validate(bad, tok) is None and any(
        "exactly one element carries the accent" in e for e in errors
    ), errors
    errors = []
    bad = dict(SAMPLES["flow"], title="<script>alert(1)</script>")
    v = validate(bad, tok)
    assert v is not None
    svg = build(*v)
    assert svg and "<script>" not in svg and "&lt;script&gt;" in svg
    errors = []
    bad = dict(
        SAMPLES["flow"], items=[{"label": "a very long label that cannot fit"} for _ in range(6)]
    )
    assert validate(bad, tok) is None and any("max 26" in e for e in errors), errors
    errors = []
    assert validate(dict(SAMPLES["flow"], accent="#222222"), tok) is None
    assert any("4.5" in e for e in errors), errors
    errors = []
    assert validate(dict(SAMPLES["flow"], items=[{"label": "a", "icon": "nope"}] * 2), tok) is None
    errors = []  # inline (no canvas, no drawn title): as tall as the content, not the preset
    inline = build(*validate({k: v for k, v in SAMPLES["flow"].items() if k != "canvas"}, tok))
    ih = float(re.search(r'viewBox="0 0 [\d.]+ ([\d.]+)"', inline).group(1))
    assert (
        ih < 600 and "@handle" not in inline and "<title>" in inline and "data-inline" in inline
    ), ih
    print("OK: self-test passed")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("spec", nargs="?", help="spec JSON file, or - for stdin")
    ap.add_argument("--out", type=Path, help="write the SVG here (default: stdout)")
    ap.add_argument("--design-system", default=None, help="design-system.md or tokens .json")
    ap.add_argument("--schema", action="store_true", help="print the spec shape as JSON")
    ap.add_argument("--canvas", choices=sorted(CANVASES), help="override the spec's canvas")
    ap.add_argument(
        "--show-title", action="store_true", help="draw the title/subtitle (slides, social cards)"
    )
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
        if args.canvas:
            spec["canvas"] = args.canvas
        if args.show_title:
            spec["show_title"] = True
        tok = dt.load(args.design_system)
    except (OSError, ValueError, dt.TokenError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    v = validate(spec, tok)
    svg = build(*v) if v else None
    if svg is None or errors:
        for line in errors:
            print(line, file=sys.stderr)
        print(f"FAIL: {len(errors)} error(s)")
        return 1
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(svg, encoding="utf-8")
        print(f"OK: wrote {args.out} (design system: {tok['name']})")
    else:
        sys.stdout.write(svg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
