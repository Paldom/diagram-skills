#!/usr/bin/env python3
"""arch_svg.py — architecture diagrams: Graphviz lays out, the design system paints.

The model writes a small JSON spec (groups, cards, edges, numbered steps,
notes); `dot -Tjson` computes positions and edge routes; this script paints a
self-contained SVG in the active design system: group panels with section
titles, cards with outline-icon tiles, pill tags, sticky notes, orthogonal
connectors with rounded corners, numbered step badges plus a legend, and the
design system's elevation. Every element carries `data-step` so
diagram-animate can reveal it in reading order. Pure stdlib + the `dot` CLI.

Spec (JSON):
  {"title": "...", "subtitle": "...", "direction": "LR"|"TB",
   "groups": [{"id", "title", "parent"?, "pill"?, "style": "panel"|"dashed"|"tint"}],
   "nodes":  [{"id", "label", "sub"?, "icon"?, "group"?, "pill"?, "accent"?, "kind": "card"|"code"}],
   "edges":  [{"from", "to", "label"?, "step"?, "dashed"?}],
   "notes":  [{"text", "near", "side"?: "top"|"right"|"bottom"|"left"}],
   "steps":  {"1": "Authenticate", ...},
   "footer": "...",
   "layout": "columns"   (optional: top-level groups become equal-height peer columns),
   "scope": {"label": "Terraform", "pill": "IaC"}   (optional: one outline around every group)}

Usage:
    python3 arch_svg.py SPEC.json --out OUT.svg [--design-system PATH]
    python3 arch_svg.py --self-test
Exit 1 with ERROR lines on an invalid spec or a missing `dot`.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import design_tokens as dt  # noqa: E402
import icons  # noqa: E402

PT = 72.0  # dot works in points; we render 1 pt = 1 px
CHAR = 0.56  # average glyph width in em for the sans stack
ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,40}$")

errors: list[str] = []


def err(msg: str) -> None:
    errors.append(f"ERROR: {msg}")


def text_w(s: str, size: float, bold: bool = False) -> float:
    return len(s) * size * (CHAR + (0.04 if bold else 0))


def wrap(s: str, size: float, max_w: float, lines: int = 2) -> list[str]:
    words, out, cur = s.split(), [], ""
    for w in words:
        cand = f"{cur} {w}".strip()
        if text_w(cand, size) <= max_w or not cur:
            cur = cand
        else:
            out.append(cur)
            cur = w
    if cur:
        out.append(cur)
    if len(out) > lines:
        out = [*out[: lines - 1], " ".join(out[lines - 1 :])]
    return out


# --- validation ------------------------------------------------------------------


def validate(spec: dict) -> bool:
    if not isinstance(spec, dict):
        err("spec must be a JSON object")
        return False
    if not isinstance(spec.get("title"), str) or not spec["title"].strip():
        err("title is required — it states the takeaway")
    groups = spec.get("groups", [])
    nodes = spec.get("nodes", [])
    if spec.get("layout", "auto") not in ("auto", "columns"):
        err(
            'layout must be "auto" or "columns" (top-level groups become equal-height peer columns)'
        )
    sc = spec.get("scope")
    if sc is not None and not (
        isinstance(sc, dict)
        and isinstance(sc.get("label"), str)
        and len(sc["label"]) <= 24
        and len(str(sc.get("pill", ""))) <= 12
    ):
        err(
            'scope must be {"label": "<= 24 chars", "pill": "<= 12 chars"} — the outline around every group'
        )
    edges = spec.get("edges", [])
    gids = {g.get("id") for g in groups if isinstance(g, dict)}
    nids = set()
    for i, g in enumerate(groups):
        if not isinstance(g, dict) or not ID_RE.match(str(g.get("id", ""))):
            err(f"groups[{i}] needs an id matching {ID_RE.pattern}")
        if g.get("parent") and g["parent"] not in gids:
            err(f"groups[{i}].parent {g['parent']!r} is not a group id")
        if g.get("style", "panel") not in ("panel", "dashed", "tint"):
            err(f"groups[{i}].style must be panel, dashed or tint")
    if not nodes or len(nodes) > 24:
        err(f"need 1-24 nodes, got {len(nodes)} — split into views above 24")
    accents = 0
    for i, n in enumerate(nodes):
        if not isinstance(n, dict) or not ID_RE.match(str(n.get("id", ""))):
            err(f"nodes[{i}] needs an id matching {ID_RE.pattern}")
            continue
        if n["id"] in nids or n["id"] in gids:
            err(f"nodes[{i}].id {n['id']!r} is not unique")
        nids.add(n["id"])
        if not isinstance(n.get("label"), str) or not n["label"].strip():
            err(f"nodes[{i}] needs a label")
        elif len(n["label"]) > 40:
            err(f"nodes[{i}].label is {len(n['label'])} chars (max 40)")
        if n.get("group") and n["group"] not in gids:
            err(f"nodes[{i}].group {n['group']!r} is not a group id")
        if n.get("icon"):
            try:
                icons.icon_svg(n["icon"], 0, 0, 10, "#000000")
            except KeyError as e:
                err(f"nodes[{i}]: {e.args[0]}")
        accents += bool(n.get("accent"))
    if accents > 1:
        err(f"{accents} nodes marked accent — the highlighter goes on one element")
    for i, e in enumerate(edges):
        if not isinstance(e, dict) or e.get("from") not in nids or e.get("to") not in nids:
            err(f"edges[{i}] from/to must be node ids")
    steps = {str(e["step"]) for e in edges if isinstance(e, dict) and e.get("step")}
    legend = {str(k) for k in spec.get("steps", {})}
    if steps and not steps <= legend:
        err(f"steps {sorted(steps - legend)} have no legend entry in spec.steps")
    for i, n in enumerate(spec.get("notes", [])):
        if not isinstance(n, dict) or n.get("near") not in nids | gids:
            err(f"notes[{i}].near must be a node or group id")
        elif len(str(n.get("text", ""))) > 160:
            err(f"notes[{i}].text is over 160 chars — a note is a sentence, not a paragraph")
    return not errors


# --- layout via dot --------------------------------------------------------------


def node_size(n: dict, t: dict) -> tuple[float, float]:
    sp, ty = t["space"], t["type"]
    if n.get("kind") == "code":
        lines = n["label"].split("\\n") + str(n.get("sub", "")).split("\n")
        lines = [ln for ln in lines if ln]
        w = max(text_w(ln, ty["small-size"]) * 1.05 for ln in lines) + 2 * sp["padding"]
        return max(w, 140), len(lines) * ty["small-size"] * 1.5 + 2 * sp["padding"]
    has_icon = bool(n.get("icon")) and t["icon"]["style"] != "none"
    w = sp["card-width"]
    lbl = wrap(n["label"], ty["label-size"], w - 16)
    w = max(w, max(text_w(ln, ty["label-size"], True) for ln in lbl) + 24)
    h = 18 + len(lbl) * ty["label-size"] * 1.25
    if n.get("sub"):
        h += len(wrap(n["sub"], ty["small-size"], w - 16)) * ty["small-size"] * 1.3 + 2
    if has_icon:
        h += t["icon"]["size"] + 10
    return w, max(h, 52)


def title_for(g: dict, t: dict) -> str:
    title = g.get("title", "")
    return title.upper() if t["type"]["section-case"] == "upper" else title


def build_dot(spec: dict, t: dict, sizes: dict) -> str:
    rank = spec.get("direction", "LR")
    out = [
        "digraph G {",
        f"  graph [rankdir={rank}, splines=ortho, nodesep=0.55, ranksep=0.9, compound=true, newrank=true];",
        '  node [shape=box, fixedsize=true, label=""];',
    ]

    def emit_group(gid: str, depth: int) -> None:
        g = next(x for x in spec.get("groups", []) if x["id"] == gid)
        out.append(f"{'  ' * depth}subgraph cluster_{gid} {{")
        # reserve the title band: dot sizes the cluster label, we draw our own text
        out.append(f'{"  " * depth}  label="{escape(title_for(g, t))}"; labeljust=l; labelloc=t;')
        # bold uppercase renders wider than dot's estimate: reserve with a larger size
        out.append(f"{'  ' * depth}  fontsize={t['type']['label-size'] + 9}; margin=18;")
        for sub in spec.get("groups", []):
            if sub.get("parent") == gid:
                emit_group(sub["id"], depth + 1)
        for n in spec["nodes"]:
            if n.get("group") == gid:
                w, h = sizes[n["id"]]
                out.append(
                    f'{"  " * depth}  "{n["id"]}" [width={w / PT:.3f}, height={h / PT:.3f}];'
                )
        out.append(f"{'  ' * depth}}}")

    for g in spec.get("groups", []):
        if not g.get("parent"):
            emit_group(g["id"], 1)
    for n in spec["nodes"]:
        if not n.get("group"):
            w, h = sizes[n["id"]]
            out.append(f'  "{n["id"]}" [width={w / PT:.3f}, height={h / PT:.3f}];')
    for e in spec.get("edges", []):
        attrs = ["arrowhead=none"]
        if e.get("constraint") is False:
            attrs.append("constraint=false")
        out.append(f'  "{e["from"]}" -> "{e["to"]}" [{", ".join(attrs)}];')
    if (
        spec.get("layout") == "columns"
    ):  # layers side by side: every node of layer k ranks before layer k+1
        tops = [g["id"] for g in spec.get("groups", []) if not g.get("parent")]
        members = {gid: nodes_in(spec, gid) for gid in tops}
        for a, b in itertools.pairwise(tops):
            for x in members[a]:
                for y in members[b]:
                    out.append(f'  "{x}" -> "{y}" [style=invis, weight=0];')
    out.append("}")
    return "\n".join(out)


def nodes_in(spec: dict, gid: str) -> list[str]:
    """Node ids in a group or any group nested inside it."""
    inside = {gid}
    changed = True
    while changed:
        changed = False
        for g in spec.get("groups", []):
            if g.get("parent") in inside and g["id"] not in inside:
                inside.add(g["id"])
                changed = True
    return [n["id"] for n in spec["nodes"] if n.get("group") in inside]


def run_dot(src: str) -> dict:
    exe = shutil.which("dot")
    if not exe:
        raise RuntimeError(
            "Graphviz `dot` not found — install it (brew install graphviz / apt-get install graphviz)"
        )
    proc = subprocess.run([exe, "-Tjson"], input=src, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(f"dot failed: {proc.stderr.strip()[-300:]}")
    return json.loads(proc.stdout)


def parse_pos(pos: str, H: float) -> list[tuple[float, float]]:
    """dot edge `pos` (optionally 'e,x,y ' prefixed) -> list of points, y flipped."""
    pts, end = [], None
    for tok in pos.split():
        if tok.startswith(("e,", "s,")):
            _, x, y = tok.split(",")
            if tok.startswith("e,"):
                end = (float(x), H - float(y))
            continue
        x, y = tok.split(",")
        pts.append((float(x), H - float(y)))
    if end:
        pts.append(end)
    return pts


def polyline_from_spline(pts: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Ortho splines come as cubic control points; keep the segment endpoints."""
    keep = pts[::3] if len(pts) >= 4 and (len(pts) - 1) % 3 == 0 else pts
    out = [keep[0]]
    for p in keep[1:]:
        if abs(p[0] - out[-1][0]) > 0.5 or abs(p[1] - out[-1][1]) > 0.5:
            out.append(p)
    # merge collinear runs
    merged = [out[0]]
    for i in range(1, len(out) - 1):
        a, b, c = merged[-1], out[i], out[i + 1]
        if abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) > 1.0:
            merged.append(b)
    merged.append(out[-1])
    return merged


