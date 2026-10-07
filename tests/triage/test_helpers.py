from tests.triage.helpers import WordHashEmbedder, gh_issue
from triage.embed import normalize


def test_word_hash_embedder_is_deterministic_and_similarity_follows_shared_words():
    embedder = WordHashEmbedder()
    a, b, c = normalize(embedder.embed(["crash on windows", "windows crash", "dark theme"]))
    assert a @ b > 0.8
    assert a @ c < 0.2
    assert embedder.calls == 1


def test_gh_issue_marks_pull_requests():
    assert "pull_request" in gh_issue(1, pr=True)
    assert "pull_request" not in gh_issue(1)
