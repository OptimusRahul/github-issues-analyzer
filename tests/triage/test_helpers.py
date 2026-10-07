import numpy as np

from tests.triage.helpers import WordHashEmbedder, gh_issue


def test_word_hash_embedder_is_deterministic_and_similarity_follows_shared_words():
    embedder = WordHashEmbedder()
    a, b, c = embedder.embed(["crash on windows", "windows crash", "dark theme"])

    def cos(x, y):
        return float(x @ y / (np.linalg.norm(x) * np.linalg.norm(y)))

    assert cos(a, b) > 0.8
    assert cos(a, c) < 0.2
    assert embedder.calls == 1


def test_gh_issue_marks_pull_requests():
    assert "pull_request" in gh_issue(1, pr=True)
    assert "pull_request" not in gh_issue(1)
