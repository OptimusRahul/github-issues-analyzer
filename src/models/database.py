"""Database schema definitions."""

# SQL schema for the application
# Repositories table stores metadata about scanned GitHub repositories
# Issues table stores the actual issues with foreign key to repositories

SCHEMA = """
CREATE TABLE IF NOT EXISTS repositories (
    id TEXT PRIMARY KEY,
    repo_name TEXT UNIQUE NOT NULL,
    last_scanned_at TIMESTAMP,
    issue_count INTEGER
);

CREATE TABLE IF NOT EXISTS issues (
    id INTEGER PRIMARY KEY,
    repository_id TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT,
    html_url TEXT NOT NULL,
    created_at TIMESTAMP,
    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (repository_id) REFERENCES repositories(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_issues_repository_id ON issues(repository_id);
CREATE INDEX IF NOT EXISTS idx_repositories_repo_name ON repositories(repo_name);
"""
