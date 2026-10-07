"""Command-line entry point: `triage`."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from triage.bench import evaluate, evaluate_with_llm, ground_truth, render_report
from triage.commands import DupesOutcome, check_duplicates
from triage.config import ConfigError, load_config
from triage.dupes import NotInIndex
from triage.embed import SetupError, embed_pending, make_embedder
from triage.github import GitHubClient, GitHubError
from triage.llm import Confirmer
from triage.store import Store
from triage.sync import IndexMismatch, sync_repo

EXPECTED_ERRORS = (ConfigError, GitHubError, NotInIndex, IndexMismatch, SetupError)

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
    bench = commands.add_parser("bench", help="measure duplicate detection against past duplicates")
    bench.add_argument("--max-pairs", type=int, default=1000, help="most recent duplicates to use")
    bench.add_argument("--sample", type=int, default=500, help="non-duplicate issues to check for false flags")
    bench.add_argument("--llm", action="store_true", help="also measure with LLM confirmation")
    bench.add_argument("--out", type=Path, help="write the Markdown report here")
    return parser


def format_outcome(number: int, outcome: DupesOutcome) -> str:
    if outcome.action == "disabled":
        return "Duplicate detection is disabled in the config."
    if not outcome.candidates:
        return f"No likely duplicates for #{number}."
    lines = [f"Likely duplicates of #{number}:"]
    for c in outcome.candidates:
        line = f"  #{c.number} ({c.score:.2f}, {c.state}) {c.title}"
        lines.append(line + (f" - {c.reason}" if c.reason else ""))
    lines.append(ACTION_TEXT[outcome.action])
    return "\n".join(lines)


def usage_lines(*models) -> str:
    """Token usage of API-backed models (local models report nothing; they cost nothing)."""
    lines = [m.usage_summary() for m in models if m is not None and hasattr(m, "usage_summary")]
    return "\n".join(["Model usage:", *(f"  {line}" for line in lines)]) if lines else ""


def _bench(args, cfg, gh, store, repo, now) -> None:
    if args.llm and not cfg.models.llm.enabled:
        raise ConfigError("models.llm: --llm needs models.llm.base_url and models.llm.model")
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
    confirmer = Confirmer(cfg.models.llm) if args.llm else None
    if confirmer is not None:
        threshold = result.recommended.threshold if result.recommended else cfg.duplicates.threshold
        llm_result = evaluate_with_llm(
            store, numbers, vectors, pairs, result.sample, threshold, confirmer, cfg.limits.max_llm_calls_per_run,
        )
    report = render_report(repo, result, llm_result)
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
    gh = GitHubClient(token=os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN"))
    try:
        repo = gh.resolve_repo(args.repo)
        store = Store(index_path(args.index_dir, repo))
        now = datetime.now(timezone.utc)
        try:
            if args.command == "sync":
                result = sync_repo(gh, store, repo, now, cfg.comments_window_days)
                print(
                    f"Synced {repo}: {result.issues} issues, {result.comments} comments in {result.pages} pages. "
                    f"Index holds {store.count_issues()} issues."
                )
            elif args.command == "dupes":
                embedder = make_embedder(cfg.models.embeddings)
                use_llm = cfg.models.llm.enabled and cfg.limits.max_llm_calls_per_run > 0
                confirmer = Confirmer(cfg.models.llm) if use_llm else None
                outcome = check_duplicates(gh, store, embedder, cfg, repo, args.number, now, confirmer)
                print(format_outcome(args.number, outcome))
                if usage := usage_lines(embedder, confirmer):
                    print(usage)
            elif args.command == "bench":
                _bench(args, cfg, gh, store, repo, now)
        finally:
            store.close()
    finally:
        gh.close()
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
