#!/usr/bin/env python3
"""svg_lint.py — deterministic checks for a minimalist technical illustration SVG.

ERRORs are the hard contract: a safe static subset (no scripts, event handlers,
external references, raster images, filters, gradients, animation), a viewBox,
a font-family on every text's ancestor chain, text that stays on the canvas
and does not overlap other text, and WCAG AA contrast for every text run.
WARNs are house guidance: one accent color, a word budget, a shape budget,
font-size floors, `<title>`/`<desc>` for accessibility.

Design-system aware: when the SVG carries `data-design-system` (every renderer
in these skills sets it) or --design-system is given, the tokens are loaded and
(1) the one sanctioned effect is allowed — `<filter data-ds="neumorph">` made
only of `<feDropShadow>` with blur <= 5 px — every other filter stays an error;
(2) the design system's neutrals do not count as accent hues; (3) the accent is
a highlighter: using it as a text fill or a stroke is an error; (4) colours
outside the palette are warned. `--diagram` switches the font floor from
feed-relative to absolute (11 px error, 13 px warn) and raises the shape budget,
for architecture diagrams read at full size. Lint the static SVG, not the
animated one (the camera track is wider than the frame by design).

Text geometry is estimated from character counts (0.55 em per glyph, 0.6 em
bold) — good enough to catch collisions and overflow, never a substitute for
looking at the render. Pure stdlib. Exit 1 on any ERROR (or WARN with --strict).

Usage:
    python3 svg_lint.py FILE.svg [--max-words 70] [--max-shapes 40] [--strict]
                        [--diagram] [--design-system PATH]
    python3 svg_lint.py --self-test

Output: `ERROR:`/`WARN:` lines, a `STATS ...` line, then `OK:`/`FAIL:`.
"""

from __future__ import annotations

