import os
import time
from pathlib import Path

import pytest

import auto_ingest as ai


@pytest.fixture
def vault(tmp_path, monkeypatch):
    v = tmp_path / "vault"
    for d in ("raw/processed", "wiki/sources", "wiki/entities", "wiki/concepts",
              "wiki/synthesis", "outputs"):
        (v / d).mkdir(parents=True)
    monkeypatch.setattr(ai, "VAULT", v)
    monkeypatch.setattr(ai, "RAW_DIR", v / "raw")
    monkeypatch.setattr(ai, "PROCESSED", v / "raw" / "processed")
    monkeypatch.setattr(ai, "WIKI_DIR", v / "wiki")
    monkeypatch.setattr(ai, "LOG_FILE", v / "outputs" / "ingest-log.md")
    monkeypatch.setattr(ai, "LAST_RUN_FILE", v / "outputs" / ".last_ingest_run")
    monkeypatch.setattr(ai, "BRAND_DIR", tmp_path / "no-voice")
    monkeypatch.setattr(ai, "DRY_RUN", False)
    return v


class TestEnvFile:
    def test_loads_and_does_not_override(self, tmp_path, monkeypatch):
        f = tmp_path / "env"
        f.write_text('# c\nFOO_T1="bar"\nEXISTING_T=new\nbad line\n\nQ_T=\'x y\'\n')
        monkeypatch.delenv("FOO_T1", raising=False)
        monkeypatch.delenv("Q_T", raising=False)
        monkeypatch.setenv("EXISTING_T", "keep")
        ai._load_env_file(f)
        assert os.environ["FOO_T1"] == "bar"
        assert os.environ["EXISTING_T"] == "keep"
        assert os.environ["Q_T"] == "x y"
        monkeypatch.delenv("FOO_T1")
        monkeypatch.delenv("Q_T")

    def test_missing_file_ok(self, tmp_path):
        ai._load_env_file(tmp_path / "absent")


class TestRunGate:
    def test_no_stamp_runs(self, vault):
        assert ai.should_run_today()

    def test_recent_run_skips(self, vault):
        ai.record_run()
        assert not ai.should_run_today()

    def test_old_run_proceeds(self, vault):
        ai.LAST_RUN_FILE.write_text(str(time.time() - 48 * 3600))
        assert ai.should_run_today()

    def test_corrupt_stamp_runs(self, vault):
        ai.LAST_RUN_FILE.write_text("garbage")
        assert ai.should_run_today()

    def test_dry_run_bypasses_and_does_not_stamp(self, vault, monkeypatch):
        monkeypatch.setattr(ai, "DRY_RUN", True)
        ai.record_run()
        assert not ai.LAST_RUN_FILE.exists()
        assert ai.should_run_today()

    def test_dry_run_defined_at_import(self):
        assert hasattr(ai, "DRY_RUN")


class TestRawFiles:
    def test_filters_extensions_and_processed(self, vault):
        raw = vault / "raw"
        for n in ("a.md", "b.PDF", "c.txt", "d.png"):
            (raw / n).write_text("x")
        (raw / "processed" / "old.md").write_text("x")
        (raw / "sub").mkdir()
        (raw / "sub" / "e.md").write_text("x")
        names = [p.name for p in ai.get_raw_files()]
        assert names == sorted(["a.md", "b.PDF", "c.txt", "e.md"])


class TestVideoId:
    @pytest.mark.parametrize("url", [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=10",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ?t=5",
        "https://www.youtube.com/embed/dQw4w9WgXcQ",
    ])
    def test_extracts(self, url):
        assert ai.extract_video_id(url) == "dQw4w9WgXcQ"

    def test_non_youtube_rejected(self):
        assert ai.extract_video_id("https://example.com/claude-opus") is None

    def test_youtube_without_id(self):
        assert ai.extract_video_id("https://www.youtube.com/") is None


class TestHtmlStripper:
    def test_skips_script_and_style(self):
        s = ai._HTMLTextStripper()
        s.feed("<p>Hello</p><script>var x=1;</script><style>a{}</style><b>World</b>")
        assert s.get_text() == "Hello\nWorld"


