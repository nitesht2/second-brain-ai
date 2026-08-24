#!/usr/bin/env python3
"""Second Brain -> VoicePost source feeder (NiteshTechAI).

Take ONE vetted vault page and atomize it into several platform pieces
(a thread, a standalone hook, a numbered-takeaways post), each drafted in the
NiteshTechAI voice and dropped into VoicePost for human review.

Two compose engines:

  chat  (default) -- POST /api/chat. VoicePost composes on Nitesh's CLAUDE
        SUBSCRIPTION (its claude-code path on kvm2) and runs its own voice gate
        + regeneration server-side. The feeder is pure HTTP: no API key, no
        model, no local voicegate. This is what "write on my subscription" means.

  openrouter -- the feeder composes locally via OpenRouter (metered) and
        pre-validates with the same voicegate package, then POSTs /api/drafts.
        Kept as an offline / no-VoicePost-LLM fallback. Select with --engine.

Either way nothing posts: every draft waits for a human in the VoicePost Plan
tab. Trust-network on the tailnet means no token is needed from the Mac.

Env (all optional):
    VOICEPOST_URL        default http://100.112.75.103:8081/voicepost
    VOICEPOST_TOKEN      Bearer token; omit on the tailnet (TRUST_NETWORK)
    VOICEPOST_CHANNEL_ID default cmrok8hjl0001nv6o5vhtikt3  (NiteshTechAI / X)
    FEEDER_ENGINE        chat | openrouter   (default chat)
    VOICEPOST_REPO       default ~/Projects/voicepost   (openrouter engine only)
    SECOND_BRAIN_PATH    default ~/SecondBrain
    OPENROUTER_API_KEY / FEEDER_MODEL         (openrouter engine only)
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
NITESHTECH_X = "cmrok8hjl0001nv6o5vhtikt3"  # NiteshTechAI / X (Postiz integration id)
CHANNEL_ID = os.environ.get("VOICEPOST_CHANNEL_ID", NITESHTECH_X)
ENGINE = os.environ.get("FEEDER_ENGINE", "chat").lower()

VOICEPOST_REPO = Path(
    os.environ.get("VOICEPOST_REPO", str(Path.home() / "Projects" / "voicepost"))
).expanduser()
VAULT = Path(
    os.environ.get("SECOND_BRAIN_PATH", str(Path.home() / "SecondBrain"))
).expanduser()

# openrouter engine only
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = os.environ.get("FEEDER_MODEL", "anthropic/claude-sonnet-5")
TEMPERATURE = 0.4
MAX_TOKENS = 2000
MAX_REGENS = 2

HTTP_TIMEOUT = 200  # chat composition can take ~45s per format
CHAT_MESSAGE_CAP = 4000  # /api/chat enforces message <= 4000 chars
SOURCE_BUDGET_LOCAL = 6000  # openrouter engine has no such server cap

# --------------------------------------------------------------------------- #
# ATOMIZE: the formats one source explodes into, and the brief for each.
# The brief IS the /api/chat message; VoicePost supplies the NiteshTechAI voice,
# the anti-slop gate, and regeneration. {title} and {source} are filled in.
# This is the voice/product knob worth tuning: edit a brief to reshape a format,
# add a key to add a format.
# --------------------------------------------------------------------------- #
FORMATS: dict[str, dict[str, str]] = {
    "thread": {
        "template_name": "brain-thread",
        "brief": (
            "Draft an X thread (3 to 5 posts) from this research of mine. Post 1 is "
            "a hard hook that earns the scroll-stop in one line. Each later post "
            "carries one concrete idea from the source, specific over vague. Sound "
            "like a builder sharing what he learned, not a summary.\n\n"
            "Source title: {title}\n\nSource notes:\n{source}"
        ),
    },
    "hook": {
        "template_name": "brain-hook",
        "brief": (
            "Draft a SINGLE standalone X post (no thread) carrying the one sharpest, "
            "most contrarian or useful insight in this research of mine.\n\n"
            "Source title: {title}\n\nSource notes:\n{source}"
        ),
    },
    "listicle": {
        "template_name": "brain-listicle",
        "brief": (
            "Draft a SINGLE X post in a numbered-takeaways format: a one-line setup, "
            "then 3 concrete takeaways from this research as separate numbered lines "
            "(1. 2. 3.). One post, multi-line.\n\n"
            "Source title: {title}\n\nSource notes:\n{source}"
        ),
    },
}
DEFAULT_FORMATS = ["thread", "hook", "listicle"]

# openrouter engine: wrap the brief with voice + a strict output contract.
_OUTPUT_RULE = (
    "Output ONLY the post(s), separated by a line containing exactly:\n"
    "---POST BREAK---\n"
    "No commentary or preamble. No hashtags, em dashes, semicolons, or backticks. "
    "Keep every post under 270 characters. Do not open a post with the word \"I\"."
)

_env_loaded = False


def _load_env_file(path: Path = Path.home() / ".secondbrain.env") -> None:
    """Load KEY=value lines from the brain's dotenv into os.environ (setdefault)."""
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
# VoicePost HTTP helpers
# --------------------------------------------------------------------------- #


