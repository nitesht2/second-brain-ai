#!/usr/bin/env python3
"""harvest_x.py - pull your X/Twitter bookmarks (or likes/timeline) into the
Second Brain via the official X API, using the `xurl` CLI you already auth'd.

Each saved tweet is turned into a vault note:
  - X-native long-form Article  -> article.plain_text written straight to raw/ (xurl is authed; no fetch)
  - external article / blog / PDF / gist -> doc2md.py (trafilatura + LightPanda)
  - external video (YouTube/TikTok/Vimeo/...) -> clip.py (yt-dlp + whisper)
  - X-native video (x.com/.../status/<id>/video/N) -> clip.py IF login cookies present, else logged & skipped
  - pure-text post (--include-posts) -> tweet text written straight to raw/
Quoted tweets, t.co self-refs and pic.* media are dropped. Dedup is tracked in a
seen-file so re-runs only ingest what's new.

PREREQUISITE - reads need OAuth2/OAuth1 *user context* (app-only bearer 403s on bookmarks).
The deployed xurl default already resolves to the authed user; otherwise:
    xurl auth oauth2 --app <app> --scope "bookmark.read like.read tweet.read users.read"

Modes:
    harvest_x.py --backfill              # paginate ALL bookmarks (first import)
    harvest_x.py                         # sync: stop once a page is entirely already-seen
    harvest_x.py --source likes          # bookmarks (default) | likes | timeline
    harvest_x.py --dry-run               # print actions, write/ingest nothing
    harvest_x.py --include-posts         # also capture pure-text tweets (no external link)
    harvest_x.py --max-pages N           # safety cap on pages fetched (quota guard)

Env overrides: SB_DOC2MD, SB_CLIP, SB_RAW, BRAIN_COOKIES.
"""

from __future__ import annotations

import argparse
import fcntl
import ipaddress
import json
import os
import re
import signal
import socket
import subprocess
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

# ── paths / config ─────────────────────────────────────────────────────────
HERE = Path(__file__).resolve().parent


def _resolve_tool(env_var: str, filename: str) -> Path:
    """Locate a sibling ingest tool, working in both the VPS layout
    (clip.py + doc2md.py siblings in /root/SecondBrain/scripts/) and the Mac
    repo layout (clip.py one level up in deploy/vps/). Env var wins."""
    override = os.environ.get(env_var)
    if override:
        return Path(override).expanduser()
    for cand in (HERE / filename, HERE.parent / filename):
        if cand.exists():
            return cand
    return HERE / filename  # sane default for error/log messages


DOC2MD = _resolve_tool("SB_DOC2MD", "doc2md.py")
CLIP = _resolve_tool("SB_CLIP", "clip.py")


def _resolve_python() -> str:
    """doc2md/clip need the vault venv (trafilatura, markitdown, faster-whisper).
    System python3 lacks them, so sys.executable is wrong on the VPS. Prefer the
    <vault>/.venv that the rest of the system uses; fall back to sys.executable
    in the Mac repo where no venv sits beside the tools."""
    override = os.environ.get("SB_PYTHON")
    if override:
        return override
    for base in (DOC2MD.parent.parent, CLIP.parent.parent, HERE.parent):
        cand = base / ".venv" / "bin" / "python"
        if cand.exists():
            return str(cand)
    return sys.executable


TOOL_PYTHON = _resolve_python()
RAW = Path(os.environ.get("SB_RAW", str(Path.home() / "SecondBrain" / "raw"))).expanduser()
COOKIES = Path(os.environ.get("BRAIN_COOKIES", str(Path.home() / ".hermes" / "cookies.txt"))).expanduser()
SEEN_DIR = Path.home() / ".hermes" / "data" / "feeds"
PAGE_SIZE = 100  # X max for bookmarks/likes/tweets

VIDEO_HOSTS = ("youtube.com", "youtu.be", "tiktok.com", "instagram.com",
               "instagr.am", "vimeo.com", "twitch.tv")
X_HOSTS = ("x.com", "twitter.com")
DROP_HOSTS = ("t.co",)  # self-ref shorteners; pic.* handled by prefix