import argparse
import colorsys
import contextlib
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import design_tokens as dt

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
ALLOWED = {
    "svg",
    "g",
    "defs",
    "title",
    "desc",
    "metadata",
    "rect",
    "circle",
    "ellipse",
    "line",
    "polyline",
    "polygon",
    "path",
    "text",
    "tspan",
    "use",
    "clipPath",
    "marker",
    "symbol",
    "style",
    "filter",  # only the design system's neumorph lift; checked in neumorph_ok()
    "feDropShadow",
}
SHAPES = {"rect", "circle", "ellipse", "line", "polyline", "polygon", "path"}
BANNED_HINT = {
    "script": "active content",
    "image": "raster or external image",
    "foreignObject": "embedded HTML",
    "linearGradient": "gradients (house style is flat)",
    "radialGradient": "gradients (house style is flat)",
    "pattern": "patterns",
    "mask": "masks",
    "a": "links",
    "animate": "animation",
    "animateTransform": "animation",
    "animateMotion": "animation",
    "set": "animation",
    "switch": "conditional content",
}
CANVAS_PRESETS = {
    (1200, 630): "social (Open Graph / LinkedIn 1.91:1)",
    (1200, 627): "social (LinkedIn)",
    (1200, 675): "social 16:9",
    (1600, 900): "slide 16:9",
    (1920, 1080): "slide 16:9",
    (1080, 1080): "square",
    (1080, 1350): "portrait 4:5",
}
MAX_WORDS = 70
MAX_SHAPES = 40
MIN_FONT_PCT_ERR = 1.15  # % of viewBox WIDTH (feeds fit width): 14px on a 1200-wide card
# 16px on a 1200-wide card: small uppercase secondary labels (step numbers, dates, axes)
# sit here in every reviewed card system; body text stays well above it
MIN_FONT_PCT_WARN = 1.3
OVERLAP_FRACTION = 0.05  # of the smaller text box
NAMED_COLORS = {
    "black": (0, 0, 0),
    "white": (255, 255, 255),
    "red": (255, 0, 0),
    "blue": (0, 0, 255),
    "green": (0, 128, 0),
    "gray": (128, 128, 128),
    "grey": (128, 128, 128),
}
NUM_RE = re.compile(r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?")
TRANSLATE_RE = re.compile(r"translate\(\s*([-+.\deE]+)(?:[\s,]+([-+.\deE]+))?\s*\)")
DANGEROUS_CSS = re.compile(r"url\s*\(|@import|expression\s*\(|javascript:", re.I)

errors: list[str] = []
warnings: list[str] = []


def err(msg: str) -> None:
    errors.append(f"ERROR: {msg}")


def warn(msg: str) -> None:
    warnings.append(f"WARN: {msg}")


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def style_map(el: ET.Element) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in (el.get("style") or "").split(";"):
        if ":" in part:
            k, v = part.split(":", 1)
            out[k.strip()] = v.strip()
    return out


def prop(el: ET.Element, name: str, parents: dict) -> str | None:
    """Presentation attribute or style property, inherited up the tree."""
    node: ET.Element | None = el
    while node is not None:
        v = style_map(node).get(name) or node.get(name)
        if v is not None and v.strip() and v.strip() != "inherit":
            return v.strip()
        node = parents.get(node)
    return None


def parse_color(value: str | None) -> tuple[int, int, int] | None:
    if not value:
        return None
    v = value.strip().lower()
    if v in ("none", "transparent", "currentcolor"):
        return None
    if v in NAMED_COLORS:
        return NAMED_COLORS[v]
    m = re.fullmatch(r"#([0-9a-f]{3}|[0-9a-f]{6})", v)
    if m:
        h = m.group(1)
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    m = re.fullmatch(r"rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)", v)
    if m:
        return tuple(min(255, int(x)) for x in m.groups())  # type: ignore[return-value]
    return None


def luminance(rgb: tuple[int, int, int]) -> float:
    def lin(c: int) -> float:
        s = c / 255.0
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4

    r, g, b = rgb
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def contrast(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def is_neutral(rgb: tuple[int, int, int]) -> bool:
    """Greys, near-blacks and near-whites: low chroma, or too dark/light to read as a hue."""
    _h, s, v = colorsys.rgb_to_hsv(*(c / 255 for c in rgb))
    return s < 0.25 or v < 0.25 or (v > 0.9 and s < 0.15)


def hue_bucket(rgb: tuple[int, int, int]) -> int:
    h, _, _ = colorsys.rgb_to_hsv(*(c / 255 for c in rgb))
    return int(h * 360) // 20


def px(value: str | None, base: float = 16.0) -> float | None:
    if value is None:
        return None
    m = NUM_RE.match(value.strip())
    if not m:
        return None
    n = float(m.group(0))
    unit = value.strip()[m.end() :].strip().lower()
    if unit in ("", "px"):
        return n
    if unit == "pt":
        return n * 96 / 72
    if unit == "em":
        return n * base
    if unit == "%":
        return n / 100 * base
    return None


def translate_of(el: ET.Element, parents: dict) -> tuple[float, float]:
    tx = ty = 0.0
    node: ET.Element | None = el
    while node is not None:
        t = node.get("transform") or ""
        if t:
            m = TRANSLATE_RE.search(t)
            if m:
                tx += float(m.group(1))
                ty += float(m.group(2) or 0)
            other = re.search(r"(scale|matrix|skew)\s*\(", t)
            odd_rot = re.search(r"rotate\s*\(", t) and not re.search(r"rotate\(\s*-?90\b", t)
            if (other or odd_rot) and node.get("class") != "icon":
                warn(f"transform {t!r} on <{local(node.tag)}> is not evaluated (only translate is)")
        node = parents.get(node)
    return tx, ty


def rect_bbox(el: ET.Element, parents: dict) -> tuple[float, float, float, float] | None:
    tx, ty = translate_of(el, parents)
    tag = local(el.tag)
    try:
        if tag == "rect":
            x, y = float(el.get("x", 0)), float(el.get("y", 0))
            w, h = float(el.get("width", 0)), float(el.get("height", 0))
            return (x + tx, y + ty, x + w + tx, y + h + ty)
        if tag in ("circle", "ellipse"):
            cx, cy = float(el.get("cx", 0)), float(el.get("cy", 0))
            rx = float(el.get("r", el.get("rx", 0)))
            ry = float(el.get("r", el.get("ry", 0)))
            return (cx - rx + tx, cy - ry + ty, cx + rx + tx, cy + ry + ty)
    except ValueError:
        return None
    return None


def text_runs(root: ET.Element, parents: dict) -> list[dict]:
    """One entry per <text> (tspans merged), with an estimated bbox."""
    runs = []
    for t in root.iter():
        if local(t.tag) != "text":
            continue
        pieces = [(t, t.text or "")]
        for ts in t.iter():
            if ts is t:
                continue
            if local(ts.tag) == "tspan":
                pieces.append((ts, ts.text or ""))
            if ts.tail:
                pieces.append((t, ts.tail))
        content = " ".join(s.strip() for _, s in pieces if s.strip())
        if not content:
            continue
        size = px(prop(t, "font-size", parents))
        weight = (prop(t, "font-weight", parents) or "normal").lower()
        bold = weight in ("bold", "bolder") or (weight.isdigit() and int(weight) >= 600)
        anchor = prop(t, "text-anchor", parents) or "start"
        tx, ty = translate_of(t, parents)
        first_ts = next((el for el, _ in pieces if el is not t and el.get("x") is not None), None)
        xs = (
            t.get("x")
            if t.get("x") is not None
            else (first_ts.get("x") if first_ts is not None else "0")
        )
        ys = (
            t.get("y")
            if t.get("y") is not None
            else (first_ts.get("y") if first_ts is not None else "0")
        )
        try:
            x = float(str(xs).split()[0]) + tx
            y = float(str(ys).split()[0]) + ty
        except ValueError:
            x, y = tx, ty
        rotated = bool(re.search(r"rotate\(\s*-?90\b", t.get("transform") or ""))
        # multi-line via tspans with explicit y or dy: take the widest line, stack heights
        lines = []
        cur_y = y
        for el, s in pieces:
            if not s.strip():
                continue
            if el is not t and el.get("y") is not None:
                with contextlib.suppress(ValueError):
                    cur_y = float(el.get("y", "0").split()[0]) + ty
            elif el is not t and el.get("dy") is not None:
                d = px(el.get("dy"), size or 16)
                cur_y += d or 0
            lines.append((s.strip(), cur_y))
        fs = size or 16.0
        char_w = fs * (0.6 if bold else 0.55)
        width = max(len(s) for s, _ in lines) * char_w
        left = x - width if anchor == "end" else x - width / 2 if anchor == "middle" else x
        top = min(yy for _, yy in lines) - 0.8 * fs
        bottom = max(yy for _, yy in lines) + 0.25 * fs
        if (
            rotated
        ):  # vertical label: the run extends along y, not x (up, or down when end-anchored)
            span = width
            if anchor == "end":
                left, top, width, bottom = x - fs * 0.8, y, fs * 1.05, y + span
            elif anchor == "middle":
                left, top, width, bottom = x - fs * 0.8, y - span / 2, fs * 1.05, y + span / 2
            else:
                left, top, width, bottom = x - fs * 0.8, y - span, fs * 1.05, y
        runs.append(
            {
                "el": t,
                "text": content,
                "size": size,
                "bold": bold,
                "bbox": (left, top, left + width, bottom),
                "cx": left + width / 2,
                "cy": (top + bottom) / 2,
            }
        )
    return runs


def overlap_area(a, b) -> float:
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return w * h if w > 0 and h > 0 else 0.0


def area(b) -> float:
    return max(b[2] - b[0], 0) * max(b[3] - b[1], 0)


def hexrgb(h: str) -> tuple[int, int, int]:
    return tuple(int(h[i : i + 2], 16) for i in (1, 3, 5))  # type: ignore[return-value]


def neumorph_ok(f: ET.Element) -> str | None:
    """None if `f` is the design system's lift filter, else why not."""
    kind = f.get("data-ds")
    if kind not in ("neumorph", "soft"):
        return 'only the design system\'s <filter data-ds="neumorph|soft"> elevation is allowed'
    kids = list(f)
    limit = 2 if kind == "neumorph" else 1
    if not kids or any(local(k.tag) != "feDropShadow" for k in kids) or len(kids) > limit:
        return f"the {kind} filter may hold only {limit} <feDropShadow>"
    for k in kids:
        try:
            blur = float(k.get("stdDeviation", "0"))
            alpha = float(k.get("flood-opacity", "1"))
        except ValueError:
            return "unparseable stdDeviation or flood-opacity"
        if kind == "neumorph" and blur > 2.5:
            return "neumorph blur is over 5 px — the lift must stay subtle"
        if kind == "soft" and (blur > 12 or alpha > 0.15):
            return "soft shadow over 24 px blur or 15% opacity — elevation, not a glow"
    return None


def check(
    path: Path,
    max_words: int,
    max_shapes: int,
    diagram: bool = False,
    ds_path: str | None = None,
) -> None:
    raw = path.read_text(encoding="utf-8", errors="replace")
    if re.search(r"<!DOCTYPE|<!ENTITY", raw, re.I):
        err("DOCTYPE/ENTITY declarations are not allowed (XML expansion attacks); remove them")
        return
    try:
        # DOCTYPE/ENTITY were rejected above, which removes the expansion and external-entity
        # vectors; defusedxml would add a runtime dependency a skill must not have.
        root = ET.fromstring(raw)  # noqa: S314
    except ET.ParseError as exc:
        err(f"not well-formed XML: {exc}")
        return
    if local(root.tag) != "svg":
        err(f"root element is <{local(root.tag)}>, expected <svg>")
        return
    parents = {c: p for p in root.iter() for c in p}
    tokens = None
    if ds_path or root.get("data-design-system"):
        named = root.get("data-design-system")
        try:
            tokens = dt.load(ds_path)
            if (
                not ds_path
                and named
                and named != tokens["name"]
                and named in (*dt.list_themes(), "studio")
            ):
                tokens = dt.load(named)  # the SVG names a theme this machine can resolve
        except dt.TokenError as exc:
            err(f"design system: {exc}")
            return
        named = root.get("data-design-system")
        if named and named != tokens["name"]:
            warn(
                f"SVG was built with design system {named!r} but linting against {tokens['name']!r} "
                "— pass the same --design-system"
            )
    filters = {f.get("id"): neumorph_ok(f) for f in root.iter() if local(f.tag) == "filter"}
    for fid, why in filters.items():
        if why:
            err(f"<filter id={fid!r}>: {why}")

    # --- safe subset ---
    shapes = 0
    for el in root.iter():
        tag = local(el.tag)
        if tag == "feDropShadow" and local(parents.get(el, root).tag) != "filter":
            err("<feDropShadow> outside a <filter>")
        if tag not in ALLOWED:
            why = BANNED_HINT.get(tag, "outside the safe static subset")
            err(f"<{tag}> is not allowed — {why}")
        if tag in SHAPES:
            shapes += 1
        for attr, value in el.attrib.items():
            a = local(attr)
            if a.lower().startswith("on"):
                err(f"event handler attribute {a!r} on <{tag}> — active content is not allowed")
            if a == "href" and not value.startswith("#"):
                err(f"external href {value[:60]!r} on <{tag}> — only internal #refs are allowed")
            if a in ("fill", "stroke") and value.strip().lower().startswith("url("):
                err(
                    f"{a}={value!r} on <{tag}> references a paint server — gradients/patterns are off"
                )
            if a == "filter":
                m = re.fullmatch(r"url\(#([^)]+)\)", value.strip())
                if not m or m.group(1) not in filters:
                    err(f"filter on <{tag}> — no shadows or blur")
            if a == "style" and (DANGEROUS_CSS.search(value) or "filter" in value):
                err(f"style {value[:60]!r} on <{tag}> uses url()/@import/filter — not allowed")
        if tag == "style":
            css = el.text or ""
            if DANGEROUS_CSS.search(css):
                err("<style> uses url()/@import — external resources are not allowed")
            else:
                warn(
                    "<style> rules are not evaluated by this lint — prefer presentation attributes"
                )

    # --- canvas ---
    vb = root.get("viewBox")
    if not vb:
        err("missing viewBox — the illustration cannot scale predictably")
        return
    try:
        vx, vy, vw, vh = (float(n) for n in NUM_RE.findall(vb)[:4])
    except ValueError:
        err(f"unparseable viewBox {vb!r}")
        return
    if vw <= 0 or vh <= 0:
        err(f"viewBox {vb!r} has a non-positive size")
        return
    key = (round(vw), round(vh))
    if (
        key not in CANVAS_PRESETS and not diagram and root.get("data-inline") != "1"
    ):  # inline figures fit content
        warn(
            f"canvas {key[0]}x{key[1]} is not a delivery preset "
            f"({', '.join(f'{w}x{h}' for w, h in CANVAS_PRESETS)})"
        )
    w_attr, h_attr = px(root.get("width")), px(root.get("height"))
    if w_attr and h_attr and abs(w_attr / h_attr - vw / vh) > 0.01:
        warn(f"width/height ({w_attr:.0f}x{h_attr:.0f}) do not match the viewBox aspect ratio")
    if root.find(f"{{{SVG_NS}}}title") is None and root.find("title") is None:
        warn("no <title> — add one for accessibility (screen readers read it)")
    if root.find(f"{{{SVG_NS}}}desc") is None and root.find("desc") is None:
        warn("no <desc> — add a one-line description of the takeaway")

    # --- background + shapes for contrast lookups ---
    canvas_bg = (255, 255, 255)
    rects = []
    hidden = {  # geometry that is never painted: clip paths, markers, defs
        d
        for g in root.iter()
        if local(g.tag) in ("clipPath", "defs", "marker", "symbol", "mask")
        for d in g.iter()
    }
    for el in root.iter():
        if local(el.tag) in ("rect", "circle", "ellipse") and el not in hidden:
            bb = rect_bbox(el, parents)
            fill = parse_color(prop(el, "fill", parents) or "black")
            if bb and fill:
                rects.append((bb, fill, el))
                if area(bb) >= 0.9 * vw * vh:
                    canvas_bg = fill
    bg_style = parse_color(
        style_map(root).get("background") or style_map(root).get("background-color")
    )
    if bg_style:
        canvas_bg = bg_style

    # --- text ---
    runs = text_runs(root, parents)
    words = sum(len(r["text"].split()) for r in runs)
    canvas = (vx, vy, vx + vw, vy + vh)
    for r in runs:
        t = r["el"]
        snippet = r["text"][:32]
        fam = prop(t, "font-family", parents)
        if not fam:
            err(f"text {snippet!r} has no font-family on itself or any ancestor — set it on <svg>")
        elif not re.search(r"\b(sans-serif|serif|monospace|system-ui)\b", fam):
            warn(
                f"font-family {fam!r} has no generic fallback (sans-serif) — non-Latin text becomes tofu"
            )
        if r["size"] is None:
            warn(f"text {snippet!r}: font-size could not be resolved (unit?) — set px")
        else:
            pct = r["size"] / vw * 100
            if diagram:
                if r["size"] < 11:
                    err(f"text {snippet!r} is {r['size']:.0f}px — below the 11px floor")
                elif r["size"] < (tokens["type"]["small-size"] if tokens else 13):
                    warn(
                        f"text {snippet!r} is {r['size']:.0f}px — small; keep it for secondary text"
                    )
            elif pct < MIN_FONT_PCT_ERR:
                err(
                    f"text {snippet!r} is {r['size']:.0f}px = {pct:.2f}% of canvas width "
                    f"(min {MIN_FONT_PCT_ERR}% = {vw * MIN_FONT_PCT_ERR / 100:.0f}px) — unreadable at feed size"
                )
            elif pct < MIN_FONT_PCT_WARN:
                warn(
                    f"text {snippet!r} is {r['size']:.0f}px ({pct:.2f}% of width) — small for a feed"
                )
        bb = r["bbox"]
        if (
            bb[0] < canvas[0] - 1
            or bb[1] < canvas[1] - 1
            or bb[2] > canvas[2] + 1
            or bb[3] > canvas[3] + 1
        ):
            err(f"text {snippet!r} overflows the canvas (approximate metrics) — shorten or wrap it")
        # contrast against the smallest shape containing the text center, else the canvas
        holder = None
        for sb, fill, el in rects:
            inside = sb[0] <= r["cx"] <= sb[2] and sb[1] <= r["cy"] <= sb[3]
            if (
                inside
                and area(sb) < 0.9 * vw * vh
                and (holder is None or area(sb) < area(holder[0]))
            ):
                holder = (sb, fill, el)
        bg = holder[1] if holder else canvas_bg
        fg = parse_color(prop(t, "fill", parents) or "black")
        op = prop(t, "fill-opacity", parents) or prop(t, "opacity", parents)
        if fg is None:
            warn(f"text {snippet!r}: fill color not understood — contrast not checked")
        elif op and px(op) is not None and float(px(op) or 1) < 1:
            warn(f"text {snippet!r}: semi-transparent fill — contrast not checked")
        else:
            ratio = contrast(fg, bg)
            size = r["size"] or 16
            large = size >= 24 or (r["bold"] and size >= 18.66)
            need = 3.0 if large else 4.5
            if ratio < need:
                err(
                    f"text {snippet!r}: contrast {ratio:.2f}:1 against its background "
                    f"(needs {need}:1, WCAG 2.2 SC 1.4.3)"
                )
    for i, a in enumerate(runs):
        if a["el"].get("data-role") == "token":  # an intentional overprint of its own code token
            continue
        for b in runs[i + 1 :]:
            if b["el"].get("data-role") == "token":
                continue
            ov = overlap_area(a["bbox"], b["bbox"])
            smaller = min(area(a["bbox"]), area(b["bbox"])) or 1.0
            if ov / smaller > OVERLAP_FRACTION:
                err(
                    f"text {a['text'][:24]!r} overlaps {b['text'][:24]!r} "
                    f"({ov / smaller:.0%} of the smaller box, approximate metrics)"
                )
    if words > 2 * max_words:
        err(
            f"{words} words on one illustration (cap {max_words}) — this is a document, not a visual"
        )
    elif words > max_words:
        warn(f"{words} words > {max_words} — cut labels to the ones that carry the takeaway")
    if diagram:
        max_shapes *= 2
    if shapes > 2 * max_shapes:
        err(f"{shapes} shapes (cap {max_shapes}) — too dense to read")
    elif shapes > max_shapes:
        warn(f"{shapes} shapes > {max_shapes} — simplify")

    # --- palette + strokes ---
    accents: dict[int, tuple[int, int, int]] = {}
    colors: set[tuple[int, int, int]] = set()
    stroke_widths: set[str] = set()
    palette: set[tuple[int, int, int]] = set()
    token_neutral: set[tuple[int, int, int]] = set()
    accent_rgb = None
    if tokens:
        tc = tokens["color"]
        palette = {hexrgb(v) for v in tc.values()} | {(255, 255, 255)}
        token_neutral = palette - {hexrgb(tc["accent"]), hexrgb(tc["signal"])}
        # an inverted highlight (accent == ink/line, e.g. paper-line, coral) is not a highlighter hue
        structural = {tc[k].upper() for k in ("ink", "line", "muted", "badge", "pill", "border")}
        accent_rgb = None if tc["accent"].upper() in structural else hexrgb(tc["accent"])
    in_icon = {  # icons and arrowheads have their own scaled strokes
        d
        for g in root.iter()
        if g.get("class") == "icon" or local(g.tag) == "marker"
        for d in g.iter()
    }
    for el in root.iter():
        if local(el.tag) not in SHAPES | {"text"}:
            continue
        for name in ("fill", "stroke"):
            c = parse_color(prop(el, name, parents))
            if c:
                colors.add(c)
                if not is_neutral(c) and c not in token_neutral:
                    accents.setdefault(hue_bucket(c), c)
                if accent_rgb and c == accent_rgb and (name == "stroke" or local(el.tag) == "text"):
                    err(
                        f"the accent {tokens['color']['accent']} is used as a {name} on "
                        f"<{local(el.tag)}> — it is a highlighter fill behind ink, never text or line"
                    )
        sw = prop(el, "stroke-width", parents)
        if (
            sw
            and el not in in_icon
            and local(el.tag) in SHAPES
            and parse_color(prop(el, "stroke", parents))
        ):
            stroke_widths.add(sw)
    if palette:
        off = sorted(c for c in colors if c not in palette)
        if off:
            warn(
                f"{len(off)} colour(s) outside design system {tokens['name']!r}: "
                + ", ".join(f"#{r:02X}{g:02X}{b:02X}" for r, g, b in off[:5])
            )
    for el in root.iter():
        if local(el.tag) not in ("rect", "circle", "ellipse", "path", "polygon"):
            continue
        stroke = parse_color(prop(el, "stroke", parents))
        fill = parse_color(prop(el, "fill", parents) or "black")
        if stroke in token_neutral:
            continue  # token borders were contrast-checked when the design system loaded
        if stroke and fill and contrast(stroke, fill) < 3.0 and contrast(stroke, canvas_bg) < 3.0:
            warn(
                f"<{local(el.tag)}> border {prop(el, 'stroke', parents)} is under 3:1 against both its fill "
                "and the canvas (WCAG 2.2 SC 1.4.11 asks 3:1 for graphical objects)"
            )
            break
    if len(accents) > 2:
        err(f"{len(accents)} accent hues {sorted(accents.values())} — one accent for the takeaway")
    elif len(accents) == 2:
        warn(
            f"2 accent hues {sorted(accents.values())} — one is the house rule; keep the second only if it encodes meaning"
        )
    if len(colors) > 6 and not palette:
        warn(f"{len(colors)} distinct colors — palette is neutrals + one accent")
    if len(stroke_widths) > 2:
        warn(f"{len(stroke_widths)} stroke widths {sorted(stroke_widths)} — use one, two at most")
    print(
        f"STATS canvas={key[0]}x{key[1]} texts={len(runs)} words={words} shapes={shapes} "
        f"accents={len(accents)} colors={len(colors)}"
    )


BAD_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 630">
<defs><linearGradient id="g"><stop offset="0"/></linearGradient></defs>
<script>alert(1)</script>
<rect width="1200" height="630" fill="#ffffff"/>
<rect x="100" y="100" width="300" height="100" fill="url(#g)" onclick="x()"/>
<text x="60" y="300" font-size="12" fill="#cccccc">tiny and faint</text>
<text x="60" y="400" font-size="40" fill="#111">Alpha beta gamma</text>
<text x="80" y="410" font-size="40" fill="#111">Overlapping run</text>
<text x="60" y="500" font-size="40" fill="#ff0000">red</text>
<text x="60" y="560" font-size="40" fill="#00aa00">green</text>
<text x="60" y="620" font-size="40" fill="#0000ff">blue</text>
</svg>"""
GOOD_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 630" width="1200" height="630"
 font-family="Inter, Helvetica, Arial, sans-serif">
<title>Deploy pipeline</title><desc>Three stages from commit to production</desc>
<rect width="1200" height="630" fill="#f7f7f5"/>
<text x="60" y="110" font-size="44" font-weight="700" fill="#1a1a1f">Three stages, one artifact</text>
<rect x="60" y="260" width="320" height="120" rx="8" fill="#ffffff" stroke="#7c7c86" stroke-width="2"/>
<text x="220" y="330" font-size="26" text-anchor="middle" fill="#1a1a1f">Commit</text>
<rect x="440" y="260" width="320" height="120" rx="8" fill="#ffffff" stroke="#2563eb" stroke-width="3"/>
<text x="600" y="330" font-size="26" text-anchor="middle" fill="#2563eb">Build once</text>
<rect x="820" y="260" width="320" height="120" rx="8" fill="#ffffff" stroke="#7c7c86" stroke-width="2"/>
<text x="980" y="330" font-size="26" text-anchor="middle" fill="#1a1a1f">Deploy</text>
<text x="60" y="590" font-size="18" fill="#6b6b75">@handle</text>
</svg>"""


def self_test() -> int:
    global errors, warnings
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        bad = Path(td) / "bad.svg"
        bad.write_text(BAD_SVG, encoding="utf-8")
        errors, warnings = [], []
        check(bad, MAX_WORDS, MAX_SHAPES)
        joined = "\n".join(errors + warnings)
        for needle in (
            "<script>",
            "<linearGradient>",
            "event handler",
            "paint server",
            "no font-family",
            "unreadable at feed size",
            "contrast",
            "overlaps",
            "accent hues",
        ):
            assert needle in joined, f"missing {needle!r} in:\n{joined}"
        good = Path(td) / "good.svg"
        good.write_text(GOOD_SVG, encoding="utf-8")
        errors, warnings = [], []
        check(good, MAX_WORDS, MAX_SHAPES)
        assert not errors, errors
        assert not warnings, warnings
        ds = Path(td) / "ds.svg"  # the design-system contract: lift allowed, accent never a line
        ds.write_text(
            GOOD_SVG.replace(
                "<title>",
                '<defs><filter id="ds-lift" data-ds="neumorph">'
                '<feDropShadow dx="2" dy="3" stdDeviation="2.5" flood-color="#000" flood-opacity=".07"/>'
                "</filter></defs><title>",
            )
            .replace('rx="8" fill="#ffffff"', 'rx="8" fill="#ffffff" filter="url(#ds-lift)"', 1)
            .replace('stroke="#2563eb"', 'stroke="#FFE27A"'),
            encoding="utf-8",
        )
        errors, warnings = [], []
        ds.write_text(ds.read_text().replace("<svg ", '<svg data-design-system="studio" ', 1))
        check(ds, MAX_WORDS, MAX_SHAPES)
        assert any("highlighter" in e for e in errors), errors
        assert not any("<filter" in e or "filter on" in e for e in errors), errors
        errors, warnings = [], []
        ds.write_text(ds.read_text().replace('stdDeviation="2.5"', 'stdDeviation="9"'))
        check(ds, MAX_WORDS, MAX_SHAPES)
        assert any("over 5 px" in e for e in errors), errors
    assert abs(contrast((255, 255, 255), (0, 0, 0)) - 21.0) < 0.01
    assert abs(contrast((0x25, 0x63, 0xEB), (255, 255, 255)) - 5.17) < 0.05
    print("OK: self-test passed")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("file", nargs="?", type=Path)
    ap.add_argument("--max-words", type=int, default=MAX_WORDS)
    ap.add_argument("--max-shapes", type=int, default=MAX_SHAPES)
    ap.add_argument("--strict", action="store_true", help="warnings fail too")
    ap.add_argument("--diagram", action="store_true", help="full-size diagram: absolute font floor")
    ap.add_argument("--design-system", default=None, help="lint against this design system")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if not args.file:
        ap.error("file is required (or --self-test)")
    if not args.file.is_file():
        print(f"ERROR: no such file: {args.file}", file=sys.stderr)
        return 1
    check(args.file, args.max_words, args.max_shapes, args.diagram, args.design_system)
    for line in errors + warnings:
        print(line, file=sys.stderr)
    failed = len(errors) + (len(warnings) if args.strict else 0)
    print(f"{'FAIL' if failed else 'OK'}: {len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
