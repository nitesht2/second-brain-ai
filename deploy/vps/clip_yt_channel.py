#!/usr/bin/env python3
"""YouTube channel/playlist caption fetch: every video -> transcript md in raw/.
Captions only (no download), so it dodges the datacenter bot-wall like clip_yt.py.

Resolves a channel to video IDs via yt-dlp --flat-playlist (full history) and
falls back to the channel RSS feed (latest 15, no dependency). Videos already in
raw/ are skipped by ID, so re-running is incremental — safe on a cron/timer.

Usage: clip_yt_channel.py <channel|playlist url> [--limit N] [--raw DIR]
"""
import argparse, json, os, re, sys, urllib.request
from pathlib import Path
from datetime import datetime
from xml.etree import ElementTree

VAULT = Path.home() / 'SecondBrain'
PROXY = os.environ.get('BRAIN_PROXY', '').strip()
RSS = 'https://www.youtube.com/feeds/videos.xml?'
NS = {'a': 'http://www.w3.org/2005/Atom', 'yt': 'http://www.youtube.com/xml/schemas/2015'}

def safe(s, n=80):
    s = re.sub(r'[^\w\s-]', '', s or '').strip(); return (re.sub(r'[\s_-]+',' ',s)[:n] or 'clip').strip()

def get(url):
    opener = urllib.request.build_opener(
        *([urllib.request.ProxyHandler({'http': PROXY, 'https': PROXY})] if PROXY else []))
    opener.addheaders = [('User-Agent', 'Mozilla/5.0')]
    return opener.open(url, timeout=30).read().decode('utf-8', 'replace')

def feed_url(url):
    """Channel/playlist URL -> RSS feed URL, resolving @handles via the page HTML."""
    if m := re.search(r'[?&]list=([A-Za-z0-9_-]+)', url): return RSS + 'playlist_id=' + m.group(1)
    if m := re.search(r'/channel/(UC[A-Za-z0-9_-]{22})', url): return RSS + 'channel_id=' + m.group(1)
    if m := re.search(r'"channelId":"(UC[A-Za-z0-9_-]{22})"', get(url)): return RSS + 'channel_id=' + m.group(1)
    return None

def via_ytdlp(url, limit):
    """Full channel history. Returns [(vid, title, uploader)] or None if unavailable."""
    try:
        import yt_dlp
    except ImportError:
        return None
    opts = {'extract_flat': 'in_playlist', 'quiet': True, 'noprogress': True, 'skip_download': True}
    if limit: opts['playlistend'] = limit
    if PROXY: opts['proxy'] = PROXY
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        print(f'  yt-dlp listing failed ({e}); falling back to RSS'); return None
    chan = info.get('channel') or info.get('uploader') or ''
    out = []
    for e in info.get('entries') or []:
        # a channel URL yields tabs (Videos/Shorts/Live) whose entries nest one level deeper
        for v in (e.get('entries') or [e]):
            if (vid := v.get('id')) and len(vid) == 11:
                out.append((vid, v.get('title') or f'YouTube {vid}', v.get('uploader') or chan))
    return out or None

def via_rss(url, limit):
    """Latest ~15 videos only — YouTube's feed is capped."""
    if not (fu := feed_url(url)):
        print('  could not resolve a channel/playlist id from that url'); return []
    root = ElementTree.fromstring(get(fu))
    out = []
    for e in root.findall('a:entry', NS):
        vid = (e.findtext('yt:videoId', '', NS) or '').strip()
        if not vid: continue
        title = (e.findtext('a:title', '', NS) or f'YouTube {vid}').strip()
        up = (e.findtext('a:author/a:name', '', NS) or '').strip()
        out.append((vid, title, up))
    print(f'  RSS gives the latest {len(out)} videos only (yt-dlp would give full history)')
    return out[:limit] if limit else out

def write(raw, vid, title, uploader, text):
    url = f'https://www.youtube.com/watch?v={vid}'
    fp = raw / f'{safe(title)}-{vid}.md'   # vid suffix: unique per video, and the skip key
    fp.write_text(f'''---
title: {json.dumps(title)}
source: {url}
platform: YouTube
uploader: {json.dumps(uploader)}
created: {datetime.now().strftime('%Y-%m-%d')}
tags: [youtube, video, transcript]
---

# {title}

Source: {url}

## Transcript

{text}
''', encoding='utf-8')
    return fp

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('url'); ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--raw', default=str(VAULT / 'raw'))
    a = ap.parse_args()

    raw = Path(a.raw); raw.mkdir(parents=True, exist_ok=True)
    vids = via_ytdlp(a.url, a.limit)
    if vids is None: vids = via_rss(a.url, a.limit)
    if not vids: print('no videos found'); return 1
    if a.limit: vids = vids[:a.limit]
    print(f'{len(vids)} video(s) to consider')

    from youtube_transcript_api import YouTubeTranscriptApi
    api = YouTubeTranscriptApi()
    done = skip = fail = 0
    for vid, title, up in vids:
        if next(raw.glob(f'*-{vid}.md'), None):
            skip += 1; continue
        try:
            text = ' '.join(r.text for r in api.fetch(vid)).strip()
        except Exception as e:
            print(f'  {vid} captions failed: {e}'); fail += 1; continue
        if not text:
            print(f'  {vid} empty transcript'); fail += 1; continue
        fp = write(raw, vid, title, up, text)
        print(f'  wrote {fp.name} ({len(text)} chars)'); done += 1
    print(f'done: {done} written, {skip} already present, {fail} failed -> watcher ingests')
    return 0 if done or skip else 2

if __name__ == '__main__':
    sys.exit(main())