X_ARTICLE_RE = re.compile(r"^https?://(?:www\.)?(?:x|twitter)\.com/i/article/(\d+)", re.I)
X_VIDEO_RE = re.compile(r"^https?://(?:www\.)?(?:x|twitter)\.com/[^/]+/status/(\d+)/video/\d+", re.I)

# source -> (endpoint template, extra query params). {id} filled at runtime.
SOURCES = {
    "bookmarks": ("/2/users/{id}/bookmarks", {}),
    "likes":     ("/2/users/{id}/liked_tweets", {}),
    "timeline":  ("/2/users/{id}/tweets", {"exclude": "retweets,replies"}),
}
TWEET_FIELDS = "entities,note_tweet,created_at,article,text"


# ── seen-file dedup (crash-safe, atomic; mirrors scripts/daily_digest.py) ───
def seen_path(source: str) -> Path:
    return SEEN_DIR / f"x_{source}_seen.json"


def load_seen(source: str) -> dict:
    p = seen_path(source)
    if p.exists():
        try:
            data = json.loads(p.read_text())
            data.setdefault("seen_urls", {})
            data.setdefault("seen_ids", {})
            data.setdefault("pending", {})
            return data
        except (json.JSONDecodeError, ValueError):
            print(f"WARN: {p} unreadable/corrupt; starting fresh", file=sys.stderr)
    return {"seen_urls": {}, "seen_ids": {}, "pending": {}}


def save_seen(source: str, data: dict) -> None:
    p = seen_path(source)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(p)  # atomic same-dir rename


# ── xurl wrapper (retry/backoff for unattended runs) ───────────────────────
def xurl_get(path: str, retries: int = 4) -> dict:
    """Call `xurl <path>`, parse JSON. Retries transient failures (timeout,
    empty body, 429) with bounded exponential backoff. xurl injects auth from
    ~/.xurl and prints raw API JSON to stdout."""
    delay = 5
    for attempt in range(retries + 1):
        try:
            res = subprocess.run(["xurl", path], capture_output=True, text=True, timeout=60)
        except subprocess.TimeoutExpired:
            if attempt == retries:
                raise RuntimeError(f"xurl timed out after {retries + 1} attempts: {path}")
            time.sleep(delay); delay = min(delay * 2, 120); continue

        out = (res.stdout or "").strip()
        if res.returncode != 0:
            transient = "429" in res.stderr or "too many requests" in res.stderr.lower()
            if transient and attempt < retries:
                time.sleep(delay); delay = min(delay * 2, 120); continue
            raise RuntimeError(f"xurl failed ({res.returncode}): {res.stderr.strip()}")
        if not out:
            if attempt < retries:
                time.sleep(delay); delay = min(delay * 2, 120); continue
            raise RuntimeError(f"xurl returned empty body: {path}")
        try:
            data = json.loads(out)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"xurl returned non-JSON: {out[:300]}") from exc

        # A 429 can arrive as rc=0 with an errors array and no data -> retry.
        if "data" not in data and "meta" not in data and data.get("errors"):
            msg = json.dumps(data["errors"])[:200]
            if ("429" in msg or "rate" in msg.lower()) and attempt < retries:
                time.sleep(delay); delay = min(delay * 2, 120); continue
            # Non-rate errors (revoked scope, suspended app, ...) must not read
            # as an empty-but-successful page; surface them as a failed run.
            raise RuntimeError(f"xurl API error: {msg}")
        return data
    raise RuntimeError(f"xurl exhausted retries: {path}")  # unreachable


def my_user_id() -> str:
    data = xurl_get("/2/users/me")
    uid = (data.get("data") or {}).get("id")
    if not uid:
        raise RuntimeError(f"could not resolve user id (auth issue?): {data}")
    return uid


# ── url helpers / classification ───────────────────────────────────────────
def host_of(url: str) -> str:
    # hostname (unlike netloc) is lowercased and strips port/brackets/userinfo
    return (urllib.parse.urlparse(url).hostname or "").removeprefix("www.")


def _host_matches(host: str, domains) -> bool:
    return any(host == d or host.endswith("." + d) for d in domains)


