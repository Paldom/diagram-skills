#!/usr/bin/env python3
"""animate.py — turn a static diagram SVG into an explanation animation.

One animation definition, two outputs: the SVG gains CSS keyframes (plays in
browsers and in GitHub READMEs via <img>), and the GIF/MP4 are captured frame
by frame from that same SVG in Chrome, so web and GIF can never drift.

What moves, in reading order (timings from the design system's `motion`):
  * elements with `data-step` (emitted by arch_svg.py / build_svg.py) fade and
    rise in step order; SVGs without them (Mermaid, Graphviz, foreign) are
    revealed child by child in document order
  * paths marked `data-draw` draw themselves along their route
  * `data-kind="badge"` pops when its connector finishes drawing
  * text in `data-kind` title/note/code types in
  * the `data-accent` element receives the highlighter last
  * `--preset pipeline` adds a camera pan across a wide diagram (the
    moodboard's pipeline-video look); the frame is `--frame-width` wide

Usage:
    python3 animate.py IN.svg --out OUT.svg [--preset reveal|pipeline]
        [--gif OUT.gif] [--mp4 OUT.mp4] [--frame-width PX] [--scale 2]
        [--design-system PATH] [--allow-install]
    python3 animate.py --self-test

The GIF/MP4 path needs Node >= 22.12, Chrome/Chromium, and ffmpeg (gifsicle
optional). puppeteer-core is pinned in assets/package-lock.json and installed
into ~/.cache/diagram-skills/ only with --allow-install. Exit 1 on failure.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import os
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import design_tokens as dt  # noqa: E402

SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")
CHROME_CANDIDATES = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
)
SKIP = {"defs", "title", "desc", "style", "metadata"}


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def find_chrome() -> str | None:
    for c in CHROME_CANDIDATES:
        if c.startswith("/"):
            if Path(c).is_file():
                return c
        elif shutil.which(c):
            return shutil.which(c)
    return None


def viewbox(root: ET.Element) -> tuple[float, float]:
    vb = root.get("viewBox")
    if vb:
        n = [float(x) for x in re.split(r"[\s,]+", vb.strip())]
        return n[2], n[3]
    return float(root.get("width", 1200)), float(root.get("height", 630))


NUM = re.compile(r"-?\d+(?:\.\d+)?")


def right_edge(el: ET.Element) -> float:
    """Rough right edge of an element tree from its x/width/cx/r and path coordinates."""
    best = 0.0
    for e in el.iter():
        try:
            if e.get("x") is not None:
                best = max(best, float(e.get("x")) + float(e.get("width", 0)))
            if e.get("cx") is not None:
                best = max(best, float(e.get("cx")) + float(e.get("r", 0)))
            if e.get("d"):
                xs = NUM.findall(e.get("d"))[0::2]
                best = max(best, *(float(x) for x in xs)) if xs else best
        except ValueError:
            continue
    return best


TRANSLATE = re.compile(r"translate\(\s*([-\d.]+)[ ,]+([-\d.]+)\s*\)(?:\s*scale\(\s*([\d.]+))?")


def bbox(el: ET.Element) -> tuple[float, float, float, float] | None:
    """Rough (x0, y0, x1, y1) of an element tree; icon groups count as their placed square."""
    xs: list[float] = []
    ys: list[float] = []

    def walk(e: ET.Element) -> None:
        m = TRANSLATE.match(e.get("transform", ""))
        if m and e is not el:
            x, y, k = float(m.group(1)), float(m.group(2)), float(m.group(3) or 1)
            xs.extend((x, x + 24 * k))
            ys.extend((y, y + 24 * k))
            return
        try:
            tag = local(e.tag)
            if tag == "text" and e.get("x") is not None:
                size = float(e.get("font-size", 14))
                xs.append(float(e.get("x")))
                ys.extend((float(e.get("y", 0)) - size, float(e.get("y", 0))))
            elif e.get("x") is not None and e.get("y") is not None:
                x, y = float(e.get("x")), float(e.get("y"))
                xs.extend((x, x + float(e.get("width", 0))))
                ys.extend((y, y + float(e.get("height", 0))))
            elif e.get("cx") is not None:
                cx, cy, r = float(e.get("cx")), float(e.get("cy", 0)), float(e.get("r", 0))
                xs.extend((cx - r, cx + r))
                ys.extend((cy - r, cy + r))
            for attr in ("d", "points"):
                v = e.get(attr)
                if v and tag in ("path", "polyline", "polygon") and not re.search(r"[a-zHV]", v):
                    nums = [float(n) for n in NUM.findall(v)]  # absolute x,y pairs only
                    xs.extend(nums[0::2])
                    ys.extend(nums[1::2])
        except ValueError:
            pass
        if local(e.tag) not in ("clipPath", "defs", "marker"):
            for k in e:
                walk(k)

    walk(el)
    if not xs or not ys:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def top_layer(root: ET.Element, gid: str | None) -> str | None:
    parent = {
        el.get("data-id"): el.get("data-group")
        for el in root.iter()
        if el.get("data-kind") == "group"
    }
    while gid and parent.get(gid):
        gid = parent[gid]
    return gid


LINE_MS_CAP = 420  # a typed line never takes longer than this, however long it is


def line_ms(chars: int, type_ms: int) -> int:
    return min(LINE_MS_CAP, max(120, chars * type_ms)) if type_ms > 0 else 90


def panel_line_ms(el: ET.Element, type_ms: int) -> list[int]:
    """Per-line typing times for a code panel, scaled down to fit the panel budget."""
    lines = [t for t in el.iter() if t.get("data-line") is not None]
    ms = [line_ms(len("".join(t.itertext())), type_ms) for t in lines]
    total = sum(ms) + 40 * len(ms)
    if total > PANEL_TYPE_BUDGET_MS:
        k = PANEL_TYPE_BUDGET_MS / total
        ms = [max(60, int(v * k)) for v in ms]
    return ms


def content_ms(el: ET.Element, type_ms: int, draw: int) -> int:
    """How long a step's own content plays (typed lines, callouts); 0 for plain steps."""
    kind = el.get("data-kind")
    if kind == "code":
        return sum(v + 40 for v in panel_line_ms(el, type_ms))
    if kind == "callouts":
        return sum(CALLOUT_MS for c in el if c.get("data-kind") == "callout")
    return 0


