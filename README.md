# GitHub Issues Analyzer

A FastAPI-based application that fetches GitHub repository issues, caches them locally in SQLite, and uses OpenAI's LLM to provide intelligent analysis based on user prompts.

## Features

- 🔍 **Fetch & Cache**: Automatically fetch all issues from any public GitHub repository
- 💾 **Local Storage**: Store issues in SQLite for fast repeated analysis
- 🤖 **AI-Powered Analysis**: Use OpenAI's LLM to analyze issues based on custom prompts
- 🚀 **Fast API**: RESTful API built with FastAPI for high performance
- 📊 **Smart Handling**: Automatically handles large repositories (3K+ issues) by analyzing the most recent issues
- ⚡ **UV Support**: Uses UV for 10-100x faster dependency installation

## Architecture

```
Client → FastAPI → Services → External APIs
                 ↓
              SQLite DB
```

**Workflow:**
1. `/scan` endpoint: Fetches issues from GitHub → Stores in SQLite
2. `/analyze` endpoint: Retrieves cached issues → Sends to OpenAI → Returns analysis

## Prerequisites

- Python 3.10 or higher
- [UV](https://github.com/astral-sh/uv) - Fast Python package manager
- OpenAI API key ([Get one here](https://platform.openai.com/api-keys))
- GitHub token (optional, but recommended for higher rate limits)

## Installation

**UV is 10-100x faster than traditional package managers!** [Learn more about UV](UV_GUIDE.md)

### Automated Setup (Recommended)

```bash
# Install UV
curl -LsSf https://astral.sh/uv/install.sh | sh
# or: brew install uv

# Clone and setup
git clone <repository-url>
cd github-issues-analyzer
./setup_with_uv.sh
```

### Manual Setup

1. **Install UV:**
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   # or: brew install uv
   ```

2. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd github-issues-analyzer
   ```

3. **Install dependencies:**
   ```bash
   uv sync
   # This creates venv and installs dependencies automatically!
   ```

4. **Configure environment variables:**
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` and add your API keys:
   ```
   OPENAI_API_KEY=your_openai_api_key_here
   GITHUB_TOKEN=your_github_token_here  # Optional but recommended
   ```

## Usage

### Start the Server

```bash
# Option 1: Using uv run (recommended - no activation needed!)
uv run main.py

# Option 2: Traditional way
source .venv/bin/activate
python main.py
```

The API will be available at `http://localhost:8000`

Interactive API documentation: `http://localhost:8000/docs`

### API Endpoints

#### 1. Health Check

```bash
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "github-issues-analyzer"
}
```

#### 2. Scan Repository

Fetch and cache issues from a GitHub repository.

```bash
POST /scan
Content-Type: application/json

{
  "repo": "owner/repository-name"
}
```

**Example:**
```bash
curl -X POST "http://localhost:8000/scan" \
  -H "Content-Type: application/json" \
  -d '{"repo": "facebook/react"}'
```

**Response:**
```json
{
  "repo": "facebook/react",
  "issues_fetched": 42,
  "cached_successfully": true
}
```

#### 3. Analyze Repository

Analyze cached issues using AI.

```bash
POST /analyze
Content-Type: application/json

{
  "repo": "owner/repository-name",
  "prompt": "Your analysis question"
}
```

**Example:**
```bash
curl -X POST "http://localhost:8000/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "repo": "facebook/react",
    "prompt": "What are the main themes in recent issues? What should maintainers prioritize?"
  }'
```

**Response:**
```json
{
  "repo": "facebook/react",
  "prompt": "What are the main themes in recent issues?",
  "analysis": "Based on the analyzed issues, here are the main themes...",
  "issues_analyzed": 42
}
```

## Example Use Cases

### 1. Find Common Themes
```json
{
  "repo": "python/cpython",
  "prompt": "What are the most common types of issues reported?"
}
```

### 2. Prioritization Recommendations
```json
{
  "repo": "microsoft/vscode",
  "prompt": "Based on recent issues, what should the maintainers fix first?"
}
```

### 3. Feature Request Analysis
```json
{
  "repo": "rust-lang/rust",
  "prompt": "Summarize the feature requests from the last 100 issues"
}
```

### 4. Bug Pattern Detection
```json
{
  "repo": "nodejs/node",
  "prompt": "Are there any patterns in the bug reports that suggest systemic issues?"
}
```

## Error Handling

### Repository Not Scanned (404)
```json
{
  "detail": "Repository 'owner/repo' has not been scanned yet. Please scan it first using the /scan endpoint."
}
```

### No Issues Found (400)
```json
{
  "detail": "No issues found for repository 'owner/repo'. The repository may have no issues or the scan may have failed."
}
```

### Invalid Repository Format (400)
```json
{
  "detail": "Repository must be in format 'owner/repository-name'. Example: 'facebook/react'"
}
```

### GitHub API Rate Limit (400)
```json
{
  "detail": "GitHub API rate limit exceeded. Please provide a GITHUB_TOKEN in .env file for higher limits."
}
```

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | Yes | - | Your OpenAI API key |
| `GITHUB_TOKEN` | No | - | GitHub personal access token (increases rate limit from 60 to 5000/hour) |
| `OPENAI_MODEL` | No | `gpt-4-turbo-preview` | OpenAI model to use for analysis |
| `DATABASE_PATH` | No | `github_issues.db` | Path to SQLite database file |

### Large Repositories (3K+ Issues)

For repositories with thousands of issues, the application automatically:
- Sorts issues by creation date (most recent first)
- Analyzes the 200 most recent issues
- Includes a note in the response indicating the limitation

This approach ensures:
- Fast response times
- Stays within LLM token limits
- Focuses on the most relevant recent issues

## Project Structure

```
github-issues-analyzer/
├── src/
│   ├── app.py              # FastAPI application
│   ├── config/
│   │   └── settings.py     # Configuration management
│   ├── database/
│   │   └── connection.py   # SQLite connection & initialization
│   ├── models/
│   │   └── database.py     # Pydantic models
│   ├── libs/
│   │   ├── github_client.py   # GitHub API wrapper
│   │   └── openai_client.py   # OpenAI API wrapper
│   └── services/
│       ├── scan/
│       │   ├── schema.py   # Scan schemas
│       │   └── service.py  # Scan business logic
│       └── analyze/
│           ├── schema.py   # Analyze schemas
│           └── service.py  # Analyze business logic
├── main.py                 # Entry point
├── pyproject.toml          # Python dependencies and project config
├── .env                    # Environment variables (not in git)
├── .env.example           # Environment variables template
└── README.md              # This file
```

## Database Schema

### Repos Table
```sql
CREATE TABLE repos (
    id TEXT PRIMARY KEY,           -- "owner/repo" format
    name TEXT NOT NULL,
    created_at TIMESTAMP
);
```

### Issues Table
```sql
CREATE TABLE issues (
    id TEXT PRIMARY KEY,           -- "owner/repo#number" format
    repo_id TEXT NOT NULL,         -- References repos.id
    title TEXT NOT NULL,
    body TEXT,
    html_url TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL,
    FOREIGN KEY (repo_id) REFERENCES repos(id)
);
```

## Development

### Running with Auto-Reload
```bash
python main.py
```

### Running with Uvicorn Directly
```bash
uvicorn src.app:app --reload --host 0.0.0.0 --port 8000
```

### View API Documentation
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'src'"
**Solution:** Make sure you're running the application from the project root directory.

### Issue: "OpenAI API error: Incorrect API key"
**Solution:** Verify your `OPENAI_API_KEY` in the `.env` file is correct.

### Issue: "GitHub API rate limit exceeded"
**Solution:** Add a `GITHUB_TOKEN` to your `.env` file to increase the rate limit from 60 to 5000 requests per hour.

### Issue: "Repository not found"
**Solution:** Verify the repository format is correct (`owner/repo`) and the repository is public.

## Future Enhancements

- [ ] Pagination for analyze endpoint
- [ ] Caching of LLM responses
- [ ] Background job processing for large repositories
- [ ] Rate limiting
- [ ] Authentication/Authorization
- [ ] Issue update synchronization
- [ ] Advanced filtering (by labels, state, date range)
- [ ] Multiple LLM provider support
- [ ] Web UI for easier interaction

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