def is_video(url: str) -> bool:
    return _host_matches(host_of(url), VIDEO_HOSTS)


def _entity_urls(tweet: dict) -> list[str]:
    """All expanded URLs from a tweet's standard + long-post (note_tweet) entities."""
    urls: list[str] = []
    blocks = [tweet.get("entities") or {}]
    note = tweet.get("note_tweet") or {}
    if isinstance(note, dict):
        blocks.append(note.get("entities") or {})
    for ent in blocks:
        for u in ent.get("urls", []):
            expanded = u.get("expanded_url") or u.get("url", "")
            if expanded:
                urls.append(expanded)
    return list(dict.fromkeys(urls))  # de-dup, preserve order


def classify_targets(tweet: dict) -> list[tuple[str, str]]:
    """Return [(url, kind)] for ingestable links. kind in {external, xvideo}.
    X-native articles are handled separately via tweet['article']; quoted
    tweets, t.co self-refs and pic.* media are dropped here."""
    out: list[tuple[str, str]] = []
    for url in _entity_urls(tweet):
        if X_ARTICLE_RE.match(url):
            continue  # ingested from tweet['article'], not fetched
        host = host_of(url)
        if _host_matches(host, X_HOSTS):
            if X_VIDEO_RE.match(url):
                out.append((url, "xvideo"))
            # bare /status/<id> (quoted tweet) and /photo/ -> drop
            continue
        if _host_matches(host, DROP_HOSTS) or host.startswith("pic."):
            continue
        out.append((url, "external"))
    return list(dict.fromkeys(out))


def tweet_permalink(tweet: dict) -> str:
    return f"https://x.com/i/web/status/{tweet.get('id', '')}"


def x_article_key(tweet: dict) -> str:
    for url in _entity_urls(tweet):
        m = X_ARTICLE_RE.match(url)
        if m:
            return f"https://x.com/i/article/{m.group(1)}"
    return f"https://x.com/i/article/tw{tweet.get('id', '')}"


# ── SSRF guard ─────────────────────────────────────────────────────────────
def is_safe_public_url(url: str) -> bool | None:
    """Reject non-http(s) and any host resolving to non-global (private/loopback/
    link-local/reserved/metadata) space. Bookmarked URLs are attacker-influenceable;
    this is the only thing standing between a crafted bookmark and a server-side GET
    to 169.254.169.254 or an RFC1918 host. Fails closed. Returns None when the host
    could not be resolved (transient DNS) so the caller can retry instead of drop."""
    parts = urllib.parse.urlparse(url)
    if parts.scheme not in ("http", "https"):
        return False
    host = parts.hostname or ""  # strips port + IPv6 brackets
    if not host:
        return False
    try:
        port = parts.port  # raises ValueError on a malformed port
    except ValueError:
        return False
    try:
        infos = socket.getaddrinfo(host, port or (443 if parts.scheme == "https" else 80))
    except OSError:
        return None  # could not resolve; likely transient, not proven unsafe
    if not infos:
        return False
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            return False
        if not ip.is_global:  # private/loopback/link-local/reserved/CGNAT/...
            return False
    return True


# ── raw-note writers (for content already in hand, no fetch) ───────────────
def _slug(title: str) -> str:
    s = re.sub(r"[\s_-]+", "-", re.sub(r"[^\w\s-]", "", title).strip().lower())[:60]
    return s or "x-note"


def _write_raw_note(title: str, url: str, body: str, *, tags: str, created: str, uid: str) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    fp = RAW / f"{_slug(title)}-{uid}.md"  # full id suffix avoids collisions
    fp.write_text(
        # json.dumps keeps the title a valid YAML double-quoted scalar
        f'---\ntitle: {json.dumps(title)}\nsource: {url}\nplatform: X\n'
        f'created: {created}\ntags: [{tags}]\n---\n\n# {title}\n\nSource: {url}\n\n{body}\n',
        encoding="utf-8",
    )


