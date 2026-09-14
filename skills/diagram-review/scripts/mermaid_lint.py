#!/usr/bin/env python3
"""mermaid_lint.py — deterministic pre-render checks for Mermaid diagrams.

Catches the failures a renderer reports late or never: the parser-crash
idioms LLMs reproduce (unquoted punctuation in labels, a lowercase `end`
node, `->` arrows in flowcharts), missing config pins that let Mermaid v12
re-theme the diagram, missing accessibility fields, and the complexity that
turns a valid diagram into arrow soup (node/edge/participant caps).

Pure stdlib. Input: a .mmd file, a Markdown file (every ```mermaid fence is
checked), or `-` for stdin. Exit 1 on any ERROR (or WARN with --strict).
Never a syntax oracle: passing here means "not obviously broken", the
renderer still has the last word.

Usage:
    python3 mermaid_lint.py DIAGRAM.mmd|README.md|- [--max-nodes 12]
        [--max-edges 20] [--max-participants 7] [--strict]
    python3 mermaid_lint.py --self-test

Output: `ERROR:`/`WARN:` lines, one `STATS ...` line per diagram, then a
final `OK:`/`FAIL:` summary.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

MAX_NODES = 12  # research consensus for one readable view; split above this
MAX_EDGES = 20
MAX_PARTICIPANTS = 7  # Miller's 7±2 lower bound for sequence lifelines
HARD_NODES = 25  # past this no styling saves it: ERROR
HARD_EDGES = 40

FENCE_RE = re.compile(r"^```mermaid[^\n]*\n(.*?)^```", re.M | re.S)
TYPE_RE = re.compile(
    r"^\s*(flowchart|graph|sequenceDiagram|stateDiagram(?:-v2)?|erDiagram|classDiagram|"
    r"gantt|pie|mindmap|timeline|journey|gitGraph|quadrantChart|requirementDiagram|"
    r"C4Context|C4Container|C4Component|C4Dynamic|C4Deployment|xychart-beta|"
    r"sankey-beta|block-beta|architecture-beta|packet-beta|kanban|zenuml)\b"
)
FLOW_TYPES = {"flowchart", "graph"}
# node id followed by a shape opener: A[..], A(..), A{..}, A((..)), A([..]), A[[..]], A[(..)], A{{..}}, A>..]
NODE_DEF_RE = re.compile(r"(?<![\w\"'])([A-Za-z0-9_]+)\s*(\[\[|\[\(|\(\(|\(\[|\{\{|\[|\(|\{|>)")
CLOSERS = {
    "[[": "]]",
    "[(": ")]",
    "((": "))",
    "([": "])",
    "{{": "}}",
    "[": "]",
    "(": ")",
    "{": "}",
    ">": "]",
}
TROUBLE = set('()[]{}:;#<>|"')
FLOW_EDGE_RE = re.compile(
    r"(?:<?--+>|<?-\.+->|<?==+>|--+(?=[|\w\[\(\{])|-\.+-(?=[|\w])|==+(?=[|\w]))"
)
BAD_ARROW_RE = re.compile(r"(?<![-.=<])->(?!>)")
GENERIC_LABELS = {
    "connects to",
    "connects",
    "connection",
    "uses",
    "calls",
    "sends",
    "data",
    "flow",
    "interacts",
    "communicates",
    "talks to",
    "goes to",
    "next",
}
EDGE_LABEL_RE = re.compile(r"\|\s*\"?([^|\"]+?)\"?\s*\||--\s*\"?([^\"]+?)\"?\s*--[>-]")
SEQ_MSG_RE = re.compile(
    r"^\s*([A-Za-z0-9_ ]+?)\s*(?:-->>|->>|-->|->|-x|--x|-\)|--\))\s*([A-Za-z0-9_ ]+?)\s*:"
)
PARTICIPANT_RE = re.compile(r"^\s*(?:participant|actor)\s+([A-Za-z0-9_]+)")
COLOR_RE = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b")
STYLE_LINE_RE = re.compile(r"^\s*(?:classDef|style|linkStyle)\b")

errors: list[str] = []
warnings: list[str] = []


def err(msg: str) -> None:
    errors.append(f"ERROR: {msg}")


def warn(msg: str) -> None:
    warnings.append(f"WARN: {msg}")


def is_neutral(hexcolor: str) -> bool:
    h = hexcolor.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    return max(r, g, b) - min(r, g, b) <= 40  # low chroma = grey/black/white family


def split_frontmatter(src: str) -> tuple[str, str]:
    """Return (frontmatter, body). Mermaid frontmatter is `---` fenced at the top."""
    lines = src.lstrip("\n").split("\n")
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return "\n".join(lines[1:i]), "\n".join(lines[i + 1 :])
    return "", src


def strip_comments(body: str) -> str:
    return "\n".join(ln for ln in body.split("\n") if not ln.strip().startswith("%%"))


def label_bodies(line: str):
    """Yield (node_id, opener, label_text) for node definitions on a line."""
    pos = 0
    while True:
        m = NODE_DEF_RE.search(line, pos)
        if not m:
            return
        opener = m.group(2)
        closer = CLOSERS[opener]
        start = m.end()
        end = line.find(closer, start)
        if end == -1:
            pos = m.end()
            continue
        yield m.group(1), opener, line[start:end]
        pos = end + len(closer)


def check_flowchart(body: str, tag: str, max_nodes: int, max_edges: int) -> dict:
    node_ids: set[str] = set()
    edges = 0
    for raw in body.split("\n"):
        line = raw.strip()
        if not line or line.startswith(
            ("subgraph", "end", "classDef", "class ", "style", "linkStyle", "click", "direction")
        ):
            if line == "end":
                pass
            continue
        # arrows first: `->` without a second `>` is not a flowchart arrow
        if BAD_ARROW_RE.search(line) and "-->" not in line and "->>" not in line:
            err(f"{tag}: `->` is not a flowchart arrow, use `-->` (line: {line[:60]!r})")
        edges += len(FLOW_EDGE_RE.findall(line))
        for node_id, opener, label in label_bodies(line):
            node_ids.add(node_id)
            if node_id == "end":
                err(
                    f"{tag}: lowercase `end` used as a node id breaks the flowchart, use `End` or `END`"
                )
            text = label.strip()
            quoted = len(text) >= 2 and text[0] == '"' and text[-1] == '"'
            if not quoted and any(ch in TROUBLE for ch in text):
                err(
                    f"{tag}: unquoted special character in label {node_id}{opener}{text[:40]}... — "
                    f'write {node_id}{opener}"{text}"{CLOSERS[opener]}'
                )
        # bare ids referenced only in edges
        for m in re.finditer(r"(?:^|[\s>|])([A-Za-z0-9_]+)\s*(?:-->|---|-\.->|==>|-.-|\|)", line):
            node_ids.add(m.group(1))
        if re.search(r"\bend\s*(?:-->|---|\[)", line) or re.search(r"(?:-->|---)\s*end\b", line):
            err(
                f"{tag}: lowercase `end` used as a node id breaks the flowchart, use `End` or `END`"
            )
    node_ids.discard("end")
    n = len(node_ids)
    if n > HARD_NODES:
        err(
            f"{tag}: {n} nodes — no layout engine keeps this readable; split into views (hard cap {HARD_NODES})"
        )
    elif n > max_nodes:
        warn(f"{tag}: {n} nodes > {max_nodes} — split into two views or group with subgraphs")
    if edges > HARD_EDGES:
        err(f"{tag}: {edges} edges (hard cap {HARD_EDGES}) — this will render as arrow soup")
    elif edges > max_edges:
        warn(f"{tag}: {edges} edges > {max_edges} — prune to the edges that carry the takeaway")
    for m in EDGE_LABEL_RE.finditer(body):
        label = (m.group(1) or m.group(2) or "").strip().lower()
        if label in GENERIC_LABELS:
            warn(
                f"{tag}: generic edge label {label!r} — say what crosses the edge (verb + payload)"
            )
    return {"nodes": n, "edges": edges}


def check_sequence(body: str, tag: str, max_participants: int) -> dict:
    names: list[str] = []
    messages = 0
    for raw in body.split("\n"):
        pm = PARTICIPANT_RE.match(raw)
        if pm:
            if pm.group(1) not in names:
                names.append(pm.group(1))
            continue
        mm = SEQ_MSG_RE.match(raw)
        if mm:
            messages += 1
            for nm in (mm.group(1).strip(), mm.group(2).strip()):
                if nm and nm not in names:
                    names.append(nm)
    n = len(names)
    if n > max_participants + 2:
        err(
            f"{tag}: {n} participants — cut to the ones the takeaway needs (max {max_participants})"
        )
    elif n > max_participants:
        warn(
            f"{tag}: {n} participants > {max_participants} — consider dropping or merging lifelines"
        )
    if messages > 2 * HARD_EDGES:
        err(f"{tag}: {messages} messages — split the scenario")
    elif messages > HARD_EDGES:
        warn(f"{tag}: {messages} messages — long sequences read poorly; split by phase")
    return {"nodes": n, "edges": messages}


def check_generic(body: str, tag: str, max_nodes: int) -> dict:
    """Coarse cap for other diagram types: count non-empty statement lines."""
    stmts = [
        ln
        for ln in body.split("\n")
        if ln.strip() and not ln.strip().startswith(("%%", "accTitle", "accDescr"))
    ]
    n = max(len(stmts) - 1, 0)
    if n > 3 * max_nodes:
        warn(f"{tag}: {n} statements — large for one view; consider splitting")
    return {"nodes": n, "edges": 0}


def check_style(body: str, tag: str) -> None:
    accents: set[str] = set()
    for raw in body.split("\n"):
        if not STYLE_LINE_RE.match(raw):
            continue
        for c in COLOR_RE.findall(raw):
            if not is_neutral(c):
                accents.add(c.lower())
    if len(accents) > 1:
        warn(
            f"{tag}: {len(accents)} accent colors {sorted(accents)} — one accent for the takeaway, neutrals elsewhere"
        )


def check_diagram(
    src: str, tag: str, max_nodes: int, max_edges: int, max_participants: int
) -> None:
    fm, body = split_frontmatter(src)
    body = strip_comments(body)
    tm = TYPE_RE.search(body)
    if not tm:
        err(
            f"{tag}: no diagram type keyword found on the first line (flowchart, sequenceDiagram, ...)"
        )
        return
    dtype = tm.group(1)
    if dtype == "graph":
        warn(
            f"{tag}: `graph` is the legacy alias — use `flowchart` (modern parser, subgraph directions)"
        )
    if not re.search(r"^\s*config\s*:", fm, re.M):
        warn(
            f"{tag}: no `config:` frontmatter — Mermaid 12 re-themes unpinned diagrams (ELK layout, neo look); "
            "pin theme/look/layout"
        )
    else:
        for key in ("theme", "look", "layout"):
            if not re.search(rf"^\s+{key}\s*:", fm, re.M):
                warn(
                    f"{tag}: config frontmatter has no `{key}` — pin it so the render is reproducible"
                )
    if "accTitle" not in body:
        warn(
            f"{tag}: missing `accTitle:` — screen readers get nothing (mermaid.js.org/config/accessibility)"
        )
    if "accDescr" not in body:
        warn(f"{tag}: missing `accDescr:` — add a one-line description")
    if dtype in FLOW_TYPES:
        stats = check_flowchart(body, tag, max_nodes, max_edges)
    elif dtype == "sequenceDiagram":
        stats = check_sequence(body, tag, max_participants)
    else:
        stats = check_generic(body, tag, max_nodes)
    check_style(body, tag)
    print(f"STATS {tag}: type={dtype} nodes={stats['nodes']} edges={stats['edges']}")


def extract_diagrams(text: str, name: str) -> list[tuple[str, str]]:
    if name.endswith((".md", ".markdown")):
        return [
            (m.group(1), f"{name}#mermaid-{i + 1}") for i, m in enumerate(FENCE_RE.finditer(text))
        ]
    return [(text, name)]


SELF_TEST_BAD = """flowchart TD
  A[Start (main)] --> end
  end --> C[Done: ok]
  C -> D
  D -->|connects to| E
  classDef a fill:#ff0000
  classDef b fill:#00ff00
