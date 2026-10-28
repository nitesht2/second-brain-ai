// Render the README images in docs/demo/*.html to PNGs in docs/screenshots/.
// Usage (from the repo root): node docs/demo/render.js
// Needs Playwright: npm i -D playwright && npx playwright install chromium
const path = require("path");
const { chromium } = require("playwright");

(async () => {
  const src = "file://" + path.resolve(__dirname, "before-after.html");
  const outDir = path.resolve(__dirname, "../screenshots");
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1200, height: 680 }, deviceScaleFactor: 2 });
  await page.goto(src);
  for (const theme of ["light", "dark"]) {
    await page.evaluate((t) => document.documentElement.classList.toggle("dark", t === "dark"), theme);
    await page.screenshot({ path: path.join(outDir, `before-after-${theme}.png`) });
  }
  const banner = await browser.newPage({ viewport: { width: 1280, height: 640 } });
  await banner.goto("file://" + path.resolve(__dirname, "banner.html"));
  await banner.screenshot({ path: path.join(outDir, "banner.png") });
  await browser.close();
})();