class TestFetchArticle:
    class Resp:
        def __init__(self, body):
            self.body = body

        def read(self):
            return self.body.encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def test_long_page(self, monkeypatch):
        html = "<p>" + "word " * 100 + "</p>"
        monkeypatch.setattr(ai.urllib.request, "urlopen", lambda *a, **k: self.Resp(html))
        assert "word" in ai.fetch_article_text("https://x.com")

    def test_short_page_empty(self, monkeypatch):
        monkeypatch.setattr(ai.urllib.request, "urlopen", lambda *a, **k: self.Resp("<p>hi</p>"))
        assert ai.fetch_article_text("https://x.com") == ""

    def test_fetch_error_empty(self, monkeypatch):
        def boom(*a, **k):
            raise OSError("down")
        monkeypatch.setattr(ai.urllib.request, "urlopen", boom)
        assert ai.fetch_article_text("https://x.com") == ""


class TestGithubReadme:
    def test_invalid_url_returns_input(self):
        assert ai.fetch_github_readme("https://gitlab.com/a/b") == "https://gitlab.com/a/b"

    def test_fallback_when_unreachable(self, monkeypatch):
        def boom(*a, **k):
            raise OSError
        monkeypatch.setattr(ai.urllib.request, "urlopen", boom)
        out = ai.fetch_github_readme("github.com/owner/repo.git")
        assert "owner/repo" in out and "README not found" in out

    def test_success(self, monkeypatch):
        class R(TestFetchArticle.Resp):
            status = 200
        monkeypatch.setattr(ai.urllib.request, "urlopen", lambda *a, **k: R("# Hi"))
        out = ai.fetch_github_readme("https://github.com/owner/repo/tree/main")
        assert out.endswith("# Hi") and "owner/repo" in out


class TestExtractContent:
    def test_md_plain(self, tmp_path):
        f = tmp_path / "a.md"
        f.write_text("# Title\nbody")
        assert ai.extract_content(f) == "# Title\nbody"

    def test_md_youtube_frontmatter_duplicate_skipped(self, vault, monkeypatch):
        (vault / "wiki/sources/Existing.md").write_text("video dQw4w9WgXcQ")
        f = vault / "raw/c.md"
        f.write_text('---\nsource: "https://youtu.be/dQw4w9WgXcQ"\n---\nbody')
        assert ai.extract_content(f) == ""

    def test_md_youtube_frontmatter_transcript(self, vault, monkeypatch):
        monkeypatch.setattr(ai, "fetch_youtube_transcript", lambda u: "TRANSCRIPT")
        f = vault / "raw/c.md"
        f.write_text('---\nsource: https://youtu.be/dQw4w9WgXcQ\n---\nnotes')
        assert ai.extract_content(f) == "notes\n\nTRANSCRIPT"

    def test_txt_note_mentioning_link_kept(self, tmp_path):
        f = tmp_path / "n.txt"
        f.write_text("my note\nsee https://youtu.be/dQw4w9WgXcQ")
        assert "my note" in ai.extract_content(f)

    def test_txt_youtube_url(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ai, "fetch_youtube_transcript", lambda u: "T")
        f = tmp_path / "n.txt"
        f.write_text("https://youtu.be/dQw4w9WgXcQ")
        assert ai.extract_content(f) == "T"

    def test_txt_youtube_failure_falls_back_to_raw(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ai, "fetch_youtube_transcript", lambda u: "")
        f = tmp_path / "n.txt"
        f.write_text("https://youtu.be/dQw4w9WgXcQ")
        assert ai.extract_content(f) == "https://youtu.be/dQw4w9WgXcQ"

    def test_txt_github(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ai, "fetch_github_readme", lambda u: "README")
        f = tmp_path / "n.txt"
        f.write_text("https://github.com/a/b")
        assert ai.extract_content(f) == "README"

    def test_txt_bare_article_with_notes(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ai, "fetch_article_text", lambda u: "ARTICLE")
        f = tmp_path / "n.txt"
        f.write_text("https://example.com/p\nmy thoughts")
        assert ai.extract_content(f) == "https://example.com/p\n\nmy thoughts\n\nARTICLE"

    def test_txt_bare_article_unfetchable(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ai, "fetch_article_text", lambda u: "")
        f = tmp_path / "n.txt"
        f.write_text("https://example.com/p")
        assert ai.extract_content(f) == ""

    def test_empty_txt(self, tmp_path):
        f = tmp_path / "n.txt"
        f.write_text("")
        assert ai.extract_content(f) == ""

    def test_unknown_suffix(self, tmp_path):
        f = tmp_path / "n.png"
        f.write_text("x")
        assert ai.extract_content(f) == ""


