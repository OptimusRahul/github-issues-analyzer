"""Async analyze service for LLM-based issue analysis"""

import logging

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.libs.openai_client import OpenAIClient
from src.models.database import Issue, Repo

from .schema import AnalyzeResponse

logger = logging.getLogger(__name__)


class AnalyzeService:
    """Async service for analyzing GitHub repository issues"""

    def __init__(self):
        """Initialize analyze service"""
        self.openai_client = OpenAIClient()

    async def analyze_repository(self, repo: str, prompt: str, db: AsyncSession) -> AnalyzeResponse:
        """
        Analyze GitHub repository issues using LLM

        Args:
            repo: Repository in format 'owner/repository-name'
            prompt: User's analysis prompt/question
            db: AsyncSession for database operations

        Returns:
            AnalyzeResponse with LLM analysis

        Raises:
            HTTPException: If repository not scanned, no issues found, or LLM errors occur
        """
        logger.info(f"Starting analysis for repository: {repo}")

        # Check if repository exists in database
        stmt = select(Repo).where(Repo.id == repo)
        result = await db.execute(stmt)
        repo_obj = result.scalar_one_or_none()

        if not repo_obj:
            logger.warning(f"Repository {repo} not found in database")
            raise HTTPException(
                status_code=404,
                detail=f"Repository '{repo}' has not been scanned yet. Please scan it first using the /scan endpoint.",
            )

        # Fetch all issues for the repository
        stmt = select(Issue).where(Issue.repo_id == repo).order_by(Issue.created_at.desc())
        result = await db.execute(stmt)
        issues_obj = result.scalars().all()

        if not issues_obj:
            logger.warning(f"No issues found for repository {repo}")
            raise HTTPException(
                status_code=400,
                detail=f"No issues found for repository '{repo}'. The repository may have no issues or the scan may have failed.",
            )

        # Convert to dictionaries
        issues = [issue.to_dict() for issue in issues_obj]
        logger.info(f"Found {len(issues)} issues for analysis")

        # Analyze issues using OpenAI
        try:
            logger.info(f"Initializing OpenAI client for analysis of {len(issues)} issues")
            analysis = self.openai_client.analyze_issues(issues, prompt)
            logger.info("Analysis completed successfully")
        except Exception as e:
            logger.error(f"Failed to analyze issues: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500, detail=f"Failed to analyze issues with LLM: {str(e)}"
            )

        # Return response
        return AnalyzeResponse(analysis=analysis)