def rounded_path(pts: list[tuple[float, float]], r: float) -> str:
    if len(pts) < 3 or r <= 0:
        return "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts)
    d = [f"M{pts[0][0]:.1f} {pts[0][1]:.1f}"]
    for i in range(1, len(pts) - 1):
        (x0, y0), (x1, y1), (x2, y2) = pts[i - 1], pts[i], pts[i + 1]
        l1 = math.hypot(x1 - x0, y1 - y0)
        l2 = math.hypot(x2 - x1, y2 - y1)
        rr = min(r, l1 / 2, l2 / 2)
        ax, ay = x1 - (x1 - x0) / l1 * rr, y1 - (y1 - y0) / l1 * rr
        bx, by = x1 + (x2 - x1) / l2 * rr, y1 + (y2 - y1) / l2 * rr
        d.append(f"L{ax:.1f} {ay:.1f} Q{x1:.1f} {y1:.1f} {bx:.1f} {by:.1f}")
    d.append(f"L{pts[-1][0]:.1f} {pts[-1][1]:.1f}")
    return " ".join(d)


def longest_segment_mid(pts: list[tuple[float, float]]) -> tuple[float, float, bool]:
    best, mid, horiz = -1.0, pts[0], True
    for a, b in itertools.pairwise(pts):
        seg = math.hypot(b[0] - a[0], b[1] - a[1])
        if seg > best:
            best, mid, horiz = seg, ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2), abs(b[1] - a[1]) < 1
    return mid[0], mid[1], horiz


