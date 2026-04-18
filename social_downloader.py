#!/usr/bin/env python3
"""
Second Brain — Social Media Downloader

Downloads TikTok and Instagram videos by intercepting CDN URLs from a real
Chrome browser session (bypasses bot detection). Transcribes with whisper-cli
(whisper.cpp, fastest on M4 Metal) and saves a transcript .md file to raw/.

Usage:
    python3 social_downloader.py <URL>
    python3 social_downloader.py https://www.tiktok.com/@user/video/123
    python3 social_downloader.py https://www.instagram.com/reel/ABC123/

The transcript lands in ~/SecondBrain/raw/ and is picked up by the next ingest.
"""

import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

RAW_DIR = Path.home() / "SecondBrain" / "raw"
WHISPER_MODEL = "/opt/homebrew/share/whisper-cpp/ggml-base.en.bin"
CHROME_PROFILE = Path.home() / "Library" / "Application Support" / "Google" / "Chrome"

# CDN domains that serve TikTok/Instagram video content
VIDEO_CDN_PATTERNS = [
    "tiktokcdn.com",
    "tiktokv.com",
    "cdninstagram.com",
    "fbcdn.net",
    "scontent",
]

# Minimum file size to consider a real video (not a thumbnail/preview)
MIN_VIDEO_BYTES = 500_000  # 500KB


def detect_platform(url: str) -> str:
    """Return 'tiktok', 'instagram', or 'unknown'."""
    if "tiktok.com" in url or "vm.tiktok" in url:
        return "tiktok"
    if "instagram.com" in url or "instagr.am" in url:
        return "instagram"
    return "unknown"


def safe_filename(url: str, platform: str) -> str:
    """Generate a filesystem-safe filename from the URL."""
    # Extract video/reel ID from URL
    patterns = [
        r"/video/(\d+)",           # TikTok
        r"/reel/([A-Za-z0-9_-]+)", # Instagram reel
        r"/p/([A-Za-z0-9_-]+)",    # Instagram post
    ]
    for pat in patterns:
        m = re.search(pat, url)
        if m:
            return f"{platform}-{m.group(1)}"
    return f"{platform}-{int(time.time())}"


