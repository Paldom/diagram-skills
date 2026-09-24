---
name: diagram-animate
description: Animates finished diagrams into explainers and slide decks - reveal in reading order, connectors that draw, a PowerPoint-style build with a focusing camera, a pipeline pan - as SVG, GIF, MP4, or an HTML deck. Use when the user asks to animate a diagram, make a GIF, video, or deck of diagrams, or build it step by step. Not for drawing or reviewing diagrams, UI animation, or screen recordings.
license: MIT
argument-hint: <diagram.svg, optionally --preset pipeline>
---

# diagram-animate

One animation definition, three outputs. `animate.py` adds CSS keyframes to
the static SVG (plays in any browser and in a README `<img>`), then
`capture.mjs` loads that same file in the system Chrome, **sets every
animation to an exact time per frame**, and screenshots — so the GIF and MP4
are deterministic and can never drift from the SVG. Timing comes from the
design system's `motion` tokens, so a theme change restyles the motion too.

Order, from the `data-step` / `data-kind` attributes the renderers in
`illustration-draw` emit (other SVGs — Mermaid, Graphviz — reveal child by
child in document order): title types in → groups fade up → cards land →
connectors draw, arrowheads arrive when the line does → step badges pop →
notes → the accent fills in last → hold.

## When NOT to use

- The diagram does not exist or is not reviewed yet → draw and review it first
  (`illustration-draw` / `mermaid-draw`, then `diagram-review`). Animation
  amplifies flaws; it never fixes them.
- UI micro-interactions, CSS for an app, screen or terminal recordings.

## Workflow

1. **Pick the preset.** `reveal` (default) for any diagram. `pipeline` for a
   wide left-to-right diagram: the frame is `--frame-width` px wide, the title
   stays pinned, the camera follows the newest step and ends on an overview
   (build the source as a flow on a `{"w": 2400, "h": 630}` canvas). `build`
   for a layered architecture from `arch_svg.py` — the PowerPoint build: the
   camera opens on the first layer, the other layers wait as ghosts, layers
   come into focus left to right (stacked ones top-down), connectors arrive
   with their later endpoint, the camera widens only when a new layer starts,
   and it settles on the whole diagram. One step per beat (`--beat-ms`,
   default 600); prefer MP4 for it — a moving camera makes GIFs large.
   With a `pipeline_svg.py` explainer, `pipeline` types code panels line by
   line, plays each callout in turn (token tints, leader draws, note fades),
   builds the dashboard part by part, grows the timing bar, and waits for each
   step's content before the next — the camera moves once per stage after a
   reading hold, and finished stages stay dimmed behind it.
2. **Animate** — SVG only needs nothing; GIF/MP4 need Node ≥ 22.12, Chrome or
   Chromium, and ffmpeg (gifsicle optional):

   ```bash
   python3 "${CLAUDE_SKILL_DIR}/scripts/animate.py" diagram.svg --out diagram.anim.svg \
     --gif diagram.gif --mp4 diagram.mp4 [--preset pipeline --frame-width 1200] \
     [--canvas social|square|wide] [--design-system design-system.md]
   ```

   `--canvas` pads the GIF/MP4 onto 1200×627, 1080×1080 or 1920×1080; with
   `pipeline` the camera frame takes the canvas shape.

   The first GIF run needs `--allow-install`: it runs `npm ci --ignore-scripts`
   on the pinned lockfile (puppeteer-core only, no browser download) into
   `~/.cache/diagram-skills/`. Ask before adding the flag.
3. **Look at frames** before handing off — early, middle, and the last one
   (`diagram.last.png` is written next to the GIF): the last frame must equal
   the static diagram, the camera must stay ahead of the reveal, and nothing
   may flash. `ffmpeg -i diagram.gif -vf "select='not(mod(n\,15))',tile=3x3" -frames:v 1 sheet.png`
   makes a contact sheet in one command.
4. **Slides.** Several diagrams become one talk with `deck.py`: a single
   offline HTML deck (→/space/click advance, each slide replays its build,
   `f` fullscreen, `a` autoplay) and, with `--mp4`, one 1080p video of every
   slide's build (`--preset auto`: layered architecture builds, cards reveal).
   Compile slide sources with `--show-title` — figures are title-less by default:

   ```bash
   python3 "${CLAUDE_SKILL_DIR}/scripts/deck.py" a.anim.svg b.anim.svg --out deck.html
   python3 "${CLAUDE_SKILL_DIR}/scripts/deck.py" a.svg arch.svg --out deck.html --mp4 talk.mp4
   ```
5. **Deliver** the paths, the duration and file sizes. Never commit or push.

## Output spec

- `*.anim.svg` — the static SVG plus one `<style>` block; a
  `prefers-reduced-motion` rule shows the final state immediately.
- `*.gif` (downscaled from 2× capture, palette tuned for flat colour, loops)
  and/or `*.mp4` (H.264, yuv420p), plus `*.last.png`.

## Motion rules (built in)

Entrances ease out (`cubic-bezier(0.23, 1, 0.32, 1)`, the design system's
`motion.easing`), camera moves ease in and out (`cubic-bezier(0.77, 0, 0.175, 1)`),
pops start at 0.96 scale, never from nothing, and nothing overshoots. Reduced
motion is gentler, not frozen: fades and order stay, movement goes — the
camera cuts between stages; preview it with `--reduced-motion`.

## Gotchas

- Lint the **static** SVG with `diagram-review`, not the animated one: the
  pipeline camera track is wider than the frame by design.
- Total length is capped by `motion.max-seconds`; long diagrams get a tighter
  stagger instead of a longer clip. Keep feeds under ~10 s.
- GIF size grows with area × frames: 1200 px wide and ≤ 6 s stays near 1 MB;
  prefer the MP4 for LinkedIn and X, the GIF for READMEs and Slack.
- Capture runs Chrome with all DNS disabled — web fonts and remote images
  cannot load, so the diagram must be self-contained (the renderers already are).