def ingest_x_native_article(tweet: dict, key: str, dry_run: bool) -> bool:
    art = tweet.get("article") or {}
    body = (art.get("plain_text") or art.get("preview_text") or "").strip()
    if not body:
        return False
    title = (art.get("title") or f"X Article {tweet.get('id', '')}")[:60]
    if dry_run:
        print(f"  DRY x-article: {title!r} ({len(body)} chars)")
        return True
    _write_raw_note(title, key, body, tags="x, article",
                    created=tweet.get("created_at", "")[:10], uid=tweet.get("id", ""))
    print(f"  ok x-article -> {title!r}")
    return True


def write_post_note(tweet: dict, dry_run: bool) -> bool:
    body = ((tweet.get("note_tweet") or {}).get("text") or tweet.get("text") or "").strip()
    if not body:
        return False
    url = tweet_permalink(tweet)
    if dry_run:
        print(f"  DRY x-post: {url}")
        return True
    title = (body.splitlines()[0] if body.splitlines() else "x-post")[:60]
    _write_raw_note(title, url, body, tags="x, post",
                    created=tweet.get("created_at", "")[:10], uid=tweet.get("id", ""))
    print(f"  ok x-post -> {url}")
    return True


# ── ingest routing (fetch via doc2md/clip) ─────────────────────────────────
def ingest_url(url: str, kind: str, dry_run: bool) -> bool:
    """Route a fetchable URL to the right extractor. Returns True if the URL is
    handled (success OR a deliberate skip we should not retry); False only on a
    transient failure worth retrying next run."""
    safe = is_safe_public_url(url)
    if safe is None:
        print(f"  SKIP[resolve] host did not resolve (transient?): {url}")
        return False  # retry next run; DNS blips must not drop bookmarks
    if not safe:
        print(f"  SKIP unsafe/non-public url: {url}")
        return True  # never retry an attacker-chosen internal target

    if kind == "xvideo":
        if not COOKIES.exists():
            print(f"  SKIP x-native video (no cookies at {COOKIES}): {url}")
            return False  # retry once cookies appear; recheck is a free stat()
        tool = CLIP
    else:
        tool = CLIP if is_video(url) else DOC2MD

    if dry_run:
        print(f"  DRY would ingest via {tool.name}: {url}")
        return True

    timeout = 1800 if tool is CLIP else 600  # clip (CPU whisper) is the slow path
    try:
        res = subprocess.run([TOOL_PYTHON, str(tool), url],
                             capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        print(f"  FAIL[timeout {timeout}s] {tool.name}: {url}")
        return False  # transient -> retry next run
    except OSError as exc:
        print(f"  FAIL[spawn] {tool.name}: {url}  {exc}")
        return False  # broken path/interpreter is fixable; don't eat the backlog
    tag = "ok" if res.returncode == 0 else f"FAIL[{res.returncode}]"
    line = (res.stdout or res.stderr).strip().splitlines()
    print(f"  {tag} {tool.name}: {url}  {line[-1] if line else ''}")
    ok = res.returncode == 0
    # X-native videos that fail are usually silent/deleted (permanent failure);
    # mark them seen so the twice-daily timer doesn't re-download + re-fail forever.
    if kind == "xvideo" and not ok:
        return True
    return ok


# ── pagination / main loop ─────────────────────────────────────────────────
def fetch_page(endpoint: str, base_params: dict, token: str | None) -> dict:
    params = {"max_results": PAGE_SIZE, "tweet.fields": TWEET_FIELDS, **base_params}
    if token:
        params["pagination_token"] = token
    query = urllib.parse.urlencode(params, safe=",")
    return xurl_get(f"{endpoint}?{query}")


def _acquire_lock(source: str):
    """Single-instance guard per source so a manual backfill and the timer's
    sync run can't run concurrently and stomp the same seen-file. Returns the
    held lock handle, or None if another run owns it."""
    SEEN_DIR.mkdir(parents=True, exist_ok=True)
    lf = open(SEEN_DIR / f"x_{source}.lock", "w")
    try:
        fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lf.close()
        return None
    return lf  # released automatically when the process exits


def run(source: str, backfill: bool, dry_run: bool,
        include_posts: bool, max_pages: int | None) -> int:
    lock = _acquire_lock(source)
    if lock is None:
        print(f"another harvest [{source}] is already running; exiting")
        return 0
    endpoint = SOURCES[source][0].format(id=my_user_id())
    base_params = SOURCES[source][1]
    seen = load_seen(source)
    seen_urls, seen_ids = seen["seen_urls"], seen["seen_ids"]
    pending = seen["pending"]
    token, new_count, pages = None, 0, 0

    try:
        # Re-attempt URLs stranded by transient failures in earlier runs. The
        # sync stop rule can't reach them: seen_ids records EVERY tweet, so
        # pagination stops at page 1 long before their tweets come around again.
        if pending:
            print(f"retrying {len(pending)} pending url(s) from earlier runs")
        for url, info in list(pending.items()):
            if ingest_url(url, info.get("kind", "external"), dry_run):
                seen_urls[url] = info.get("created", "")
                del pending[url]

        while True:
            page = fetch_page(endpoint, base_params, token)
            tweets = page.get("data", []) or []
            pages += 1
            page_new = 0
            page_all_seen = bool(tweets)  # computed against PRIOR-run ids below

            for tw in tweets:
                tid = str(tw.get("id", ""))
                if tid and tid not in seen_ids:
                    page_all_seen = False

                handled_external = False

                # 1. X-native long-form Article (body already in hand via xurl)
                if tw.get("article"):
                    akey = x_article_key(tw)
                    if akey not in seen_urls:
                        ok = ingest_x_native_article(tw, akey, dry_run)
                        page_new += 1; new_count += 1
                        if ok:
                            seen_urls[akey] = tw.get("created_at", "")
                    handled_external = True

                # 2. external links + recoverable X-native video
                for url, kind in classify_targets(tw):
                    handled_external = True
                    if url in seen_urls:
                        continue
                    ok = ingest_url(url, kind, dry_run)
                    page_new += 1; new_count += 1
                    if ok:
                        seen_urls[url] = tw.get("created_at", "")
                        pending.pop(url, None)
                    else:
                        # transient failure: queue for retry at next run's start
                        pending[url] = {"kind": kind, "created": tw.get("created_at", "")}

                # 3. pure-text post (only if nothing else to ingest)
                if include_posts and not handled_external:
                    pkey = tweet_permalink(tw)
                    if pkey not in seen_urls:
                        ok = write_post_note(tw, dry_run)
                        page_new += 1; new_count += 1
                        if ok:
                            seen_urls[pkey] = tw.get("created_at", "")

                if tid:
                    seen_ids[tid] = tw.get("created_at", "")  # record EVERY tweet

            print(f"page {pages}: {len(tweets)} tweets, {page_new} new")
            if not dry_run:
                save_seen(source, seen)  # per-page checkpoint

            if not backfill and page_all_seen:
                break
            if max_pages and pages >= max_pages:
                print(f"reached --max-pages {max_pages}; stopping")
                break
            token = (page.get("meta") or {}).get("next_token")
            if not token:
                break
    finally:
        if not dry_run:
            save_seen(source, seen)  # flush on any exit (incl. Ctrl-C / mid-page raise)

    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"done [{source}] {stamp}: {new_count} new across {pages} page(s); "
          f"{len(seen_urls)} urls / {len(seen_ids)} tweets tracked; {len(pending)} pending")
    return 0


def main() -> int:
    # systemd's TimeoutStartSec kill arrives as SIGTERM; convert it to SystemExit
    # so run()'s finally-block save_seen still flushes in-page progress.
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    ap = argparse.ArgumentParser(description="Harvest X bookmarks/likes/timeline into the Second Brain.")
    ap.add_argument("--source", choices=list(SOURCES), default="bookmarks")
    ap.add_argument("--backfill", action="store_true", help="paginate everything (first import)")
    ap.add_argument("--dry-run", action="store_true", help="print actions, write/ingest nothing")
    ap.add_argument("--include-posts", action="store_true",
                    help="also capture pure-text tweets (no external link)")
    ap.add_argument("--max-pages", type=int, default=None, help="safety cap on pages fetched")
    args = ap.parse_args()
    try:
        return run(args.source, args.backfill, args.dry_run, args.include_posts, args.max_pages)
    except Exception as exc:  # noqa: BLE001 - top-level guard for clean cron logs
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
