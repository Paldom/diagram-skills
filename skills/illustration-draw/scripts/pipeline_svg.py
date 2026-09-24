#!/usr/bin/env python3
"""pipeline_svg.py — a pipeline explainer: artifacts in, a processor, artifacts out.

The storyboard format of a "how does it work" video, as one wide SVG: columns of
labelled blocks left to right — plain-text boxes, syntax-coloured code/JSON
panels whose tokens can carry bracket callouts to coloured notes, tall processor
boxes with a latency caption, a rendered mini-dashboard — joined by arrows, and
closed by a stacked timing bar. Every element carries `data-step` (code lines are
`data-line`), so `diagram-animate --preset pipeline` types the panels line by
line, draws the callouts after them, pans stage by stage and grows the bar.

Spec (JSON):
  {"title"?: "...", "height"?: 900,
   "columns": [[block, ...], ...],          # one list per stage, left to right
   "timing"?: [{"label": "gateway", "ms": 12}, ...],
   "footer"?: "one request, one round trip."}
  block kinds:
   {"kind": "text", "label": "request", "text": "Top products this quarter"}
   {"kind": "code", "label": "query plan", "code": "{\\n  ...\\n}",
        "highlight"?: [{"match": "38", "note": "under the cost limit", "tone": 1}]}
   {"kind": "process", "label": "Gateway", "caption"?: "parse · validate · plan · 12 ms"}
   {"kind": "render", "label": "render", "title": "...", "subtitle"?: "...",
        "kpis"?: [{"label", "value", "delta"?}], "line"?: [[...], ...], "bars"?: [...],
        "table"?: {"columns": [...], "rows": [[...], ...]}}

Usage:
    python3 pipeline_svg.py SPEC.json --out OUT.svg [--design-system PATH]
    python3 pipeline_svg.py --sample --out OUT.svg
    python3 pipeline_svg.py --self-test
Exit 1 with ERROR lines on an invalid spec.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import design_tokens as dt  # noqa: E402
from arch_svg import svg_defs  # noqa: E402

MONO_W = 0.6  # em per glyph in a monospace face
SANS_W = 0.55
TOKEN = re.compile(
    r'("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\')(\s*:)?|(\$?-?\d+(?:\.\d+)?|null|true|false)'
)
KINDS = {"text", "code", "process", "render"}
errors: list[str] = []


def err(msg: str) -> None:
    errors.append(f"ERROR: {msg}")


def esc(s: str) -> str:
    return escape(s, {'"': "&quot;"})


def mix(a: str, b: str, k: float) -> str:
    ca = [int(a[i : i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i : i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * k):02X}" for x, y in zip(ca, cb, strict=True))


def text(x, y, s, size, fill, weight=400, anchor="start", family=None, extra="") -> str:
    fam = f' font-family="{esc(family)}"' if family else ""
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" font-weight="{weight}" fill="{fill}" '
        f'text-anchor="{anchor}"{fam}{extra}>{escape(s)}</text>'
    )


class Theme:
    def __init__(self, t: dict):
        self.t, self.c, self.ty, self.sh = t, t["color"], t["type"], t["shape"]
        c = self.c
        self.tones = [c["series-1"], c["series-2"], c["series-3"], c["series-4"]]
        self.string = mix(c["series-4"], c["ink"], 0.45)  # warm, readable string colour
        self.number = c["series-2"]
        self.box = f'fill="{c["surface"]}" stroke="{c["line"]}" stroke-width="1.3"'
        self.mono = self.ty["mono"]


# --------------------------------------------------------------------------- sizing
CODE_PX, CODE_LH, PAD = 17, 27, 24


def block_size(b: dict) -> tuple[float, float]:
    k = b["kind"]
    if k == "text":
        return max(420, len(b["text"]) * 22 * SANS_W + 2 * PAD), 58
    if k == "code":
        lines = b["code"].split("\n")
        w = max(len(ln) for ln in lines) * CODE_PX * MONO_W + 2 * PAD
        return max(420, w), len(lines) * CODE_LH + 2 * PAD - 6
    if k == "process":
        return 240, 0  # height is the column's
    if k == "render":
        rows = len(b.get("table", {}).get("rows", []))
        return 600, 100 + (130 if b.get("kpis") else 0) + (
            170 if b.get("line") or b.get("bars") else 0
        ) + (40 + rows * 30 if rows else 0)
    return 0, 0


def notes_height(b: dict) -> float:
    notes = len(b.get("highlight", [])) * 26 + (10 if b.get("highlight") else 0)
    return notes + (34 if b.get("caption") and b["kind"] != "process" else 0)


# --------------------------------------------------------------------------- blocks
def code_lines(code: str, x: float, y: float, th: Theme) -> list[str]:
    """One <text> per line (data-line), keys ink, strings warm, numbers/literals green."""
    out = []
    for i, ln in enumerate(code.split("\n")):
        spans, pos = [], 0
        for m in TOKEN.finditer(ln):
            if m.start() > pos:
                spans.append((ln[pos : m.start()], th.c["ink"]))
            if m.group(1):
                spans.append((m.group(1), th.c["ink"] if m.group(2) else th.string))
                if m.group(2):
                    spans.append((m.group(2), th.c["ink"]))
            else:
                spans.append((m.group(3), th.number))
            pos = m.end()
        if pos < len(ln):
            spans.append((ln[pos:], th.c["ink"]))
        inner = "".join(f'<tspan fill="{fill}">{escape(seg)}</tspan>' for seg, fill in spans if seg)
        out.append(
            f'<text x="{x:.1f}" y="{y + i * CODE_LH:.1f}" font-size="{CODE_PX}" fill="{th.c["ink"]}" font-family="{esc(th.mono)}" '
            f'xml:space="preserve" data-line="{i}">{inner}</text>'
        )
    return out


def locate(code: str, match: str) -> tuple[int, int] | None:
    for i, ln in enumerate(code.split("\n")):
        j = ln.find(match)
        if j >= 0:
            return i, j
    return None


def callouts(
    b: dict, x: float, y: float, w: float, h: float, th: Theme, uid: str
) -> tuple[list[str], list[str]]:
    """(highlights, callouts): a tint behind each matched token — drawn under the code so
    the token stays one text — and a bracket from it to its note under the panel."""
    rects, out = [], []
    hs = b.get("highlight", [])
    for k, hl in enumerate(hs):
        at = locate(b["code"], hl["match"])
        if not at:
            err(f"highlight {hl['match']!r} not found in the code of {b.get('label')!r}")
            continue
        li, col = at
        tone = th.tones[(hl.get("tone", 1) - 1) % 4]
        tx = x + PAD + col * CODE_PX * MONO_W
        tw = len(hl["match"]) * CODE_PX * MONO_W
        ty = y + PAD + 12 + li * CODE_LH
        # the leader leaves from the end of the line, never across the code after the token
        lead = max(
            tx + tw + 5, x + PAD + len(b["code"].split("\n")[li].rstrip()) * CODE_PX * MONO_W + 6
        )
        ny = y + h + 30 + k * 26
        rail = x + w + 18 + (len(hs) - 1 - k) * 14
        note_w = len(hl["note"]) * 15 * MONO_W
        if note_w > w:
            err(
                f"note {hl['note']!r} is wider than its panel — keep it under {int(w / (15 * MONO_W))} characters"
            )
        hid = f"{uid}-{k}"
        rects.append(
            f'<rect x="{tx - 3:.1f}" y="{ty - 17:.1f}" width="{tw + 6:.1f}" height="23" rx="3" '
            f'fill="{mix(th.c["surface"], tone, 0.1)}" data-hl="{hid}"/>'
        )
        out.append(
            f'<g data-kind="callout" data-order="{k}" data-hl="{hid}">'
            f'<path d="M{lead:.1f},{ty - 5:.1f} H{rail:.1f} V{ny - 5:.1f} H{x + note_w + 12:.1f}" '
            f'fill="none" stroke="{tone}" stroke-width="1.3" data-draw="1"/>'
            + text(x, ny, hl["note"], 15, tone, 500, family=th.mono)
            + "</g>"
        )
    return rects, out


SECTION = "<!--ds-section-->"  # render_panel splits here: each part becomes its own step


def render_panel(b: dict, x: float, y: float, w: float, h: float, th: Theme) -> list[str]:
    c = th.c
    out = [f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" {th.box}/>']
    cx, cy = x + PAD, y + PAD + 24
    out.append(text(cx, cy, b.get("title", ""), 24, c["ink"], 500))
    if b.get("subtitle"):
        out.append(text(cx, cy + 26, b["subtitle"], 13, c["muted"], 400, family=th.mono))
    cy += 50
    inner = w - 2 * PAD
    if b.get("kpis"):
        out.append(SECTION)
        n = len(b["kpis"])
        kw = (inner - (n - 1) * 12) / n
        for i, kp in enumerate(b["kpis"]):
            kx = cx + i * (kw + 12)
            out.append(
                f'<rect x="{kx:.1f}" y="{cy:.1f}" width="{kw:.1f}" height="100" fill="none" stroke="{c["line"]}" stroke-width="1"/>'
            )
            out.append(
                text(kx + 12, cy + 24, kp["label"].upper(), 11, c["muted"], 500, family=th.mono)
            )
            out.append(text(kx + 12, cy + 58, kp["value"], 24, c["ink"], 500))
            if kp.get("delta"):
                up = not kp["delta"].startswith("-")
                out.append(
                    text(kx + 12, cy + 84, ("↑ " if up else "↓ ") + kp["delta"], 12,
                         c["ink"] if up else mix(c["signal"], c["ink"], 0.4), 500, family=th.mono)
                )  # fmt: skip
        cy += 120
    if b.get("line") or b.get("bars"):
        out.append(SECTION)
        halves = [k for k in ("line", "bars") if b.get(k)]
        pw = (inner - 12 * (len(halves) - 1)) / len(halves)
        for i, k in enumerate(halves):
            px = cx + i * (pw + 12)
            out.append(
                f'<rect x="{px:.1f}" y="{cy:.1f}" width="{pw:.1f}" height="150" fill="none" stroke="{c["line"]}" stroke-width="1"/>'
            )
            out.append(text(px + 12, cy + 22, b.get(f"{k}_title", ""), 12, c["ink"], 500))
            gx, gy, gw, gh = px + 16, cy + 36, pw - 32, 100
            if k == "line":
                vals = [v for s in b["line"] for v in s]
                lo, hi = min(vals), max(vals)
                for si, series in enumerate(b["line"]):
                    pts = " ".join(
                        f"{gx + j * gw / (len(series) - 1):.1f},{gy + gh - (v - lo) / (hi - lo or 1) * gh:.1f}"
                        for j, v in enumerate(series)
                    )
                    out.append(
                        f'<polyline points="{pts}" fill="none" stroke="{th.tones[si % 4]}" stroke-width="2" '
                        f'stroke-linejoin="round" data-draw="1"/>'
                    )
            else:
                hi = max(b["bars"]) or 1
                bw = gw / len(b["bars"])
                for j, v in enumerate(b["bars"]):
                    bx = gx + j * bw + bw * 0.5
                    top = gy + gh - v / hi * gh
                    out.append(  # a bar is a thick line drawn upward, so it grows when animated
                        f'<path d="M{bx:.1f},{gy + gh:.1f} V{top:.1f}" stroke="{c["series-1"]}" '
                        f'stroke-width="{bw * 0.62:.1f}" data-draw="1"/>'
                    )
        cy += 170
    tb = b.get("table")
    if tb:
        out.append(SECTION)
        cols = tb["columns"]
        cw = inner / len(cols)
        out.append(
            f'<rect x="{cx:.1f}" y="{cy:.1f}" width="{inner:.1f}" height="{30 + 30 * len(tb["rows"]):.1f}" '
            f'fill="none" stroke="{c["line"]}" stroke-width="1"/>'
        )
        for j, col in enumerate(cols):
            anchor = "start" if j == 0 else "end"
            tx = cx + 12 if j == 0 else cx + (j + 1) * cw - 12
            out.append(text(tx, cy + 20, col.upper(), 11, c["muted"], 500, anchor, family=th.mono))
        for r, row in enumerate(tb["rows"]):
            ry = cy + 30 + r * 30
            out.append(
                f'<path d="M{cx:.1f},{ry:.1f} H{cx + inner:.1f}" stroke="{c["subtle"]}" stroke-width="1"/>'
            )
            for j, v in enumerate(row):
                anchor = "start" if j == 0 else "end"
                tx = cx + 12 if j == 0 else cx + (j + 1) * cw - 12
                out.append(text(tx, ry + 20, str(v), 13, c["ink"], 400, anchor))
    return out


# --------------------------------------------------------------------------- layout
def validate(spec: dict) -> bool:
    cols = spec.get("columns")
    if not isinstance(cols, list) or not 2 <= len(cols) <= 12:
        err("columns must be a list of 2-12 stages")
        return False
    for i, col in enumerate(cols):
        if not isinstance(col, list) or not 1 <= len(col) <= 3:
            err(f"columns[{i}] must hold 1-3 blocks")
            continue
        for j, b in enumerate(col):
            if not isinstance(b, dict) or b.get("kind") not in KINDS:
                err(f"columns[{i}][{j}].kind must be one of {sorted(KINDS)}")
                continue
            if b["kind"] == "process" and len(col) != 1:
                err(f"columns[{i}]: a process box stands alone in its column")
            if b["kind"] == "code":
                lines = str(b.get("code", "")).split("\n")
                if len(lines) > 22 or max(map(len, lines)) > 64:
                    err(
                        f"columns[{i}][{j}] code is {len(lines)} lines / {max(map(len, lines))} wide (max 22 x 64) — cut it"
                    )
                if len(b.get("highlight", [])) > 3:
                    err(f"columns[{i}][{j}]: at most 3 callouts per panel")
            if b["kind"] == "text" and not isinstance(b.get("text"), str):
                err(f"columns[{i}][{j}] text block needs text")
    tm = spec.get("timing")
    if tm is not None and not (
        isinstance(tm, list)
        and 1 <= len(tm) <= 6
        and all(isinstance(s.get("ms"), (int, float)) for s in tm)
    ):
        err("timing must be 1-6 {label, ms} segments")
    return not errors


def wrap_columns(items: list[str]) -> list[str]:
    """Group every element of a stage into <g data-colwrap="k"> (keeps order within a stage)."""
    cols: dict[int, list[str]] = {}
    loose = []
    for it in items:
        m = re.search(r'data-col="(\d+)"', it[:200])
        if m:
            cols.setdefault(int(m.group(1)), []).append(it)
        else:
            loose.append(it)
    return loose + [
        f'<g data-colwrap="{k}">' + "\n".join(v) + "</g>" for k, v in sorted(cols.items())
    ]


def render(spec: dict, t: dict) -> str:
    th = Theme(t)
    c = th.c
    H = spec.get("height", 900)
    m, gap = 64, 104
    title_h = 90 if spec.get("title") and spec.get("show_title") else 0  # inline by default
    cols = spec["columns"]
    widths, heights = [], []
    for col in cols:
        sizes = [block_size(b) for b in col]
        widths.append(max(s[0] for s in sizes))
        heights.append(
            sum(s[1] + 34 + notes_height(b) for s, b in zip(sizes, col, strict=True))
            + 48 * (len(col) - 1)
        )
    avail = H - title_h - 2 * m
    process_h = min(avail * 0.62, 520)
    parts: list[str] = []
    step = 1
    x = m + 40
    col_boxes: list[list[tuple[float, float, float, float]]] = []
    for ci, col in enumerate(cols):
        w = widths[ci]
        boxes = []
        if col[0]["kind"] == "process":
            b = col[0]
            h = process_h
            y = title_h + m + (avail - h) / 2
            spaced = " ".join(b["label"].upper())
            g = [f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" {th.box}/>']
            size = min(40, (w - 36) / (len(spaced) * 0.62))  # letter-spaced name fits its box
            g.append(
                text(
                    x + w / 2, y + h / 2 + size * 0.36, spaced, round(size), c["ink"], 400, "middle"
                )
            )
            parts.append(f'<g data-step="{step}" data-kind="node" data-col="{ci}">{"".join(g)}</g>')
            step += 1
            if b.get("caption"):
                cap = [
                    text(
                        x + w / 2,
                        y + h + 34 + k * 20,
                        ln,
                        15,
                        c["series-3"],
                        500,
                        "middle",
                        family=th.mono,
                    )
                    for k, ln in enumerate(b["caption"].split("\n"))
                ]
                parts.append(
                    f'<g data-step="{step}" data-kind="note" data-col="{ci}">{"".join(cap)}</g>'
                )
                step += 1
            boxes.append((x, y, w, h))
        else:
            y = title_h + m + (avail - heights[ci]) / 2
            for b in col:
                bw, bh = block_size(b)
                bw = w
                label = text(x, y + 16, b.get("label", ""), 17, c["muted"], 400, family=th.mono)
                by = y + 30
                g = [label]
                kind = "node"
                if b["kind"] == "text":
                    g.append(
                        f'<rect x="{x:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{bh:.1f}" {th.box}/>'
                    )
                    g.append(
                        text(x + PAD, by + bh / 2 + 7, b["text"], 20, c["ink"], 400, family=th.mono)
                    )
                elif b["kind"] == "code":
                    kind = "code"
                    g.append(
                        f'<rect x="{x:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{bh:.1f}" {th.box}/>'
                    )
                    hl_rects, hl_groups = callouts(b, x, by, bw, bh, th, f"{ci}-{len(boxes)}")
                    g += hl_rects  # tints sit under the code lines
                    g += code_lines(b["code"], x + PAD, by + PAD + 12, th)
                elif b["kind"] == "render":
                    g += render_panel(b, x, by, bw, bh, th)
                for section in "".join(g).split(SECTION):  # a dashboard builds part by part
                    parts.append(
                        f'<g data-step="{step}" data-kind="{kind}" data-col="{ci}">{section}</g>'
                    )
                    step += 1
                step -= 1
                step += 1
                if b["kind"] == "code" and b.get("highlight"):
                    cl = hl_groups
                    parts.append(
                        f'<g data-step="{step}" data-kind="callouts" data-col="{ci}">{"".join(cl)}</g>'
                    )
                    step += 1
                if b.get("caption"):  # a caption under any artifact ("23 ms · the spec becomes …")
                    cy_ = by + bh + notes_height(b) - 4
                    parts.append(
                        f'<g data-step="{step}" data-kind="note" data-col="{ci}">'
                        + text(
                            x + bw / 2,
                            cy_,
                            b["caption"],
                            15,
                            c["series-3"],
                            500,
                            "middle",
                            family=th.mono,
                        )
                        + "</g>"
                    )
                    step += 1
                boxes.append((x, by, bw, bh))
                y = by + bh + notes_height(b) + 48
        col_boxes.append(boxes)
        x += w + gap
    # arrows between neighbouring columns: one per block on the side that has several
    arrows = []
    for ci in range(len(cols) - 1):
        a, b = col_boxes[ci], col_boxes[ci + 1]
        ys = [bb[1] + bb[3] / 2 for bb in (a if len(a) >= len(b) else b)]
        x0 = max(bb[0] + bb[2] for bb in a) + 10
        x1 = min(bb[0] for bb in b) - 10
        lo = max(min(bb[1] for bb in a), min(bb[1] for bb in b)) + 16  # both sides must be there
        hi = min(max(bb[1] + bb[3] for bb in a), max(bb[1] + bb[3] for bb in b)) - 16
        for yy in ys:
            yy = min(max(yy, lo), hi)  # clamp the port into the shared span
            arrows.append(
                f'<g data-step="{ci}" data-kind="edge" data-col="{ci + 1}"><path d="M{x0:.1f},{yy:.1f} H{x1:.1f}" '
                f'fill="none" stroke="{c["line"]}" stroke-width="1.3" marker-end="url(#ds-arrow)" data-draw="1"/></g>'
            )
    # wire each arrow step to the step of the block it enters
    first_step = {}
    for p in parts:
        mm = re.match(r'<g data-step="(\d+)" data-kind="\w+" data-col="(\d+)"', p)
        if mm:
            first_step.setdefault(int(mm.group(2)), int(mm.group(1)))
    arrows = [
        re.sub(
            r'data-step="\d+" data-kind="edge" data-col="(\d+)"',
            lambda mm: (
                f'data-step="{first_step[int(mm.group(1))]}" data-kind="edge" data-col="{mm.group(1)}"'
            ),
            a,
        )
        for a in arrows
    ]
    W = x - gap + m + 40
    # timing bar: its own closing stage
    if spec.get("timing"):
        tm = spec["timing"]
        total = sum(s_["ms"] for s_ in tm)
        bw = 620
        tx, ty = W + 20, title_h + m + avail / 2 - 40
        seg = [text(tx, ty - 22, f"total {total:g} ms", 26, c["ink"], 400, family=th.mono)]
        parts.append(
            f'<g data-step="{step}" data-kind="note" data-col="{len(cols)}">{"".join(seg)}</g>'
        )
        step += 1
        cx, label_end, row = tx, -1e9, 0
        for k, s_ in enumerate(tm):
            w_ = max(6.0, s_["ms"] / total * bw) - (4 if k < len(tm) - 1 else 0)
            tone = th.tones[k % 4]
            lab = f"{s_['label']} {s_['ms']:g} ms"
            lw = len(lab) * 16 * 0.62  # mono advance
            lx = max(cx, label_end + 20)  # a short segment's label must not run into the next one
            if lx + lw > tx + bw + 60:
                lx, row = cx, row + 1  # no room on this line: drop below
            label_end = lx + lw
            g = (
                f'<path d="M{cx:.1f},{ty + 8:.1f} H{cx + w_:.1f}" stroke="{tone}" stroke-width="16" data-draw="1"/>'
                + text(lx, ty + 50 + 24 * row, lab, 16, tone, 500, family=th.mono)
            )
            parts.append(f'<g data-step="{step}" data-kind="edge" data-col="{len(cols)}">{g}</g>')
            step += 1
            cx += w_ + 4
        if spec.get("footer"):
            parts.append(
                f'<g data-step="{step}" data-kind="note" data-col="{len(cols)}">'
                + text(tx, ty + 110 + 24 * row, spec["footer"], 18, c["muted"], 400, family=th.mono)
                + "</g>"
            )
            step += 1
        foot_w = len(spec.get("footer") or "") * 18 * 0.62  # mono advance
        W = tx + max(bw, foot_w) + m + 40
    head = (
        text(m, m + 34, spec["title"], 34, c["ink"], t["type"]["title-weight"]) if title_h else ""
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:.0f} {H:.0f}" width="{W:.0f}" height="{H:.0f}" '
        f'font-family="{esc(t["type"]["sans"])}" data-design-system="{escape(t["name"])}">\n'
        f"<title>{escape(spec.get('title') or 'Pipeline')}</title><desc>{escape(spec.get('footer') or 'pipeline explainer')}</desc>\n"
        f"<defs>{svg_defs(t)}</defs>\n"
        f'<rect width="{W:.0f}" height="{H:.0f}" fill="{c["canvas"]}"/>\n'
        f'<g data-step="0" data-kind="title">{head}</g>\n'
        + "\n".join(wrap_columns(arrows + parts))
        + "\n</svg>\n"
    )


SAMPLE = {
    "columns": [
        [
            {"kind": "text", "label": "request", "text": "Top products this quarter"},
            {
                "kind": "code",
                "label": "graphql query",
                "code": "query TopProducts($range: Range!) {\n"
                "  totals(range: $range, compare: PREVIOUS) {\n"
                "    revenue orders avgOrder newBuyers\n"
                "  }\n"
                "  products(first: 4, range: $range) {\n"
                "    name revenue orders share\n"
                "    weekly { revenue }\n"
                "  }\n"
                "}",
                "highlight": [
                    {
                        "match": "newBuyers",
                        "note": "only the fields the dashboard shows",
                        "tone": 1,
                    }
                ],
            },
        ],
        [{"kind": "process", "label": "Gateway", "caption": "parse · validate · plan\n12 ms"}],
        [
            {
                "kind": "code",
                "label": "query plan",
                "code": "{\n"
                '  "totals": { "from": "warehouse" },\n'
                '  "products": { "from": "catalog" },\n'
                '  "weekly": {\n'
                '    "from": "warehouse",\n'
                '    "batched": true\n'
                "  },\n"
                '  "orders": { "from": "orders-db" },\n'
                '  "cost": 38\n'
                "}",
                "highlight": [
                    {"match": "true", "note": "DataLoader batches the N+1 lookups", "tone": 1},
                    {"match": "38", "note": "under the 100-point cost limit", "tone": 2},
                ],
            }
        ],
        [{"kind": "process", "label": "Resolvers", "caption": "3 sources in parallel · 64 ms"}],
        [
            {
                "kind": "render",
                "label": "render",
                "title": "Top products · Q3",
                "subtitle": "Jul 1 - Sep 20 · vs Apr 1 - Jun 20",
                "kpis": [
                    {"label": "Revenue", "value": "$512K", "delta": "+9.2%"},
                    {"label": "Orders", "value": "4,380", "delta": "+6.1%"},
                    {"label": "Avg order", "value": "$117", "delta": "-2.4%"},
                    {"label": "New buyers", "value": "1,204", "delta": "+12.5%"},
                ],
                "line_title": "Revenue per week by product",
                "line": [
                    [3, 4, 3.8, 5, 5.2, 4.6, 6, 5.9],
                    [2, 2.4, 2.2, 2.8, 3, 2.7, 3.4, 3.2],
                    [1.2, 1.4, 1.3, 1.8, 1.7, 1.6, 2.2, 2],
                    [0.8, 0.9, 1.1, 1, 1.2, 1.3, 1.2, 1.5],
                ],
                "bars_title": "Revenue by product",
                "bars": [182, 141, 108, 81],
                "table": {
                    "columns": ["Product", "Revenue", "Orders", "Share"],
                    "rows": [
                        ["Trail Pack", "$182K", "1,532", "36%"],
                        ["Rain Shell", "$141K", "1,208", "28%"],
                        ["Camp Stove", "$108K", "921", "21%"],
                        ["Trail Mug", "$81K", "719", "15%"],
                    ],
                },
            }
        ],
    ],
    "timing": [
        {"label": "gateway", "ms": 12},
        {"label": "resolvers", "ms": 64},
        {"label": "render", "ms": 9},
    ],
    "footer": "one request, one round trip, only the fields that were asked for.",
}


def self_test() -> int:
    global errors
    errors = []
    t = dt.load(None)
    assert validate(SAMPLE), errors
    svg = render(SAMPLE, t)
    ET.fromstring(svg)  # noqa: S314 - our own generated markup
    assert svg.count("data-line=") > 15 and 'data-kind="callouts"' in svg and "total 85 ms" in svg
    assert not errors, errors
    errors = []
    assert not validate(
        {"columns": [[{"kind": "process", "label": "x"}, {"kind": "text", "text": "y"}], []]}
    )
    print("OK: self-test passed")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("spec", nargs="?", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--design-system", default=None)
    ap.add_argument("--sample", action="store_true")
    ap.add_argument("--show-title", action="store_true", help="draw the title (slides)")
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
        spec = SAMPLE if a.sample else json.loads(a.spec.read_text(encoding="utf-8"))
        if a.show_title:
            spec = dict(spec, show_title=True)
        t = dt.load(a.design_system)
    except (OSError, ValueError, AttributeError, dt.TokenError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if not validate(spec):
        print("\n".join(errors), file=sys.stderr)
        return 1
    svg = render(spec, t)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    if a.canvas:
        svg, small = dt.fit_canvas(svg, a.canvas, t["color"]["canvas"])
        if small < dt.READABLE_PX:
            print(
                f"WARN: on {a.canvas} the smallest text is {small:.1f}px (< {dt.READABLE_PX}) — "
                "use a larger canvas or the natural size, or animate it with a camera",
                file=sys.stderr,
            )
    if not a.out:
        sys.stdout.write(svg)
        return 0
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(svg, encoding="utf-8")
    print(f"OK: wrote {a.out} (design system: {t['name']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
