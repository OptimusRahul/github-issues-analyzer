"""Command-line entry point: `triage`."""

from __future__ import annotations

import argparse
import os
import sys
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path

from triage.ask import AskError, ask
from triage.bench import evaluate, evaluate_with_llm, ground_truth, render_report
from triage.commands import (
    DupesOutcome,
    LabelsOutcome,
    check_duplicates,
    check_labels,
    ignored_labels,
)
from triage.config import ConfigError, load_config
from triage.digest import build_digest, render_digest
from triage.dupes import NotInIndex
from triage.embed import SetupError, embed_pending, make_embedder
from triage.github import GitHubClient, GitHubError
from triage.labels import evaluate_labels
from triage.llm import ChatModel, Confirmer
from triage.search import Hit, hybrid_search
from triage.store import Store
from triage.sync import IndexMismatch, sync_repo

EXPECTED_ERRORS = (ConfigError, GitHubError, NotInIndex, IndexMismatch, SetupError, AskError)

ACTION_TEXT = {
    "dry-run": "Dry run: nothing posted. Set dry_run: false to post comments.",
    "created": "Posted a comment.",
    "updated": "Updated the existing comment.",
}


def index_path(index_dir: Path, repo: str) -> Path:
    return index_dir / f"{repo.replace('/', '__')}.sqlite"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="triage", description="AI triage for GitHub issues.")
    parser.add_argument("-R", "--repo", default=os.environ.get("GITHUB_REPOSITORY"), help="owner/repo (default: $GITHUB_REPOSITORY)")
    parser.add_argument("--config", type=Path, default=Path(".github/issue-triage.yml"), help="config file")
    parser.add_argument("--index-dir", type=Path, default=Path(os.environ.get("TRIAGE_INDEX_DIR", ".triage")), help="where index files are kept")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("sync", help="fetch new and updated issues and comments")
    dupes = commands.add_parser("dupes", help="find likely duplicates of an issue")
    dupes.add_argument("number", type=int)
    labels = commands.add_parser("labels", help="suggest labels and a priority for an issue (needs labels.enabled)")
    labels.add_argument("number", type=int)
    search = commands.add_parser("search", help="search issues by keywords and meaning")
    search.add_argument("query")
    search.add_argument("--state", choices=["open", "closed"])
    search.add_argument("--label", action="append", help="require this label (repeatable)")
    search.add_argument("--since", help="only issues created on or after this date (YYYY-MM-DD)")
    search.add_argument("--limit", type=int, default=10)
    commands.add_parser("digest", help="weekly digest of themes and issues needing attention")
    ask_cmd = commands.add_parser("ask", help="answer a question about the issues, citing them (needs models.llm)")
    ask_cmd.add_argument("question")
    bench = commands.add_parser("bench", help="measure duplicate detection against past duplicates")
    bench.add_argument("--max-pairs", type=int, default=1000, help="most recent duplicates to use")
    bench.add_argument("--sample", type=int, default=500, help="non-duplicate issues to check for false flags")
    bench.add_argument("--llm", action="store_true", help="also measure with LLM confirmation")
    bench.add_argument("--labels", action="store_true", help="also measure label suggestions against applied labels")
    bench.add_argument("--out", type=Path, help="write the Markdown report here")
    return parser


def format_outcome(number: int, outcome: DupesOutcome) -> str:
    if outcome.action == "disabled":
        return "Duplicate detection is disabled in the config."
    if not outcome.candidates:
        return f"No related issues for #{number}."
    lines = [f"Related issues for #{number}:"]
    for c in outcome.candidates:
        mark = "possible duplicate, " if c.confirmed else ""
        line = f"  #{c.number} ({mark}{c.score:.2f}, {c.state}) {c.title}"
        lines.append(line + (f" - {c.reason}" if c.reason else ""))
    lines.append(ACTION_TEXT[outcome.action])
    return "\n".join(lines)


def format_labels(number: int, outcome: LabelsOutcome) -> str:
    if outcome.action == "disabled":
        return "Label suggestions are disabled in the config (labels.enabled)."
    s = outcome.suggestion
    if not s.labels:
        return f"No label suggestions for #{number}. Priority: {s.priority}."
    text = f"Suggested labels for #{number}: {', '.join(s.labels)}. Priority: {s.priority}."
    return f"{text}\n{ACTION_TEXT[outcome.action]}"


def format_hits(hits: list[Hit]) -> str:
    if not hits:
        return "No matching issues."
    return "\n".join(f"  #{h.number} ({h.state}) {h.title}\n      {h.html_url}" for h in hits)


def usage_lines(*models) -> str:
    """Token usage of API-backed models (local models report nothing; they cost nothing)."""
    lines = [summary for m in models if m is not None and (summary := m.usage_summary())]
    return "\n".join(["Model usage:", *(f"  {line}" for line in lines)]) if lines else ""


def chat_for(cfg, task: str, cls=None):
    """The chat model configured for a task (models.<task>, else models.llm), or None if none is set."""
    llm = cfg.models.llm_for(task)
    if not llm.enabled:
        return None
    return (cls or ChatModel)(llm, max_calls=cfg.limits.max_llm_calls_per_run, task=task)