class TestIsAlreadyIngested:
    def test_no_dir(self, vault):
        (vault / "wiki/sources").rmdir()
        assert not ai.is_already_ingested("abc")

    def test_hit_and_miss(self, vault):
        (vault / "wiki/sources/X.md").write_text("id=abc123")
        assert ai.is_already_ingested("abc123")
        assert not ai.is_already_ingested("zzz")


class TestLLM:
    def test_requires_keys(self, monkeypatch):
        monkeypatch.setattr(ai, "OPENROUTER_API_KEY", "")
        monkeypatch.setattr(ai, "DEEPSEEK_API_KEY", "")
        with pytest.raises(RuntimeError):
            ai.call_openrouter("x")
        with pytest.raises(RuntimeError):
            ai.call_deepseek("x")

    def test_routing(self, monkeypatch):
        monkeypatch.setattr(ai, "call_openrouter", lambda p: "or")
        monkeypatch.setattr(ai, "call_deepseek", lambda p: "ds")
        monkeypatch.setattr(ai, "PROVIDER", "openrouter")
        assert ai.call_llm("x") == "or"
        monkeypatch.setattr(ai, "PROVIDER", "deepseek")
        assert ai.call_llm("x") == "ds"

    def test_response_parsing_and_errors(self, monkeypatch):
        monkeypatch.setattr(ai, "OPENROUTER_API_KEY", "k")
        resp = TestFetchArticle.Resp('{"choices":[{"message":{"content":"  hi "}}]}')
        monkeypatch.setattr(ai.urllib.request, "urlopen", lambda *a, **k: resp)
        assert ai.call_openrouter("x") == "hi"
        bad = TestFetchArticle.Resp('{}')
        monkeypatch.setattr(ai.urllib.request, "urlopen", lambda *a, **k: bad)
        with pytest.raises(RuntimeError):
            ai.call_openrouter("x")

        def unreachable(*a, **k):
            raise ai.urllib.error.URLError("no")
        monkeypatch.setattr(ai.urllib.request, "urlopen", unreachable)
        with pytest.raises(RuntimeError):
            ai.call_openrouter("x")


class TestBrandAndPrompt:
    def test_brand_missing(self, vault):
        assert ai.load_brand_foundation() == ""

    def test_brand_skips_underscore(self, tmp_path, monkeypatch):
        d = tmp_path / "voice"
        d.mkdir()
        (d / "tone-rules.md").write_text("be brief")
        (d / "_ref.md").write_text("HUGE")
        monkeypatch.setattr(ai, "BRAND_DIR", d)
        out = ai.load_brand_foundation()
        assert "Tone Rules" in out and "be brief" in out and "HUGE" not in out

    def test_prompt_truncates(self, vault):
        p = ai.build_prompt("x" * (ai.RAW_CHUNK + 10), "f.md", ["A"] * 100)
        assert "[truncated]" in p and "[[A]]" in p and "RAW FILE: f.md" in p


class TestParseResponse:
    def test_parses_blocks(self):
        r = ("junk\n===FILE: wiki/sources/A B.md===\n# A\n===END===\n"
             "===FILE: wiki/concepts/C.md===\n# C\n===END===")
        assert ai.parse_response(r) == [("wiki/sources/A B.md", "# A"),
                                        ("wiki/concepts/C.md", "# C")]

    def test_malformed(self):
        assert ai.parse_response("no blocks") == []