def type_lines(el: ET.Element, d: int, type_ms: int, enter: int) -> int:
    """Type a code panel line by line (or fade lines in turn when typing is off)."""
    t0 = panel = d + enter // 2  # the panel box lands first
    budget = iter(panel_line_ms(el, type_ms))
    for tx in (t for t in el.iter() if t.get("data-line") is not None):
        chars = len("".join(tx.itertext()))
        dur = next(budget)
        if type_ms > 0:
            tx.set("class", (tx.get("class", "") + " ds-type ds-line").strip())
            tx.set(
                "style",
                f"--ds-panel:{panel}ms;animation-delay:{t0}ms;animation-duration:{dur}ms;"
                f"animation-timing-function:steps({max(1, chars)},end)",
            )
        else:
            tx.set("class", (tx.get("class", "") + " ds-in").strip())
            tx.set("style", f"animation-delay:{t0}ms")
        t0 += dur + 40
    return t0


READ_HOLD_MS = 1500  # a finished stage stays still this long before the camera moves on
PANEL_TYPE_BUDGET_MS = 3000  # however long a code panel is, typing it takes at most this
CALLOUT_MS = 1320  # tint 200 ms, leader 420 ms, then the whole callout holds to be read


def play_callouts(root: ET.Element, el: ET.Element, d: int) -> int:
    """One callout at a time: the token's tint fades in, the leader draws, the note fades in."""
    t0 = d
    for co in (c for c in el if c.get("data-kind") == "callout"):
        hid = co.get("data-hl")
        for r in root.iter():
            if r.get("data-hl") == hid and local(r.tag) == "rect":
                r.set("class", "ds-in")
                r.set("style", f"animation-delay:{t0}ms;animation-duration:200ms")
        for p in co:
            if p.get("data-draw"):
                p.set("style", f"animation-delay:{t0 + 80}ms;animation-duration:420ms")
            elif local(p.tag) == "text":
                p.set("class", "ds-in")
                p.set("style", f"animation-delay:{t0 + 200}ms;animation-duration:220ms")
        t0 += CALLOUT_MS
    return t0


def plan_stages(root: ET.Element, steps: list, frame_width: float | None) -> dict | None:
    """Camera stops for a column-structured pipeline: one per stage, the stage centred,
    and a move time that grows with the distance (650-1100 ms)."""
    wraps = {int(el.get("data-colwrap")): el for el in root.iter() if el.get("data-colwrap")}
    if not wraps:
        return None
    W, H = viewbox(root)
    fw = frame_width or min(W, round(H * 16 / 9))
    if fw >= W - 1:
        return None
    reach, move_ms = {}, {}
    keep: set[int] = set()
    boxes = {k: bbox(wraps[k]) or (0.0, 0.0, 0.0, 0.0) for k in wraps}
    order = sorted(wraps)
    if len(order) > 1:  # the ending frames the payoff with the summary when both fit
        a, z = boxes[order[-2]], boxes[order[-1]]
        if max(a[2], z[2]) - min(a[0], z[0]) + 48 <= fw:
            boxes[order[-1]] = (min(a[0], z[0]), 0.0, max(a[2], z[2]), 0.0)
            keep.add(order[-2])
    prev = None
    for k in order:
        b = boxes[k]
        at = reach[prev] if prev is not None else 0.0
        if prev is not None and at - 1 <= b[0] - 24 and b[2] + 24 <= at + fw + 1:
            reach[k] = at  # the stage is already in frame: no move
        else:
            reach[k] = min(W - fw, max(0.0, (b[0] + b[2]) / 2 - fw / 2))
            if prev is not None:
                move_ms[k] = int(min(1100, max(650, 450 + 0.9 * abs(reach[k] - at))))
        prev = k
    first_step: dict[int, int] = {}
    for el, st in steps:
        if el.get("data-col") is not None:
            k = int(el.get("data-col"))
            first_step[k] = min(first_step.get(k, 10**6), st)
    return {"fw": fw, "reach": reach, "move_ms": move_ms, "first_step": first_step, "keep": keep}


def compact_steps(root: ET.Element) -> None:
    """Close gaps in data-step numbering (a gap is dead time), keeping the order."""
    marked = [el for el in root.iter() if el.get("data-step") not in (None, "0")]
    dense = {v: i + 1 for i, v in enumerate(sorted({int(el.get("data-step")) for el in marked}))}
    for el in marked:
        el.set("data-step", str(dense[int(el.get("data-step"))]))


