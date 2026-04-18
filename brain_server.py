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