# --- painting --------------------------------------------------------------------


def text(x, y, s, size, fill, weight=400, anchor="start", family=None, extra="") -> str:
    fam = f' font-family="{escape(family, {chr(34): "&quot;"})}"' if family else ""
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" font-weight="{weight}" fill="{fill}" '
        f'text-anchor="{anchor}"{fam}{extra}>{escape(s)}</text>'
    )


def render(spec: dict, t: dict) -> str:
    c, ty, sh, sp = t["color"], t["type"], t["shape"], t["space"]
    sizes = {n["id"]: node_size(n, t) for n in spec["nodes"]}
    layout = run_dot(build_dot(spec, t, sizes))
    bb = [float(v) for v in layout["bb"].split(",")]
    GW, GH = bb[2], bb[3]
    objs = layout.get("objects", [])
    by_name = {o.get("name"): o for o in objs}

    m = sp["margin"]
    show = bool(spec.get("show_title"))  # inline by default: the title is only <title>/<desc>
    title_h = (
        ty["title-size"] * 1.3 + (ty["body-size"] * 1.8 if spec.get("subtitle") else 0) + 24
        if show
        else 0
    )
    steps = spec.get("steps", {})
    legend_h = 56 if steps else 0
    notes_pad = 150 if spec.get("notes") else 0
    W = GW + 2 * m + notes_pad
    head_w = max(  # the canvas is never narrower than its own title (display faces run wide)
        text_w(spec["title"], ty["title-size"], True) * 1.06,
        text_w(spec.get("subtitle") or "", ty["body-size"]),
    )
    if show and head_w + 2 * m > W:
        notes_pad += head_w + 2 * m - W  # grow the side margins so the diagram stays centred
        W = head_w + 2 * m
    scope_h = 40 if spec.get("scope") else 0
    H = GH + title_h + legend_h + scope_h + 2 * m + (24 if spec.get("footer") else 0)
    ox, oy = m + notes_pad / 2, m + title_h

    lift = t["elevation"]["style"] in ("neumorph", "soft")
    flt = ' filter="url(#ds-lift)"' if lift else ""
    parts: list[str] = []
    step = 0

    # groups (outer first)
    def raw_rect(gid):
        o = by_name.get(f"cluster_{gid}")
        if not o:
            return None
        x0, y0, x1, y1 = (float(v) for v in o["bb"].split(","))
        return ox + x0, oy + (GH - y1), x1 - x0, y1 - y0

    tops = [g["id"] for g in spec.get("groups", []) if not g.get("parent")]
    span = None
    if spec.get("layout") == "columns":  # peer layers share top and bottom edges
        rs = [r for g in tops if (r := raw_rect(g))]
        if rs:
            span = (min(r[1] for r in rs), max(r[1] + r[3] for r in rs))

    def group_rect(gid):
        r = raw_rect(gid)
        if r and span and gid in tops:
            return r[0], span[0], r[2], span[1] - span[0]
        return r

    gdepth = {}
    for g in spec.get("groups", []):
        d, p = 0, g.get("parent")
        while p:
            d += 1
            p = next((x.get("parent") for x in spec["groups"] if x["id"] == p), None)
        gdepth[g["id"]] = d
    group_boxes = {}
    gfill: dict[str, str] = {}  # the paint a node actually sits on, per group
    for g in sorted(spec.get("groups", []), key=lambda g: gdepth[g["id"]]):
        r = group_rect(g["id"])
        if not r:
            continue
        x, y, w, h = r
        group_boxes[g["id"]] = r
        style = g.get("style", "panel")
        rad = sh["radius"]
        under = gfill.get(g.get("parent"), c["canvas"])
        gfill[g["id"]] = (
            under
            if style == "dashed"
            else c["tile"]
            if (style == "tint" or gdepth[g["id"]] > 0)
            else c["group"]
        )
        if style == "dashed":
            shape = f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rad}" fill="none" stroke="{c["border"]}" stroke-width="{sh["stroke"]}" stroke-dasharray="6 5"/>'
        elif style == "tint" or gdepth[g["id"]] > 0:
            shape = f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rad}" fill="{c["tile"]}"/>'
        else:
            border = (
                f' stroke="{c["group-border"]}" stroke-width="1"'
                if sh["card-border"] == "hairline"
                else ""
            )
            shape = f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rad}" fill="{c["group"]}"{border}{flt}/>'
        title = g.get("title", "")
        if ty["section-case"] == "upper":
            title = title.upper()
        tl = text(
            x + 16,
            y + 26,
            title,
            ty["label-size"] + 1,
            c["ink"],
            ty["section-weight"],
            extra=f' letter-spacing="{ty["section-tracking"]}em"',
        )
        pill = pill_svg(g.get("pill"), x + w - 16, y, c, ty, anchor="end") if g.get("pill") else ""
        parent = f' data-group="{g["parent"]}"' if g.get("parent") else ""
        parts.append(
            f'<g data-step="{step}" data-kind="group" data-id="{g["id"]}"{parent}>{shape}{tl}{pill}</g>'
        )
    step += 1

    # nodes in reading order
    centers = {}
    for n in spec["nodes"]:
        o = by_name.get(n["id"])
        cx, cy = (float(v) for v in o["pos"].split(","))
        centers[n["id"]] = (ox + cx, oy + (GH - cy))
    order = sorted(
        spec["nodes"],
        key=lambda n: (
            (centers[n["id"]][0], centers[n["id"]][1])
            if spec.get("direction", "LR") == "LR"
            else (centers[n["id"]][1], centers[n["id"]][0])
        ),
    )
    node_boxes = {}
    for n in order:
        cx, cy = centers[n["id"]]
        w, h = sizes[n["id"]]
        x, y = cx - w / 2, cy - h / 2
        node_boxes[n["id"]] = (x, y, w, h)
        parts.append(
            f'<g data-step="{step}" data-kind="node" data-id="{n["id"]}" data-group="{n.get("group", "")}">'
            f"{node_svg(n, x, y, w, h, t, flt, gfill.get(n.get('group')))}</g>"
        )
        step += 1

    # edges: step-numbered first (in step order), then the rest
    edges = spec.get("edges", [])
    edge_order = sorted(
        range(len(edges)),
        key=lambda i: (edges[i].get("step") is None, edges[i].get("step") or 0, i),
    )
    dot_edges = list(layout.get("edges", []))
    badge_boxes: list[tuple[float, float, float, float]] = []
    wire_boxes: list[tuple[float, float, float, float]] = []
    marker = ' marker-end="url(#ds-arrow)"' if sh["arrow"] != "none" else ""
    for i in edge_order:
        e = edges[i]
        de = dot_edges[i]
        pts = polyline_from_spline(parse_pos(de["pos"], GH))
        pts = [(ox + x, oy + y) for x, y in pts]
        pts = clip_to_box(pts, node_boxes[e["from"]], node_boxes[e["to"]])
        for (px0, py0), (px1, py1) in itertools.pairwise(pts):  # connectors are obstacles for notes
            wire_boxes.append(
                (min(px0, px1) - 4, min(py0, py1) - 4, abs(px1 - px0) + 8, abs(py1 - py0) + 8)
            )
        d = rounded_path(pts, sh["corner"] if sh["connector"] != "straight" else 0)
        dash = ' stroke-dasharray="5 4"' if e.get("dashed") else ""
        g = [
            f'<path d="{d}" fill="none" stroke="{c["line"]}" stroke-width="{sh["stroke"]}"{dash}{marker} data-draw="1"/>'
        ]
        mx, my, horiz = longest_segment_mid(pts)
        if e.get("step"):
            r = sh["badge-radius"]
            badge_boxes.append((mx - r - 4, my - r - 4, 2 * r + 8, 2 * r + 8))
            g.append(
                f'<g data-kind="badge">{badge_shape(mx, my, r, c["badge"], sh)}'
                + text(
                    mx,
                    my + ty["small-size"] * 0.36,
                    str(e["step"]),
                    ty["small-size"] + 1,
                    c["badge-ink"],
                    700,
                    "middle",
                )
                + "</g>"
            )
            if e.get("label"):
                lx, ly = (mx, my - r - 6) if horiz else (mx + r + 6, my + 4)
                g.append(label_svg(e["label"], lx, ly, "middle" if horiz else "start", c, ty))
        elif e.get("label"):
            lx, ly = (mx, my - 7) if horiz else (mx + 8, my + 4)
            g.append(label_svg(e["label"], lx, ly, "middle" if horiz else "start", c, ty))
        parts.append(
            f'<g data-step="{step}" data-kind="edge" data-from="{e["from"]}" data-to="{e["to"]}">{"".join(g)}</g>'
        )
        step += 1

    # notes: beside their anchor, first side that does not collide
    seams = [  # a note must not straddle two layers
        (bx - 8, by, 16, bh)
        for gid, (gx, gy, gw, gh) in group_boxes.items()
        if gid in tops
        for bx, by, bh in ((gx, gy, gh), (gx + gw, gy, gh))
    ]
    occupied = list(node_boxes.values()) + badge_boxes + seams + wire_boxes
    for nt in spec.get("notes", []):
        anchor = node_boxes.get(nt["near"]) or group_boxes.get(nt["near"])
        home = next(  # keep the note inside the anchor's own layer when it has one
            (
                group_boxes[g]
                for g in tops
                if g in group_boxes and nt["near"] in [*nodes_in(spec, g), g]
            ),
            None,
        )
        box = place_note(nt, anchor, occupied, W, H, ty, home)
        occupied.append(box)
        parts.append(
            f'<g data-step="{step}" data-kind="note">{note_svg(nt["text"], box, c, ty, sh)}</g>'
        )
        step += 1

    # title, legend, footer
    head = ""
    if show:
        head = text(
            m,
            m + ty["title-size"],
            spec["title"],
            ty["title-size"],
            c["ink"],
            ty["title-weight"],
            extra=f' letter-spacing="{ty["title-tracking"]}em"',
        )
        if spec.get("subtitle"):
            head += text(
                m,
                m + ty["title-size"] + ty["body-size"] * 1.6,
                spec["subtitle"],
                ty["body-size"],
                c["lede"],
                400,
            )
    scope = ""
    if spec.get("scope") and group_boxes:
        sc = spec["scope"]
        pad = 14
        x0 = min(b[0] for b in group_boxes.values()) - pad
        y0 = min(b[1] for b in group_boxes.values()) - pad
        x1 = max(b[0] + b[2] for b in group_boxes.values()) + pad
        y1 = max(b[1] + b[3] for b in group_boxes.values()) + pad
        lab = sc.get("label", "")
        tag = sc.get("pill", "")
        ls_, ts_ = ty["label-size"] + 2, ty["small-size"] + 1
        lw = text_w(lab, ls_, True) + (text_w(tag, ts_) + 14 if tag else 0) + 40
        bx, bh = (x0 + x1) / 2 - lw / 2, 30
        inner = text(bx + 20, y1 + ls_ * 0.36, lab, ls_, c["ink"], 700)
        if tag:
            mono = ty["mono"] if ty["small-family"] == "mono" else None
            tx0 = bx + 34 + text_w(lab, ls_, True)
            inner += text(tx0, y1 + ts_ * 0.36, tag, ts_, c["muted"], 500, family=mono)
        scope = (
            f'<g data-step="{step}" data-kind="scope">'
            f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{x1 - x0:.1f}" height="{y1 - y0:.1f}" rx="{sh["radius"] + 4}" '
            f'fill="none" stroke="{c["badge"]}" stroke-width="{sh["stroke-strong"]}"/>'
            f'<rect x="{bx:.1f}" y="{y1 - bh / 2:.1f}" width="{lw:.1f}" height="{bh}" rx="{bh / 2}" fill="{c["surface"]}" '
            f'stroke="{c["badge"]}" stroke-width="{sh["stroke-strong"]}"/>{inner}</g>'
        )
        step += 1
    legend = ""
    if steps:
        lx, ly = (
            ox,
            H - m - (24 if spec.get("footer") else 0) - 8,
        )  # aligned with the diagram, not the canvas
        items = []
        for k in sorted(steps, key=lambda s: int(s)):
            r = sh["badge-radius"]
            items.append(
                badge_shape(lx + r, ly - 4, r, c["badge"], sh)
                + text(
                    lx + r,
                    ly - 4 + ty["small-size"] * 0.36,
                    k,
                    ty["small-size"] + 1,
                    c["badge-ink"],
                    700,
                    "middle",
                )
                + text(lx + 2 * r + 8, ly, steps[k], ty["label-size"], c["ink"], ty["label-weight"])
            )
            lx += 2 * r + 8 + text_w(steps[k], ty["label-size"]) + 32
        legend = f'<g data-step="{step}" data-kind="legend">{"".join(items)}</g>'
        step += 1
    foot = (
        text(W - m, H - m + 4, spec["footer"], ty["small-size"], c["muted"], 400, "end")
        if spec.get("footer")
        else ""
    )

    defs = svg_defs(t)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:.0f} {H:.0f}" width="{W:.0f}" height="{H:.0f}" '
        f'font-family="{escape(ty["sans"], {chr(34): "&quot;"})}" data-design-system="{escape(t["name"])}">\n'
        f"<title>{escape(spec['title'])}</title><desc>{escape(spec.get('subtitle') or spec['title'])}</desc>\n"
        f"<defs>{defs}</defs>\n"
        f'<rect width="{W:.0f}" height="{H:.0f}" fill="{c["canvas"]}"/>\n'
        f'<g data-step="0" data-kind="title">{head}</g>\n'
        + "\n".join(parts)
        + f"\n{scope}{legend}{foot}\n</svg>\n"
    )


