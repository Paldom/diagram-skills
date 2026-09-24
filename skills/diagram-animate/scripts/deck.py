#!/usr/bin/env python3
"""deck.py — turn diagrams into slides: one HTML deck, optionally one MP4.

Each SVG becomes a 16:9 slide on the design system's canvas colour. Animated
SVGs (from animate.py) replay their build every time the slide is entered, so
the deck behaves like a PowerPoint build: → / space / click advance, ← goes
back, `f` toggles fullscreen, `a` toggles autoplay. One self-contained file,
no network, no dependencies.

With --mp4 every slide is animated and captured (same engine as animate.py,
same pinned puppeteer-core) and the clips are joined into one 1920x1080 video.

Usage:
    python3 deck.py a.anim.svg b.anim.svg --out deck.html [--title "..."] [--autoplay 6]
    python3 deck.py a.svg b.svg --out deck.html --mp4 deck.mp4 [--preset auto|reveal|build] [--allow-install]
    (auto: architecture with layers builds like PowerPoint, a wide pipeline pans, cards reveal)
    python3 deck.py --self-test
Exit 1 on failure.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import animate  # noqa: E402
import design_tokens as dt  # noqa: E402

PAGE = """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>{title}</title>
<style>
html,body{{margin:0;height:100%;background:{canvas};overflow:hidden;font-family:{font}}}
.slide{{position:fixed;inset:0;display:none;align-items:center;justify-content:center}}
.slide.on{{display:flex}}
.slide svg{{width:min(100vw,calc(100vh*16/9));height:auto;max-height:100vh}}
#bar{{position:fixed;left:0;bottom:0;height:3px;background:{ink};opacity:.35;transition:width .3s}}
#n{{position:fixed;right:14px;bottom:10px;font:12px {mono};color:{muted}}}
</style>
{slides}
<div id="bar"></div><div id="n"></div>
<script>
const S=[...document.querySelectorAll('.slide')];let i=0,auto={autoplay},timer=null;
function show(k){{i=Math.max(0,Math.min(S.length-1,k));S.forEach((s,j)=>s.classList.toggle('on',j===i));
  const svg=S[i].querySelector('svg');const fresh=svg.cloneNode(true);svg.replaceWith(fresh); // replay the build
  document.getElementById('bar').style.width=((i+1)/S.length*100)+'%';
  document.getElementById('n').textContent=(i+1)+' / '+S.length;
  clearTimeout(timer);if(auto)timer=setTimeout(()=>show(i+1<S.length?i+1:0),auto*1000);}}
addEventListener('keydown',e=>{{if(['ArrowRight',' ','PageDown'].includes(e.key))show(i+1);
  if(['ArrowLeft','PageUp'].includes(e.key))show(i-1);if(e.key==='f')document.documentElement.requestFullscreen?.();
  if(e.key==='a'){{auto=auto?0:6;show(i);}}}});
