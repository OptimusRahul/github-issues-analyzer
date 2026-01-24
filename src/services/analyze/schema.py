"""Pydantic schemas for analyze service."""

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    """Request schema for analyzing GitHub issues."""
    
    repo: str = Field(
        ...,
        description="GitHub repository in format 'owner/name'",
        examples=["octocat/Hello-World"]
    )
    prompt: str = Field(
        ...,
        description="Natural language prompt for analyzing issues",
        examples=["What are the common themes in these issues?"]
    )


class AnalyzeResponse(BaseModel):
    """Response schema for analysis operation."""
    
    analysis: str = Field(..., description="LLM-generated analysis of the issues")
