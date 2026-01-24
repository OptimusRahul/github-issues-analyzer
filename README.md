# GitHub Issues Analyzer

A FastAPI-based service that fetches GitHub issues and analyzes them using Large Language Models (LLMs).

## Features

- **Fetch & Cache**: Scan GitHub repositories and cache open issues locally
- **LLM Analysis**: Analyze cached issues using natural language prompts
- **REST API**: Clean, documented API with automatic OpenAPI docs
- **Persistent Storage**: SQLite database for reliable data persistence

## Architecture

The application follows a layered architecture:

```
API Layer (FastAPI) → Services (Business Logic) → Libraries (External APIs) → Database (SQLite)
```

### Project Structure

```
github-issues-analyzer/
├── main.py                      # FastAPI application entry point
├── requirements.txt             # Python dependencies
├── .env.example                 # Example environment variables
├── .gitignore                   # Git ignore rules
├── README.md                    # This file
└── src/
    ├── config/
    │   └── settings.py          # Configuration management
    ├── database/
    │   └── connection.py        # Database connection setup
    ├── lib/
    │   ├── github_client.py     # GitHub API wrapper (PyGithub)
    │   └── openai_client.py     # OpenAI API wrapper
    ├── models/
    │   └── database.py          # Database schema
    └── services/
        ├── scan/
        │   ├── service.py       # Scan business logic
        │   └── schema.py        # Pydantic models
        └── analyze/
            ├── service.py       # Analyze business logic
            └── schema.py        # Pydantic models
```

## Setup Instructions

### Prerequisites

- Python 3.10 or higher
- GitHub account (optional, for higher API rate limits)
- OpenAI API key (required)

### Installation

1. **Clone the repository**

```bash
git clone <repository-url>
cd github-issues-analyzer
```

2. **Create a virtual environment**

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**

```bash
pip install -r requirements.txt
```

4. **Configure environment variables**

Copy the example environment file and add your API keys:

```bash
cp .env.example .env
```

Edit `.env` and add your credentials:

```env
# Required: OpenAI API key
OPENAI_API_KEY=your_openai_api_key_here

# Optional: GitHub token (increases rate limit from 60 to 5000 requests/hour)
GITHUB_TOKEN=your_github_token_here

# Optional: OpenAI model (defaults to gpt-4-turbo-preview)
OPENAI_MODEL=gpt-4-turbo-preview

# Optional: Database path (defaults to github_issues.db)
DATABASE_PATH=github_issues.db
```

## Running the Application

Start the FastAPI server:

```bash
uvicorn main:app --reload
```

The server will start at `http://localhost:8000`

### Interactive API Documentation

Once the server is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## API Usage

### Using Postman (Recommended)

A complete Postman collection is included for easy testing:

1. **Import the collection**: `GitHub-Issues-Analyzer.postman_collection.json`
2. **Follow the guide**: See `POSTMAN_GUIDE.md` for detailed instructions
3. **11 pre-configured requests** with automated tests included

The collection includes:
- Health check endpoint
- Multiple scan scenarios (small/large repos, error cases)
- Various analysis prompts (themes, priorities, sentiment)
- Automated validation tests
- Customizable variables

### Using cURL

### 1. Scan a Repository

Fetch and cache all open issues from a GitHub repository:

```bash
curl -X POST http://localhost:8000/scan \
  -H "Content-Type: application/json" \
  -d '{"repo": "octocat/Hello-World"}'
```

**Response:**
```json
{
  "repo": "octocat/Hello-World",
  "issues_fetched": 42,
  "cached_successfully": true
}
```

### 2. Analyze Issues

Analyze cached issues using a natural language prompt:

```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "repo": "octocat/Hello-World",
    "prompt": "What are the common themes in these issues and which should be prioritized?"
  }'
```

**Response:**
```json
{
  "analysis": "Based on the 42 open issues in this repository, here are the key themes:\n\n1. Documentation improvements (15 issues)...\n\n[LLM-generated analysis]"
}
```

## Storage Choice Rationale

### Why SQLite?

We chose **SQLite** as the storage solution for the following reasons:

1. **ACID Properties**: Ensures data consistency and reliability with atomic transactions
2. **Query Flexibility**: SQL support enables complex queries and future feature additions
3. **Easy Migration**: Schema design allows seamless migration to PostgreSQL for production
4. **Indexed Lookups**: Handles multiple repositories efficiently with indexed queries
5. **Persistent Storage**: Data survives server restarts with minimal setup
6. **Zero Configuration**: No separate database server required for MVP
7. **Production-Ready**: Used by major applications (browsers, mobile apps) at scale

