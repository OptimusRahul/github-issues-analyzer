# GitHub Issues Analyzer

A FastAPI-based application that fetches GitHub repository issues, caches them locally, and uses OpenAI's LLM to provide intelligent analysis.

## How to Run the Server

### Prerequisites

- Python 3.10 or higher
- [UV](https://github.com/astral-sh/uv) - Fast Python package manager
- OpenAI API key
- GitHub token (optional, but recommended)

### Setup

1. **Install UV:**
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Install dependencies:**
   ```bash
   uv sync
   ```

3. **Configure environment variables:**
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` and add your API keys:
   ```
   OPENAI_API_KEY=your_openai_api_key_here
   GITHUB_TOKEN=your_github_token_here
   ```

### Start the Server

```bash
uv run main.py
```

The API will be available at `http://localhost:8000`

Interactive API documentation: `http://localhost:8000/docs`

## Why SQLite?

**SQLite** was chosen over alternatives like in-memory storage or JSON files because:

1. **No Custom Query Logic Needed**: With in-memory storage or JSON files, you'd need to write custom logic to query issues by repo, filter by date, etc. SQLite handles all of this with simple SQL queries through SQLAlchemy ORM.

2. **Persistent & Organized Storage**: Once a repo is scanned, it stays cached in an organized relational structure. You don't need to re-scan the same repositories during development/testing, saving GitHub API calls and making development smooth.

3. **Development-Friendly**: Unlike in-memory storage (lost on restart) or JSON files (messy to manage and query), SQLite gives you a single organized database file that persists across server restarts and is easy to query, inspect, or delete.

4. **Zero Configuration**: No separate database server required - just a single `github_issues.db` file that's created automatically.

For a production application with high concurrent writes or multiple application instances, PostgreSQL would be recommended. But for this local caching + LLM analysis MVP, SQLite is the optimal choice.
