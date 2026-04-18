#!/usr/bin/env python3
"""
Second Brain Save Server

A tiny local HTTP server that runs in the background and accepts
URLs from the browser bookmarklet, saving them to ~/SecondBrain/raw/.

Runs on http://localhost:7331

Usage:
    python3 brain_server.py   # started automatically by launchd
"""

import json
import re
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

SETUP_HTML = """\
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>Add Second Brain Bookmarklet</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 600px; margin: 80px auto; padding: 0 20px; background: #0f0f0f; color: #fff; }
    h1 { font-size: 24px; margin-bottom: 8px; }
    p { color: #aaa; line-height: 1.6; }
    .step { background: #1a1a1a; border: 1px solid #333; border-radius: 12px; padding: 24px; margin: 24px 0; text-align: center; }
    .bookmarklet { display: inline-block; background: #ff0000; color: white; font-size: 18px; font-weight: bold; padding: 14px 28px; border-radius: 8px; text-decoration: none; cursor: grab; margin: 16px 0; user-select: none; }
    .bookmarklet:hover { background: #cc0000; }
    .arrow { font-size: 36px; display: block; margin: 8px 0; animation: bounce 1.5s infinite; }
    @keyframes bounce { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-8px); } }
    .hint { font-size: 13px; color: #666; margin-top: 12px; }
    .done { background: #0d2818; border: 1px solid #1a4a2a; border-radius: 12px; padding: 20px; margin-top: 24px; }
    .done h3 { color: #4ade80; margin: 0 0 8px; }
    .done p { color: #aaa; margin: 4px 0; font-size: 14px; }
    code { background: #222; padding: 2px 6px; border-radius: 4px; font-size: 13px; color: #4ade80; }
  </style>
</head>
<body>
  <h1>&#x1F9E0; Add Second Brain Bookmarklet</h1>
  <p>One-time setup. Drag the red button to your bookmarks bar.</p>
  <div class="step">
    <span class="arrow">&#x1F446;</span>
    <p style="color:#aaa; margin-bottom:12px;">Drag this to your <strong style="color:white;">bookmarks bar</strong></p>
    <a class="bookmarklet"
       href="javascript:(function(){fetch('http://localhost:7331/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:location.href,title:document.title})}).then(r=>r.json()).then(d=>alert('\\u2705 Saved to Second Brain: '+d.file)).catch(()=>alert('\\u274C Save server not running'));})();"
    >&#x2192; Brain</a>
    <p class="hint">If bookmarks bar is hidden: View &#x2192; Always Show Bookmarks Bar (&#x2318;&#x21E7;B)</p>
  </div>
  <div class="done">
    <h3 id="status">&#x2705; Server running &#x2014; ready to go!</h3>
    <p>Go to any YouTube video &#x2192; click <code>&#x2192; Brain</code> in your bar</p>
    <p>You will see: <code>&#x2705; Saved to Second Brain: Video-Title.txt</code></p>
    <p>Next ingest automatically fetches the full transcript.</p>
  </div>
</body>
</html>
"""

RAW_DIR = Path.home() / "SecondBrain" / "raw"
PORT = 7331

YOUTUBE_DOMAINS = {"youtube.com", "youtu.be", "www.youtube.com", "m.youtube.com"}


def filename_from_url(url: str, title: str) -> str:
    """Generate a safe filename from the page title or URL."""
    if title and title.strip():
        safe = re.sub(r'[^\w\s-]', '', title).strip()
        safe = re.sub(r'\s+', '-', safe)[:60]
        return safe or "untitled"
    # Fallback: use timestamp
    return datetime.now().strftime("saved-%Y%m%d-%H%M%S")


def is_youtube(url: str) -> bool:
    """Return True if the URL is a YouTube video."""
    host = urlparse(url).netloc.lower().lstrip("www.")
    return host in {"youtube.com", "youtu.be", "m.youtube.com"}


class SaveHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        """Serve the bookmarklet setup page at /setup."""
        if self.path == "/setup":
            body = SETUP_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        """Handle CORS preflight so bookmarklet can POST from any site."""
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_POST(self):
        if self.path != "/save":
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            return

        url = data.get("url", "").strip()
        title = data.get("title", "").strip()

        if not url:
            self.send_response(400)
            self._cors()
            self.end_headers()
            self.wfile.write(b'{"error":"no url"}')
            return

        RAW_DIR.mkdir(parents=True, exist_ok=True)
        fname = filename_from_url(url, title)

        # YouTube → .txt with URL (transcript fetched during ingest)
        # Everything else → .txt with URL (Web Clipper handles richer content)
        out_path = RAW_DIR / f"{fname}.txt"

        # Avoid overwriting existing files
        if out_path.exists():
            out_path = RAW_DIR / f"{fname}-{datetime.now().strftime('%H%M%S')}.txt"

        out_path.write_text(url, encoding="utf-8")
        platform = "YouTube" if is_youtube(url) else "URL"
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Saved {platform}: {url} → {out_path.name}")

        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({
            "ok": True,
            "file": out_path.name,
            "platform": platform,
        }).encode())

    def _cors(self):
        """Allow requests from any browser origin (bookmarklet runs on any site)."""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def log_message(self, format, *args):
        pass  # suppress default request logging


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    server = HTTPServer(("127.0.0.1", PORT), SaveHandler)
    print(f"Second Brain save server running on http://127.0.0.1:{PORT}")
    print(f"Saving to: {RAW_DIR}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopped.")


if __name__ == "__main__":
    main()
