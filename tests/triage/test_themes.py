import json

import numpy as np

from tests.triage.test_llm import FakeClient
from triage.config import LLMConfig
from triage.llm import ChatModel
from triage.themes import cluster, keywords, name_theme


def unit(*xs):
    v = np.array(xs, dtype=np.float32)
    return v / np.linalg.norm(v)


def test_cluster_groups_similar_vectors_largest_first_and_leaves_loners_out():
    vectors = np.stack([
        unit(1, 0.1, 0), unit(1, 0, 0.1), unit(1, 0.05, 0.05), unit(1, 0, 0),   # group A (4)
        unit(0, 1, 0.1), unit(0.1, 1, 0), unit(0, 1, 0),                       # group B (3)
        unit(0, 0, 1),                                                          # loner
    ])
    groups = cluster(vectors, threshold=0.9, min_size=3)
    assert [sorted(g.tolist()) for g in groups] == [[0, 1, 2, 3], [4, 5, 6]]


def test_cluster_of_empty_input_is_empty():
    assert cluster(np.zeros((0, 3), dtype=np.float32)) == []


def test_keywords_prefer_words_distinctive_to_the_group():
    group = ["Crash on startup", "Startup crash on Windows", "startup crash after the update"]
    corpus = group + ["Dark theme on Linux", "Add an API for the plugin", "Docs typo on the site", "Crash in the docs build"]
    words = keywords(group, corpus, n=2)
    assert words == ["startup", "crash"]


def test_name_theme_uses_the_llm_when_given_and_sanitizes_it():
    chat = ChatModel(LLMConfig(base_url="http://x", model="m"), client=FakeClient(json.dumps({"name": "Startup crashes @team"})))
    assert name_theme(["Crash on startup"], ["Crash on startup"], chat) == "Startup crashes team"


def test_name_theme_falls_back_to_keywords():
    group = ["Crash on startup", "Startup crash"]
    assert name_theme(group, group + ["Dark theme"]) == "crash / startup"  # tie broken alphabetically


def test_keywords_fall_back_to_distinctive_words_when_titles_share_none():
    group = ["Duplicate benchmark", "Scale run on vscode", "Two-week maintainer test"]
    words = keywords(group, group + ["Dark theme", "Plugin API"], n=2)
    assert len(words) == 2 and set(words) <= {"duplicate", "benchmark", "scale", "run", "vscode", "two", "week", "maintainer", "test"}
