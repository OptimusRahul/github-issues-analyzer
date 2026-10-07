import json

import pytest

from tests.triage.helpers import WordHashEmbedder, gh_issue
from tests.triage.test_llm import FakeClient
from triage.ask import SYSTEM_PROMPT, AskError, ask
from triage.config import LLMConfig
from triage.embed import embed_pending
from triage.llm import ChatModel

ISSUES = [
    gh_issue(1, "Crash on startup on Windows"),
    gh_issue(2, "Dark theme request"),
    gh_issue(3, "Startup crash after update"),
]


def setup(store):
    embedder = WordHashEmbedder()
    store.upsert_issues(ISSUES)
    embed_pending(store, embedder)
    return embedder


def chat(*replies):
    return ChatModel(LLMConfig(base_url="http://x", model="m"), client=FakeClient(*replies))


def test_answer_keeps_only_citations_that_were_retrieved(store):
    embedder = setup(store)
    model = chat(json.dumps({"answer": "Two reports of startup crashes.", "citations": [1, 3, 999, "2"]}))
    result = ask(store, embedder, model, "What crashes are reported?")
    assert result.text == "Two reports of startup crashes."
    assert [h.number for h in result.citations] == [1, 3]


def test_prompt_passes_issue_text_as_untrusted_data(store):
    embedder = setup(store)
    model = chat(json.dumps({"answer": "x", "citations": []}))
    ask(store, embedder, model, "crashes?")
    system, user = model.client.calls[0]["messages"]
    assert system["content"] == SYSTEM_PROMPT and "untrusted" in SYSTEM_PROMPT
    assert '<issue number="1"' in user["content"]


def test_question_length_is_bounded_before_any_model_call(store):
    embedder = setup(store)
    model = chat()
    for question in ("", "   ", "x" * 1001):
        with pytest.raises(AskError, match="1 to 1000"):
            ask(store, embedder, model, question)
    assert model.calls == 0


def test_model_that_never_answers_is_an_error(store):
    embedder = setup(store)
    with pytest.raises(AskError, match="usable answer"):
        ask(store, embedder, chat("nope", '{"answer": 5}'), "crashes?")
