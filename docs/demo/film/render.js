// Render hero.html to MP4 (1920x1080, 30 fps) and a README GIF (800 wide, ~4.6 MB).
// Usage (from the repo root):
//   node docs/demo/film/render.js            full render -> docs/screenshots/hero.{mp4,gif}
//   node docs/demo/film/render.js stills 1.2 3.4 7.9   single frames -> /tmp/hero-stills
// Needs Playwright (npm i -D playwright) and ffmpeg on PATH.
const { chromium } = require("playwright");
const { execFileSync } = require("child_process");
const fs = require("fs");
const http = require("http");
const os = require("os");
const path = require("path");

const FPS = 30, DURATION = 12.5;
const ROOT = path.resolve(__dirname, "..");            // docs/demo, served so fetch() works
const OUT = path.resolve(__dirname, "../../screenshots");

function serve() {
  const types = { ".html": "text/html", ".css": "text/css", ".json": "application/json", ".woff2": "font/woff2", ".svg": "image/svg+xml" };
  const srv = http.createServer((req, res) => {
    const file = path.join(ROOT, decodeURIComponent(req.url.split("?")[0]));
    if (!file.startsWith(ROOT) || !fs.existsSync(file)) { res.writeHead(404); return res.end(); }
    res.writeHead(200, { "Content-Type": types[path.extname(file)] || "application/octet-stream" });
    fs.createReadStream(file).pipe(res);
  });
  return new Promise((r) => srv.listen(0, "127.0.0.1", () => r(srv)));
}

(async () => {
  const [mode, ...times] = process.argv.slice(2);
  const srv = await serve();
  const url = `http://127.0.0.1:${srv.address().port}/film/hero.html`;
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  await page.goto(url);
  await page.waitForFunction(() => window.ready === true);
  await page.evaluate(() => document.body.classList.add("render"));
  const stage = await page.$("#stage");
  const shot = async (t, file) => {
    await page.evaluate((t) => window.seek(t), t);
    await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
    await stage.screenshot({ path: file });
  };

  if (mode === "stills") {
    const dir = path.join(os.tmpdir(), "hero-stills");
    fs.mkdirSync(dir, { recursive: true });
    for (const t of times) await shot(parseFloat(t), path.join(dir, `t${t}.png`));
    console.log("stills in", dir);
  } else {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), "hero-frames-"));
    const n = Math.round(DURATION * FPS);
    for (let i = 0; i < n; i++) await shot(i / FPS, path.join(dir, `f${String(i).padStart(4, "0")}.png`));
    const ff = (args) => execFileSync("ffmpeg", ["-y", "-loglevel", "error", ...args], { stdio: "inherit" });
    ff(["-framerate", String(FPS), "-i", path.join(dir, "f%04d.png"),
        "-c:v", "libx264", "-crf", "18", "-preset", "slow", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        path.join(OUT, "hero.mp4")]);
    ff(["-i", path.join(OUT, "hero.mp4"), "-vf",
        "fps=15,scale=800:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=3:diff_mode=rectangle",
        path.join(OUT, "hero.gif")]);
    fs.rmSync(dir, { recursive: true });
    console.log("wrote", path.join(OUT, "hero.mp4"), "and hero.gif");
  }
  await browser.close();
  srv.close();
})();