def svg_defs(t: dict) -> str:
    """The design system's shared <defs>: the ds-arrow marker and, for neumorph, ds-lift."""
    c, sh = t["color"], t["shape"]
    lift = t["elevation"]["style"] == "neumorph"
    soft = t["elevation"]["style"] == "soft"
    defs = [
        f'<marker id="ds-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="9" markerHeight="9" '
        f'markerUnits="userSpaceOnUse" orient="auto-start-reverse"><path d="M1,1 L9,5 L1,9" fill="{c["line"] if sh["arrow"] == "filled" else "none"}" '
        f'stroke="{c["line"]}" stroke-width="1.4" stroke-linejoin="round"/></marker>'
    ]
    if lift:
        lo, dk = t["elevation"]["light"], t["elevation"]["dark"]
        defs.append(
            '<filter id="ds-lift" data-ds="neumorph" x="-10%" y="-10%" width="120%" height="120%">'
            f'<feDropShadow dx="{lo["dx"]}" dy="{lo["dy"]}" stdDeviation="{lo["blur"] / 2}" flood-color="{lo["color"]}" flood-opacity="{lo["opacity"]}"/>'
            f'<feDropShadow dx="{dk["dx"]}" dy="{dk["dy"]}" stdDeviation="{dk["blur"] / 2}" flood-color="{dk["color"]}" flood-opacity="{dk["opacity"]}"/>'
            "</filter>"
        )
    if soft:  # one wide, faint drop shadow (shadcn/slide cards) instead of the two-sided lift
        dk = t["elevation"]["dark"]
        defs.append(
            '<filter id="ds-lift" data-ds="soft" x="-20%" y="-20%" width="140%" height="160%">'
            f'<feDropShadow dx="0" dy="{dk["dy"]}" stdDeviation="{dk["blur"] / 2}" flood-color="{dk["color"]}" flood-opacity="{dk["opacity"]}"/>'
            "</filter>"
        )
    return "".join(defs)