class TestWriteWikiEntry:
    def test_creates(self, vault):
        assert ai.write_wiki_entry("wiki/concepts/New.md", "# New [[A]]") is True
        assert (vault / "wiki/concepts/New.md").read_text() == "# New [[A]]"

    def test_append_novel_links_only(self, vault):
        f = vault / "wiki/concepts/E.md"
        f.write_text("# E [[A]]")
        assert ai.write_wiki_entry("wiki/concepts/E.md", "[[A]] [[B]]") is False
        text = f.read_text()
        assert "New Connections" in text and "- [[B]]" in text
        assert text.count("[[A]]") == 1

    def test_no_novel_links_unchanged(self, vault):
        f = vault / "wiki/concepts/E.md"
        f.write_text("# E [[A]]")
        ai.write_wiki_entry("wiki/concepts/E.md", "[[A]]")
        assert f.read_text() == "# E [[A]]"

    def test_replace(self, vault):
        f = vault / "wiki/synthesis/S.md"
        f.write_text("old")
        assert ai.write_wiki_entry("wiki/synthesis/S.md", "new", replace=True) is False
        assert f.read_text() == "new"

    def test_dry_run_writes_nothing(self, vault, monkeypatch):
        monkeypatch.setattr(ai, "DRY_RUN", True)
        assert ai.write_wiki_entry("wiki/concepts/D.md", "x") is True
        assert not (vault / "wiki/concepts/D.md").exists()

    @pytest.mark.parametrize("rel", [
        "wiki/../../escape.md",
        "wiki/../outputs/ingest-log.md",
        "raw/injected.md",
        "../evil.md",
    ])
    def test_rejects_paths_outside_wiki(self, vault, rel):
        assert ai.write_wiki_entry(rel, "x") is False
        assert not (vault.parent / "escape.md").exists()
        assert not (vault / "raw/injected.md").exists()
        assert not (vault.parent / "evil.md").exists()
        assert not (vault / "outputs/ingest-log.md").exists()


class TestLog:
    def test_append(self, vault):
        ai.append_log([("a.md", ["wiki/x.md", "wiki/y.md"])])
        text = ai.LOG_FILE.read_text()
        assert "**a.md** → 2 entries" in text and "`wiki/y.md`" in text

    def test_dry_run(self, vault, monkeypatch):
        monkeypatch.setattr(ai, "DRY_RUN", True)
        ai.append_log([("a.md", [])])
        assert not ai.LOG_FILE.exists()


class TestSynthesisHelpers:
    def test_norm(self):
        assert ai._norm("Hello, World-1!") == "helloworld1"

    def test_parse_clusters_dedups_and_strips_brackets(self):
        r = "===CLUSTER: Theme A===\n[Foo], [foo], Bar\nBaz\n===END==="
        assert ai.parse_clusters(r) == {"Theme A": ["Foo", "Bar", "Baz"]}

    def test_parse_clusters_empty(self):
        assert ai.parse_clusters("nothing") == {}

    def test_collect_digests(self, vault):
        (vault / "wiki/entities/E.md").write_text("line1\nline2")
        d = ai.collect_wiki_digests()
        assert d[0]["stem"] == "E" and d[0]["summary"] == "line1 line2"

    def test_cluster_prompt(self):
        p = ai.build_cluster_prompt([{"stem": "A", "summary": "s"}])
        assert "1. [A] s" in p

    def test_needs_resynthesis(self, vault):
        entry = vault / "wiki/concepts/C.md"
        entry.write_text("x")
        assert ai.needs_resynthesis("T", [entry])  # no synthesis yet
        synth = vault / "wiki/synthesis/Synthesis - T.md"
        synth.write_text("s")
        now = time.time()
        os.utime(entry, (now - 100, now - 100))
        os.utime(synth, (now, now))
        assert not ai.needs_resynthesis("T", [entry])
        os.utime(entry, (now + 100, now + 100))
        assert ai.needs_resynthesis("T", [entry])
        assert ai.needs_resynthesis("T", [vault / "gone.md"])

    def test_synthesis_prompt(self, vault):
        p = ai.build_synthesis_prompt("My Theme", "TEXT", ["A"])
        assert "Synthesis - My Theme.md" in p and "[[A]]" in p


class TestRunSynthesis:
    def test_end_to_end(self, vault, monkeypatch):
        for n in ("A", "B", "C"):
            (vault / f"wiki/concepts/{n}.md").write_text(f"{n} body")
        responses = iter([
            "===CLUSTER: Group One===\nA, B, C\n===END===",
            "===FILE: wiki/synthesis/Synthesis - Group One.md===\n# S\n===END===",
        ])
        monkeypatch.setattr(ai, "call_llm", lambda p: next(responses))
        monkeypatch.setattr(ai.sys, "argv", ["auto_ingest.py", "--synthesize"])
        ai.run_synthesis()
        assert (vault / "wiki/synthesis/Synthesis - Group One.md").read_text() == "# S"

    def test_no_entries(self, vault, capsys):
        ai.run_synthesis()
        assert "No wiki entries" in capsys.readouterr().out

    def test_llm_error_handled(self, vault, monkeypatch):
        (vault / "wiki/concepts/A.md").write_text("a")

        def boom(p):
            raise RuntimeError("down")
        monkeypatch.setattr(ai, "call_llm", boom)
        ai.run_synthesis()


