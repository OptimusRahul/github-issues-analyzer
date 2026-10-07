import pytest

from triage.store import Store


@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path / "index.sqlite")
    yield s
    s.close()