def badge_shape(cx: float, cy: float, r: float, fill: str, sh: dict) -> str:
    if sh["badge-shape"] == "square":
        return f'<rect x="{cx - r:.1f}" y="{cy - r:.1f}" width="{2 * r:.1f}" height="{2 * r:.1f}" fill="{fill}"/>'
    return f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="{fill}"/>'


def pill_svg(label: str, x: float, y: float, c: dict, ty: dict, anchor: str = "middle") -> str:
    size = ty["small-size"]
    w = text_w(label, size) + 20
    h = size + 10
    px = x - w if anchor == "end" else x - w / 2
    return (
        f'<rect x="{px:.1f}" y="{y - h / 2:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{h / 2:.1f}" fill="{c["pill"]}"/>'
        + text(px + w / 2, y + size * 0.36, label, size, c["pill-ink"], 600, "middle")
    )


def label_svg(label: str, x: float, y: float, anchor: str, c: dict, ty: dict) -> str:
    size = ty["small-size"]
    w = text_w(label, size) + 8
    bx = x - w / 2 if anchor == "middle" else x - 4
    return (
        f'<rect x="{bx:.1f}" y="{y - size:.1f}" width="{w:.1f}" height="{size + 5:.1f}" fill="{c["canvas"]}" opacity="0.92"/>'
        + text(x, y, label, size, c["muted"], 500, anchor)
    )


