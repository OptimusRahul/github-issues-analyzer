"""GitHub API client wrapper"""

from typing import Any, Dict, List

from github import Github, GithubException, Repository

from src.config import settings


class GitHubClient:
    """Wrapper around PyGithub for fetching repository issues"""

    def __init__(self):
        """Initialize GitHub client with optional authentication"""
        if settings.github_token:
            self.client = Github(settings.github_token)
        else:
            # Use unauthenticated access (lower rate limit: 60 requests/hour)
            self.client = Github()

    def fetch_repository_issues(self, owner: str, repo: str) -> List[Dict[str, Any]]:
        """
        Fetch all open issues from a GitHub repository

        Args:
            owner: Repository owner (username or organization)
            repo: Repository name

        Returns:
            List of open issues with relevant fields extracted

        Raises:
            GithubException: If repository not found or API error occurs
        """
        try:
            # Get repository
            repository: Repository.Repository = self.client.get_repo(f"{owner}/{repo}")

            # Fetch only open issues
            # Note: In GitHub API, pull requests are also considered issues
            # We filter them out by checking if pull_request attribute exists
            issues = repository.get_issues(state="open")

            # Extract relevant fields
            issue_list = []
            for issue in issues:
                # Skip pull requests (they have a pull_request attribute)
                if issue.pull_request is not None:
                    continue

                issue_data = {
                    "id": str(issue.number),  # Use issue number as ID
                    "title": issue.title,
                    "body": issue.body or "",  # Handle None body
                    "html_url": issue.html_url,
                    "created_at": issue.created_at.isoformat(),
                }
                issue_list.append(issue_data)

            return issue_list

        except GithubException as e:
            if e.status == 404:
                raise ValueError(f"Repository '{owner}/{repo}' not found")
            elif e.status == 403:
                raise ValueError(
                    "GitHub API rate limit exceeded. "
                    "Please provide a GITHUB_TOKEN in .env file for higher limits."
                )
            else:
                raise ValueError(f"GitHub API error: {e.data.get('message', str(e))}")

    def get_rate_limit(self) -> Dict[str, Any]:
        """
        Get current rate limit status

        Returns:
            Dictionary with rate limit information
        """
        rate_limit = self.client.get_rate_limit()
        return {
            "core": {
                "limit": rate_limit.core.limit,
                "remaining": rate_limit.core.remaining,
                "reset": rate_limit.core.reset.isoformat(),
            }
        }