def restep_build(root: ET.Element) -> None:
    """The PowerPoint build: a connector appears with its later endpoint, and a group
    (layer) comes into focus with its first member instead of up front."""
    groups = {el.get("data-id"): el for el in root.iter() if el.get("data-kind") == "group"}
    gparent = {gid: el.get("data-group") for gid, el in groups.items()}

    def top(gid: str | None) -> str | None:
        while gid and gparent.get(gid):
            gid = gparent[gid]
        return gid

    nodes = [el for el in root.iter() if el.get("data-kind") == "node" and el.get("data-id")]

    # layer by layer: a layer's rank is its left edge; ungrouped cards rank by their own
    def rank(el: ET.Element) -> tuple[int, float, int]:
        g = top(el.get("data-group"))
        b = bbox(groups[g]) if g in groups else bbox(el)
        # columns of layers left to right (80 px tolerance), stacked layers top-down
        return (round(b[0] / 80) if b else 0, b[1] if b else 0.0, int(el.get("data-step")))

    first_step = min((int(el.get("data-step")) for el in nodes), default=1)
    for i, el in enumerate(sorted(nodes, key=rank)):
        el.set("data-step", str(first_step + i))
    node_step = {el.get("data-id"): int(el.get("data-step")) for el in nodes}
    for el in root.iter():
        a, b = el.get("data-from"), el.get("data-to")
        if el.get("data-kind") == "edge" and a in node_step and b in node_step:
            el.set("data-step", str(max(node_step[a], node_step[b])))
    parent = gparent
    first: dict[str, int] = {}
    for el in root.iter():
        if el.get("data-kind") == "node" and el.get("data-group"):
            g = el.get("data-group")
            while g:  # a node also wakes every enclosing group
                first[g] = min(first.get(g, 10**6), int(el.get("data-step")))
                g = parent.get(g)
    for el in root.iter():
        if el.get("data-kind") == "group" and el.get("data-id") in first:
            el.set("data-step", str(first[el.get("data-id")]))
            el.set("data-ghost", "1")


def plan_steps(root: ET.Element) -> list[tuple[ET.Element, int]]:
    """(element, step) pairs. Prefer data-step; else top-level children in order."""
    marked = [
        (el, int(el.get("data-step"))) for el in root.iter() if el.get("data-step") is not None
    ]
    if marked:
        return marked
    kids = [k for k in root if local(k.tag) not in SKIP]
    if kids and local(kids[0].tag) == "rect":
        kids = kids[1:]  # background
    # a single wrapper group (Mermaid/Graphviz output): descend until there is fan-out
    while len(kids) == 1 and len([k for k in kids[0] if local(k.tag) not in SKIP]) > 1:
        kids = [k for k in kids[0] if local(k.tag) not in SKIP]
    # foreign SVGs often emit all edges first: reveal by position along the main
    # axis instead, so a node appears before the connector that leaves it
    W, H = viewbox(root)
    axis = 0 if W > H * 1.2 else 1
    order = sorted(range(len(kids)), key=lambda i: (start_point(kids[i])[axis], i))
    for k in kids:  # bare connector lines draw instead of fading
        for e in k.iter():
            if local(e.tag) in ("path", "polyline", "line") and e.get("fill", "") == "none":
                e.set("data-draw", "1")
    return [(kids[i], rank + 1) for rank, i in enumerate(order)]


def start_point(el: ET.Element) -> tuple[float, float]:
    """First coordinate an element draws at (x/y, cx/cy, points, or path M)."""
    for e in el.iter():
        try:
            if e.get("x") is not None and e.get("y") is not None:
                return float(e.get("x")), float(e.get("y"))
            if e.get("cx") is not None:
                return float(e.get("cx")), float(e.get("cy", 0))
            for attr in ("points", "d"):
                nums = NUM.findall(e.get(attr) or "")
                if len(nums) >= 2:
                    return float(nums[0]), float(nums[1])
        except ValueError:
            continue
    return (0.0, 0.0)


