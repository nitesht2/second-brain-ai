#!/usr/bin/env python3
"""
Daily Knowledge Digest — Data Collector
Collects structured data from APIs and feeds.
Outputs to ~/SecondBrain/raw/generated/<date>/ for agent processing.
Uses curl-like HTTP requests, NOT browser — avoids bot detection.
"""

import json, os, re, subprocess, sys, datetime, urllib.request, urllib.error
from pathlib import Path

CACHE = Path.home() / ".hermes" / "data" / "feeds"
SEEN_FILE = CACHE / "seen.json"
OUTPUT_DIR = Path.home() / "SecondBrain" / "raw" / "generated"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"

def load_seen():
    if SEEN_FILE.exists():
        return json.loads(SEEN_FILE.read_text())
    return {"seen_urls": {}}

def save_seen(data):
    SEEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    SEEN_FILE.write_text(json.dumps(data, indent=2))

def is_seen(url, data):
    return url in data.get("seen_urls", {})

def mark_seen(url, title, data):
    data.setdefault("seen_urls", {})[url] = title

def fetch(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT}, method="GET")
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        return None

# ── GitHub Trending (via API) ──────────────────────────────────────────
def get_github_trending():
    """Search GitHub API for trending AI/automation repos"""
    items = []
    queries = [
        "topic:ai-agents sort:stars",
        "topic:automation sort:stars",
        "topic:data-engineering sort:stars",
        "topic:python sort:stars-desc"
    ]
    for q in queries:
        url = f"https://api.github.com/search/repositories?q={urllib.parse.quote(q)}&per_page=5&sort=stars"
        try:
            data = fetch(url)
            if data:
                parsed = json.loads(data)
                for repo in parsed.get("items", [])[:3]:
                    items.append({
                        "name": repo["full_name"],
                        "url": repo["html_url"],
                        "desc": repo.get("description", "")[:200],
                        "stars": repo.get("stargazers_count", 0)
                    })
        except:
            pass
    # Deduplicate by url
    seen = set()
    unique = []
    for item in items:
        if item["url"] not in seen:
            seen.add(item["url"])
            unique.append(item)
    return unique[:5]

# ── HN Front Page (via Firebase API) ───────────────────────────────────
def get_hn_stories():
    """Get top HN stories via Firebase API"""
    items = []
    try:
        top_ids = json.loads(fetch("https://hacker-news.firebaseio.com/v0/topstories.json") or "[]")
        for story_id in top_ids[:30]:
            story = fetch(f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json")
            if story:
                s = json.loads(story)
                title = s.get("title", "")
                url = s.get("url", f"https://news.ycombinator.com/item?id={story_id}")
                # Filter for AI/tech relevant
                keywords = ["ai", "agent", "python", "automation", "code", "model", "llm",
                           "gpt", "claude", "deepseek", "openai", "anthropic", "robot",
                           "programming", "data", "neural", "machine learning"]
                if any(k in title.lower() for k in keywords):
                    items.append({
                        "title": title,
                        "url": url,
                        "score": s.get("score", 0)
                    })
                    if len(items) >= 5:
                        break
    except:
        pass
    return items

# ── OpenRouter Models (API) ────────────────────────────────────────────
def get_openrouter_models():
    """Check OpenRouter for new models/changes"""
    try:
        data = fetch("https://openrouter.ai/api/v1/models")
        if data:
            models = json.loads(data).get("data", [])
            # Get new/updated models
            new_models = []
            for m in models:
                name = m.get("id", "")
                pricing = m.get("pricing", {})
                new_models.append({
                    "name": name,
                    "input_price": pricing.get("prompt", "N/A"),
                    "output_price": pricing.get("completion", "N/A"),
                    "url": f"https://openrouter.ai/{name}"
                })
            return new_models[:5]
    except:
        pass
    return []

def main():
    seen = load_seen()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.date.today().isoformat()
    digest = []
    
    # 1. OpenRouter new models
    models = get_openrouter_models()
    if models:
        digest.append("## AI Model Changes")
        for m in models:
            if not is_seen(m["url"], seen):
                digest.append(f"- {m['name']} — input: ${m['input_price']}/M, output: ${m['output_price']}/M")
                mark_seen(m["url"], m["name"], seen)
    
    # 2. GitHub trending
    repos = get_github_trending()
    if repos:
        digest.append("\n## GitHub AI Repos")
        for r in repos:
            if not is_seen(r["url"], seen):
                digest.append(f"- [{r['name']}]({r['url']}) — {r['desc'][:150]} ({r['stars']} ★)")
                mark_seen(r["url"], r["name"], seen)
    
    # 3. HN stories
    stories = get_hn_stories()
    if stories:
        digest.append("\n## HN AI Stories")
        for s in stories:
            if not is_seen(s["url"], seen):
                digest.append(f"- [{s['title']}]({s['url']}) — {s['score']} points")
                mark_seen(s["url"], s["title"], seen)
    
    if not digest:
        digest.append("Nothing notable today across all sources.")
    
    content = f"# Daily Digest: {today}\n\n" + "\n".join(digest)
    output_file = OUTPUT_DIR / f"daily-digest-{today}.md"
    output_file.write_text(content)
    save_seen(seen)
    print(f"✓ Written: {output_file}")
    print(f"  Items: {len(digest)-1} (deduplicated)")
    print(f"  Seen DB: {len(seen['seen_urls'])} total tracked")

if __name__ == "__main__":
    main()
