// Render docs/demo/before-after.html to light and dark PNGs.
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
  await browser.close();
})();
