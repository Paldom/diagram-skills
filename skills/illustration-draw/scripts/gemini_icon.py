#!/usr/bin/env python3
"""gemini_icon.py — optional: generate a 3D line-art icon with a Gemini image model.

The procedural icons in icons.py are the default and the consistency
guarantee. Use this only for a subject icons.py does not cover (a product, a
mascot, a hero illustration). It builds the prompt from the active design
system (ink colour, canvas, stroke, isometric vs flat line) so the result
matches the rest of the diagram, then calls the Gemini API.

Needs network and a key, so it runs only with --allow-network:
    export GEMINI_API_KEY="..."   # https://aistudio.google.com/apikey ; never commit it

Usage:
    python3 gemini_icon.py "a vector database" --out db.jpg --allow-network
        [--model gemini-3-pro-image] [--design-system PATH] [--size 1K]
    python3 gemini_icon.py "requests flowing through one API gateway" --kind illustration --out hero.jpg --allow-network
    python3 gemini_icon.py "a vector database" --print-prompt
    python3 gemini_icon.py --self-test

Models: gemini-3-pro-image (Nano Banana Pro, best line quality),
gemini-3.1-flash-image (Nano Banana 2, faster/cheaper). Every image carries
Google's SynthID watermark. The API returns JPEG only; the image is raster: place it with <image> only in
HTML/slide output — svg_lint rejects rasters inside the static SVG subset, by
design. Exit 1 on any failure; the key is never printed.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import design_tokens as dt  # noqa: E402

ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/interactions"
MODELS = ("gemini-3-pro-image", "gemini-3.1-flash-image", "gemini-3.1-flash-lite-image")


def prompt_for(subject: str, t: dict, kind: str = "icon") -> str:
    c, ic = t["color"], t["icon"]
    if kind == "illustration":
        return (
            f"A wide minimalist technical illustration of {subject}: isometric 3D line art "
            f"with 6 to 8 simple objects and ONE clear focal object, joined by single thin "
            f"connector lines. Uniform 2 px monoline strokes in {c['ink']}, flat {c['surface']} "
            f"faces, only the focal object filled with {c['accent']}. No miniature screens or "
            f"dashboards, no repeated rails or trusses, no bundled cables, no shading, no "
            f"gradients, no shadows, no people, no text, no logos. Plain flat {c['canvas']} "
            f"background with generous empty space, like an architect's line drawing."
        )
    view = (
        "isometric 3D line art, 30-degree axes, the object seen from above-front"
        if ic["style"] == "isometric-line"
        else "3D-feeling outline icon, slight three-quarter view"
    )
    return (
        f"A single icon of {subject}. Style: {view}; uniform monoline stroke in {c['ink']} of "
        f"about {ic['stroke'] * 2:.0f} px at 1024 px, rounded caps and joins, no fill except a "
        f"flat {c['surface']} on the faces, no shading, no gradient, no shadow, no text, no "
        f"logo. Centered with generous padding on a plain flat {c['canvas']} background. "
        "Minimalist technical-illustration look, like a line-art icon set; crisp vector-like "
        "edges."
    )


def generate(subject: str, t: dict, model: str, size: str, kind: str = "icon") -> bytes:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set — create a key at https://aistudio.google.com/apikey and "
            "`export GEMINI_API_KEY=...` in your shell profile (never commit it)"
        )
    body = {
        "model": model,
        "input": [{"type": "text", "text": prompt_for(subject, t, kind)}],
        "response_format": {
            "type": "image",
            "mime_type": "image/jpeg",  # the only format the API returns (2026-09)
            "aspect_ratio": "16:9" if kind == "illustration" else "1:1",
            "image_size": size,
        },
    }
    req = urllib.request.Request(  # noqa: S310 - fixed https endpoint above
        ENDPOINT,
        data=json.dumps(body).encode(),
        headers={"x-goog-api-key": key, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:  # noqa: S310 - fixed https endpoint
            data = json.load(r)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:300]
        raise RuntimeError(f"Gemini API HTTP {exc.code}: {detail}") from None
    except urllib.error.URLError as exc:
        raise RuntimeError(f"cannot reach the Gemini API: {exc.reason}") from None
    img = find_image(data)
    if not img:
        raise RuntimeError("the response carried no image (blocked prompt or quota?)")
    return base64.b64decode(img)


def find_image(data) -> str | None:
    """The base64 image, wherever this API version nests it: steps[].content[] items of
    type "image" (2026-09), or the older output_image.data."""
    if isinstance(data, dict):
        if data.get("type") == "image" and isinstance(data.get("data"), str):
            return data["data"]
        if isinstance(data.get("output_image"), dict) and data["output_image"].get("data"):
            return data["output_image"]["data"]
        for v in data.values():
            hit = find_image(v)
            if hit:
                return hit
    elif isinstance(data, list):
        for v in data:
            hit = find_image(v)
            if hit:
                return hit
    return None


def self_test() -> int:
    t = dt.load(None)
    p = prompt_for("a database", t)
    assert t["color"]["ink"] in p and "no text" in p
    assert "wide" in prompt_for("a gateway", t, "illustration")
    assert find_image({"outputs": [{"output_image": {"data": "QQ=="}}]}) == "QQ=="
    assert find_image({"x": 1}) is None
    shape = {
        "steps": [
            {"type": "thought", "signature": "x"},
            {"content": [{"type": "image", "data": "Qg=="}]},
        ]
    }
    assert find_image(shape) == "Qg=="
    print("OK: self-test passed")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("subject", nargs="?")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--model", default=MODELS[0], choices=MODELS)
    ap.add_argument("--size", default="1K", choices=["1K", "2K", "4K"])
    ap.add_argument("--design-system", default=None)
    ap.add_argument("--kind", choices=["icon", "illustration"], default="icon")
    ap.add_argument("--allow-network", action="store_true")
    ap.add_argument("--print-prompt", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if not a.subject:
        ap.error("a subject is required")
    try:
        t = dt.load(a.design_system)
        if a.print_prompt:
            print(prompt_for(a.subject, t, a.kind))
            return 0
        if not a.allow_network:
            raise RuntimeError("calling the Gemini API needs --allow-network (it sends the prompt)")
        if not a.out:
            raise RuntimeError("--out is required")
        png = generate(a.subject, t, a.model, a.size, a.kind)
    except (RuntimeError, dt.TokenError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    out = a.out if a.out.suffix.lower() in (".jpg", ".jpeg") else a.out.with_suffix(".jpg")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(png)
    print(f"OK: wrote {out} ({len(png) / 1024:.0f} KB JPEG, {a.model}, SynthID-watermarked)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