def _digest(cfg, gh, store, repo, now) -> None:
    if not cfg.digest.enabled:
        print("The digest is disabled in the config.")
        return
    embedder = make_embedder(cfg.models.embeddings)
    namer = chat_for(cfg, "themes")
    sync_repo(gh, store, repo, now, cfg.comments_window_days)
    embed_pending(store, embedder)
    body = render_digest(repo, build_digest(store, embedder.name, cfg, now, namer), now)
    if cfg.dry_run or cfg.digest.target == "none":
        print(body)
    else:
        issue = gh.create_issue(repo, f"Triage digest – {now:%Y-%m-%d}", body)
        print(f"Opened {issue['html_url']}")
    if usage := usage_lines(embedder, namer):
        print(usage)


def _bench(args, cfg, gh, store, repo, now) -> None:
    if args.llm and not cfg.models.llm_for("confirm").enabled:
        raise ConfigError("models.llm: --llm needs models.llm (or models.confirm) base_url and model")
    sync_repo(gh, store, repo, now, cfg.comments_window_days)
    embedder = make_embedder(cfg.models.embeddings)
    embed_pending(store, embedder)

    def fetch_comments(number: int) -> list[dict]:
        items = gh.issue_comments(repo, number)
        store.upsert_comments(items)
        store.commit()
        return items

    pairs = ground_truth(store, fetch_comments, args.max_pairs)
    numbers, vectors = store.matrix(embedder.name)
    result = evaluate(numbers, vectors, pairs, embedder.name, sample_size=args.sample)
    llm_result = None
    confirmer = chat_for(cfg, "confirm", Confirmer) if args.llm else None
    if confirmer is not None:
        threshold = cfg.duplicates.threshold  # related issues are listed from here; the LLM picks duplicates
        llm_result = evaluate_with_llm(
            store, numbers, vectors, pairs, result.sample, threshold, confirmer, cfg.limits.max_llm_calls_per_run,
        )
    report = render_report(repo, result, llm_result)
    if args.labels:
        lab = evaluate_labels(store, embedder.name, gh.list_labels(repo), cfg.labels, ignored_labels(cfg), args.sample)
        report += (
            f"\n## Label suggestions\n\n- Issues replayed: {lab.issues}\n"
            f"- Precision: {lab.precision:.0%}\n- Recall: {lab.recall:.0%}\n"
            f"- Settings: {cfg.labels.neighbors} neighbors, min share {cfg.labels.min_share}, at most {cfg.labels.max_labels} labels\n"
        )
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report)
        print(f"Wrote {args.out}")
    else:
        print(report)
    if usage := usage_lines(embedder, confirmer):
        print(usage)


def _run(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    with ExitStack() as stack:
        gh = GitHubClient(token=os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN"))
        stack.callback(gh.close)
        repo = gh.resolve_repo(args.repo)
        store = Store(index_path(args.index_dir, repo))
        stack.callback(store.close)
        now = datetime.now(timezone.utc)
        if args.command == "sync":
            result = sync_repo(gh, store, repo, now, cfg.comments_window_days)
            print(
                f"Synced {repo}: {result.issues} issues, {result.comments} comments in {result.pages} pages. "
                f"Index holds {store.count_issues()} issues."
            )
        elif args.command == "dupes":
            embedder = make_embedder(cfg.models.embeddings)
            confirmer = chat_for(cfg, "confirm", Confirmer)
            outcome = check_duplicates(gh, store, embedder, cfg, repo, args.number, now, confirmer)
            print(format_outcome(args.number, outcome))
            if usage := usage_lines(embedder, confirmer):
                print(usage)
        elif args.command == "labels":
            embedder = make_embedder(cfg.models.embeddings)
            chat = chat_for(cfg, "labels")
            outcome = check_labels(gh, store, embedder, cfg, repo, args.number, now, chat)
            print(format_labels(args.number, outcome))
            if usage := usage_lines(embedder, chat):
                print(usage)
        elif args.command == "search":
            embedder = make_embedder(cfg.models.embeddings)
            sync_repo(gh, store, repo, now, cfg.comments_window_days)
            embed_pending(store, embedder)
            hits = hybrid_search(store, embedder, args.query, args.limit, args.state, args.label, args.since)
            print(format_hits(hits))
            if usage := usage_lines(embedder):
                print(usage)
        elif args.command == "digest":
            _digest(cfg, gh, store, repo, now)
        elif args.command == "ask":
            chat = chat_for(cfg, "ask")
            if chat is None:
                raise ConfigError("models.llm: ask needs models.llm (or models.ask) base_url and model")
            embedder = make_embedder(cfg.models.embeddings)
            sync_repo(gh, store, repo, now, cfg.comments_window_days)
            embed_pending(store, embedder)
            answer = ask(store, embedder, chat, args.question)
            print(answer.text)
            if answer.citations:
                print("\nCited issues:")
                print(format_hits(answer.citations))
            if usage := usage_lines(embedder, chat):
                print(usage)
        elif args.command == "bench":
            _bench(args, cfg, gh, store, repo, now)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.repo:
        print("error: pass --repo owner/repo or set GITHUB_REPOSITORY", file=sys.stderr)
        return 2
    try:
        return _run(args)
    except EXPECTED_ERRORS as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
