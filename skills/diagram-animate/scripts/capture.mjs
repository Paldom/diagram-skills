#!/usr/bin/env node
// capture.mjs — deterministic frame capture of a CSS-animated SVG.
//
// Loads the SVG inline in a blank page in the system Chrome (puppeteer-core,
// no bundled browser download), waits for fonts, then for every frame pauses
// each animation at exactly t and takes a screenshot. Frames are therefore
// identical on every run and the last frame equals the static final state.
//
// Usage: node capture.mjs --svg in.svg --out DIR --width W --height H
//          --fps 20 --duration 8000 [--scale 2] --chrome /path/to/chrome
// Output: DIR/f0000.png ... and a final "FRAMES <n>" line. Exit 1 on error.

import { readFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import puppeteer from "puppeteer-core";

function arg(name, fallback) {
  const i = process.argv.indexOf(`--${name}`);
  return i > -1 ? process.argv[i + 1] : fallback;
}

const svgPath = arg("svg");
const outDir = arg("out");
const width = Number(arg("width"));
const height = Number(arg("height"));
const fps = Number(arg("fps", "20"));
const duration = Number(arg("duration"));
const scale = Number(arg("scale", "1"));
const chrome = arg("chrome");
const reduced = process.argv.includes("--reduced-motion");

if (!svgPath || !outDir || !width || !height || !duration || !chrome) {
  console.error("ERROR: --svg --out --width --height --duration --chrome are required");
  process.exit(1);
}

const svg = readFileSync(svgPath, "utf8");
mkdirSync(outDir, { recursive: true });

const browser = await puppeteer.launch({
  executablePath: chrome,
  headless: true,
  args: ["--host-resolver-rules=MAP * ~NOTFOUND", "--disable-gpu", "--hide-scrollbars"],
});
try {
  const page = await browser.newPage();
  await page.setViewport({ width, height, deviceScaleFactor: scale });
  if (reduced) await page.emulateMediaFeatures([{ name: "prefers-reduced-motion", value: "reduce" }]);
  await page.setContent(
    `<!doctype html><meta charset="utf-8"><style>html,body{margin:0;padding:0;overflow:hidden;background:transparent}svg{display:block;width:${width}px;height:${height}px}</style>${svg}`,
    { waitUntil: "load" },
  );
  await page.evaluate(() => document.fonts.ready);
  const frames = Math.max(1, Math.round((duration / 1000) * fps));
  for (let k = 0; k <= frames; k++) {
    const t = Math.min(duration, (k * 1000) / fps);
    const count = await page.evaluate((time) => {
      const anims = document.getAnimations();
      for (const a of anims) {
        a.pause();
        a.currentTime = time;
      }
      return anims.length;
    }, t);
    if (k === 0 && count === 0) console.error("WARN: no CSS animations found in the SVG");
    await page.screenshot({ path: join(outDir, `f${String(k).padStart(4, "0")}.png`), omitBackground: false });
  }
  console.log(`FRAMES ${frames + 1}`);
} catch (err) {
  console.error(`ERROR: ${err.message}`);
  process.exitCode = 1;
} finally {
  await browser.close();
}