def node_svg(
    n: dict, x: float, y: float, w: float, h: float, t: dict, flt: str, bg: str | None = None
) -> str:
    c, ty, sh = t["color"], t["type"], t["shape"]
    in_group = bool(n.get("group"))
    if n.get("kind") == "code":
        lines = [ln for ln in (n["label"].split("\\n") + str(n.get("sub", "")).split("\n")) if ln]
        body = f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{sh["radius-small"]}" fill="none" stroke="{c["border"]}" stroke-width="1.2" stroke-dasharray="5 4"/>'
        for i, ln in enumerate(lines):
            body += text(
                x + t["space"]["padding"],
                y + t["space"]["padding"] + (i + 0.8) * ty["small-size"] * 1.5,
                ln,
                ty["small-size"],
                c["ink"],
                400,
                family=ty["mono"],
            )
        return body
    # a card inside a group is surface-coloured unless the group already is; then it is a tile
    on_surface = (bg or c["surface"]).upper() == c["surface"].upper()
    fill = (
        c["accent"] if n.get("accent") else (c["tile"] if in_group and on_surface else c["surface"])
    )
    border = f' stroke="{c["border"]}" stroke-width="1"' if sh["card-border"] == "hairline" else ""
    lift = "" if in_group else flt
    acc = ' data-accent="1"' if n.get("accent") else ""
    out = [
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{sh["radius"]}" fill="{fill}"{border}{lift}{acc}/>'
    ]
    cy = y + 14
    ink = c["accent-ink"] if n.get("accent") else c["ink"]
    if n.get("icon") and t["icon"]["style"] != "none":
        s = t["icon"]["size"]
        out.append(
            icons.icon_svg(
                n["icon"],
                x + (w - s) / 2,
                cy,
                s,
                ink if n.get("accent") else c["icon"],
                t["icon"]["stroke"],
                t["icon"]["style"],
                fill,
            )
        )
        cy += s + 10
    lbl = wrap(n["label"], ty["label-size"], w - 16)
    for ln in lbl:
        cy += ty["label-size"] * 1.05
        out.append(
            text(x + w / 2, cy, ln, ty["label-size"], ink, ty["label-weight"] + 100, "middle")
        )
        cy += ty["label-size"] * 0.2
    if n.get("sub"):
        for ln in wrap(n["sub"], ty["small-size"], w - 16):
            cy += ty["small-size"] * 1.3
            out.append(
                text(
                    x + w / 2,
                    cy,
                    ln,
                    ty["small-size"],
                    c["muted"] if not n.get("accent") else ink,
                    400,
                    "middle",
                )
            )
    if n.get("pill"):
        out.append(pill_svg(n["pill"], x + w - 8, y, c, ty, anchor="end"))
    return "".join(out)