def build(
    svg_text: str,
    tokens: dict,
    preset: str,
    frame_width: float | None,
    beat_ms: int | None = None,
) -> tuple[str, dict]:
    root = ET.fromstring(svg_text)  # noqa: S314 - local file the caller supplies; no DOCTYPE allowed below
    if re.search(r"<!DOCTYPE|<!ENTITY", svg_text[:2000], re.I):
        raise ValueError("DOCTYPE/ENTITY declarations are not allowed")
    mo = tokens["motion"]
    stagger, enter, draw, type_ms, hold = (
        mo["stagger-ms"],
        mo["enter-ms"],
        mo["draw-ms"],
        mo["type-ms"],
        mo["hold-ms"],
    )
    ease = "cubic-bezier({})".format(", ".join(str(v) for v in mo["easing"]))
    if preset == "build":
        restep_build(root)
    compact_steps(root)
    steps = plan_steps(root)
    n_steps = max((s for _, s in steps), default=0)
    # compress the stagger if the whole reveal would exceed max-seconds
    if beat_ms or preset == "build":  # a presented build: one beat per step, like slide clicks
        stagger = beat_ms or max(stagger, 600)
    budget = mo["max-seconds"] * 1000 - hold - draw - enter
    if preset == "reveal" and n_steps and n_steps * stagger > budget:
        stagger = max(40, budget // n_steps)
    end = 0

    pauses: dict[int, int] = {}
    if preset == "build":  # a held beat whenever the build moves on to a new layer
        layer_of: dict[int, str] = {}
        for el, s_ in steps:
            if el.get("data-kind") == "node":
                layer_of.setdefault(s_, top_layer(root, el.get("data-group")) or "")
        seen_l, extra = None, 0
        for s_ in sorted(layer_of):
            if seen_l and layer_of[s_] and layer_of[s_] != seen_l:  # only between two layers
                extra += 1600
            seen_l = layer_of[s_]
            pauses[s_] = extra
        last = 0
        for s_ in range(max((s_ for _, s_ in steps), default=0) + 1):
            last = pauses.get(s_, last)
            pauses[s_] = last

    stages = plan_stages(root, steps, frame_width) if preset == "pipeline" else None
    if stages:  # a reading hold, then one camera move, before each new stage's content
        extra_by_step: dict[int, int] = {}
        for k, st in stages["first_step"].items():
            if stages["move_ms"].get(k):
                extra_by_step[st] = READ_HOLD_MS + stages["move_ms"][k]
        acc_p = 0
        for s_ in range(max((s_ for _, s_ in steps), default=0) + 1):
            acc_p += extra_by_step.get(s_, 0)
            pauses[s_] = pauses.get(s_, 0) + acc_p

    # steps that carry content with its own duration (typed code, callouts) push later steps back
    extra: dict[int, int] = {}
    for el, s_ in steps:
        extra[s_] = max(extra.get(s_, 0), content_ms(el, type_ms, draw) - stagger)
    shift: dict[int, int] = {}
    acc = 0
    for s_ in range(max((s_ for _, s_ in steps), default=0) + 1):
        shift[s_] = acc
        acc += max(0, extra.get(s_, 0))

    def delay_of(step: int) -> int:
        return step * stagger + pauses.get(step, 0) + shift.get(step, 0)

    for el, s in steps:
        d = delay_of(s)
        kind = el.get("data-kind", "")
        if el.get("data-ghost"):  # a layer waiting for its content: visible but dimmed
            el.set("class", (el.get("class", "") + " ds-ghost").strip())
            el.set("style", (el.get("style", "") + f";animation-delay:{d}ms").lstrip(";"))
        elif not el.get("data-draw"):  # a line drawing itself must not also fade
            el.set("class", (el.get("class", "") + " ds-in").strip())
            el.set("style", (el.get("style", "") + f";animation-delay:{d}ms").lstrip(";"))
            end = max(end, d + enter)
        for p in el.iter():
            if p.get("data-draw"):
                p.set("pathLength", "1")
                p.set("class", (p.get("class", "") + " ds-draw").strip())
                p.set("style", f"animation-delay:{d}ms")
                end = max(end, d + draw)
            if p.get("data-kind") == "badge":
                p.set("class", (p.get("class", "") + " ds-pop").strip())
                p.set("style", f"animation-delay:{d + int(draw * 0.85)}ms")
                end = max(end, d + int(draw * 0.85) + 300)
        if kind == "code":
            end = max(end, type_lines(el, d, type_ms, enter))
        if kind == "callouts":
            end = max(end, play_callouts(root, el, d))
        if kind in ("title", "note") and type_ms > 0 and preset != "build":
            for i, tx in enumerate(t for t in el.iter() if local(t.tag) == "text"):
                chars = len("".join(tx.itertext()))
                dur = max(200, chars * type_ms)
                start = d + i * 120
                tx.set("class", (tx.get("class", "") + " ds-type").strip())
                tx.set(
                    "style",
                    f"animation-delay:{start}ms;animation-duration:{dur}ms;animation-timing-function:steps({max(1, chars)},end)",
                )
                end = max(end, start + dur)
    accent_els = [el for el in root.iter() if el.get("data-accent")]
    tc = tokens["color"]
    if dt.contrast(tc["accent-ink"], tc["tile"]) < 3:
        accent_els = []  # a dark (inverted) highlight: its light text would vanish on the pre-fill colour
    for el in accent_els:
        to = el.get("fill")
        el.set("class", (el.get("class", "") + " ds-accent").strip())
        el.set("style", f"--ds-to:{to};--ds-from:{tokens['color']['tile']};animation-delay:{end}ms")
        end += 500
    total = end + (max(hold, 3500) if preset in ("build", "pipeline") else hold)

    W, H = viewbox(root)
    pan = None
    if stages:
        fw = stages["fw"]
        cam = ET.Element(f"{{{SVG_NS}}}g", {"class": "ds-camera"})
        kids = [k for k in list(root) if local(k.tag) not in SKIP]
        bg = kids[0] if kids and local(kids[0].tag) == "rect" else None
        for k in kids:
            if k is bg or k.get("data-kind") == "title":
                continue
            root.remove(k)
            cam.append(k)
        root.insert(list(root).index(bg) + 1 if bg is not None else 0, cam)
        span = total + 200
        frames = [(0.0, f"translate({-stages['reach'][0]:.0f}px,0px)")]
        cols = sorted(stages["reach"])
        leave: dict[int, int] = {}
        for prev, k in itertools.pairwise(cols):
            mv = stages["move_ms"].get(k, 0)
            if not mv:
                continue
            arrive = delay_of(stages["first_step"][k])
            depart = arrive - mv
            if prev not in stages["keep"]:
                leave[prev] = arrive  # dim once the next stage has something lit, never all at once
            frames.append((depart / span * 100, f"translate({-stages['reach'][prev]:.0f}px,0px)"))
            frames.append((arrive / span * 100, f"translate({-stages['reach'][k]:.0f}px,0px)"))
        frames.append((100.0, frames[-1][1]))
        pan = {"dur": int(span), "frames": frames, "ease": "cubic-bezier(0.65, 0, 0.35, 1)"}
        # a stage the camera has left steps back (opacity .28) and stays back: the ending belongs to the last stage
        for wrap in root.iter():
            k = wrap.get("data-colwrap")
            if k is not None and int(k) in leave:
                wrap.set("class", "ds-past")
                wrap.set("style", f"animation-delay:{leave[int(k)]}ms")
        root.set("viewBox", f"0 0 {fw:.0f} {H:.0f}")
        root.set("width", f"{fw:.0f}")
        W = fw
    elif preset == "pipeline":
        fw = frame_width or min(W, round(H * 16 / 9))
        if fw < W - 1:
            cam = ET.Element(f"{{{SVG_NS}}}g", {"class": "ds-camera"})
            kids = [k for k in list(root) if local(k.tag) not in SKIP]
            bg = kids[0] if kids and local(kids[0].tag) == "rect" else None
            for k in kids:
                if k is bg or k.get("data-kind") == "title":
                    continue  # the background and the headline stay put while the camera pans
                root.remove(k)
                cam.append(k)
            root.insert(list(root).index(bg) + 1 if bg is not None else 0, cam)
            if bg is not None:
                bg.set("width", str(W))
            # one keyframe per step: keep the newest step's right edge in frame
            right: dict[int, float] = {}
            for el, st in steps:
                if el.get("data-kind") != "title":
                    right[st] = max(right.get(st, 0), right_edge(el))
            # then pull back to an overview so the whole journey is seen at once — unless it is
            # so wide the overview would be unreadable; then hold on the last stage
            overview = 900 if fw * 1.9 >= W else 0
            span = end + overview
            k = fw / W
            frames, reach = [(0, "translate(0px,0px) scale(1)")], 0.0
            centre: dict[int, float] = {}
            for el, st in steps:
                if el.get("data-kind") != "title" and (b := bbox(el)) is not None:
                    centre[st] = max(centre.get(st, 0.0), (b[0] + b[2]) / 2)
            for st in sorted(right):
                # the active stage sits a little right of centre, the one before it stays in view
                target = centre.get(st, right[st]) - fw * 0.55
                reach = max(reach, min(W - fw, max(0.0, target, right[st] - fw + 40)))
                pct = min(100.0, (delay_of(st) + enter) / span * 100)
                frames.append((pct, f"translate({-reach:.0f}px,0px) scale(1)"))
            frames.append((end / span * 100, f"translate({-reach:.0f}px,0px) scale(1)"))
            ty = H * (1 - k) / 2 + H * 0.06
            if overview:
                frames.append((100.0, f"translate(0px,{ty:.0f}px) scale({k:.4f})"))
            else:
                frames.append((100.0, frames[-1][1]))
            pan = {"dur": int(span), "frames": frames}
            total += overview
            root.set("viewBox", f"0 0 {fw:.0f} {H:.0f}")
            root.set("width", f"{fw:.0f}")
            W = fw
    if preset == "build":
        cam = ET.Element(f"{{{SVG_NS}}}g", {"class": "ds-camera"})
        kids = [k for k in list(root) if local(k.tag) not in SKIP]
        bg = kids[0] if kids and local(kids[0].tag) == "rect" else None
        title = next((k for k in kids if k.get("data-kind") == "title"), None)
        for k in kids:
            if k is bg or k is title:
                continue
            root.remove(k)
            cam.append(k)
        root.insert(list(root).index(bg) + 1 if bg is not None else 0, cam)
        tb = bbox(title) if title is not None else None
        top = (tb[3] + 24) if tb else 0.0  # the camera frames the area under the pinned title
        vw, vh = W, H - top
        # PowerPoint camera: frame the ACTIVE layers (top-level groups whose first member has
        # appeared, plus any ungrouped content) and move only when that set changes
        groups = {el.get("data-id"): el for el, _ in steps if el.get("data-kind") == "group"}
        parent = {gid: el.get("data-group") for gid, el in groups.items()}

        def top_group(gid: str | None) -> str | None:
            while gid and parent.get(gid):
                gid = parent[gid]
            return gid

        # a layer's frame is its content (every member card + its title strip), not the
        # rectangle — equal-height columns would otherwise leave nothing to zoom into
        layer_box: dict[str, tuple[float, float, float, float]] = {}
        for el, _ in steps:
            g = top_group(el.get("data-group"))
            if el.get("data-kind") == "node" and g in groups and (b := bbox(el)) is not None:
                o = layer_box.get(g, b)
                layer_box[g] = (min(o[0], b[0]), min(o[1], b[1]), max(o[2], b[2]), max(o[3], b[3]))
        for g, b in list(layer_box.items()):
            if (r := bbox(groups[g])) is not None:  # keep the layer's title strip in view
                layer_box[g] = (min(b[0], r[0]), min(b[1], r[1]), b[2], b[3])
        frames: list[tuple[float, str]] = []
        span = end + 900
        active: list[tuple[float, float, float, float]] = []
        seen_groups: set[str] = set()
        k_prev = 10.0
        # open on the first layer the build enters, not on a lone card beside it
        grouped = sorted(
            (s_, top_group(el.get("data-group")))
            for el, s_ in steps
            if el.get("data-kind") == "node" and top_group(el.get("data-group")) in groups
        )
        if grouped and (b0 := layer_box.get(grouped[0][1])) is not None:
            active.append(b0)
            seen_groups.add(grouped[0][1])
        content = [(el, s_) for el, s_ in steps if el.get("data-kind") not in ("title", "group")]
        last = None
        for st in sorted({s_ for _, s_ in content}):
            for el, s_ in content:
                if s_ != st:
                    continue
                g = top_group(el.get("data-group"))
                if g and g in groups:
                    if g not in seen_groups:
                        seen_groups.add(g)
                        if (b := layer_box.get(g)) is not None:
                            active.append(b)
                elif (b := bbox(el)) is not None:  # ungrouped cards, notes, scope, legend
                    active.append(b)
            if not active:
                continue
            x0, y0 = min(b[0] for b in active) - 40, min(b[1] for b in active) - 40
            x1, y1 = max(b[2] for b in active) + 40, max(b[3] for b in active) + 40
            k = max(1.0, min(2.0, vw / (x1 - x0), vh / (y1 - y0), k_prev))  # only ever pull back
            k_prev = k
            tx, ty = vw / 2 - k * (x0 + x1) / 2, top + vh / 2 - k * (y0 + y1) / 2
            if k == 1.0:
                tx = ty = 0.0
            tf = f"translate({tx:.0f}px,{ty:.0f}px) scale({k:.3f})"
            if tf != last:
                pct = min(100.0, delay_of(st) / span * 100)
                if frames:  # hold the previous framing until this move starts
                    frames.append((max(frames[-1][0], pct - 3), frames[-1][1]))
                frames.append((pct + 3 if frames else pct, tf))
                last = tf
        if frames:
            frames.insert(0, (0.0, frames[0][1]))
            frames.append((end / span * 100, frames[-1][1]))
            frames.append((100.0, "translate(0px,0px) scale(1)"))  # settle on the whole diagram
            pan = {"dur": int(span), "frames": frames}
            total += 900
    css = f"""
.ds-in{{opacity:0;animation:ds-in {enter}ms {ease} both}}
.ds-draw{{stroke-dasharray:1;stroke-dashoffset:1;animation:ds-draw {draw}ms {ease} both}}
.ds-pop{{transform-box:fill-box;transform-origin:center;opacity:0;animation:ds-pop 320ms {ease} both}}
.ds-type{{clip-path:inset(0 100% 0 0);animation-name:ds-type;animation-fill-mode:both}}
.ds-accent{{animation:ds-accent 480ms {ease} both}}
.ds-ghost{{animation:ds-focus {enter}ms {ease} both}}
.ds-past{{animation:ds-dim 400ms {ease} both}}
@keyframes ds-dim{{from{{opacity:1}}to{{opacity:.28}}}}
@keyframes ds-focus{{from{{opacity:.25}}to{{opacity:1}}}}
@keyframes ds-in{{from{{opacity:0;transform:translateY(6px)}}to{{opacity:1;transform:none}}}}
@keyframes ds-draw{{0%,96%{{marker-end:none;marker-start:none}}100%{{stroke-dashoffset:0}}}}
@keyframes ds-pop{{from{{opacity:0;transform:scale(.96)}}to{{opacity:1;transform:scale(1)}}}}
@keyframes ds-type{{to{{clip-path:inset(0 0 0 0)}}}}
@keyframes ds-accent{{from{{fill:var(--ds-from)}}to{{fill:var(--ds-to)}}}}
"""
    if pan:
        kf = "".join(f"{p:.1f}%{{transform:{tf}}}" for p, tf in pan["frames"])
        curve = pan.get("ease", "cubic-bezier(0.77, 0, 0.175, 1)")
        css += (
            f".ds-camera{{animation:ds-pan {pan['dur']}ms {curve} both}}\n"
            f"@keyframes ds-pan{{{kf}}}\n"
        )
    # reduced motion is gentler, not frozen: keep fades, order and line draws; drop movement
    css += (
        "@keyframes ds-fade{from{opacity:0}to{opacity:1}}\n"
        "@media (prefers-reduced-motion: reduce){"
        ".ds-camera{animation-timing-function:step-end!important}"  # cut between stages, no travel
        ".ds-in,.ds-pop,.ds-type{animation-name:ds-fade!important;animation-duration:200ms!important;"
        "animation-timing-function:ease!important;clip-path:none!important}"
        ".ds-draw{animation-name:ds-fade!important;animation-duration:200ms!important;stroke-dashoffset:0!important;stroke-dasharray:none!important}"
        ".ds-line{animation-delay:var(--ds-panel)!important}"  # a code panel fades in whole
        ".ds-ghost{animation-name:ds-fade!important}}\n"
    )
    style = ET.Element(f"{{{SVG_NS}}}style")
    style.text = css
    root.insert(0, style)
    out = ET.tostring(root, encoding="unicode")
    meta = {"width": round(W), "height": round(H), "duration": int(total), "steps": n_steps}
    return out, meta


# --- GIF / MP4 -------------------------------------------------------------------


def node_env(allow_install: bool) -> Path:
    lock = HERE.parent / "assets" / "package-lock.json"
    digest = hashlib.sha256(lock.read_bytes()).hexdigest()[:12]
    cache = (
        Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
        / "diagram-skills"
        / f"diagram-animate-{digest}"
    )
    if (cache / "node_modules" / "puppeteer-core").is_dir():
        return cache
    if not allow_install:
        raise RuntimeError(
            f"puppeteer-core is not installed yet; re-run with --allow-install to run "
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


def capture(
    svg_path: Path,
    meta: dict,
    fps: int,
    scale: float,
    allow_install: bool,
    reduced: bool = False,
) -> Path:
    chrome = find_chrome()
    if not chrome:
        raise RuntimeError("Chrome/Chromium not found — needed to capture frames")
    if not shutil.which("node"):
        raise RuntimeError("node not found — install Node.js >= 22.12")
    env_dir = node_env(allow_install)
    frames = Path(tempfile.mkdtemp(prefix="ds-frames-"))
    script = env_dir / "capture.mjs"
    shutil.copy(HERE / "capture.mjs", script)
    cmd = [
        "node", str(script), "--svg", str(svg_path.resolve()), "--out", str(frames),
        "--width", str(meta["width"]), "--height", str(meta["height"]),
        "--fps", str(fps), "--duration", str(meta["duration"]), "--scale", str(scale), "--chrome", chrome,
    ]  # fmt: skip
    if reduced:  # preview the prefers-reduced-motion variant
        cmd.append("--reduced-motion")
    # headless Chrome occasionally hangs at launch (seen with several captures in parallel):
    # give up after a budget that scales with the frame count, and retry once
    budget = 120 + meta["duration"] / 1000 * fps * 1.5
    for attempt in (1, 2):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, cwd=env_dir, timeout=budget)
            break
        except subprocess.TimeoutExpired:
            if attempt == 2:
                raise
            for f in frames.glob("f*.png"):
                f.unlink()
    if r.returncode != 0:
        raise RuntimeError(f"frame capture failed: {(r.stderr or r.stdout).strip()[-400:]}")
    return frames


def add_poster(frames: Path) -> None:
    """Prepend the final frame as frame 0: feeds, chat apps and READMEs use the first
    frame as the thumbnail, and a loop from last frame to poster is seamless."""
    pngs = sorted(frames.glob("f*.png"))
    if len(pngs) < 2 or (frames / "poster.done").exists():
        return
    for p in reversed(pngs):
        p.rename(frames / f"f{int(p.stem[1:]) + 1:04d}.png")
    shutil.copy(frames / f"f{len(pngs):04d}.png", frames / "f0000.png")
    (frames / "poster.done").touch()


def fit_vf(canvas: tuple[int, int, str]) -> str:
    w, h, fill = canvas
    return (
        f"scale={w}:{h}:force_original_aspect_ratio=decrease:flags=lanczos,"
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color={fill.lstrip('#')},setsar=1"
    )


def encode(
    frames: Path,
    fps: int,
    gif: Path | None,
    mp4: Path | None,
    scale: float,
    poster: bool = True,
    canvas: tuple[int, int, str] | None = None,
) -> None:
    """canvas=(w, h, fill): scale to fit and pad onto a standard canvas (social, square, wide)."""
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found — brew install ffmpeg / apt-get install ffmpeg")
    pattern = str(frames / "f%04d.png")
    if poster:
        add_poster(frames)
    if gif:
        gif.parent.mkdir(parents=True, exist_ok=True)
        vf = "split[a][b];[a]palettegen=max_colors=128:stats_mode=diff[p];[b][p]paletteuse=dither=none:diff_mode=rectangle"
        if canvas:
            vf = fit_vf(canvas) + "," + vf
        elif scale != 1:
            vf = f"scale=iw/{scale}:ih/{scale}:flags=lanczos," + vf
        r = subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-framerate",
                str(fps),
                "-i",
                pattern,
                "-vf",
                vf,
                "-loop",
                "0",
                str(gif),
            ],
            capture_output=True,
            text=True,
        )
        if r.returncode != 0:
            raise RuntimeError(f"ffmpeg gif failed: {r.stderr.strip()[-300:]}")
        if shutil.which("gifsicle"):
            subprocess.run(["gifsicle", "-O3", "-b", str(gif)], capture_output=True)
    if mp4:
        mp4.parent.mkdir(parents=True, exist_ok=True)
        r = subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-framerate", str(fps), "-i", pattern,
             "-vf", fit_vf(canvas) if canvas else "pad=ceil(iw/2)*2:ceil(ih/2)*2", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", str(mp4)],
            capture_output=True, text=True,
        )  # fmt: skip
        if r.returncode != 0:
            raise RuntimeError(f"ffmpeg mp4 failed: {r.stderr.strip()[-300:]}")


