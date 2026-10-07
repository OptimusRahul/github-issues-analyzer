import pytest

from tests.triage.helpers import FakeGitHub, WordHashEmbedder, gh_comment, gh_issue
from triage import cli

ISSUES = [
    gh_issue(1, "App crashes when opening settings on Windows"),
    gh_issue(2, "Crash when opening settings on Windows 11"),
    gh_issue(4, "Fix typo", pr=True),
]


@pytest.fixture
def fake(monkeypatch):
    fake = FakeGitHub(issues=ISSUES)
    monkeypatch.setattr(cli, "GitHubClient", lambda token=None: fake.client())
    monkeypatch.setattr(cli, "make_embedder", lambda cfg: WordHashEmbedder())
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    monkeypatch.delenv("TRIAGE_DRY_RUN", raising=False)
    return fake


def args(tmp_path, *rest):
    config = tmp_path / "issue-triage.yml"
    if not config.exists():
        config.write_text("duplicates:\n  threshold: 0.5\n")
    return ["--repo", "o/r", "--config", str(config), "--index-dir", str(tmp_path / "idx"), *rest]


def test_missing_repo_exits_2(fake, capsys):
    assert cli.main(["sync"]) == 2
    assert "--repo" in capsys.readouterr().err


def test_sync_prints_summary_and_writes_index(fake, tmp_path, capsys):
    assert cli.main(args(tmp_path, "sync")) == 0
    assert "Synced o/r: 2 issues" in capsys.readouterr().out
    assert cli.index_path(tmp_path / "idx", "o/r").exists()


def test_dupes_dry_run_prints_candidates_and_posts_nothing(fake, tmp_path, capsys):
    assert cli.main(args(tmp_path, "dupes", "2")) == 0
    out = capsys.readouterr().out
    assert "Likely duplicates of #2:" in out and "#1" in out and "Dry run" in out
    assert fake.issue_comments == {}


def test_cli_reports_not_in_index(fake, tmp_path, capsys):
    assert cli.main(args(tmp_path, "dupes", "4")) == 1
    assert "#4 is not in the index" in capsys.readouterr().err


def test_config_error_exits_1_with_field_name(fake, tmp_path, capsys):
    (tmp_path / "issue-triage.yml").write_text("duplicates:\n  thresold: 1\n")
    assert cli.main(args(tmp_path, "sync")) == 1
    assert "duplicates.thresold" in capsys.readouterr().err


def test_index_path_is_per_repo(tmp_path):
    assert cli.index_path(tmp_path, "octo/repo").name == "octo__repo.sqlite"


def test_bench_writes_report(monkeypatch, tmp_path, capsys):
    issues = [
        gh_issue(1, "App crashes when opening settings on Windows", created="2026-01-01T00:00:00Z"),
        gh_issue(2, "Add dark theme to editor", created="2026-01-02T00:00:00Z"),
        gh_issue(3, "Crash when opening settings on Windows 11", created="2026-01-03T00:00:00Z",
                 state="closed", labels=["duplicate"], closed="2026-01-04T00:00:00Z"),
    ]
    fake = FakeGitHub(issues=issues, comments=[gh_comment(10, 3, "Duplicate of #1", created="2026-06-01T00:00:00Z")])
    monkeypatch.setattr(cli, "GitHubClient", lambda token=None: fake.client())
    monkeypatch.setattr(cli, "make_embedder", lambda cfg: WordHashEmbedder())
    out = tmp_path / "report.md"
    assert cli.main(args(tmp_path, "bench", "--out", str(out))) == 0
    report = out.read_text()
    assert "Duplicate pairs: 1" in report
    assert "Recall@3 with no threshold: 100%" in report
    assert str(out) in capsys.readouterr().out


def test_bench_llm_without_llm_config_is_an_error(fake, tmp_path, capsys):
    assert cli.main(args(tmp_path, "bench", "--llm")) == 1
    assert "models.llm" in capsys.readouterr().err


def test_usage_lines_lists_only_models_that_report_usage():
    class Reports:
        def usage_summary(self):
            return "llm m: 1 calls, 5 prompt + 1 completion tokens"

    assert cli.usage_lines(WordHashEmbedder(), None) == ""
    assert cli.usage_lines(WordHashEmbedder(), Reports()) == "Model usage:\n  llm m: 1 calls, 5 prompt + 1 completion tokens"


def test_llm_call_limit_of_zero_disables_the_llm_in_dupes(fake, tmp_path, monkeypatch, capsys):
    (tmp_path / "issue-triage.yml").write_text(
        "duplicates:\n  threshold: 0.5\nmodels:\n  llm:\n    base_url: http://x\n    model: m\nlimits:\n  max_llm_calls_per_run: 0\n"
    )

    def no_llm(cfg):
        raise AssertionError("LLM must not be created when the call limit is 0")

    monkeypatch.setattr(cli, "Confirmer", no_llm)
    assert cli.main(args(tmp_path, "dupes", "2")) == 0
    assert "Likely duplicates of #2:" in capsys.readouterr().out
