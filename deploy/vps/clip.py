#!/usr/bin/env python3
"""VPS universal clipper: URL -> transcript markdown in raw/ (auto-ingested).
Uses a residential proxy (env BRAIN_PROXY) so YouTube/TikTok/etc. work from the VPS.
yt-dlp downloads bestaudio -> faster-whisper transcribes. YouTube also tries captions first.
Usage: clip.py <url> [--model base.en|small]
"""
import os, re, sys, tempfile
from pathlib import Path
from datetime import datetime

VAULT = Path.home() / 'SecondBrain'; RAW = VAULT / 'raw'
PROXY = os.environ.get('BRAIN_PROXY', '').strip()

def safe(s, n=80):
    s = re.sub(r'[^\w\s-]', '', s or '').strip(); return (re.sub(r'[\s_-]+',' ',s)[:n] or 'clip').strip()
def yt_id(u):
    m = re.search(r'(?:v=|youtu\.be/|shorts/|embed/)([A-Za-z0-9_-]{11})', u); return m.group(1) if m else None
def write(title, url, platform, text, uploader=''):
    RAW.mkdir(parents=True, exist_ok=True); fp = RAW / f'{safe(title)}.md'
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
''', encoding='utf-8')
    print(f'wrote {fp.name} ({len(text)} chars) -> watcher ingests'); return fp

def main():
    if len(sys.argv) < 2: print('usage: clip.py <url> [--model NAME]'); return 1
    url = sys.argv[1]; model = sys.argv[sys.argv.index('--model')+1] if '--model' in sys.argv else 'base.en'
    if not PROXY: print('WARN: BRAIN_PROXY not set — YouTube/TikTok likely blocked from datacenter IP')
    vid = yt_id(url)
    if vid:
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            api = YouTubeTranscriptApi()
            if PROXY:
                from youtube_transcript_api.proxies import GenericProxyConfig
                api = YouTubeTranscriptApi(proxy_config=GenericProxyConfig(http_url=PROXY, https_url=PROXY))
            rows = api.fetch(vid)
            text = ' '.join(r.text for r in rows).strip()
            if text: write(f'YouTube {vid}', url, 'YouTube', text); return 0
        except Exception as e:
            print(f'captions failed ({e}); trying yt-dlp+whisper')
    import yt_dlp
    with tempfile.TemporaryDirectory() as td:
        out = str(Path(td)/'a.%(ext)s')
        opts = {'format':'bestaudio/best','outtmpl':out,'quiet':True,'noprogress':True,
                'postprocessors':[{'key':'FFmpegExtractAudio','preferredcodec':'mp3','preferredquality':'128'}]}
        if PROXY: opts['proxy'] = PROXY
        try:
            with yt_dlp.YoutubeDL(opts) as ydl: info = ydl.extract_info(url, download=True)
        except Exception as e:
            print(f'yt-dlp failed: {e}'); return 1
        title = info.get('title','clip'); platform = info.get('extractor_key','web')
        uploader = info.get('uploader') or info.get('channel') or ''
        audio = next(Path(td).glob('a.*'), None)
        if not audio: print('no audio'); return 1
        print(f'transcribing "{title}" ({platform}) faster-whisper {model}...')
        from faster_whisper import WhisperModel
        wm = WhisperModel(model, device='cpu', compute_type='int8')
        segs,_ = wm.transcribe(str(audio), language='en' if model.endswith('.en') else None)
        text = ' '.join(s.text.strip() for s in segs).strip()
    if not text: print('empty transcript'); return 1
    write(title, url, platform, text, uploader); return 0
if __name__ == '__main__': sys.exit(main())
