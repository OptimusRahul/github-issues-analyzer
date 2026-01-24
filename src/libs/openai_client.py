"""OpenAI API client wrapper"""

import logging
from typing import Any, Dict, List

from openai import OpenAI, OpenAIError

from src.config import settings

logger = logging.getLogger(__name__)


class OpenAIClient:
    """Wrapper around OpenAI API for issue analysis"""

    # Maximum number of issues to analyze at once (to handle token limits)
    MAX_ISSUES_PER_ANALYSIS = 200

    def __init__(self):
        """Initialize OpenAI client"""
        try:
            # Initialize with minimal configuration to avoid compatibility issues
            self.client = OpenAI(
                api_key=settings.openai_api_key,
                timeout=60.0,  # 60 second timeout
                max_retries=2,
            )
            self.model = settings.openai_model
            logger.info(f"OpenAI client initialized successfully with model: {self.model}")
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {str(e)}", exc_info=True)
            raise

    def analyze_issues(self, issues: List[Dict[str, Any]], user_prompt: str) -> str:
        """
        Analyze GitHub issues using OpenAI LLM

        Args:
            issues: List of issue dictionaries with id, title, body, html_url, created_at
            user_prompt: User's analysis request

        Returns:
            LLM analysis response

        Raises:
            ValueError: If OpenAI API error occurs
        """
        if not issues:
            raise ValueError("No issues provided for analysis")

        # Handle large number of issues by limiting to most recent
        total_issues = len(issues)
        if len(issues) > self.MAX_ISSUES_PER_ANALYSIS:
            # Sort by created_at (most recent first) and take top N
            issues = sorted(issues, key=lambda x: x.get("created_at", ""), reverse=True)[
                : self.MAX_ISSUES_PER_ANALYSIS
            ]

        # Format issues into a structured prompt
        issues_text = self._format_issues_for_llm(issues)

        # Create system prompt
        system_prompt = (
            "You are an expert at analyzing GitHub issues. "
            "You help maintainers understand patterns, themes, and priorities in their issue tracker. "
            "Provide clear, actionable insights based on the issues provided."
        )

        # Create user prompt with context
        full_prompt = f"""
            Analyze the following GitHub issues and respond to this request:

            User Prompt: {user_prompt}

            Issues to analyze:
            {issues_text}
        """
        logger.info(f"Full prompt: {full_prompt}")

        # Add note if we limited the number of issues
        if total_issues > self.MAX_ISSUES_PER_ANALYSIS:
            full_prompt += f"\n\nNote: This analysis is based on the {self.MAX_ISSUES_PER_ANALYSIS} most recent issues out of {total_issues} total issues in the repository."

        try:
            # Call OpenAI API
            logger.info(f"Calling OpenAI API with model: {self.model}")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": full_prompt},
                ],
                temperature=0.7,
                max_tokens=2000,
            )

            logger.info("OpenAI API call successful")
            return response.choices[0].message.content  # type: ignore

        except OpenAIError as e:
            logger.error(f"OpenAI API error: {str(e)}", exc_info=True)
            raise ValueError(f"OpenAI API error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during OpenAI API call: {str(e)}", exc_info=True)
            raise ValueError(f"Unexpected error: {str(e)}")

    def _format_issues_for_llm(self, issues: List[Dict[str, Any]]) -> str:
        """
        Format issues into a readable text format for the LLM

        Args:
            issues: List of issue dictionaries

        Returns:
            Formatted string representation of issues
        """
        formatted_issues = []

        for idx, issue in enumerate(issues, 1):
            # Truncate long issue bodies to avoid token limit issues
            body = issue.get("body", "")
            if len(body) > 500:
                body = body[:500] + "... (truncated)"

            issue_text = f"""
Issue #{issue.get("id", "N/A")}:
Title: {issue.get("title", "N/A")}
Created: {issue.get("created_at", "N/A")}
URL: {issue.get("html_url", "N/A")}
Description: {body if body else "(No description)"}
---
"""
            formatted_issues.append(issue_text)

        return "\n".join(formatted_issues)
