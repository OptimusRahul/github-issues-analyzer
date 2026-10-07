import sqlite3

import numpy as np
import pytest

from tests.triage.helpers import gh_comment, gh_issue
from triage.store import Store


@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path / "index.sqlite")
    yield s
    s.close()


def test_upsert_skips_pull_requests_and_updates_existing(store):
    assert store.upsert_issues([gh_issue(1, "old"), gh_issue(2, pr=True)]) == 1
    store.upsert_issues([gh_issue(1, "new", labels=["bug"], body=None)])
    store.commit()
    issue = store.issue(1)
    assert issue["title"] == "new"
    assert issue["labels"] == ["bug"]
    assert issue["body"] == ""
    assert store.issue(2) is None
    assert store.count_issues() == 1


def test_state_roundtrip_and_delete(store):
    store.set_state("cursor", {"phase": "issues"})
    assert store.get_state("cursor") == {"phase": "issues"}
    store.set_state("cursor", None)
    assert store.get_state("cursor", "missing") == "missing"


def test_comments_are_linked_to_issue_number(store):
    store.upsert_comments([gh_comment(10, 3, "Duplicate of #1"), gh_comment(11, 3, "thanks", created="2026-01-03T00:00:00Z")])
    assert [c["body"] for c in store.comments_for(3)] == ["Duplicate of #1", "thanks"]


def test_pending_embeddings_only_new_or_changed(store):
    store.upsert_issues([gh_issue(1, "a"), gh_issue(2, "b")])
    pending = store.pending_embeddings("m", lambda i: i["title"])
    assert [p[0] for p in pending] == [1, 2]
    store.save_embeddings("m", [(n, h, np.ones(3)) for n, _, h in pending])
    assert store.pending_embeddings("m", lambda i: i["title"]) == []
    store.upsert_issues([gh_issue(2, "b changed")])
    assert [p[0] for p in store.pending_embeddings("m", lambda i: i["title"])] == [2]
    assert len(store.pending_embeddings("other-model", lambda i: i["title"])) == 2


def test_matrix_is_ordered_by_creation_and_filtered_by_model(store):
    store.upsert_issues([gh_issue(5, created="2026-02-01T00:00:00Z"), gh_issue(9, created="2026-01-01T00:00:00Z")])
    store.save_embeddings("m", [(5, "h5", np.array([1, 0], np.float32)), (9, "h9", np.array([0, 1], np.float32))])
    numbers, vectors = store.matrix("m")
    assert numbers.tolist() == [9, 5]
    assert vectors.tolist() == [[0, 1], [1, 0]]
    empty_numbers, empty_vectors = store.matrix("other")
    assert empty_numbers.size == 0 and empty_vectors.size == 0


def test_stores_assignees_milestone_and_author(store):
    store.upsert_issues([gh_issue(1, assignees=["ana", "bo"], milestone="v2", author="cy")])
    issue = store.issue(1)
    assert issue["assignees"] == ["ana", "bo"]
    assert issue["milestone"] == "v2"
    assert issue["author"] == "cy"
    store.upsert_issues([gh_issue(2)])
    assert store.issue(2)["milestone"] is None and store.issue(2)["assignees"] == []


def test_index_created_by_an_older_version_gains_new_columns(tmp_path):
    path = tmp_path / "old.sqlite"
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE issues (number INTEGER PRIMARY KEY, title TEXT NOT NULL, body TEXT NOT NULL DEFAULT '', "
        "state TEXT NOT NULL, state_reason TEXT, labels TEXT NOT NULL DEFAULT '[]', author_association TEXT, "
        "comments_count INTEGER NOT NULL DEFAULT 0, reactions_total INTEGER NOT NULL DEFAULT 0, html_url TEXT NOT NULL, "
        "created_at TEXT NOT NULL, updated_at TEXT NOT NULL, closed_at TEXT)"
    )
    conn.execute(
        "INSERT INTO issues (number, title, state, html_url, created_at, updated_at) "
        "VALUES (1, 't', 'open', 'u', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"
    )
    conn.commit()
    conn.close()
    s = Store(path)
    assert s.issue(1)["assignees"] == []
    s.upsert_issues([gh_issue(1, assignees=["ana"])])
    assert s.issue(1)["assignees"] == ["ana"]
    s.close()