def intercept_video_url(page_url: str) -> str | None:
    """
    Open page_url in real Chrome (with user's logged-in session),
    intercept the CDN video response, and return the CDN URL.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  ✗ Playwright not installed: pip3 install playwright")
        return None

    video_cdn_url = None

    print(f"  ▶ Opening browser to intercept video URL...")
    with sync_playwright() as p:
        # Use persistent Chrome profile so TikTok/Instagram see a real logged-in user
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(CHROME_PROFILE),
            channel="chrome",
            headless=False,          # Must be non-headless — TikTok blocks headless
            args=[
                "--mute-audio",      # Don't play audio while scanning
                "--no-first-run",
                "--disable-notifications",
            ],
        )

        page = ctx.new_page()

        def on_response(response):
            nonlocal video_cdn_url
            if video_cdn_url:
                return
            try:
                content_type = response.headers.get("content-type", "")
                content_length = int(response.headers.get("content-length", "0"))
                url_lower = response.url.lower()

                is_video_type = "video" in content_type
                is_video_cdn = any(p in url_lower for p in VIDEO_CDN_PATTERNS)
                is_large_enough = content_length > MIN_VIDEO_BYTES

                if (is_video_type or is_video_cdn) and is_large_enough and response.status == 200:
                    video_cdn_url = response.url
                    print(f"  ✓ Video CDN URL intercepted")
            except Exception:
                pass

        page.on("response", on_response)

        try:
            page.goto(page_url, wait_until="domcontentloaded", timeout=30_000)
            # Wait up to 15s for the video request to appear
            deadline = time.time() + 15
            while not video_cdn_url and time.time() < deadline:
                page.wait_for_timeout(500)
        except Exception as e:
            print(f"  ✗ Browser navigation failed: {e}")
        finally:
            ctx.close()

    return video_cdn_url


def download_video(cdn_url: str, dest: Path) -> bool:
    """Download the video from a CDN URL."""
    print(f"  ▶ Downloading video...")
    try:
        req = urllib.request.Request(cdn_url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/124.0.0.0 Safari/537.36",
            "Referer": "https://www.tiktok.com/",
        })
        with urllib.request.urlopen(req, timeout=60) as resp, open(dest, "wb") as f:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            while chunk := resp.read(65536):
                f.write(chunk)
                downloaded += len(chunk)
            size_mb = downloaded / 1_048_576
            print(f"  ✓ Downloaded {size_mb:.1f}MB")
        return True
    except Exception as e:
        print(f"  ✗ Download failed: {e}")
        return False


def transcribe(video_path: Path) -> str:
    """
    Transcribe a video file using whisper-cli (whisper.cpp, Metal GPU) first,
    falling back to faster-whisper, then openai-whisper.
    """
    # Option 1: whisper-cli (whisper.cpp — fastest on M4 Metal)
    if shutil.which("whisper-cli") and Path(WHISPER_MODEL).exists():
        print(f"  ▶ Transcribing with whisper-cli (Metal GPU)...")
        try:
            result = subprocess.run(
                ["whisper-cli", "-m", WHISPER_MODEL, str(video_path), "--output-txt", "--no-prints"],
                capture_output=True, text=True, timeout=300,
            )
            txt_path = video_path.with_suffix(".txt")
            if txt_path.exists():
                transcript = txt_path.read_text(encoding="utf-8").strip()
                txt_path.unlink()
                if transcript:
                    return transcript
        except Exception as e:
            print(f"  ⚠ whisper-cli failed: {e} — trying faster-whisper")

    # Option 2: faster-whisper (4x faster than openai-whisper, CPU)
    try:
        from faster_whisper import WhisperModel
        print(f"  ▶ Transcribing with faster-whisper...")
        model = WhisperModel("base.en", device="cpu", compute_type="int8")
        segments, _ = model.transcribe(str(video_path), language="en")
        return " ".join(seg.text.strip() for seg in segments)
    except ImportError:
        pass
    except Exception as e:
        print(f"  ⚠ faster-whisper failed: {e} — trying openai-whisper")

    # Option 3: openai-whisper (most accurate, slowest)
    try:
        import whisper
        print(f"  ▶ Transcribing with openai-whisper...")
        model = whisper.load_model("base.en")
        result = model.transcribe(str(video_path), language="en")
        return result["text"].strip()
    except ImportError:
        print("  ✗ No whisper variant available. Install: pip3 install faster-whisper")
        return ""
    except Exception as e:
        print(f"  ✗ Transcription failed: {e}")
        return ""


def save_to_raw(url: str, platform: str, title: str, transcript: str) -> Path:
    """Write a markdown file to raw/ with frontmatter + transcript."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    stem = safe_filename(url, platform)
    out_path = RAW_DIR / f"{stem}.md"

    content = f"""---
title: "{title}"
source: {url}
platform: {platform}
created: {time.strftime('%Y-%m-%d')}
tags: [{platform}, video, transcript]
---

# {title}

## Transcript

{transcript}
"""
    out_path.write_text(content, encoding="utf-8")
    return out_path


def download_and_transcribe(url: str) -> bool:
    """Full pipeline: intercept → download → transcribe → save to raw/."""
    platform = detect_platform(url)
    if platform == "unknown":
        print(f"  ✗ Unsupported platform. Supported: TikTok, Instagram")
        return False

    print(f"\n🎬 Processing {platform} video...")
    print(f"   URL: {url}")

    # Step 1: Intercept CDN video URL via real browser
    cdn_url = intercept_video_url(url)
    if not cdn_url:
        print("  ✗ Could not intercept video URL. Make sure you are logged in to "
              f"{platform.capitalize()} in Chrome.")
        return False

    # Step 2: Download video to temp file
    with tempfile.TemporaryDirectory() as tmp:
        video_path = Path(tmp) / f"video.mp4"
        if not download_video(cdn_url, video_path):
            return False

        # Step 3: Transcribe
        transcript = transcribe(video_path)
        if not transcript:
            print("  ✗ Transcription produced no output")
            return False

    # Step 4: Save to raw/ as .md
    title = safe_filename(url, platform).replace("-", " ").title()
    out_path = save_to_raw(url, platform, title, transcript)
    print(f"\n✅ Saved: {out_path.name}")
    print(f"   Transcript: {len(transcript.split())} words")
    print(f"   Next ingest will build wiki entries automatically.")
    return True


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 social_downloader.py <TikTok or Instagram URL>")
        sys.exit(1)

    url = sys.argv[1].strip()
    success = download_and_transcribe(url)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