def note_svg(txt: str, box, c: dict, ty: dict, sh: dict) -> str:
    x, y, w, h = box
    f = 12
    body = (
        f'<path d="M{x:.1f} {y:.1f} H{x + w - f:.1f} L{x + w:.1f} {y + f:.1f} V{y + h:.1f} H{x:.1f} Z" '
        f'fill="{c["note"]}" stroke="{c["note-border"]}" stroke-width="1"/>'
        f'<path d="M{x + w - f:.1f} {y:.1f} V{y + f:.1f} H{x + w:.1f}" fill="none" stroke="{c["note-border"]}" stroke-width="1"/>'
    )
    size = ty["small-size"]
    for i, ln in enumerate(wrap(txt, size, w - 18, lines=6)):
        body += text(x + 9, y + 10 + (i + 1) * size * 1.3, ln, size, c["ink"], 500)
    return body


def place_note(
    nt: dict, anchor, occupied, W, H, ty, home=None
) -> tuple[float, float, float, float]:
    size = ty["small-size"]
    w = 150.0
    lines = wrap(nt["text"], size, w - 18, lines=6)
    h = len(lines) * size * 1.3 + 20
    ax, ay, aw, ah = anchor
    sides = [nt.get("side")] if nt.get("side") else []
    sides += ["top", "right", "bottom", "left"]
    cands = {
        "top": (ax + aw / 2 - w / 2, ay - h - 14),
        "right": (ax + aw + 14, ay),
        "bottom": (ax + aw / 2 - w / 2, ay + ah + 14),
        "left": (ax - w - 14, ay),
    }
    for s in sides:
        x, y = cands[s]
        if x < 8 or y < 8 or x + w > W - 8 or y + h > H - 8:
            continue
        if not any(overlaps((x, y, w, h), o) for o in occupied):
            return (x, y, w, h)
    # every side is taken: search outward from the anchor for the nearest free slot
    best = None
    for dy in range(-400, 401, 12):
        for dx in range(-500, 501, 12):
            x, y = ax + dx, ay + dy
            if x < 8 or y < 8 or x + w > W - 8 or y + h > H - 8:
                continue
            if home and not (
                home[0] + 8 <= x
                and x + w <= home[0] + home[2] - 8
                and home[1] + 40 <= y
                and y + h <= home[1] + home[3] - 8
            ):
                continue
            if not any(overlaps((x, y, w, h), o) for o in occupied):
                d = dx * dx + dy * dy
                if best is None or d < best[0]:
                    best = (d, x, y)
    if best:
        return (best[1], best[2], w, h)
    raise RuntimeError(
        f"note {nt['text'][:40]!r} has no free spot near {nt['near']!r} — shorten it, "
        "anchor it to a less crowded node, or drop it"
    )


def overlaps(a, b, pad=6) -> bool:
    return not (
        a[0] + a[2] + pad <= b[0]
        or b[0] + b[2] + pad <= a[0]
        or a[1] + a[3] + pad <= b[1]
        or b[1] + b[3] + pad <= a[1]
    )


