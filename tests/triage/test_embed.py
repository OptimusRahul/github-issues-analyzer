from types import SimpleNamespace

import numpy as np

from tests.triage.helpers import WordHashEmbedder, gh_issue
from triage.config import EmbeddingsConfig
from triage.embed import OpenAIEmbedder, embed_pending, make_embedder, normalize
from triage.text import issue_text, sanitize


def test_issue_text_handles_missing_body():
    assert issue_text({"title": "Crash", "body": None}) == "Crash"
    assert issue_text({"title": "Crash", "body": "  "}) == "Crash"
    assert issue_text({"title": "Crash", "body": "x" * 5000}) == "Crash\n\n" + "x" * 2000


def test_sanitize_strips_mentions_links_and_markup():
    text = "See @octocat and https://evil.example/x <script>`code`</script>  now"
    assert sanitize(text) == "See octocat and scriptcode/script now"


def test_sanitize_caps_length():
    assert sanitize("a" * 300, limit=10) == "aaaaaaaaa…"
    assert sanitize(None) == ""


def test_normalize_gives_unit_vectors_and_keeps_zero_rows():
    out = normalize([[3, 4], [0, 0]])
    assert np.allclose(out, [[0.6, 0.8], [0, 0]])


def test_embed_pending_only_embeds_new_or_changed(store):
    embedder = WordHashEmbedder()
    store.upsert_issues([gh_issue(1, "crash on start"), gh_issue(2, "dark theme")])
    assert embed_pending(store, embedder) == 2
    assert embed_pending(store, embedder) == 0
    store.upsert_issues([gh_issue(2, "dark theme please")])
    assert embed_pending(store, embedder) == 1
    numbers, vectors = store.matrix(embedder.name)
    assert numbers.tolist() == [1, 2]
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0)


def test_embed_pending_batches(store):
    embedder = WordHashEmbedder()
    store.upsert_issues([gh_issue(n, f"issue {n}") for n in range(1, 6)])
    embed_pending(store, embedder, batch_size=2)
    assert embedder.calls == 3


def test_make_embedder_openai_uses_configured_endpoint(monkeypatch):
    monkeypatch.setenv("MY_KEY", "secret")
    embedder = make_embedder(
        EmbeddingsConfig(provider="openai", model="m", base_url="http://localhost:9999/v1", api_key_env="MY_KEY")
    )
    assert isinstance(embedder, OpenAIEmbedder)
    assert embedder.name == "openai:m"
    assert str(embedder._client.base_url).startswith("http://localhost:9999/v1")
    assert embedder._client.api_key == "secret"


def test_sanitize_neutralises_protocol_relative_links_and_entity_mentions():
    for text in ("[Fix here](//evil.example/x)", "![img](//evil.example/p.png)", "[a]: //evil.example"):
        out = sanitize(text)
        assert "evil.example" not in out
        assert "](" not in out
    assert sanitize("&#64;octocat").startswith("\\&")


def test_sanitize_removes_issue_references():
    out = sanitize("Same as #999 and GH-12")
    assert "#999" not in out and "GH-12" not in out
    assert "999" in out


def test_openai_embedder_reports_token_usage():
    embedder = OpenAIEmbedder("m", base_url="http://localhost:9999/v1")
    response = SimpleNamespace(data=[SimpleNamespace(embedding=[1.0, 0.0])], usage=SimpleNamespace(prompt_tokens=7))
    embedder._client = SimpleNamespace(embeddings=SimpleNamespace(create=lambda **kwargs: response))
    embedder.embed(["a"])
    embedder.embed(["b"])
    assert embedder.usage_summary() == "embeddings openai:m: 2 texts, 14 tokens"
