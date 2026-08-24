#!/usr/bin/env python3
"""Second Brain -> VoicePost source feeder (Phase 1: NiteshTechAI on X).

Pipeline:
    vetted vault page  ->  compose NiteshTechAI X thread  ->  pre-validate with
    voicegate (the same gate VoicePost enforces)  ->  POST /api/drafts

VoicePost then handles the gate, human review/approve, scheduling, and posting
to X via Postiz. This feeder only selects, composes, pre-validates, and pushes.
Nothing here posts anything; a draft always waits for a human in the VoicePost
Plan tab.

Design notes:
  - Voice rules are pulled LIVE from VoicePost (GET /api/voice-rules) so the
    feeder composes and validates against the exact rules the server enforces.
  - The LLM call mirrors the brain's OpenRouter path (stdlib only) instead of
    importing auto_ingest.py, to avoid that module's heavy deps.
  - voicegate is imported from the VoicePost repo by path (it is pure stdlib).

Env (all optional, sane defaults):
    VOICEPOST_URL        default http://100.112.75.103:8081/voicepost
    VOICEPOST_TOKEN      Bearer service token; omit when on the tailnet
                         (VoicePost runs TRUST_NETWORK, so tailnet == credential)
    VOICEPOST_CHANNEL_ID default cmrok8hjl0001nv6o5vhtikt3  (NiteshTechAI / X)
    VOICEPOST_REPO       default ~/Projects/voicepost  (to import voicegate)
    SECOND_BRAIN_PATH    default ~/SecondBrain
    OPENROUTER_API_KEY / OPENROUTER_MODEL / SECOND_BRAIN_PROVIDER
                         read from env, falling back to ~/.secondbrain.env
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #

VOICEPOST_URL = os.environ.get(
    "VOICEPOST_URL", "http://100.112.75.103:8081/voicepost"
).rstrip("/")
VOICEPOST_TOKEN = os.environ.get("VOICEPOST_TOKEN", "")
# NiteshTechAI / X channel (Postiz integration id).
NITESHTECH_X = "cmrok8hjl0001nv6o5vhtikt3"
CHANNEL_ID = os.environ.get("VOICEPOST_CHANNEL_ID", NITESHTECH_X)

VOICEPOST_REPO = Path(
    os.environ.get("VOICEPOST_REPO", str(Path.home() / "Projects" / "voicepost"))
).expanduser()
VAULT = Path(
    os.environ.get("SECOND_BRAIN_PATH", str(Path.home() / "SecondBrain"))
).expanduser()

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
# Social copy quality matters; default to a current, capable model. Overridable
# via the FEEDER_MODEL env (kept separate from the brain's OPENROUTER_MODEL so
# fixing one does not silently change the other).
OPENROUTER_MODEL = os.environ.get("FEEDER_MODEL", "anthropic/claude-sonnet-5")
TEMPERATURE = 0.4  # a touch of variety for social copy; brain uses 0.2 for structure
MAX_TOKENS = 2000
MAX_REGENS = 2  # regen attempts when the voice gate flags a draft

# --------------------------------------------------------------------------- #
# THE ONE PIECE OF VOICE/PRODUCT JUDGEMENT WORTH TUNING.
# How a vetted vault page becomes a NiteshTechAI X thread. Everything else is
# plumbing. Edit this to change what the drafts feel like. {system_prompt},
# {title}, and {source} are filled in at compose time.
# --------------------------------------------------------------------------- #
COMPOSE_INSTRUCTION = """{system_prompt}

---

You are turning ONE piece of Nitesh's own vetted research into an X thread in
his voice (rules above).

Source title: {title}

Source notes:
{source}

Write an X/Twitter thread of 3 to 5 posts:
  - Post 1 is a hard hook. No throat-clearing. Earn the scroll-stop in one line.
  - Each later post carries one concrete idea from the source. Specific over vague.
  - Keep every post under 270 characters.
  - No hashtags. No em dashes. No semicolons. No backticks. Do not open a post
    with the word "I". Plain text only.
  - Sound like a builder sharing what he learned, not a summary of an article.