def _vp_headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if VOICEPOST_TOKEN:
        headers["Authorization"] = f"Bearer {VOICEPOST_TOKEN}"
    return headers


def _vp_request(path: str, obj: dict | None = None, method: str = "GET") -> dict:
    """Call the VoicePost API and return parsed JSON. obj -> JSON body for POST."""
    data = json.dumps(obj).encode() if obj is not None else None
    req = urllib.request.Request(
        f"{VOICEPOST_URL}{path}", data=data, headers=_vp_headers(), method=method
    )
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{method} {path} -> HTTP {e.code}: {e.read().decode(errors='ignore')}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"VoicePost not reachable at {VOICEPOST_URL}: {e}")


def chat_compose(message: str, channel_id: str) -> dict:
    """Ask VoicePost to compose a draft on the Claude subscription. Returns draft."""
    return _vp_request(
        "/api/chat", {"message": message, "channel_id": channel_id}, method="POST"
    )


def push_draft(thread: list[str], repo_meta: dict, channel_id: str, template_name: str) -> dict:
    """POST a pre-composed thread as a draft (openrouter engine)."""
    return _vp_request(
        "/api/drafts",
        {
            "thread": thread,
            "source": "brain",
            "template_name": template_name,
            "repo_meta": repo_meta,
            "channel_id": channel_id,
        },
        method="POST",
    )


def fetch_voice_rules_md(channel_id: str) -> str:
    """Live voice-rules markdown for a channel, or the bundled default (openrouter)."""
    try:
        body = _vp_request(f"/api/voice-rules?channel_id={channel_id}")
        if body.get("content_md"):
            return body["content_md"]
    except RuntimeError as e:
        print(f"  ! voice-rules fetch failed ({e}); using bundled default", file=sys.stderr)
    _, default_rules_md, _ = _import_voicegate()
    return default_rules_md()


# --------------------------------------------------------------------------- #
# openrouter engine (local compose + voicegate pre-validation)
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
            f"cannot import voicegate from {VOICEPOST_REPO}; set VOICEPOST_REPO ({e})"
        )
    return load_rules, default_rules_md, validate_thread


def _openrouter(prompt: str) -> str:
    """Call OpenRouter (reasoning off) and return the completion text."""
    _load_env_file()
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY not set (env + ~/.secondbrain.env)")
    payload = json.dumps(
        {
            "model": OPENROUTER_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": TEMPERATURE,
            "max_tokens": MAX_TOKENS,
            # Claude 5 models reason by default on OpenRouter and burn the whole
            # budget on it, returning null content. Off for short social copy.
            "reasoning": {"enabled": False},
        }
    ).encode()
    req = urllib.request.Request(
        OPENROUTER_BASE_URL,
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            choice = json.loads(resp.read())["choices"][0]
            content = choice["message"].get("content")
            if not content:
                raise RuntimeError(
                    f"empty completion (finish_reason={choice.get('finish_reason')})"
                )
            return content.strip()
    except urllib.error.URLError as e:
        raise RuntimeError(f"OpenRouter not reachable: {e}")
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"unexpected OpenRouter response: {e}")


def _split_thread(raw: str) -> list[str]:
    return [p.strip() for p in raw.split("---POST BREAK---") if p.strip()]


def _excerpt(text: str, budget: int) -> str:
    """Best `budget` chars of a source. Synthesis pages bury the payoff (Key
    Insight / Actionable Takeaways) at the end, so prefer those sections; fall
    back to the head for other pages."""
    picks: list[str] = []
    for key in ("## Key Insight", "## Actionable Takeaways", "## Contradictions"):
        i = text.find(key)
        if i != -1:
            picks.append(text[i : i + 1600])
    body = "\n\n".join(picks) if picks else text
    return body[:budget].strip()