"""
SELF_TEST_GOOD = """---
config:
  theme: base
  look: classic
  layout: dagre
---
flowchart LR
  accTitle: Deploy pipeline
  accDescr: Three stages from commit to production
  A["Commit (main)"] --> B["Build"]
  B -->|"artifact"| C["Deploy"]
  classDef accent fill:#2563eb,color:#fff
  class C accent
"""
SELF_TEST_SEQ = "sequenceDiagram\n" + "\n".join(f"  P{i}->>P{i + 1}: step {i}" for i in range(11))


def self_test() -> int:
    global errors, warnings
    errors, warnings = [], []
    check_diagram(SELF_TEST_BAD, "bad", MAX_NODES, MAX_EDGES, MAX_PARTICIPANTS)
    joined = "\n".join(errors + warnings)
    assert "unquoted special character" in joined, joined
    assert "lowercase `end`" in joined, joined
    assert "`->` is not a flowchart arrow" in joined, joined
    assert "generic edge label" in joined, joined
    assert "2 accent colors" in joined, joined
    assert "no `config:` frontmatter" in joined, joined
    errors, warnings = [], []
    check_diagram(SELF_TEST_GOOD, "good", MAX_NODES, MAX_EDGES, MAX_PARTICIPANTS)
    assert not errors, errors
    assert not warnings, warnings
    errors, warnings = [], []
    check_diagram(SELF_TEST_SEQ, "seq", MAX_NODES, MAX_EDGES, MAX_PARTICIPANTS)
    assert any("participants" in e for e in errors), errors
    errors, warnings = [], []
    md = "intro\n```mermaid\nflowchart TD\n  A --> B\n```\ntext\n```mermaid\nsequenceDiagram\n  A->>B: hi\n```\n"
    assert len(extract_diagrams(md, "x.md")) == 2
    print("OK: self-test passed")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("file", nargs="?", help=".mmd or .md file, or - for stdin")
    ap.add_argument("--max-nodes", type=int, default=MAX_NODES)
    ap.add_argument("--max-edges", type=int, default=MAX_EDGES)
    ap.add_argument("--max-participants", type=int, default=MAX_PARTICIPANTS)
    ap.add_argument("--strict", action="store_true", help="warnings fail too")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if not args.file:
        ap.error("file is required (or --self-test)")
    if args.file == "-":
        text, name = sys.stdin.read(), "stdin"
    else:
        p = Path(args.file)
        if not p.is_file():
            print(f"ERROR: no such file: {p}", file=sys.stderr)
            return 1
        text, name = p.read_text(encoding="utf-8"), str(p)
    diagrams = extract_diagrams(text, name)
    if not diagrams:
        print(f"ERROR: no ```mermaid fences found in {name}", file=sys.stderr)
        return 1
    for src, tag in diagrams:
        check_diagram(src, tag, args.max_nodes, args.max_edges, args.max_participants)
    for line in errors + warnings:
        print(line, file=sys.stderr)
    failed = len(errors) + (len(warnings) if args.strict else 0)
    print(f"{'FAIL' if failed else 'OK'}: {len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