addEventListener('click',()=>show(i+1));show(0);
</script></html>
"""


def page(svgs: list[str], title: str, tokens: dict, autoplay: float) -> str:
    c, ty = tokens["color"], tokens["type"]
    slides = "\n".join(f'<section class="slide">{s}</section>' for s in svgs)
    return PAGE.format(
        title=escape(title),
        canvas=c["canvas"],
        ink=c["ink"],
        muted=c["muted"],
        font=ty["sans"],
        mono=ty["mono"],
        slides=slides,
        autoplay=autoplay or 0,
    )


def strip_xml_decl(svg: str) -> str:
    return svg.split("?>", 1)[1] if svg.lstrip().startswith("<?xml") else svg


def render_mp4(
    files: list[Path],
    tokens: dict,
    preset: str,
    out: Path,
    allow_install: bool,
    min_seconds: float = 7.0,
) -> None:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found")
    work = Path(tempfile.mkdtemp(prefix="ds-deck-"))
    clips = []
    lengths = []
    reads = []  # per-slide minimum time on screen, from its word count
    try:
        for k, f in enumerate(files):
            text = f.read_text(encoding="utf-8")
            kind = preset
            fw = None
            if preset == "auto":  # layered architecture builds; a wide pipeline pans; cards reveal
                vw, vh = animate.viewbox(animate.ET.fromstring(text))
                if vw > 2 * vh:
                    kind, fw = "pipeline", round(vh * 16 / 9)
                else:
                    kind = "build" if 'data-kind="group" data-id=' in text else "reveal"
            svg, meta = animate.build(text, tokens, kind, fw)
            src = work / f"s{k}.svg"
            src.write_text(svg, encoding="utf-8")
            frames = animate.capture(src, meta, tokens["motion"]["fps"], 2.0, allow_install)
            clip = work / f"s{k}.mp4"
            animate.encode(frames, tokens["motion"]["fps"], None, clip, 2.0, poster=False)
            shutil.rmtree(frames, ignore_errors=True)
            clips.append(clip)
            lengths.append(meta["duration"] / 1000)
            words = len(" ".join(animate.ET.fromstring(text).itertext()).split())
            reads.append(min(14.0, max(min_seconds, 0.22 * words)))  # ~270 wpm, capped
        pad = (
            "scale=1920:1080:force_original_aspect_ratio=decrease,"
            f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color={tokens['color']['canvas'].lstrip('#')},setsar=1"
        )
        inputs = [arg for p in clips for arg in ("-i", str(p))]
        # every slide stays on screen long enough to read: hold its last frame
        graph = "".join(
            f"[{i}:v]{pad},tpad=stop_mode=clone:stop_duration={max(0.0, reads[i] - lengths[i]):.2f}[v{i}];"
            for i in range(len(clips))
        )
        graph += (
            "".join(f"[v{i}]" for i in range(len(clips))) + f"concat=n={len(clips)}:v=1:a=0[out]"
        )
        r = subprocess.run(
            ["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", graph, "-map", "[out]",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", str(out)],
            capture_output=True, text=True,
        )  # fmt: skip
        if r.returncode != 0:
            raise RuntimeError(f"ffmpeg concat failed: {r.stderr.strip()[-300:]}")
    finally:
        shutil.rmtree(work, ignore_errors=True)


def self_test() -> int:
    t = dt.load(None)
    html = page(
        ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"></svg>'] * 2, "T", t, 0
    )
    assert html.count('class="slide"') == 2 and t["color"]["canvas"] in html and "replay" in html
    assert strip_xml_decl('<?xml version="1.0"?><svg/>') == "<svg/>"
    print("OK: self-test passed")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("svgs", nargs="*", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--title", default="Diagrams")
    ap.add_argument("--autoplay", type=float, default=0, help="seconds per slide (0 = manual)")
    ap.add_argument("--mp4", type=Path, help="also render every slide's animation into one video")
    ap.add_argument("--preset", choices=["auto", "reveal", "pipeline", "build"], default="auto")
    ap.add_argument("--min-seconds", type=float, default=7.0, help="shortest time a slide stays up")
    ap.add_argument("--design-system", default=None)
    ap.add_argument("--allow-install", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if not a.svgs or not a.out:
        ap.error("SVG files and --out are required")
    try:
        tokens = dt.load(a.design_system)
        svgs = [strip_xml_decl(p.read_text(encoding="utf-8")) for p in a.svgs]
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(page(svgs, a.title, tokens, a.autoplay), encoding="utf-8")
        print(f"OK: {a.out} ({len(svgs)} slides)")
        if a.mp4:
            render_mp4(a.svgs, tokens, a.preset, a.mp4, a.allow_install, a.min_seconds)
            print(f"OK: {a.mp4} ({a.mp4.stat().st_size / 1e6:.1f} MB)")
    except (OSError, RuntimeError, dt.TokenError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
