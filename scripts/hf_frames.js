// Render a HyperFrames-style composition to PNG frames with the system Chrome (no FFmpeg needed).
// Usage: node hf_frames.js <composition index.html> <out_dir> [fps] [composition-id]
// Then encode with: python encode_frames.py <out_dir> <out.mp4> [fps] [audio]
const path = require("path");
const fs = require("fs");
const puppeteer = require(path.join(__dirname, "..", "hyperframes", "node_modules", "puppeteer-core"));

const [, , htmlPath, outDir, fpsArg, compArg] = process.argv;
const fps = Number(fpsArg || 30);
const compId = compArg || "main";
// Chrome path: env var, else common install locations per OS (scripts/vp.py sets the env var for you)
const CHROME = process.env.HYPERFRAMES_BROWSER_PATH || [
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  "/usr/bin/google-chrome",
  "/usr/bin/chromium",
  "/usr/bin/chromium-browser",
].find((p) => fs.existsSync(p));

(async () => {
  fs.mkdirSync(outDir, { recursive: true });
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: true,
    args: ["--allow-file-access-from-files", "--hide-scrollbars", "--force-device-scale-factor=1"],
  });
  const page = await browser.newPage();
  page.on("console", (m) => console.log("[page]", m.type(), m.text()));
  page.on("pageerror", (e) => console.log("[page error]", e.message));
  page.on("requestfailed", (r) => console.log("[request failed]", r.url(), r.failure() && r.failure().errorText));
  const url = "file:///" + path.resolve(htmlPath).replace(/\\/g, "/");
  await page.goto(url, { waitUntil: "load", timeout: 120000 });
  await page.evaluate(() => document.fonts && document.fonts.ready);
  const state = await page.evaluate(() => ({
    gsap: typeof window.gsap, timelines: window.__timelines ? Object.keys(window.__timelines) : null,
    href: location.href,
  }));
  console.log("state", JSON.stringify(state));
  // poll on an interval: requestAnimationFrame-based polling can stall in headless Chrome
  await page.waitForFunction((id) => !!(window.__timelines && window.__timelines[id]), { timeout: 15000, polling: 100 }, compId);

  const info = await page.evaluate((id) => {
    const root = document.querySelector(`[data-composition-id="${id}"]`);
    return {
      w: Number(root.dataset.width || 1080),
      h: Number(root.dataset.height || 1920),
      dur: Number(root.dataset.duration || window.__timelines[id].duration()),
    };
  }, compId);
  await page.setViewport({ width: info.w, height: info.h, deviceScaleFactor: 1 });

  const n = Math.round(info.dur * fps);
  for (let i = 0; i < n; i++) {
    const t = i / fps;
    await page.evaluate(
      (id, t) => {
        // clip visibility from data-start / data-duration (what the HyperFrames runtime normally does)
        document.querySelectorAll("[data-start]").forEach((el) => {
          if (el.dataset.compositionId) return;
          const s = Number(el.dataset.start), d = Number(el.dataset.duration || 1e9);
          el.style.visibility = t >= s && t < s + d ? "visible" : "hidden";
        });
        window.__timelines[id].seek(t, false);
      },
      compId,
      t
    );
    await page.screenshot({ path: path.join(outDir, `f_${String(i).padStart(5, "0")}.png`) });
    if (i % 30 === 0) console.log(`frame ${i}/${n}`);
  }
  await browser.close();
  console.log(JSON.stringify({ frames: n, fps, ...info }));
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
