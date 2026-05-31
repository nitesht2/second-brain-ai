#!/usr/bin/env python3
"""Universal clipper: URL -> transcript markdown in raw/ (auto-ingested by the watcher).

Video/audio (YouTube, TikTok, Instagram, X, podcasts, 1000+ sites via yt-dlp) ->
download bestaudio -> faster-whisper transcribe -> raw/<title>.md.
Articles/plain pages are left to the agent's web_extract (it handles those directly).

Usage: clip.py <url> [--model base.en|small|medium]
"""
import re, sys, json, tempfile, subprocess
from pathlib import Path
from datetime import datetime

VAULT = Path.home() / 'SecondBrain'
RAW = VAULT / 'raw'
VENV_PY = VAULT / '.venv' / 'bin' / 'python'

def safe(s, n=80):
    s = re.sub(r'[^\w\s-]', '', s or '').strip()
    s = re.sub(r'[\s_-]+', ' ', s)
    return (s[:n] or 'clip').strip()

def main():
    if len(sys.argv) < 2:
        print('usage: clip.py <url> [--model NAME]'); return 1
    url = sys.argv[1]
    model = 'base.en'
    if '--model' in sys.argv:
        model = sys.argv[sys.argv.index('--model') + 1]
    RAW.mkdir(parents=True, exist_ok=True)

    import yt_dlp
    with tempfile.TemporaryDirectory() as td:
        out = str(Path(td) / 'a.%(ext)s')
        opts = {'format': 'bestaudio/best', 'outtmpl': out, 'quiet': True,
                'noprogress': True, 'postprocessors': [{'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3', 'preferredquality': '128'}]}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
        title = info.get('title', 'clip')
        uploader = info.get('uploader') or info.get('channel') or ''
        platform = info.get('extractor_key', 'web')
        audio = next(Path(td).glob('a.*'), None)
        if not audio:
            print('no audio extracted'); return 1
        print(f'transcribing "{title}" ({platform}) with faster-whisper {model}...')
        from faster_whisper import WhisperModel
        wm = WhisperModel(model, device='cpu', compute_type='int8')
        segs, _ = wm.transcribe(str(audio), language='en' if model.endswith('.en') else None)
        transcript = ' '.join(s.text.strip() for s in segs).strip()

    if not transcript:
        print('empty transcript'); return 1
    stem = safe(title)
    fp = RAW / f'{stem}.md'
    fp.write_text(f'''---
title: "{title}"
source: {url}
platform: {platform}
uploader: "{uploader}"
created: {datetime.now().strftime('%Y-%m-%d')}
tags: [{platform.lower()}, video, transcript]
---

# {title}

Source: {url}
{('Uploader: ' + uploader) if uploader else ''}

## Transcript

{transcript}
''', encoding='utf-8')
    print(f'wrote {fp}  ({len(transcript)} chars) -> watcher will ingest')
    return 0

if __name__ == '__main__':
    sys.exit(main())