class TestIndex:
    def test_writes_index(self, vault):
        (vault / "wiki/concepts/Zed.md").write_text("x")
        (vault / "wiki/concepts/alpha.md").write_text("x")
        ai.update_wiki_index()
        text = (vault / "wiki/index.md").read_text()
        assert "**Total entries: 2**" in text
        assert text.index("[[alpha]]") < text.index("[[Zed]]")

    def test_dry_run(self, vault, monkeypatch):
        monkeypatch.setattr(ai, "DRY_RUN", True)
        ai.update_wiki_index()
        assert not (vault / "wiki/index.md").exists()


class TestMain:
    def _run(self, monkeypatch, *args):
        monkeypatch.setattr(ai.sys, "argv", ["auto_ingest.py", *args])
        ai.main()

    def test_ingest_moves_file_and_logs(self, vault, monkeypatch):
        (vault / "raw/note.md").write_text("# Note\nhello")
        monkeypatch.setattr(ai, "call_llm", lambda p: (
            "===FILE: wiki/sources/Note.md===\n# Note [[A]] [[B]]\n===END==="))
        monkeypatch.setattr(ai, "run_synthesis", lambda: None)
        self._run(monkeypatch)
        assert (vault / "wiki/sources/Note.md").exists()
        assert (vault / "raw/processed/note.md").exists()
        assert not (vault / "raw/note.md").exists()
        assert "note.md" in ai.LOG_FILE.read_text()
        assert ai.LAST_RUN_FILE.exists()
        assert (vault / "wiki/index.md").exists()

    def test_processed_name_collision_keeps_extension(self, vault, monkeypatch):
        (vault / "raw/processed/note.md").write_text("old")
        (vault / "raw/note.md").write_text("new")
        monkeypatch.setattr(ai, "call_llm", lambda p: (
            "===FILE: wiki/sources/N.md===\n# N\n===END==="))
        monkeypatch.setattr(ai, "run_synthesis", lambda: None)
        self._run(monkeypatch)
        assert (vault / "raw/processed/note.md").read_text() == "old"
        moved = [p for p in (vault / "raw/processed").iterdir() if p.name != "note.md"]
        assert len(moved) == 1 and moved[0].suffix == ".md"

    def test_dry_run_changes_nothing(self, vault, monkeypatch):
        (vault / "raw/note.md").write_text("hello")
        monkeypatch.setattr(ai, "call_llm", lambda p: (
            "===FILE: wiki/sources/Note.md===\n# Note\n===END==="))
        monkeypatch.setattr(ai, "run_synthesis", lambda: None)
        self._run(monkeypatch, "--dry-run")
        assert (vault / "raw/note.md").exists()
        assert not (vault / "wiki/sources/Note.md").exists()
        assert not ai.LAST_RUN_FILE.exists()

    def test_llm_failure_leaves_file(self, vault, monkeypatch):
        (vault / "raw/note.md").write_text("hello")

        def boom(p):
            raise RuntimeError("down")
        monkeypatch.setattr(ai, "call_llm", boom)
        self._run(monkeypatch)
        assert (vault / "raw/note.md").exists()

    def test_gate_skips(self, vault, monkeypatch):
        ai.record_run()
        (vault / "raw/note.md").write_text("hello")
        called = []
        monkeypatch.setattr(ai, "call_llm", lambda p: called.append(1) or "")
        self._run(monkeypatch)
        assert not called

    def test_empty_raw_updates_index(self, vault, monkeypatch):
        self._run(monkeypatch)
        assert (vault / "wiki/index.md").exists()

    def test_save_without_url_prints_usage(self, vault, monkeypatch, capsys):
        self._run(monkeypatch, "--save")
        assert "Usage" in capsys.readouterr().out
