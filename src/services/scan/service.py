"""Async scan service for fetching and caching GitHub issues"""

import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.libs.github_client import GitHubClient
from src.models.database import Issue, Repo

from .schema import ScanResponse

logger = logging.getLogger(__name__)


class ScanService:
    """Async service for scanning GitHub repositories"""

    def __init__(self):
        """Initialize scan service"""
        self.github_client = GitHubClient()

    async def scan_repository(self, repo: str, db: AsyncSession) -> ScanResponse:
        """
        Scan a GitHub repository and cache its issues in the database

        Args:
            repo: Repository in format 'owner/repository-name'
            db: AsyncSession for database operations

        Returns:
            ScanResponse with results of the scan

        Raises:
            ValueError: If GitHub API errors occur or repository is invalid
        """
        logger.info(f"Starting scan for repository: {repo}")

        # Parse owner and repo name
        owner, repo_name = repo.split("/")

        # Check if repository already exists in database
        result = await db.execute(select(Repo).where(Repo.id == repo))
        logger.info(f"Checking if repository {repo} exists in database")
        existing_repo = result.scalar_one_or_none()
        logger.info(f"Repository {repo} exists in database: {existing_repo}")

        if existing_repo:
            # Count existing issues for this repo
            result = await db.execute(select(Issue).where(Issue.repo_id == repo))
            existing_issues = result.scalars().all()
            issues_count = len(existing_issues)

            logger.info(f"Repository {repo} already scanned with {issues_count} issues")
            return ScanResponse(
                repo=repo,
                issues_fetched=issues_count,
                cached_successfully=True,
                message=f"Repository already scanned. Found {issues_count} cached issues.",
            )

        # Fetch issues from GitHub (synchronous GitHub client)
        try:
            issues = self.github_client.fetch_repository_issues(owner, repo_name)
            logger.info(f"Fetched {len(issues)} issues from GitHub for {repo}")
        except Exception as e:
            logger.error(f"Failed to fetch issues from GitHub: {str(e)}", exc_info=True)
            raise ValueError(f"Failed to fetch issues from GitHub: {str(e)}")

        # Store in database
        try:
            # Upsert repository record
            stmt = insert(Repo).values(id=repo, name=repo, created_at=datetime.utcnow())
            stmt = stmt.on_conflict_do_update(
                index_elements=["id"], set_=dict(name=repo, created_at=datetime.utcnow())
            )
            await db.execute(stmt)
            logger.info(f"Repository {repo} record upserted")

            # Upsert issues
            issues_stored = 0
            for issue in issues:
                issue_id = f"{repo}#{issue['id']}"

                stmt = insert(Issue).values(
                    id=issue_id,
                    repo_id=repo,
                    title=issue["title"],
                    body=issue["body"],
                    html_url=issue["html_url"],
                    created_at=datetime.fromisoformat(issue["created_at"].replace("Z", "+00:00")),
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=["id"],
                    set_=dict(
                        repo_id=repo,
                        title=issue["title"],
                        body=issue["body"],
                        html_url=issue["html_url"],
                        created_at=datetime.fromisoformat(
                            issue["created_at"].replace("Z", "+00:00")
                        ),
                    ),
                )
                await db.execute(stmt)
                issues_stored += 1

            await db.commit()
            logger.info(f"Stored {issues_stored} issues for {repo}")

        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to store issues in database: {str(e)}", exc_info=True)
            raise ValueError(f"Failed to store issues in database: {str(e)}")

        # Return response
        return ScanResponse(repo=repo, issues_fetched=len(issues), cached_successfully=True)
