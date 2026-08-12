---
name: youtube-transcript
description: Fetch YouTube transcripts (single video, or every video on a channel/playlist) into the vault's raw/ drop zone. Use whenever the user pastes a YouTube link, asks to ingest/clip/read a YouTube video or channel, or asks why a YouTube fetch failed. Covers the caption-first path, the yt-dlp+whisper fallback, the bot-wall, and the egress block that stops YouTube from being reachable inside Claude Code web sessions.
---

# YouTube transcripts

## Read this first: YouTube is unreachable from Claude Code web sessions

**Do not spend a turn re-testing this.** In a Claude Code remote/web session the
egress proxy denies youtube.com outright. Verified 2026-08-12:

| Attempt | Result |
| --- | --- |
| `curl https://www.youtube.com/` | `403` — `CONNECT tunnel failed` |
| WebFetch on a watch URL | `EGRESS_BLOCKED` |
| `yt-dlp --list-subs <url>` | `Unable to connect to proxy — Tunnel connection failed: 403 Forbidden` |
| `youtube_transcript_api.fetch(vid)` | same proxy denial |
| Same, with `HTTPS_PROXY` unset | `CERTIFICATE_VERIFY_FAILED` (proxy is the only route out) |
| `youtube.com/feeds/videos.xml` (channel RSS) | blocked |

The blocker is **network policy, not tooling**. yt-dlp being open source is
irrelevant — it is a client, and the connection is refused before the request
leaves the container. Installing a different library will not change this.
`pypi.org` and `github.com` *are* reachable, so installs succeed and then fail at
runtime, which is a misleading signal.

When a user pastes a link in a web session, say so plainly and offer:

1. **Run it where YouTube is reachable** — their Mac (`scripts/brain_clip.py`) or
   the VPS (`deploy/vps/clip.py`). This is the normal path for this repo.
2. **Allowlist the domain** — add `youtube.com` (and `googlevideo.com` for the
   audio-download path) to the environment's allowed domains, then it works
   in-session. See https://code.claude.com/docs/en/claude-code-on-the-web
3. **Paste the transcript text** — fine for a one-off; process it directly.

Everything below applies to runs on the Mac or VPS, not to web sessions.

## Which script to use

All of these end the same way: a markdown file in `~/SecondBrain/raw/`, which the
watcher picks up and the agent ingests. Never write to the vault directly.

| Script | Where | Path |
| --- | --- | --- |
| `deploy/vps/clip_yt.py` | anywhere | Captions only, one video. No download, so it dodges the datacenter bot-wall. Fastest, and the right default for YouTube. |
| `scripts/brain_clip.py` | Mac | Captions first, then yt-dlp audio + `whisper-cli` (Metal GPU). Residential IP, so downloads work. `scp`s the result to the VPS. |
| `deploy/vps/clip.py` | VPS | Captions first, then yt-dlp audio + `faster-whisper` (CPU). Needs `BRAIN_PROXY` (residential) for the download path. |
| `deploy/vps/clip_yt_channel.py` | anywhere | Captions for **every** video on a channel or playlist. Wraps the single-video path. |

## Channels and playlists

A channel is not a video — the single-video scripts reject a channel URL. Use
`clip_yt_channel.py`, which resolves a channel to video IDs two ways:

- **yt-dlp `--flat-playlist`** — full history, needs yt-dlp installed. Preferred.
- **RSS** (`/feeds/videos.xml?channel_id=UC...`) — no dependency, but capped at
  the **latest 15 videos**. Automatic fallback.

```bash
python3 deploy/vps/clip_yt_channel.py https://www.youtube.com/@SomeChannel --limit 25
python3 deploy/vps/clip_yt_channel.py https://www.youtube.com/playlist?list=PL...
```

Already-fetched videos are skipped by ID, so re-running is cheap and incremental
— safe to put on a cron/timer for a channel you follow.

## Failure modes worth recognising

- **`Tunnel connection failed: 403`** — the egress block above. Not fixable from
  inside the session.
- **Captions fetch fails but the video has captions** — usually the datacenter
  bot-wall. YouTube blocks VPS IP ranges. Set `BRAIN_PROXY` to a residential
  proxy, or run from the Mac. This is why `clip_yt.py` exists.
- **`no captions` / empty transcript** — the video genuinely has none (no
  auto-captions on some music, age-gated, or very new uploads). Fall back to the
  audio+whisper path via `brain_clip.py` / `clip.py`.
- **`ModuleNotFoundError: yt_dlp`** — `pip install -r requirements-vps.txt`.

## Conventions to preserve

- Output frontmatter matches the other clippers: `title`, `source`, `platform`,
  `uploader`, `created`, `tags`. Keep it identical so ingest stays uniform.
- Title collisions get an 8-char URL-hash suffix rather than overwriting — see
  `write()` in `scripts/brain_clip.py`.
- The video-ID regex is shared across all four scripts:
  `(?:v=|youtu\.be/|shorts/|embed/)([A-Za-z0-9_-]{11})`
