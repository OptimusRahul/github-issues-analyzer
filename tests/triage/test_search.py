import numpy as np

from tests.triage.helpers import WordHashEmbedder, gh_issue
from triage.embed import embed_pending
from triage.search import hybrid_search
from triage.store import Store


class ConstantEmbedder:
    """Every text gets the same vector, so vector ranking carries no signal."""

    name = "test:constant"

    def embed(self, texts):
        return np.ones((len(texts), 4), dtype=np.float32)

    def usage_summary(self):
        return ""


ISSUES = [
    gh_issue(1, "Editor freezes when opening large files", body="Happens with 2GB logs"),
    gh_issue(2, "Startup fails with ERR_OSSL_EVP_UNSUPPORTED", body="node 17"),
    gh_issue(3, "Dark theme colours wrong", state="closed", closed="2026-01-05T00:00:00Z"),
    gh_issue(4, "Large file freezes editor", labels=["perf"], created="2026-03-01T00:00:00Z"),
]


def index(store, embedder, issues=ISSUES):
    store.upsert_issues(issues)
    embed_pending(store, embedder)
    store.commit()
    return embedder


def test_exact_error_string_ranks_first_even_when_embeddings_are_uninformative(store):
    embedder = index(store, ConstantEmbedder())
    hits = hybrid_search(store, embedder, "ERR_OSSL_EVP_UNSUPPORTED")
    assert hits[0].number == 2
    assert hits[0].html_url.endswith("/issues/2")


def test_semantic_match_found_without_shared_keywords_ranked_by_both(store):
    embedder = index(store, WordHashEmbedder())
    hits = hybrid_search(store, embedder, "large files freeze the editor")
    assert {h.number for h in hits[:2]} == {1, 4}


def test_filters_apply_before_ranking(store):
    embedder = index(store, WordHashEmbedder())
    assert 3 not in {h.number for h in hybrid_search(store, embedder, "dark theme", state="open")}
    assert [h.number for h in hybrid_search(store, embedder, "editor freezes", labels=["perf"])] == [4]
    assert [h.number for h in hybrid_search(store, embedder, "editor freezes", since="2026-02-01")] == [4]


def test_query_punctuation_does_not_break_keyword_search(store):
    embedder = index(store, WordHashEmbedder())
    hits = hybrid_search(store, embedder, 'freezes "large" (files) AND OR NOT * -')
    assert hits


def test_keyword_index_is_built_for_an_index_created_before_it_existed(tmp_path):
    path = tmp_path / "old.sqlite"
    s = Store(path)
    s.upsert_issues(ISSUES)
    s.conn.executescript(
        "DROP TRIGGER issues_ai; DROP TRIGGER issues_ad; DROP TRIGGER issues_au; DROP TABLE issues_fts;"
    )
    s.commit()
    s.close()
    s = Store(path)
    assert s.keyword_search("ERR_OSSL_EVP_UNSUPPORTED") == [2]
    s.close()
