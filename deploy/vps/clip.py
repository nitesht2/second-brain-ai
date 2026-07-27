#!/usr/bin/env python3
"""VPS universal clipper: URL -> transcript markdown in raw/ (auto-ingested).
Uses a residential proxy (env BRAIN_PROXY) so YouTube/TikTok/etc. work from the VPS.
yt-dlp downloads bestaudio -> faster-whisper transcribes. YouTube also tries captions first.
Usage: clip.py <url> [--model base.en|small]
"""
import hashlib, json, os, re, sys, tempfile
from pathlib import Path
from datetime import datetime

VAULT = Path.home() / 'SecondBrain'; RAW = VAULT / 'raw'
PROXY = os.environ.get('BRAIN_PROXY', '').strip()
# Netscape cookies.txt for login-walled sites (Instagram, etc.). Export from a
# logged-in (ideally burner) account. Default path; override with BRAIN_COOKIES.
COOKIES = os.environ.get('BRAIN_COOKIES', str(Path.home() / '.hermes' / 'cookies.txt'))

def safe(s, n=80):
    s = re.sub(r'[^\w\s-]', '', s or '').strip(); return (re.sub(r'[\s_-]+',' ',s)[:n] or 'clip').strip()
def yt_id(u):
    m = re.search(r'(?:v=|youtu\.be/|shorts/|embed/)([A-Za-z0-9_-]{11})', u); return m.group(1) if m else None
def write(title, url, platform, text, uploader='', caption=''):
    RAW.mkdir(parents=True, exist_ok=True); fp = RAW / f'{safe(title)}.md'
    if fp.exists():  # same normalized title, different video: suffix with url hash instead of overwriting
        fp = RAW / f'{safe(title)}-{hashlib.sha256(url.encode()).hexdigest()[:8]}.md'
    cap_section = f'## Caption\n\n{caption}\n\n' if caption else ''
    tr_section = f'## Transcript\n\n{text}\n' if text else ''
    fp.write_text(f'''---
title: {json.dumps(title)}
source: {url}
platform: {platform}
uploader: {json.dumps(uploader)}
created: {datetime.now().strftime('%Y-%m-%d')}
tags: [{platform.lower()}, clip]
---

# {title}

Source: {url}

{cap_section}{tr_section}''', encoding='utf-8')
    print(f'wrote {fp.name} (caption {len(caption)}c, transcript {len(text)}c) -> watcher ingests'); return fp

def main():
    if len(sys.argv) < 2: print('usage: clip.py <url> [--model NAME]'); return 1
    url = sys.argv[1]; model = 'base.en'
    if '--model' in sys.argv:
        mi = sys.argv.index('--model')+1
        if mi < len(sys.argv): model = sys.argv[mi]  # bare trailing --model keeps default
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
        opts = {'format':'bestaudio/best','outtmpl':out,'quiet':True,'noprogress':True,'noplaylist':True,
                'postprocessors':[{'key':'FFmpegExtractAudio','preferredcodec':'mp3','preferredquality':'128'}]}
        if PROXY: opts['proxy'] = PROXY
        if os.path.exists(COOKIES): opts['cookiefile'] = COOKIES  # IG/login-walled sites
        try:
            with yt_dlp.YoutubeDL(opts) as ydl: info = ydl.extract_info(url, download=True)
        except Exception as e:
            print(f'yt-dlp failed: {e}'); return 1
        title = info.get('title','clip'); platform = info.get('extractor_key','web')
        uploader = info.get('uploader') or info.get('channel') or ''
        caption = (info.get('description') or '').strip()   # IG/post caption text
        audio = next(Path(td).glob('a.*'), None)
        text = ''
        if audio:
            print(f'transcribing "{title}" ({platform}) faster-whisper {model}...')
            from faster_whisper import WhisperModel
            wm = WhisperModel(model, device='cpu', compute_type='int8')
            segs,_ = wm.transcribe(str(audio), language='en' if model.endswith('.en') else None)
            text = ' '.join(s.text.strip() for s in segs).strip()
    if not text and not caption:
        print(f'no audio and no caption (login-walled? add cookies at {COOKIES})'); return 1
    write(title, url, platform, text, uploader, caption); return 0
if __name__ == '__main__': sys.exit(main())
