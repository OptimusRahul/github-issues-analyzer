"""Schemas for scan service - re-exported from models"""

import re

from pydantic import BaseModel, Field, field_validator


class ScanRequest(BaseModel):
    """Request model for /scan endpoint

    Example:
        {
            "repo": "owner/repository-name"
        }
    """

    repo: str = Field(
        ...,
        description="Repository in format 'owner/repository-name'",
        examples=["facebook/react", "microsoft/vscode", "owner/repository-name"],
    )

    model_config = {
        "json_schema_extra": {
            "examples": [{"repo": "owner/repository-name"}, {"repo": "facebook/react"}]
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


class ScanResponse(BaseModel):
    """Response model for /scan endpoint

    Example:
        {
            "repo": "owner/repository-name",
            "issues_fetched": 42,
            "cached_successfully": true
        }
    """

    repo: str = Field(..., description="Repository that was scanned")
    issues_fetched: int = Field(..., description="Number of issues fetched")
    cached_successfully: bool = Field(..., description="Whether caching was successful")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"repo": "owner/repository-name", "issues_fetched": 42, "cached_successfully": True}
            ]
        }
    }