### Database Schema

The application uses a normalized relational schema:

- **repositories**: Stores repository metadata with UUID primary key
- **issues**: Stores issue details with foreign key to repositories
- **Indexes**: Optimized for lookups by repository name and joins

This design supports:
- Multiple repositories efficiently
- Fast queries by repository
- CASCADE deletes for data consistency
- Future migration to PostgreSQL

## Development Prompts Log

This section documents the AI-assisted development process as required by the project specification.

### Planning Phase

1. **Initial Architecture Design**
   - Prompt: "Design a FastAPI application with layered architecture for fetching GitHub issues and analyzing them with LLMs. Use SQLite for storage."
   - Result: Established the services-based architecture with clear separation of concerns

2. **Database Schema Design**
   - Prompt: "Design a SQLite schema for storing GitHub repositories and issues with proper normalization and indexing"
   - Result: Created normalized schema with UUID primary keys and foreign key relationships

### Implementation Phase

3. **Configuration Management**
   - Prompt: "Implement Pydantic BaseSettings for managing environment variables with validation"
   - Result: Created `src/config/settings.py` with type-safe configuration

4. **GitHub Client Implementation**
   - Prompt: "Create a wrapper around PyGithub that fetches open issues with pagination handling"
   - Result: Implemented `GitHubClient` with error handling and rate limit management

5. **OpenAI Client Implementation**
   - Prompt: "Create an OpenAI client that formats GitHub issues and handles token limits for LLM analysis"
   - Result: Implemented context management with truncation for large issue sets

6. **Service Layer**
   - Prompt: "Implement scan and analyze services with database operations and error handling"
   - Result: Created clean service interfaces with transaction management

7. **API Endpoints**
   - Prompt: "Create FastAPI endpoints with proper error handling and OpenAPI documentation"
   - Result: Implemented RESTful endpoints with comprehensive error responses

### LLM Prompt Engineering

8. **System Prompt for Analysis**
   - Used prompt: "You are an expert at analyzing GitHub issues. Provide actionable insights based on the data provided. Be specific, concise, and focus on patterns and priorities."
   - This guides the LLM to provide practical, structured analysis

9. **Issue Formatting**
   - Structured issues with: title, creation date, URL, and truncated body
   - Ensures LLM has context while managing token limits

## Testing Checklist

- [ ] Test `/scan` with small repository (e.g., `octocat/Hello-World`)
- [ ] Test `/scan` with large repository (100+ issues)
- [ ] Test `/analyze` before scanning (should return 404)
- [ ] Test `/analyze` with various prompts
- [ ] Test invalid repository format
- [ ] Test with missing environment variables
- [ ] Test repository with 0 open issues

## Example Use Cases

### 1. Priority Analysis
```bash
# Scan a repository
curl -X POST http://localhost:8000/scan \
  -H "Content-Type: application/json" \
  -d '{"repo": "microsoft/vscode"}'

# Analyze for priorities
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "repo": "microsoft/vscode",
    "prompt": "What are the top 3 most critical issues that should be addressed first?"
  }'
```

### 2. Theme Discovery
```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "repo": "facebook/react",
    "prompt": "What are the common themes across these issues?"
  }'
```

### 3. Sentiment Analysis
```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "repo": "nodejs/node",
    "prompt": "Analyze the sentiment and urgency level of these issues"
  }'
```

## Scalability Considerations

### Current MVP
- Single uvicorn process
- SQLite with WAL mode for concurrent reads
- Synchronous API calls

### Future Enhancements
1. **Async Operations**: Convert to `async def` endpoints with `httpx`
2. **PostgreSQL**: Migrate to PostgreSQL for production workloads
3. **Multi-Worker**: Deploy with multiple uvicorn workers
4. **Caching Layer**: Add Redis for LLM response caching
5. **Background Jobs**: Use Celery for long-running scans
6. **Rate Limiting**: Implement API rate limiting for production

## Troubleshooting

### GitHub API Rate Limit
- **Symptom**: "GitHub API rate limit exceeded"
- **Solution**: Add `GITHUB_TOKEN` to `.env` to increase limit from 60 to 5000 requests/hour

### OpenAI API Errors
- **Symptom**: "OpenAI API error: Incorrect API key"
- **Solution**: Verify `OPENAI_API_KEY` in `.env` is correct

### Database Locked
- **Symptom**: "database is locked"
- **Solution**: Ensure WAL mode is enabled (done automatically). Check no other process is writing.

## License

MIT

## Contributing

Contributions welcome! Please ensure code follows the established architecture patterns.