def _chat_message(fmt: str, title: str, full_text: str) -> str:
    """Build a /api/chat message that fits under CHAT_MESSAGE_CAP."""
    tmpl = FORMATS[fmt]["brief"]
    overhead = len(tmpl.format(title=title, source=""))
    budget = max(0, CHAT_MESSAGE_CAP - overhead - 20)
    return tmpl.format(title=title, source=_excerpt(full_text, budget))


def compose_local(brief: str, rules) -> tuple[list[str], list[str]]:
    """Compose a format via OpenRouter and regen until the gate passes."""
    _, _, validate_thread = _import_voicegate()
    prompt = f"{rules.system_prompt}\n\n---\n\n{brief}\n\n{_OUTPUT_RULE}"
    thread = _split_thread(_openrouter(prompt))
    clean, violations = validate_thread(thread, rules)
    attempt = 0
    while not clean and attempt < MAX_REGENS:
        attempt += 1
        fix = (
            f"{rules.system_prompt}\n\n---\n\nYour previous draft failed the voice "
            f"gate:\n- " + "\n- ".join(violations) + "\n\nRewrite it fixing every "
            f"violation, same ideas and voice.\n\n{brief}\n\n{_OUTPUT_RULE}"
        )
        thread = _split_thread(_openrouter(fix))
        clean, violations = validate_thread(thread, rules)
    return thread, violations


# --------------------------------------------------------------------------- #
# Runner
# --------------------------------------------------------------------------- #


def run(source_path: Path, channel_id: str, formats: list[str], engine: str, dry_run: bool) -> int:
    """Atomize one vault page into `formats` and feed each to VoicePost."""
    if not source_path.exists():
        print(f"source not found: {source_path}", file=sys.stderr)
        return 1
    unknown = [f for f in formats if f not in FORMATS]
    if unknown:
        print(f"unknown format(s): {unknown}. known: {list(FORMATS)}", file=sys.stderr)
        return 1

    title = source_path.stem
    full_text = source_path.read_text(encoding="utf-8", errors="ignore")
    print(f"source: {title}\nengine: {engine}  formats: {', '.join(formats)}\n")

    rules = None
    if engine == "openrouter":
        load_rules, _, _ = _import_voicegate()
        rules = load_rules(fetch_voice_rules_md(channel_id))

    pushed = 0
    for fmt in formats:
        print(f"--- {fmt} ---")
        if engine == "chat":
            message = _chat_message(fmt, title, full_text)
            if dry_run:
                print(f"[dry-run] would POST /api/chat ({len(message)} chars):\n{message[:200]}...\n")
                continue
            draft = chat_compose(message, channel_id)
            thread = draft.get("thread") or draft.get("thread_json") or []
            _preview(thread)
            print(f"-> draft id={draft.get('id')} status={draft.get('status')}\n")
            pushed += 1
        else:  # openrouter
            brief = FORMATS[fmt]["brief"].format(
                title=title, source=_excerpt(full_text, SOURCE_BUDGET_LOCAL)
            )
            thread, violations = compose_local(brief, rules)
            _preview(thread)
            print("gate:", "CLEAN" if not violations else f"flagged {violations}")
            if dry_run:
                print("[dry-run] not pushing.\n")
                continue
            repo_meta = {"vault_ref": str(source_path), "title": title, "format": fmt}
            draft = push_draft(thread, repo_meta, channel_id, FORMATS[fmt]["template_name"])
            print(f"-> draft id={draft.get('id')} status={draft.get('status')}\n")
            pushed += 1

    if not dry_run:
        print(f"pushed {pushed} draft(s). review at {VOICEPOST_URL}/plan")
    return 0


def _preview(thread: list[str]) -> None:
    for i, post in enumerate(thread, 1):
        print(f"  [{i}] {post[:200]}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Atomize a vault page into VoicePost drafts.")
    ap.add_argument("--source", required=True, help="path to a vetted vault .md page")
    ap.add_argument("--channel", default=CHANNEL_ID, help="VoicePost channel id")
    ap.add_argument(
        "--formats",
        default=",".join(DEFAULT_FORMATS),
        help=f"comma list from {list(FORMATS)} (default all)",
    )
    ap.add_argument(
        "--engine", choices=["chat", "openrouter"], default=ENGINE,
        help="chat = compose on your Claude subscription (default); openrouter = local/metered",
    )
    ap.add_argument("--dry-run", action="store_true", help="show what would be sent, do not create drafts")
    args = ap.parse_args()
    formats = [f.strip() for f in args.formats.split(",") if f.strip()]
    return run(Path(args.source).expanduser(), args.channel, formats, args.engine, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
