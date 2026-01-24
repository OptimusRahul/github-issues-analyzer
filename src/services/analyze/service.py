"""Analyze service business logic."""

import logging
from typing import Dict, Any, List

from src.lib.openai_client import OpenAIClient
from src.database.connection import get_db_connection

# Configure logger
logger = logging.getLogger(__name__)


def analyze_repository(repo_name: str, prompt: str) -> Dict[str, Any]:
    """
    Analyze cached GitHub issues using LLM.
    
    Args:
        repo_name: Repository in format "owner/name"
        prompt: User's analysis prompt
        
    Returns:
        Dictionary with analysis text
        
    Raises:
        ValueError: If repository not found or no issues cached
        Exception: For database or API errors
    """
    logger.info(f"Starting analysis for repository: {repo_name}")
    logger.debug(f"Analysis prompt: '{prompt[:100]}...'")
    
    # 1. Look up repository_id from repo_name
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if repository exists
        logger.debug(f"Looking up repository: {repo_name}")
        cursor.execute("SELECT id FROM repositories WHERE repo_name = ?", (repo_name,))
        row = cursor.fetchone()
        
        if not row:
            logger.warning(f"Repository not found in cache: {repo_name}")
            raise ValueError(
                f"No cached issues for repository '{repo_name}'. "
                "Please run /scan first to fetch and cache issues."
            )
        
        repository_id = row['id']
        logger.debug(f"Found repository with ID: {repository_id}")
        
        # 2. Query database for cached issues using repository_id
        logger.debug(f"Querying cached issues for repository_id: {repository_id}")
        cursor.execute(
            """
            SELECT id, title, body, html_url, created_at
            FROM issues
            WHERE repository_id = ?
            ORDER BY created_at DESC
            """,
            (repository_id,)
        )
        
        issues_rows = cursor.fetchall()
        logger.info(f"Found {len(issues_rows)} cached issues")
        
        # Convert rows to dictionaries
        issues = []
        for row in issues_rows:
            issues.append({
                'id': row['id'],
                'title': row['title'],
                'body': row['body'],
                'html_url': row['html_url'],
                'created_at': row['created_at']
            })
        
        if not issues:
            # Repository exists but has no issues
            logger.info(f"Repository {repo_name} has no open issues")
            return {
                "analysis": f"Repository '{repo_name}' has no open issues."
            }
        
        # 3. Format issues and call OpenAI
        logger.debug("Initializing OpenAI client for analysis")
        openai_client = OpenAIClient()
        analysis = openai_client.analyze_issues(issues, prompt, repo_name)
        
        logger.info(f"Analysis completed successfully for {repo_name}")
        return {
            "analysis": analysis
        }
        
    except ValueError:
        # Re-raise ValueError without logging (already logged)
        raise
    except Exception as e:
        logger.error(f"Error during analysis: {str(e)}", exc_info=True)
        raise
    finally:
        conn.close()