def clip_to_box(pts, src, dst):
    """dot ends edges at node borders already; nudge the end to leave room for the arrowhead."""
    if len(pts) >= 2:
        (x1, y1), (x2, y2) = pts[-2], pts[-1]
        seg = math.hypot(x2 - x1, y2 - y1) or 1
        pts[-1] = (x2 - (x2 - x1) / seg * 1.5, y2 - (y2 - y1) / seg * 1.5)
    return pts


def smooth_path(pts):
    if len(pts) < 3:
        return "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts)
    d = [f"M{pts[0][0]:.1f} {pts[0][1]:.1f}"]
    for a, b in itertools.pairwise(pts):
        mx = (a[0] + b[0]) / 2
        d.append(f"C{mx:.1f} {a[1]:.1f} {mx:.1f} {b[1]:.1f} {b[0]:.1f} {b[1]:.1f}")
    return " ".join(d)


SAMPLE = {
    "title": "Every client query goes through one gateway",
    "subtitle": "Authenticate once, validate against the registry, resolve through subgraphs",
    "direction": "LR",
    "groups": [
        {"id": "platform", "title": "API platform", "pill": "Governed"},
        {"id": "subgraphs", "title": "Subgraphs", "parent": "platform", "style": "dashed"},
        {"id": "external", "title": "Data sources"},
    ],
    "nodes": [
        {"id": "user", "label": "User", "icon": "user"},
        {"id": "app", "label": "Client app", "icon": "code"},
        {"id": "auth", "label": "Auth", "icon": "key", "group": "platform"},
        {
            "id": "gw",
            "label": "GraphQL gateway",
            "icon": "shield",
            "group": "platform",
            "accent": True,
        },
        {
            "id": "reg",
            "label": "Schema registry",
            "icon": "document",
            "group": "platform",
            "pill": "Checks",
        },
        {"id": "products", "label": "Products", "icon": "table", "group": "subgraphs"},
        {"id": "orders", "label": "Orders", "icon": "package", "group": "subgraphs"},
        {"id": "pg", "label": "Postgres", "icon": "database", "group": "external"},
        {"id": "search", "label": "Search index", "icon": "search", "group": "external"},
    ],
    "edges": [
        {"from": "user", "to": "app"},
        {"from": "app", "to": "auth", "step": 1},
        {"from": "auth", "to": "gw", "step": 2},
        {"from": "reg", "to": "gw", "dashed": True},
        {"from": "gw", "to": "products", "step": 3},
        {"from": "gw", "to": "orders", "step": 3},
        {"from": "products", "to": "search", "step": 4},
        {"from": "orders", "to": "pg", "step": 4},
    ],
    "notes": [{"text": "Persisted queries: only known operations", "near": "auth"}],
    "steps": {"1": "Authenticate", "2": "Validate", "3": "Resolve", "4": "Read data"},
}


def self_test() -> int:
    global errors
    import tempfile
    import xml.etree.ElementTree as ET

    errors = []
    assert validate(SAMPLE), errors
    if shutil.which("dot"):
        for theme in (None,):
            svg = render(SAMPLE, dt.load(theme))
            ET.fromstring(svg)  # noqa: S314 - own markup
            assert svg.count('data-kind="node"') == len(SAMPLE["nodes"])
            assert "ds-lift" in svg
    errors = []
    bad = dict(SAMPLE, nodes=[*SAMPLE["nodes"], {"id": "x", "label": "X", "icon": "nope"}])
    assert not validate(bad) and any("unknown icon" in e for e in errors), errors
    errors = []
    bad = dict(SAMPLE, steps={"1": "a"})
    assert not validate(bad) and any("legend" in e for e in errors), errors
    with tempfile.TemporaryDirectory():
        pass
    print("OK: self-test passed" + ("" if shutil.which("dot") else " (render skipped: no dot)"))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("spec", nargs="?", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--design-system", default=None)
    ap.add_argument("--sample", action="store_true", help="print a sample spec")
    ap.add_argument(
        "--show-title", action="store_true", help="draw the title/subtitle (slides, social cards)"
    )
    ap.add_argument(
        "--canvas",
        choices=sorted(dt.CANVASES),
        help="fit onto a standard canvas: social 1200x627, square 1080x1080, wide 1920x1080",
    )
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if args.sample:
        print(json.dumps(SAMPLE, indent=2))
        return 0
    if not args.spec or not args.out:
        ap.error("SPEC and --out are required")
    try:
        spec = json.loads(args.spec.read_text(encoding="utf-8"))
        if args.show_title:
            spec["show_title"] = True
        tokens = dt.load(args.design_system)
    except (OSError, ValueError, dt.TokenError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if not validate(spec):
        print("\n".join(errors), file=sys.stderr)
        print(f"FAIL: {len(errors)} error(s)")
        return 1
    try:
        svg = render(spec, tokens)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if args.canvas:
        svg, small = dt.fit_canvas(svg, args.canvas, tokens["color"]["canvas"])
        if small < dt.READABLE_PX:
            print(
                f"WARN: on {args.canvas} the smallest text is {small:.1f}px (< {dt.READABLE_PX}) — "
                "use a larger canvas or the natural size, or animate it with a camera",
                file=sys.stderr,
            )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(svg, encoding="utf-8")
    print(f"OK: wrote {args.out} (design system: {tokens['name']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