Output ONLY the posts, separated by a line containing exactly:
---POST BREAK---
No numbering, no commentary, no preamble."""

_env_loaded = False


def _load_env_file(path: Path = Path.home() / ".secondbrain.env") -> None:
    """Load KEY=value lines from the brain's dotenv into os.environ (setdefault).

    Mirrors auto_ingest's loader so the feeder runs standalone (cron/launchd do
    not source shell rc). Existing env wins.
    """
    global _env_loaded
    if _env_loaded or not path.exists():
        _env_loaded = True
        return
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))
    _env_loaded = True


# --------------------------------------------------------------------------- #
# voicegate (imported from the VoicePost repo; pure stdlib, no install needed)
# --------------------------------------------------------------------------- #


def _import_voicegate():
    """Return (load_rules, default_rules_md, validate_thread) from voicegate."""
    if str(VOICEPOST_REPO) not in sys.path:
        sys.path.insert(0, str(VOICEPOST_REPO))
    try:
        from voicegate.rules import default_rules_md, load_rules
        from voicegate.validator import validate_thread
    except ImportError as e:
        raise RuntimeError(
            f"cannot import voicegate from {VOICEPOST_REPO}. "
            f"Set VOICEPOST_REPO to the voicepost checkout. ({e})"
        )
    return load_rules, default_rules_md, validate_thread


# --------------------------------------------------------------------------- #
# LLM (mirrors the brain's OpenRouter path, stdlib only)
# --------------------------------------------------------------------------- #


def _openrouter(prompt: str) -> str:
    """Call OpenRouter and return the completion text."""
    _load_env_file()
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY not set (checked env + ~/.secondbrain.env)")
    payload = json.dumps(
        {
            "model": OPENROUTER_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": TEMPERATURE,
            "max_tokens": MAX_TOKENS,
            # Short social copy does not need extended thinking. Claude 5 models
            # run reasoning by default on OpenRouter and will spend the whole
            # token budget on it, returning null content. Turn it off.
            "reasoning": {"enabled": False},
        }
    ).encode()
    req = urllib.request.Request(
        OPENROUTER_BASE_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = json.loads(resp.read())
            choice = body["choices"][0]
            content = choice["message"].get("content")
            if not content:
                raise RuntimeError(
                    f"empty completion (finish_reason={choice.get('finish_reason')}); "
                    "raise MAX_TOKENS or check the model"
                )
            return content.strip()
    except urllib.error.URLError as e:
        raise RuntimeError(f"OpenRouter not reachable: {e}")
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"unexpected OpenRouter response: {e}")


# --------------------------------------------------------------------------- #
# VoicePost API
# --------------------------------------------------------------------------- #


def _vp_headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if VOICEPOST_TOKEN:
        headers["Authorization"] = f"Bearer {VOICEPOST_TOKEN}"
    return headers


def fetch_voice_rules_md(channel_id: str) -> str:
    """Return the live voice-rules markdown for a channel, or the bundled default.

    Falls back to voicegate.default_rules_md() if VoicePost is unreachable so the
    feeder still validates against something sane.
    """
    url = f"{VOICEPOST_URL}/api/voice-rules?channel_id={channel_id}"
    req = urllib.request.Request(url, headers=_vp_headers(), method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read())
            md = body.get("content_md", "")
            if md:
                return md
    except (urllib.error.URLError, json.JSONDecodeError, KeyError) as e:
        print(f"  ! voice-rules fetch failed ({e}); using bundled default", file=sys.stderr)
    _, default_rules_md, _ = _import_voicegate()
    return default_rules_md()


def push_draft(thread: list[str], repo_meta: dict, channel_id: str) -> dict:
    """POST one thread to VoicePost as a draft. Returns the response JSON."""
    payload = json.dumps(
        {
            "thread": thread,
            "source": "brain",
            "template_name": "brain-synthesis",
            "repo_meta": repo_meta,
            "channel_id": channel_id,
        }
    ).encode()
    req = urllib.request.Request(
        f"{VOICEPOST_URL}/api/drafts", data=payload, headers=_vp_headers(), method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="ignore")
        raise RuntimeError(f"push failed HTTP {e.code}: {detail}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"VoicePost not reachable: {e}")


# --------------------------------------------------------------------------- #
# Compose + validate
# --------------------------------------------------------------------------- #


def _split_thread(raw: str) -> list[str]:
    """Split model output on the POST BREAK delimiter into clean posts."""
    parts = [p.strip() for p in raw.split("---POST BREAK---")]
    return [p for p in parts if p]


def compose_thread(title: str, source: str, system_prompt: str) -> list[str]:
    """Compose one NiteshTechAI X thread from a vetted source."""
    prompt = COMPOSE_INSTRUCTION.format(
        system_prompt=system_prompt, title=title, source=source[:6000]
    )
    return _split_thread(_openrouter(prompt))


def compose_validated(title: str, source: str, rules_md: str) -> tuple[list[str], list[str]]:
    """Compose and regenerate until the voice gate passes or attempts run out.

    Returns (thread, remaining_violations). Empty violations means the thread is
    gate-clean and will land in VoicePost as `validated`.
    """
    load_rules, _, validate_thread = _import_voicegate()
    rules = load_rules(rules_md)
    system_prompt = rules.system_prompt

    thread = compose_thread(title, source, system_prompt)
    clean, violations = validate_thread(thread, rules)
    attempt = 0
    while not clean and attempt < MAX_REGENS:
        attempt += 1
        fix = (
            f"{system_prompt}\n\n---\n\nYour previous draft failed the voice gate "
            f"with these violations:\n- " + "\n- ".join(violations) + "\n\n"
            "Rewrite the thread fixing every violation. Keep the same ideas and "
            "voice.\n\nSource title: " + title + "\n\nSource notes:\n" + source[:6000]
            + "\n\nOutput ONLY the posts separated by a line containing exactly:\n"
            "---POST BREAK---"
        )
        thread = _split_thread(_openrouter(fix))
        clean, violations = validate_thread(thread, rules)
    return thread, violations


# --------------------------------------------------------------------------- #
# Runner
# --------------------------------------------------------------------------- #


def run(source_path: Path, channel_id: str, dry_run: bool) -> int:
    """Compose one draft from a vault page and push it (unless dry-run)."""
    if not source_path.exists():
        print(f"source not found: {source_path}", file=sys.stderr)
        return 1

    title = source_path.stem
    source_text = source_path.read_text(encoding="utf-8", errors="ignore")
    print(f"source: {title}")

    rules_md = fetch_voice_rules_md(channel_id)
    thread, violations = compose_validated(title, source_text, rules_md)

    print(f"\ncomposed {len(thread)} post(s):")
    for i, post in enumerate(thread, 1):
        print(f"  [{i}] {post}")
    if violations:
        print("\ngate still flags (VoicePost will mark this `flagged` for a human fix):")
        for v in violations:
            print(f"  ! {v}")
    else:
        print("\ngate: CLEAN")

    if dry_run:
        print("\n[dry-run] not pushing.")
        return 0

    repo_meta = {"vault_ref": str(source_path), "title": title, "kind": "synthesis"}
    resp = push_draft(thread, repo_meta, channel_id)
    print(
        f"\npushed -> draft id={resp.get('id')} status={resp.get('status')}\n"
        f"review at {VOICEPOST_URL}/plan"
    )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Feed a vault page into VoicePost as a draft.")
    ap.add_argument("--source", required=True, help="path to a vetted vault .md page")
    ap.add_argument("--channel", default=CHANNEL_ID, help="VoicePost channel id")
    ap.add_argument("--dry-run", action="store_true", help="compose + validate, do not push")
    args = ap.parse_args()
    return run(Path(args.source).expanduser(), args.channel, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