SAMPLE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 200" width="400" height="200">
<rect width="400" height="200" fill="#EEEFF4"/>
<g data-step="0" data-kind="title"><text x="20" y="40" font-size="20">Hello</text></g>
<g data-step="1" data-kind="node"><rect x="20" y="80" width="80" height="60" fill="#FFFFFF"/></g>
<g data-step="2" data-kind="node"><rect data-accent="1" x="300" y="80" width="80" height="60" fill="#FFE27A"/></g>
<g data-step="3" data-kind="edge"><path d="M100 110 H300" stroke="#000" data-draw="1"/><g data-kind="badge"><circle cx="200" cy="110" r="10"/></g></g>
</svg>"""


def self_test() -> int:
    t = dt.load(None)
    out, meta = build(SAMPLE, t, "reveal", None)
    ET.fromstring(out)  # noqa: S314 - own markup
    assert "@keyframes ds-draw" in out and 'pathLength="1"' in out and "ds-pop" in out
    assert "ds-type" in out and "ds-accent" in out
    assert meta["duration"] > t["motion"]["hold-ms"] and meta["steps"] == 3
    out2, meta2 = build(SAMPLE, t, "pipeline", 200)
    assert "ds-camera" in out2 and meta2["width"] == 200
    with tempfile.TemporaryDirectory() as td:
        fr = Path(td)
        for i, b in enumerate((b"a", b"b", b"c")):
            (fr / f"f{i:04d}.png").write_bytes(b)
        add_poster(fr)
        got = [(fr / f"f{i:04d}.png").read_bytes() for i in range(4)]
        assert got == [b"c", b"a", b"b", b"c"], got
    plain = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect width="10" height="10"/><g><circle r="1"/><circle r="2"/></g></svg>'
    _, m3 = build(plain, t, "reveal", None)
    assert m3["steps"] == 2, m3
    foreign = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 300">'
        '<polyline points="50,40 50,200" fill="none" stroke="#000"/>'
        '<rect x="20" y="10" width="60" height="30"/><rect x="20" y="200" width="60" height="30"/></svg>'
    )
    out4, _ = build(foreign, t, "reveal", None)
    r = ET.fromstring(out4)  # noqa: S314 - own markup
    delays = [
        int(re.search(r"animation-delay:(\d+)", k.get("style")).group(1))
        for k in r
        if k.get("style")
    ]
    tags = [local(k.tag) for k in r if k.get("style")]
    assert tags[delays.index(min(delays))] == "rect", (tags, delays)  # the top node comes first
    line = next(k for k in r if local(k.tag) == "polyline")
    assert "ds-draw" in line.get("class") and "ds-in" not in line.get("class")
    print("OK: self-test passed")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("svg", nargs="?", type=Path)
    ap.add_argument("--out", type=Path, help="animated SVG output")
    ap.add_argument("--preset", choices=["reveal", "pipeline", "build"], default="reveal")
    ap.add_argument("--frame-width", type=float, default=None)
    ap.add_argument(
        "--beat-ms", type=int, default=None, help="ms between steps (build default 600)"
    )
    ap.add_argument("--gif", type=Path)
    ap.add_argument("--mp4", type=Path)
    ap.add_argument(
        "--scale", type=float, default=2.0, help="capture pixel density (GIF is downscaled)"
    )
    ap.add_argument("--fps", type=int, default=None)
    ap.add_argument("--design-system", default=None)
    ap.add_argument("--allow-install", action="store_true")
    ap.add_argument(
        "--reduced-motion", action="store_true", help="capture the prefers-reduced-motion variant"
    )
    ap.add_argument(
        "--canvas",
        choices=sorted(dt.CANVASES),
        help="pad GIF/MP4 onto social 1200x627, square 1080x1080 or wide 1920x1080",
    )
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if not args.svg or not args.out:
        ap.error("IN.svg and --out are required")
    try:
        tokens = dt.load(args.design_system)
        text = args.svg.read_text(encoding="utf-8")
        fw = args.frame_width
        if (
            args.canvas and fw is None and args.preset == "pipeline"
        ):  # the camera frame takes the canvas shape
            cw, ch = dt.CANVASES[args.canvas]
            fw = round(viewbox(ET.fromstring(text))[1] * cw / ch)  # noqa: S314 - local file the user passed
        svg, meta = build(text, tokens, args.preset, fw, args.beat_ms)
    except (OSError, ValueError, ET.ParseError, dt.TokenError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(svg, encoding="utf-8")
    print(
        f"SVG {args.out} ({meta['width']}x{meta['height']}, {meta['duration'] / 1000:.1f}s, {meta['steps']} steps)"
    )
    if args.gif or args.mp4:
        fps = args.fps or tokens["motion"]["gif-fps"]
        try:
            frames = capture(
                args.out, meta, fps, args.scale, args.allow_install, args.reduced_motion
            )
            canvas = (*dt.CANVASES[args.canvas], tokens["color"]["canvas"]) if args.canvas else None
            encode(frames, fps, args.gif, args.mp4, args.scale, canvas=canvas)
        except (RuntimeError, subprocess.TimeoutExpired) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        finally:
            if "frames" in locals():
                last = sorted(frames.glob("f*.png"))[-1] if any(frames.glob("f*.png")) else None
                if last and args.gif:
                    shutil.copy(last, args.gif.with_suffix(".last.png"))
                shutil.rmtree(frames, ignore_errors=True)
        for p in (args.gif, args.mp4):
            if p:
                print(f"{p.suffix[1:].upper()} {p} ({p.stat().st_size / 1e6:.2f} MB)")
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
