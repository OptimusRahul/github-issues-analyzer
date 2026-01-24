"""Schemas for analyze service - re-exported from models"""

import re

from pydantic import BaseModel, Field, field_validator


class AnalyzeRequest(BaseModel):
    """Request model for /analyze endpoint

    Example:
        {
            "repo": "owner/repository-name",
            "prompt": "Find themes across recent issues and recommend what the maintainers should fix first"
        }
    """

    repo: str = Field(
        ...,
        description="Repository in format 'owner/repository-name'",
        examples=["facebook/react", "microsoft/vscode", "owner/repository-name"],
    )
    prompt: str = Field(
        ...,
        description="User's analysis prompt",
        min_length=1,
        examples=[
            "Find themes across recent issues and recommend what the maintainers should fix first",
            "What are the most common bug reports?",
            "Summarize feature requests from the community",
            "Identify security-related issues",
        ],
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "repo": "owner/repository-name",
                    "prompt": "Find themes across recent issues and recommend what the maintainers should fix first",
                },
                {"repo": "facebook/react", "prompt": "What are the most common bug reports?"},
            ]
        }
    }

    @field_validator("repo")
    @classmethod
    def validate_repo_format(cls, v: str) -> str:
        """Validate that repo is in 'owner/repo' format"""
        if not re.match(r"^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$", v):
            raise ValueError(
                "Repository must be in format 'owner/repository-name'. Example: 'facebook/react'"
            )
        return v


class AnalyzeResponse(BaseModel):
    """Response model for /analyze endpoint

    Example:
        {
            "analysis": "<LLM-generated text here>"
        }
    """

    analysis: str = Field(
        ...,
        description="LLM-generated analysis of the repository issues",
        examples=[
            "Based on the analyzed issues, the main themes are: 1) Performance optimization requests, 2) UI/UX improvements, 3) Bug fixes for edge cases. The maintainers should prioritize fixing the performance issues as they affect the most users."
        ],
    )

    model_config = {"json_schema_extra": {"examples": [{"analysis": "<LLM-generated text here>"}]}}
