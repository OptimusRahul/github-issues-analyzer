"""Pydantic schemas for scan service."""

from pydantic import BaseModel, Field, field_validator


class ScanRequest(BaseModel):
    """Request schema for scanning a GitHub repository."""
    
    repo: str = Field(
        ...,
        description="GitHub repository in format 'owner/name'",
        examples=["octocat/Hello-World"]
    )
    
    @field_validator('repo')
    @classmethod
    def validate_repo_format(cls, v: str) -> str:
        """Validate repository format is 'owner/name'."""
        if '/' not in v or len(v.split('/')) != 2:
            raise ValueError('Repository must be in format "owner/name"')
        
        owner, name = v.split('/')
        if not owner or not name:
            raise ValueError('Repository owner and name cannot be empty')
        
        return v


class ScanResponse(BaseModel):
    """Response schema for scan operation."""
    
    repo: str = Field(..., description="Repository that was scanned")
    issues_fetched: int = Field(..., description="Number of issues fetched")
    cached_successfully: bool = Field(..., description="Whether caching was successful")
