#!/usr/bin/env node
// render_mermaid.mjs — Mermaid source to a themed SVG (beautiful-mermaid) and,
// optionally, a PNG rasterized in the system Chrome. The SVG styles itself
// with CSS variables and color-mix(), so only a browser rasterizes it right.
//
// Usage: node render_mermaid.mjs IN.mmd OUT.svg OPTIONS_JSON [--png OUT.png --chrome PATH --scale 2]
//        node render_mermaid.mjs IN.svg OUT.svg {} --png OUT.png --chrome PATH   (rasterize only)
// Exit 1 on a parse or render error.

import { readFileSync, writeFileSync } from "node:fs";
import { renderMermaidSVG } from "beautiful-mermaid";

const [, , inPath, outPath, optsJson] = process.argv;
function arg(name) {
  const i = process.argv.indexOf(`--${name}`);
  return i > -1 ? process.argv[i + 1] : undefined;
}

// Bring beautiful-mermaid's output in line with the design system: no web-font
// fetch, the full font stack, card radius/border/lift, and the connector weight.
function restyle(svg, p) {
  if (!p) return svg;
  const lift = p.lift
    ? `<filter id="ds-lift" data-ds="${p.liftKind || "neumorph"}" x="-20%" y="-20%" width="140%" height="160%">` +
      p.lift.map((s) => `<feDropShadow dx="${s.dx}" dy="${s.dy}" stdDeviation="${s.blur / 2}" flood-color="${s.color}" flood-opacity="${s.opacity}"/>`).join("") +
      `</filter>`
    : "";
  return svg
    .replace(/^\s*@import url\([^)]*\);\n/m, "")
    // a canvas-coloured halo keeps lifelines and edges from striking through message/edge labels
    .replace("</style>", `  text[fill="var(--_text-muted)"] { paint-order: stroke; stroke: var(--bg); stroke-width: 5px; stroke-linejoin: round; }\n</style>`)
    .replace(/font-family: 'Manrope', system-ui, sans-serif;/, `font-family: ${p.font};`)
    .replace(/font-family: '[^']*', system-ui, sans-serif;/, `font-family: ${p.font};`)
    .replace("<defs>", `<defs>${lift}`)
    .replace(/<marker (id="arrowhead[^"]*")/g, '<marker $1 markerUnits="userSpaceOnUse"')
    .replace(/<rect([^>]*?) rx="[\d.]+" ry="[\d.]+" fill="var\(--_node-fill\)" stroke="var\(--_node-stroke\)" stroke-width="[\d.]+"/g,
      (_, a) => `<rect${a} rx="${p.radius}" ry="${p.radius}" fill="var(--_node-fill)" ${p.border ? `stroke="var(--_node-stroke)" stroke-width="1"` : `stroke="none"`}${lift ? ' filter="url(#ds-lift)"' : ""}`)
    .replace(/<rect([^>]*?) rx="2" ry="2" fill="var\(--bg\)" stroke="var\(--_inner-stroke\)" stroke-width="1"/g,
      (_, a) => `<rect${a} rx="${p.radiusSmall}" ry="${p.radiusSmall}" fill="var(--bg)" stroke="none"`)
    .replace(/(<polyline class="edge"[^>]*?) stroke-width="1"/g, `$1 stroke-width="${p.stroke}"`);
}

let svg;
if (inPath.endsWith(".svg")) {
  // an already-rendered (e.g. canvas-fitted) SVG: only rasterize it
  svg = readFileSync(inPath, "utf8");
} else try {
  // strip a leading config: frontmatter — it is for GitHub/mmdc, not this renderer
  const src = readFileSync(inPath, "utf8").replace(/^---\n[\s\S]*?\n---\n/, "");
  const { post, ...opts } = JSON.parse(optsJson);
  svg = restyle(renderMermaidSVG(src, opts), post);
} catch (err) {
  console.error(`ERROR: ${err.message}`);
  process.exit(1);
}
writeFileSync(outPath, svg);

const png = arg("png");
if (png) {
  const { default: puppeteer } = await import("puppeteer-core");
  const browser = await puppeteer.launch({
    executablePath: arg("chrome"),
    headless: true,
    args: ["--host-resolver-rules=MAP * ~NOTFOUND", "--disable-gpu"],
  });
  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 800, height: 600, deviceScaleFactor: Number(arg("scale") || 2) });
    await page.setContent(`<!doctype html><style>body{margin:0}</style>${svg}`, { waitUntil: "load" });
    await page.evaluate(() => document.fonts.ready);
    const el = await page.$("svg");
    await el.screenshot({ path: png });
  } finally {
    await browser.close();
  }
}
console.log(`OK ${outPath}${png ? ` ${png}` : ""}`);
