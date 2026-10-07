from datetime import datetime, timezone

from tests.triage.helpers import WordHashEmbedder, gh_comment, gh_issue
from triage.config import Config, DigestConfig, DuplicatesConfig
from triage.digest import Theme, build_digest, render_digest, split_themes
from triage.embed import embed_pending

NOW = datetime(2026, 6, 1, tzinfo=timezone.utc)
CFG = Config(duplicates=DuplicatesConfig(threshold=0.6), digest=DigestConfig(theme_threshold=0.6, min_theme_size=3))

ISSUES = [
    gh_issue(1, "Settings crash on Windows", created="2026-05-28T00:00:00Z"),
    gh_issue(2, "Crash opening settings Windows", created="2026-05-29T00:00:00Z"),
    gh_issue(3, "Windows settings crash again", created="2026-05-30T00:00:00Z"),
    gh_issue(4, "Dark theme request @octocat", created="2026-01-10T00:00:00Z", reactions=30),
    gh_issue(5, "Dark theme colours", created="2026-01-12T00:00:00Z", reactions=5),
    gh_issue(6, "Add plugin API", created="2026-02-01T00:00:00Z"),
    gh_issue(7, "Old closed bug", created="2026-01-01T00:00:00Z", state="closed", closed="2026-01-02T00:00:00Z"),
]
COMMENTS = [
    gh_comment(10, 5, "We will look at this", created="2026-03-01T00:00:00Z", association="MEMBER"),
    gh_comment(11, 6, "Any update?", created="2026-05-01T00:00:00Z", association="NONE"),
]


def setup(store):
    embedder = WordHashEmbedder()
    store.upsert_issues(ISSUES)
    store.upsert_comments(COMMENTS)
    embed_pending(store, embedder)
    return embedder.name


def test_digest_sections(store):
    digest = build_digest(store, setup(store), CFG, NOW)
    assert [sorted(t.numbers) for t in digest.new_themes] == [[1, 2, 3]]
    assert "crash" in digest.new_themes[0].name
    assert [i["number"] for i in digest.most_wanted] == [4]
    assert [(i["number"], days) for i, days in digest.waiting] == [(6, 31)]
    assert (2, 1) in {(new, old) for new, old, _ in digest.open_duplicates}
    assert all(old != 7 and new != 7 for new, old, _ in digest.open_duplicates)


def test_split_themes_by_share_of_new_issues_and_growth():
    fresh = Theme("a", [1, 2, 3, 4], new=3, previous=0)
    growing = Theme("b", list(range(10)), new=3, previous=1)
    steady = Theme("c", list(range(10)), new=1, previous=3)
    assert split_themes([fresh, growing, steady]) == ([fresh], [growing])


def test_render_lists_sections_and_sanitizes_titles(store):
    text = render_digest("o/r", build_digest(store, setup(store), CFG, NOW), NOW)
    assert text.startswith("# Triage digest – 2026-06-01")
    for heading in ("## New themes", "## Growing themes", "## Most-wanted, no maintainer reply",
                    "## Waiting on maintainers", "## Likely duplicates still open"):
        assert heading in text
    assert "#4" in text and "30 reactions" in text
    assert "@octocat" not in text
    assert "None this week." in text  # growing themes is empty here
