"""Application configuration settings"""
import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # GitHub API Configuration
    github_token: Optional[str] = None
    
    # OpenAI API Configuration
    openai_api_key: str
    openai_model: str = "gpt-4-turbo-preview"
    
    # Database Configuration
    database_path: str = "github_issues.db"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )


# Global settings instance
settings = Settings()
