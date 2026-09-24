#!/usr/bin/env python3
"""design_tokens.py — load, validate and translate a design-system.md.

A design system is a Markdown file with ONE fenced block tagged
`design-tokens` holding JSON (a bare .json file also works). Every key is
optional except where noted: a partial file is merged onto the built-in
default ("studio"), so a brand variant can be six lines. `"extends"`
names another design-system file (relative to this one) to merge onto first.

Resolution order for which design system applies:
  1. an explicit path or theme NAME (--design-system / the `path` argument)
  2. $DIAGRAM_DESIGN_SYSTEM (a path or a theme name)
  3. ./design-system.md in the current directory
  4. the built-in default below

A theme name ("coral", "my-brand") is looked up as <name>.md or <name>.json in,
first hit wins: ./themes/, each dir in $DIAGRAM_THEMES (os.pathsep-separated),
~/.config/diagram-skills/themes/, then the themes shipped with the
diagram-design-system skill (found next to this skill when installed together).
Add a theme by dropping a file into any of those; `--list-themes` shows them.
`"extends"` also accepts a theme name.

Outputs are baked at generation time: pointing at another file means
regenerating the diagram, not restyling an existing one.

This file is vendored byte-identical into every skill that needs tokens
(scripts/test_vendored.py enforces it). Pure stdlib.

Usage:
    python3 design_tokens.py [PATH] --print      # resolved tokens as JSON
    python3 design_tokens.py [PATH] --check      # validate + contrast report
    python3 design_tokens.py [PATH] --css        # CSS custom properties
    python3 design_tokens.py [PATH] --mermaid    # Mermaid `config:` frontmatter
    python3 design_tokens.py [PATH] --beautiful  # beautiful-mermaid options JSON
    python3 design_tokens.py [PATH] --dot        # `dot` -G/-N/-E default args
    python3 design_tokens.py --list-themes       # every theme name this machine can resolve
    python3 design_tokens.py --self-test
Exit 1 on an invalid design system.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
from pathlib import Path

DEFAULT: dict = {
    "name": "studio",
    "version": 1,
    "color": {
        "canvas": "#EEEFF4",
        "surface": "#FFFFFF",
        "tile": "#EEEFF4",
        "ink": "#232F3E",
        "muted": "#5B6472",
        "line": "#3D4756",
        "border": "#8E95A2",
        "subtle": "#D0D3D2",
        "group": "#FFFFFF",
        "group-border": "#D0D3D2",
        "accent": "#FFE27A",
        "accent-ink": "#232F3E",
        "accent-muted": "#454E5C",
        "note": "#FFFFFF",
        "note-border": "#C9CDD4",
        "pill": "#D0D3D2",
        "pill-ink": "#232F3E",
        "badge": "#232F3E",
        "badge-ink": "#FFFFFF",
        "signal": "#E8563F",
        "lede": "#5B6472",
        "tag": "#232F3E",
        "tag-ink": "#FFFFFF",
        "icon": "#232F3E",
        "series-1": "#2F5FA8",
        "series-2": "#2E7A3F",
        "series-3": "#5B4AAE",
        "series-4": "#B7791F",
    },
    "type": {
        "sans": "Manrope, Inter, 'Helvetica Neue', Helvetica, Arial, sans-serif",
        "mono": "'JetBrains Mono', 'SF Mono', Menlo, Consolas, monospace",
        "serif": "'Instrument Serif', 'Times New Roman', Georgia, serif",
        "title-size": 40,
        "body-size": 15,
        "label-size": 13,
        "small-size": 11,
        "title-weight": 700,
        "label-weight": 500,
        "section-weight": 800,
        "title-tracking": -0.01,
        "section-case": "upper",
        "section-tracking": 0.02,
        "small-family": "sans",
    },
    "shape": {
        "radius": 10,
        "radius-small": 6,
        "stroke": 1.5,
        "stroke-strong": 2,
        "card-border": "none",
        "connector": "orthogonal",
        "corner": 8,
        "arrow": "open",
        "dot-radius": 6,
        "badge-radius": 11,
        "badge-shape": "circle",
        "flow-connector": "line",
    },
    "space": {"margin": 48, "gap": 28, "padding": 16, "card-width": 116, "card-height": 96},
    "elevation": {
        "style": "neumorph",
        "light": {"dx": -2, "dy": -2, "blur": 3, "color": "#FFFFFF", "opacity": 0.9},
        "dark": {"dx": 2, "dy": 3, "blur": 5, "color": "#1C2433", "opacity": 0.07},
    },
    "icon": {"style": "line", "stroke": 1.6, "size": 30, "tile": True},
    "motion": {
        "easing": [0.23, 1, 0.32, 1],
        "stagger-ms": 160,
        "enter-ms": 480,
        "draw-ms": 700,
        "type-ms": 26,
        "hold-ms": 1800,
        "fps": 24,
        "gif-fps": 20,
        "max-seconds": 12,
    },
}

HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
FENCE_RE = re.compile(r"```design-tokens\s*\n(.*?)```", re.S)
ENUMS = {
    ("type", "section-case"): {"upper", "none"},
    ("shape", "card-border"): {"none", "hairline"},
    ("shape", "connector"): {"curve", "straight", "orthogonal"},
    ("shape", "arrow"): {"none", "open", "filled"},
    ("elevation", "style"): {"flat", "neumorph", "soft"},
    ("type", "small-family"): {"sans", "mono"},
    ("shape", "badge-shape"): {"circle", "square"},
    ("shape", "flow-connector"): {"line", "disc"},
    ("icon", "style"): {"line", "isometric-line", "none"},
}


class TokenError(ValueError):
    pass


def luminance(hexcolor: str) -> float:
    h = hexcolor.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i : i + 2], 16) / 255
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * out[0] + 0.7152 * out[1] + 0.0722 * out[2]


def contrast(a: str, b: str) -> float:
    la, lb = luminance(a), luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def _read(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        raw = text
    else:
        m = FENCE_RE.search(text)
        if not m:
            raise TokenError(f"{path}: no ```design-tokens fenced block found")
        raw = m.group(1)
    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise TokenError(f"{path}: design-tokens block is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise TokenError(f"{path}: design-tokens must be a JSON object")
    return data


def _check_keys(data: dict, schema: dict, where: str) -> None:
    for key, value in data.items():
        if key in ("extends",) and where == "":
            continue
        if key not in schema:
            raise TokenError(f"unknown token {where}{key!r} (known: {', '.join(sorted(schema))})")
        if isinstance(schema[key], dict):
            if not isinstance(value, dict):
                raise TokenError(f"token {where}{key} must be an object")
            _check_keys(value, schema[key], f"{where}{key}.")


def _merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in over.items():
        if k == "extends":
            continue
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def validate(tokens: dict) -> list[str]:
    """Hard errors raise; soft problems are returned as warnings."""
    warns: list[str] = []
    for name, value in tokens["color"].items():
        if not isinstance(value, str) or not HEX_RE.match(value):
            raise TokenError(f"color.{name} must be a #RRGGBB hex string, got {value!r}")
    for (group, key), allowed in ENUMS.items():
        if tokens[group][key] not in allowed:
            raise TokenError(f"{group}.{key} must be one of {sorted(allowed)}")
    ease = tokens["motion"]["easing"]
    if not (isinstance(ease, list) and len(ease) == 4):
        raise TokenError("motion.easing must be [x1, y1, x2, y2] (a cubic-bezier)")
    c = tokens["color"]
    for fg, bg, need, what in (
        ("ink", "canvas", 4.5, "body text"),
        ("ink", "surface", 4.5, "text on cards"),
        ("ink", "group", 4.5, "text in groups"),
        ("muted", "canvas", 4.5, "secondary text"),
        ("muted", "surface", 4.5, "secondary text on cards"),
        ("ink", "tile", 4.5, "text on tiles"),
        ("muted", "tile", 4.5, "secondary text on tiles"),
        ("accent-ink", "accent", 4.5, "text on the accent"),
        ("accent-muted", "accent", 4.5, "secondary text on the accent"),
        ("ink", "note", 4.5, "sticky-note text"),
        ("pill-ink", "pill", 4.5, "pill text"),
        ("badge-ink", "badge", 4.5, "badge numbers"),
        ("lede", "canvas", 4.5, "the subtitle"),
        ("tag-ink", "tag", 4.5, "tag pill text"),
        ("icon", "surface", 3.0, "icons (graphical objects, SC 1.4.11)"),
        ("series-1", "canvas", 4.5, "series-1 notes and captions"),
        ("series-2", "canvas", 4.5, "series-2 notes and captions"),
        ("series-3", "canvas", 4.5, "series-3 notes and captions"),
        ("series-4", "surface", 3.0, "series-4 chart marks (SC 1.4.11)"),
    ):
        ratio = contrast(c[fg], c[bg])
        if ratio < need:
            raise TokenError(
                f"color.{fg} on color.{bg} is {ratio:.2f}:1 — {what} needs {need}:1 (WCAG 2.2 SC 1.4.3)"
            )
    ratio = contrast(c["line"], c["canvas"])
    if ratio < 3.0:
        warns.append(
            f"color.line on canvas is {ratio:.2f}:1 — connectors need 3:1 (WCAG 2.2 SC 1.4.11)"
        )
    if tokens["shape"]["card-border"] == "hairline" and contrast(c["border"], c["canvas"]) < 3.0:
        warns.append(
            f"color.border on canvas is {contrast(c['border'], c['canvas']):.2f}:1 with card-border "
            "hairline — borders that carry meaning need 3:1 (WCAG 2.2 SC 1.4.11)"
        )
    if contrast(c["accent"], c["canvas"]) < 3.0:
        warns.append(
            f"color.accent on canvas is {contrast(c['accent'], c['canvas']):.2f}:1 — use it only as a "
            "fill behind accent-ink, never as text or a line (the lint enforces this)"
        )
    return warns


_HERE = Path(__file__).resolve().parent


def theme_dirs() -> list[Path]:
    dirs = [Path("themes")]
    dirs += [Path(d) for d in os.environ.get("DIAGRAM_THEMES", "").split(os.pathsep) if d]
    dirs.append(Path.home() / ".config" / "diagram-skills" / "themes")
    # shipped themes: this skill's own assets, or the sibling skill when installed together
    dirs.append(_HERE.parent / "assets" / "themes")
    dirs.append(_HERE.parent.parent / "diagram-design-system" / "assets" / "themes")
    return dirs


def list_themes() -> dict[str, Path]:
    found: dict[str, Path] = {}
    for d in theme_dirs():
        if d.is_dir():
            for f in sorted(d.iterdir()):
                if f.suffix in (".md", ".json") and f.stem not in found:
                    found[f.stem] = f
    return found


def _is_name(s: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9][a-z0-9-]{0,40}", s))


def _find(ref: str, base: Path | None = None) -> Path:
    """A path (relative to `base` when given) or a theme name."""
    p = (base / ref) if base and not Path(ref).is_absolute() else Path(ref)
    if p.is_file():
        return p
    if _is_name(ref):
        themes = list_themes()
        if ref in themes:
            return themes[ref]
        raise TokenError(
            f"no design system or theme named {ref!r}; themes found: "
            f"{', '.join(sorted(themes)) or 'none'} (add one as themes/{ref}.md)"
        )
    raise TokenError(f"design system not found: {p}")


BUILTIN = ("studio", "default")


def resolve_path(path: str | os.PathLike | None = None) -> Path | None:
    if path in BUILTIN:
        return None
    if path:
        return _find(str(path))
    env = os.environ.get("DIAGRAM_DESIGN_SYSTEM")
    if env:
        try:
            return _find(env)
        except TokenError as exc:
            raise TokenError(f"$DIAGRAM_DESIGN_SYSTEM: {exc}") from None
    local = Path("design-system.md")
    return local if local.is_file() else None


def load(path: str | os.PathLike | None = None, _seen: tuple = ()) -> dict:
    """Resolve and load a design system; returns the full token dict + `_source`."""
    p = resolve_path(path) if not _seen else Path(path)  # type: ignore[arg-type]
    if p is None:
        tokens = copy.deepcopy(DEFAULT)
        tokens["_source"] = "built-in default (studio)"
        return tokens
    p = p.resolve()
    if p in _seen:
        raise TokenError(f"extends cycle at {p}")
    data = _read(p)
    _check_keys(data, DEFAULT, "")
    base = DEFAULT
    ext = data.get("extends")
    if ext and ext not in BUILTIN:
        base = load(_find(ext, p.parent), (*_seen, p))
        base = {k: v for k, v in base.items() if not k.startswith("_")}
    tokens = _merge(base, data)
    # newer tokens follow the older ones a theme already sets, unless it sets them too
    dc = data.get("color", {})
    for new, old in (
        ("lede", "muted"),
        ("tag", "badge"),
        ("tag-ink", "badge-ink"),
        ("icon", "ink"),
    ):
        if old in dc and new not in dc and base["color"][new] == base["color"][old]:
            tokens["color"][new] = dc[old]
    tokens["_warnings"] = validate(tokens)
    tokens["_source"] = str(p)
    return tokens


# --- translations --------------------------------------------------------------


def css_vars(t: dict) -> str:
    lines = [":root {"]
    for k, v in t["color"].items():
        lines.append(f"  --ds-{k}: {v};")
    for k in ("sans", "mono", "serif"):
        lines.append(f"  --ds-font-{k}: {t['type'][k]};")
    lines.append(f"  --ds-radius: {t['shape']['radius']}px;")
    lines.append(f"  --ds-stroke: {t['shape']['stroke']}px;")
    lines.append(f"  --ds-ease: cubic-bezier({', '.join(map(str, t['motion']['easing']))});")
    lines.append("}")
    return "\n".join(lines)


def mermaid_config(t: dict) -> str:
    """Mermaid `config:` frontmatter (theme base + variables; fontFamily at top level too)."""
    c, ty = t["color"], t["type"]
    v = {
        "fontFamily": ty["sans"],
        "background": c["canvas"],
        "primaryColor": c["surface"],
        "primaryTextColor": c["ink"],
        "primaryBorderColor": c["border"],
        "secondaryColor": c["tile"],
        "tertiaryColor": c["group"],
        "lineColor": c["line"],
        "textColor": c["ink"],
        "clusterBkg": c["group"],
        "clusterBorder": c["group-border"],
        "edgeLabelBackground": c["canvas"],
        "actorBkg": c["surface"],
        "actorBorder": c["border"],
        "actorLineColor": c["line"],
        "signalColor": c["ink"],
        "labelBoxBkgColor": c["surface"],
        "labelBoxBorderColor": c["border"],
        "noteBkgColor": c["note"],
        "noteBorderColor": c["note-border"],
    }
    out = ["---", "config:", "  theme: base", "  look: classic", "  layout: dagre"]
    out.append(f'  fontFamily: "{ty["sans"]}"')
    out.append("  themeVariables:")
    out += [f'    {k}: "{val}"' for k, val in v.items()]
    out.append("---")
    return "\n".join(out)


def beautiful_options(t: dict) -> dict:
    c = t["color"]
    return {
        "bg": c["canvas"],
        "fg": c["ink"],
        "line": c["line"],
        "accent": c["ink"],
        "muted": c["muted"],
        "surface": c["surface"],
        "border": c["border"],
        "font": t["type"]["sans"].split(",")[0].strip("'\" "),
    }


def dot_args(t: dict) -> list[str]:
    """Graphviz defaults as -G/-N/-E args; explicit attributes in the .dot still win."""
    c, s = t["color"], t["shape"]
    font = t["type"]["sans"].split(",")[0].strip("'\" ")
    splines = {"curve": "true", "straight": "line", "orthogonal": "ortho"}[s["connector"]]
    return [
        f"-Gbgcolor={c['canvas']}",
        f"-Gfontname={font}",
        f"-Gfontcolor={c['ink']}",
        f"-Gsplines={splines}",
        "-Gnodesep=0.55",
        "-Granksep=0.75",
        "-Gpad=0.4",
        f"-Nfontname={font}",
        "-Nfontsize=13",
        f"-Nfontcolor={c['ink']}",
        "-Nshape=box",
        "-Nstyle=rounded,filled",
        f"-Nfillcolor={c['surface']}",
        f"-Ncolor={c['border'] if s['card-border'] == 'hairline' else c['surface']}",
        f"-Npenwidth={s['stroke']}",
        "-Nmargin=0.22,0.12",
        f"-Efontname={font}",
        "-Efontsize=11",
        f"-Efontcolor={c['muted']}",
        f"-Ecolor={c['line']}",
        f"-Epenwidth={s['stroke']}",
        "-Earrowsize=0.6",
        f"-Earrowhead={ {'none': 'none', 'open': 'vee', 'filled': 'normal'}[s['arrow']] }",
        f"-Gfontsize={t['type']['label-size']}",
    ]


CANVASES = {"social": (1200, 627), "square": (1080, 1080), "wide": (1920, 1080)}
READABLE_PX = 12  # smallest text size that survives a feed or a projector


def fit_canvas(svg: str, canvas: str, fill: str) -> tuple[str, float]:
    """Centre a finished SVG, scaled to fit, on a standard canvas (social 1200x627, square
    1080x1080, wide 1920x1080). Returns the new SVG and its smallest font size in canvas px,
    so callers can warn when a wide diagram becomes unreadable at that size."""
    W, H = CANVASES[canvas]
    m = re.search(r"<svg\b[^>]*>", svg)
    if not m:
        raise TokenError("not an SVG")
    head = m.group(0)
    vb = re.search(r'viewBox="([^"]+)"', head)
    if vb:
        _, _, w, h = (float(v) for v in vb.group(1).replace(",", " ").split())
    else:
        w = float(re.search(r'\swidth="([\d.]+)', head).group(1))
        h = float(re.search(r'\sheight="([\d.]+)', head).group(1))
        head2 = head.replace("<svg", f'<svg viewBox="0 0 {w:g} {h:g}"', 1)
        svg, head = svg.replace(head, head2, 1), head2
    pad = 0.04 * min(W, H)
    k = min((W - 2 * pad) / w, (H - 2 * pad) / h)
    x, y = (W - w * k) / 2, (H - h * k) / 2
    inner = re.sub(r'\s(?:width|height|x|y)="[^"]*"', "", head)
    inner = inner.replace(
        "<svg", f'<svg x="{x:.1f}" y="{y:.1f}" width="{w * k:.1f}" height="{h * k:.1f}"', 1
    )
    ds = re.search(r'data-design-system="[^"]*"', head)
    sizes = [float(v) for v in re.findall(r'font-size[=:]\s*"?([\d.]+)', svg)] or [16.0]
    out = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
        f'data-canvas="{canvas}"{" " + ds.group(0) if ds else ""}>\n'
        f'<rect width="{W}" height="{H}" fill="{fill}"/>\n'
        + svg[m.start() :].replace(head, inner, 1).rstrip()
        + "\n</svg>\n"
    )
    return out, min(sizes) * k


def self_test() -> int:
    import tempfile

    t = load(None) if not os.environ.get("DIAGRAM_DESIGN_SYSTEM") else None
    assert t is None or t["name"] == "studio"
    fitted, small = fit_canvas(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 2400 600" width="2400" '
        'height="600"><text x="1" y="20" font-size="14">a</text></svg>',
        "social",
        "#FFFFFF",
    )
    assert 'viewBox="0 0 1200 627"' in fitted and fitted.count("<svg") == 2 and 6 < small < 7
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "brand.md").write_text(
            '# brand\n```design-tokens\n{"name": "brand", "color": {"accent": "#FFD400"}}\n```\n'
        )
        b = load(d / "brand.md")
        assert b["color"]["accent"] == "#FFD400" and b["color"]["ink"] == DEFAULT["color"]["ink"]
        (d / "child.json").write_text('{"extends": "brand.md", "type": {"title-size": 60}}')
        tdir = d / "mythemes"
        tdir.mkdir()
        (tdir / "night-owl.md").write_text('```design-tokens\n{"name": "night-owl"}\n```')
        os.environ["DIAGRAM_THEMES"] = str(tdir)
        assert load("night-owl")["name"] == "night-owl" and "night-owl" in list_themes()
        assert load("studio")["name"] == "studio" and resolve_path("default") is None
        (d / "kid.json").write_text('{"extends": "night-owl", "type": {"title-size": 44}}')
        assert load(d / "kid.json")["type"]["title-size"] == 44
        try:
            load("no-such-theme")
            raise AssertionError("unknown theme name must fail")
        except TokenError as exc:
            assert "night-owl" in str(exc)
        del os.environ["DIAGRAM_THEMES"]
        ch = load(d / "child.json")
        assert ch["color"]["accent"] == "#FFD400" and ch["type"]["title-size"] == 60
        (d / "bad.md").write_text('```design-tokens\n{"color": {"canvas": "white"}}\n```')
        try:
            load(d / "bad.md")
            raise AssertionError("hex not enforced")
        except TokenError:
            pass
        (d / "typo.md").write_text('```design-tokens\n{"colour": {}}\n```')
        try:
            load(d / "typo.md")
            raise AssertionError("unknown key accepted")
        except TokenError as e:
            assert "colour" in str(e)
        (d / "lowc.md").write_text('```design-tokens\n{"color": {"muted": "#BBBBBB"}}\n```')
        try:
            load(d / "lowc.md")
            raise AssertionError("contrast not enforced")
        except TokenError as e:
            assert "4.5:1" in str(e)
    assert "--ds-canvas" in css_vars(DEFAULT)
    assert "themeVariables" in mermaid_config(DEFAULT)
    assert beautiful_options(DEFAULT)["bg"] == DEFAULT["color"]["canvas"]
    assert any(a.startswith("-Gsplines=ortho") for a in dot_args(DEFAULT))
    print("OK: self-test passed")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("path", nargs="?", help="design-system.md or .json (default: resolution order)")
    g = ap.add_mutually_exclusive_group()
    for flag in (
        "--print",
        "--check",
        "--css",
        "--mermaid",
        "--beautiful",
        "--dot",
        "--list-themes",
        "--self-test",
    ):
        g.add_argument(flag, action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if args.list_themes:
        print(f"{'studio':14s} (built-in default)")
        for name, f in list_themes().items():
            try:
                t = load(f)
                print(
                    f"{name:14s} {f}  ({t['color']['canvas']} canvas, accent {t['color']['accent']})"
                )
            except TokenError as exc:
                print(f"{name:14s} {f}  INVALID: {exc}")
        return 0
    try:
        t = load(args.path)
    except TokenError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if args.css:
        print(css_vars(t))
    elif args.mermaid:
        print(mermaid_config(t))
    elif args.beautiful:
        print(json.dumps(beautiful_options(t)))
    elif args.dot:
        print("\n".join(dot_args(t)))
    elif args.check:
        for w in t.get("_warnings", []):
            print(f"WARN: {w}", file=sys.stderr)
        c = t["color"]
        print(f"design system: {t['name']} ({t['_source']})")
        for fg, bg in (
            ("ink", "canvas"),
            ("muted", "canvas"),
            ("line", "canvas"),
            ("ink", "note"),
            ("badge-ink", "badge"),
            ("accent-ink", "accent"),
        ):
            print(f"  {fg:10s} on {bg:7s} {contrast(c[fg], c[bg]):5.2f}:1")
        print("OK: valid")
    else:
        print(json.dumps({k: v for k, v in t.items() if not k.startswith("_")}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
