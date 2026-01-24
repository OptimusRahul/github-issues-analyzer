"""Scan service business logic."""

import uuid
import logging
from typing import Dict, Any

from src.lib.github_client import GitHubClient
from src.database.connection import get_db_connection

# Configure logger
logger = logging.getLogger(__name__)


def scan_repository(repo_name: str) -> Dict[str, Any]:
    """
    Fetch issues from GitHub and store in database.
    
    Args:
        repo_name: Repository in format "owner/name"
        
    Returns:
        Dictionary with repo, issues_fetched, and cached_successfully
        
    Raises:
        ValueError: If repository not found or invalid
        Exception: For database or API errors
    """
    logger.info(f"Starting scan for repository: {repo_name}")
    
    # 1. Fetch issues from GitHub using PyGithub
    try:
        github_client = GitHubClient()
        issues = github_client.fetch_open_issues(repo_name)
        logger.info(f"Fetched {len(issues)} issues from GitHub")
    except Exception as e:
        logger.error(f"Failed to fetch issues from GitHub: {str(e)}", exc_info=True)
        raise
    
    # 2. Store in database (transaction: delete old + insert new)
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 2a. Get or create repository record with UUID
        # First check if repository exists
        logger.debug(f"Checking if repository {repo_name} exists in database")
        cursor.execute("SELECT id FROM repositories WHERE repo_name = ?", (repo_name,))
        row = cursor.fetchone()
        
        if row:
            repository_id = row['id']
            logger.debug(f"Repository exists with ID: {repository_id}, updating metadata")
            # Update existing repository
            cursor.execute(
                "UPDATE repositories SET last_scanned_at = datetime('now'), issue_count = ? WHERE id = ?",
                (len(issues), repository_id)
            )
        else:
            # Create new repository with UUID
            repository_id = str(uuid.uuid4())
            logger.info(f"Creating new repository record with ID: {repository_id}")
            cursor.execute(
                "INSERT INTO repositories (id, repo_name, last_scanned_at, issue_count) "
                "VALUES (?, ?, datetime('now'), ?)",
                (repository_id, repo_name, len(issues))
            )
        
        # 2b. Delete old issues and insert new ones
        logger.debug(f"Deleting old issues for repository_id: {repository_id}")
        cursor.execute("DELETE FROM issues WHERE repository_id = ?", (repository_id,))
        
        logger.debug(f"Inserting {len(issues)} issues into database")
        for idx, issue in enumerate(issues, 1):
            cursor.execute(
                "INSERT INTO issues (id, repository_id, title, body, html_url, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (issue['id'], repository_id, issue['title'], issue['body'],
                 issue['html_url'], issue['created_at'])
            )
            if idx % 10 == 0:
                logger.debug(f"Inserted {idx}/{len(issues)} issues")
        
        conn.commit()
        logger.info(f"Successfully cached {len(issues)} issues for {repo_name}")
        
        # 3. Return summary
        return {
            "repo": repo_name,
            "issues_fetched": len(issues),
            "cached_successfully": True
        }
        
    except Exception as e:
        logger.error(f"Database error while caching issues: {str(e)}", exc_info=True)
        conn.rollback()
        raise Exception(f"Database error while caching issues: {str(e)}")
    finally:
        conn.close()
