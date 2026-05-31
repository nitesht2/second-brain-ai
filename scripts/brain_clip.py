#!/usr/bin/env python3
"""brain-clip: clip any URL from the Mac (residential IP) -> transcript md -> push to VPS raw/.
YouTube: fast caption fetch (no download). Other sites: yt-dlp audio + whisper-cli (Metal).
Usage: brain_clip.py <url>
"""
import re, sys, subprocess, tempfile, shutil
from pathlib import Path
from datetime import datetime

RAW = Path.home() / "SecondBrain" / "raw"
VPS = __import__("os").environ.get("BRAIN_VPS_HOST", "root@YOUR_VPS_IP")
VPS_RAW = "/root/SecondBrain/raw/"
WHISPER_MODEL = "/opt/homebrew/share/whisper-cpp/ggml-base.en.bin"

def safe(s, n=80):
    s = re.sub(r"[^\w\s-]", "", s or "").strip()
    return (re.sub(r"[\s_-]+", " ", s)[:n] or "clip").strip()

def yt_id(u):
    m = re.search(r"(?:v=|youtu\.be/|shorts/|embed/)([A-Za-z0-9_-]{11})", u)
    return m.group(1) if m else None

def push(fp):
    try:
        subprocess.run(["scp", "-q", str(fp), f"{VPS}:{VPS_RAW}"], check=True, timeout=60)
        print(f"  pushed to VPS -> Chanakya will ingest")
    except Exception as e:
        print(f"  ! push failed ({e}); file is in local raw/, will sync later")

def write(title, url, platform, text, uploader=""):
    RAW.mkdir(parents=True, exist_ok=True)
    fp = RAW / f"{safe(title)}.md"
    fp.write_text(f'''---
title: "{title}"
source: {url}
platform: {platform}
uploader: "{uploader}"
created: {datetime.now().strftime('%Y-%m-%d')}
tags: [{platform.lower()}, clip, transcript]
---

# {title}

Source: {url}

## Transcript

{text}
''', encoding="utf-8")
    print(f"  wrote {fp.name} ({len(text)} chars)")
    push(fp)

def main():
    if len(sys.argv) < 2:
        print("usage: brain_clip.py <url>"); return 1
    url = sys.argv[1]
    vid = yt_id(url)
    # YouTube -> captions (fast, residential IP works)
    if vid:
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            rows = YouTubeTranscriptApi().fetch(vid)
            text = " ".join(r.text for r in rows).strip()
            if text:
                write(f"YouTube {vid}", url, "YouTube", text); return 0
            print("  no captions; falling back to audio download")
        except Exception as e:
            print(f"  captions failed ({e}); falling back to yt-dlp+whisper")
    # Any site -> yt-dlp audio + whisper-cli (Metal)
    with tempfile.TemporaryDirectory() as td:
        out = str(Path(td) / "a.%(ext)s")
        try:
            import yt_dlp
            with yt_dlp.YoutubeDL({"format":"bestaudio/best","outtmpl":out,"quiet":True,
                "noprogress":True,"postprocessors":[{"key":"FFmpegExtractAudio",
                "preferredcodec":"wav"}]}) as ydl:
                info = ydl.extract_info(url, download=True)
        except Exception as e:
            print(f"  yt-dlp failed: {e}"); return 1
        title = info.get("title","clip"); platform = info.get("extractor_key","web")
        uploader = info.get("uploader") or info.get("channel") or ""
        wav = next(Path(td).glob("a.*"), None)
        if not wav: print("  no audio"); return 1
        if not (shutil.which("whisper-cli") and Path(WHISPER_MODEL).exists()):
            print("  whisper-cli/model missing"); return 1
        print(f'  transcribing "{title}" ({platform}) with whisper-cli (Metal)...')
        subprocess.run(["whisper-cli","-m",WHISPER_MODEL,str(wav),"--output-txt","--no-prints"],
                       capture_output=True, timeout=900)
        txt = wav.with_suffix(".txt")
        text = txt.read_text(encoding="utf-8").strip() if txt.exists() else ""
        if not text: print("  empty transcript"); return 1
        write(title, url, platform, text, uploader); return 0

if __name__ == "__main__":
    sys.exit(main())
