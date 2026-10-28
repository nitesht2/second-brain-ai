import re
from pathlib import Path

DEMO = Path(__file__).resolve().parent.parent / "examples" / "demo-vault"
WIKI_FOLDERS = ("sources", "entities", "concepts", "synthesis")


def wiki_notes():
    return [p for f in WIKI_FOLDERS for p in (DEMO / "wiki" / f).glob("*.md")]


def test_every_wikilink_resolves():
    stems = {p.stem for p in (DEMO / "wiki").rglob("*.md")}
    dangling = [
        (p.name, link)
        for p in (DEMO / "wiki").rglob("*.md")
        for link in re.findall(r"\[\[([^\]]+)\]\]", p.read_text(encoding="utf-8"))
        if link not in stems
    ]
    assert dangling == []


def test_index_lists_every_note():
    index = (DEMO / "wiki" / "index.md").read_text(encoding="utf-8")
    notes = wiki_notes()
    assert f"**Total entries: {len(notes)}**" in index
    for p in notes:
        assert f"[[{p.stem}]]" in index


def test_notes_have_frontmatter():
    for p in wiki_notes():
        if p.parent.name == "synthesis":
            continue
        assert p.read_text(encoding="utf-8").startswith("---\nconfidence: ")


def test_pending_inputs_exist():
    pending = [p.name for p in (DEMO / "raw").glob("*.md")]
    assert sorted(pending) == ["evergreen-notes.md", "why-we-forget.md"]
