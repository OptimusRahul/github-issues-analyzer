# Testing Guide

This document outlines the testing procedures for the GitHub Issues Analyzer MVP.

## Pre-Testing Setup

1. **Install Dependencies**
```bash
pip install -r requirements.txt
```

2. **Configure Environment**
Create a `.env` file with your API keys:
```bash
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY and optionally GITHUB_TOKEN
```

3. **Start the Server**
```bash
uvicorn main:app --reload
```

Server should start at `http://localhost:8000`

## Testing Checklist

### ✅ 1. Basic Server Health Check

**Test:** Verify server is running
```bash
curl http://localhost:8000/
```

**Expected:** JSON response with API information

---

### ✅ 2. Test /scan with Small Repository

**Test:** Scan a small repository
```bash
curl -X POST http://localhost:8000/scan \
  -H "Content-Type: application/json" \
  -d '{"repo": "octocat/Hello-World"}'
```

**Expected Response:**
```json
{
  "repo": "octocat/Hello-World",
  "issues_fetched": <number>,
  "cached_successfully": true
}
```

**Verify:**
- Issues are fetched successfully
- Database file `github_issues.db` is created
- No errors in server logs

---

### ✅ 3. Test /scan with Large Repository (100+ issues)

**Test:** Validate pagination handling
```bash
curl -X POST http://localhost:8000/scan \
  -H "Content-Type: application/json" \
  -d '{"repo": "microsoft/vscode"}'
```

**Expected:**
- Successfully fetches all issues (PyGithub handles pagination)
- Response shows total count (likely 100+)
- Database stores all issues

**Verify:**
- Check database has correct number of issues
- No pagination errors in logs

---

### ✅ 4. Test /analyze Before Scanning (Error Case)

**Test:** Try to analyze without scanning first
```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "repo": "some/unscanned-repo",
    "prompt": "Analyze these issues"
  }'
```

**Expected Response:** HTTP 404
```json
{
  "detail": "No cached issues for repository 'some/unscanned-repo'. Please run /scan first to fetch and cache issues."
}
```

---

### ✅ 5. Test /analyze with Various Prompts

After scanning a repository, test different analysis prompts:

**A. Theme Analysis**
```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "repo": "octocat/Hello-World",
    "prompt": "What are the common themes in these issues?"
  }'
```

**B. Priority Analysis**
```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "repo": "octocat/Hello-World",
    "prompt": "Which issues should be prioritized and why?"
  }'
```

**C. Sentiment Analysis**
```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "repo": "octocat/Hello-World",
    "prompt": "Summarize the sentiment of these issues"
  }'
```

**Expected:**
- Each returns meaningful LLM analysis
- Responses are relevant to the prompt
- No token limit errors

---

### ✅ 6. Test Invalid Repository Format

**Test:** Invalid repo format validation
```bash
curl -X POST http://localhost:8000/scan \
  -H "Content-Type: application/json" \
  -d '{"repo": "invalid-format"}'
```

**Expected Response:** HTTP 422 (Validation Error)
```json
{
  "detail": [
    {
      "loc": ["body", "repo"],
      "msg": "Repository must be in format \"owner/name\"",
      "type": "value_error"
    }
  ]
}
```

---

### ✅ 7. Test Non-Existent Repository

**Test:** Repository that doesn't exist
```bash
curl -X POST http://localhost:8000/scan \
  -H "Content-Type: application/json" \
  -d '{"repo": "this-owner/does-not-exist-12345"}'
```

**Expected Response:** HTTP 400
```json
{
  "detail": "Repository 'this-owner/does-not-exist-12345' not found"
}
```

---

### ✅ 8. Test Repository with 0 Open Issues

**Test:** Repository with no open issues
```bash
curl -X POST http://localhost:8000/scan \
  -H "Content-Type: application/json" \
  -d '{"repo": "<repo-with-no-issues>"}'
```

**Expected:**
- Scan succeeds with `issues_fetched: 0`
- Analyze returns message about no open issues

---

### ✅ 9. Test Missing Environment Variables

**Test:** Start server without required OPENAI_API_KEY

1. Remove or comment out `OPENAI_API_KEY` in `.env`
2. Restart server

**Expected:**
- Server fails to start with validation error
- Error message indicates missing required field

---

### ✅ 10. Test Interactive API Documentation

**Test:** Access Swagger UI
1. Open browser to `http://localhost:8000/docs`
2. Try executing requests through the UI

**Expected:**
- Documentation loads successfully
- Can test both endpoints interactively
- Schemas are properly displayed

---

## Database Verification

After running tests, verify database integrity:

```bash
# Install sqlite3 if needed
sqlite3 github_issues.db

# Check repositories table
SELECT * FROM repositories;

# Check issues count
SELECT repo_name, COUNT(*) FROM repositories r
JOIN issues i ON r.id = i.repository_id
GROUP BY r.id;

# Verify indexes exist
.indexes

# Exit
.exit
```

**Expected:**
- Repositories table has correct entries
- Issues table has foreign key relationships
- Indexes are created

---

## Performance Testing

### Test Large Repository Scan Time

```bash
time curl -X POST http://localhost:8000/scan \
  -H "Content-Type: application/json" \
  -d '{"repo": "facebook/react"}'
```

**Monitor:**
- Scan completion time
- Memory usage
- No timeout errors

### Test Analysis with Many Issues

After scanning a large repo:
```bash
time curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "repo": "facebook/react",
    "prompt": "Analyze all issues"
  }'
```

**Monitor:**
- Token truncation handling
- Response time
- Quality of analysis

---

## Rate Limiting Tests

### Without GitHub Token
1. Remove `GITHUB_TOKEN` from `.env`
2. Scan multiple repositories quickly

**Expected:**
- May hit rate limit after ~60 requests/hour
- Error message about rate limiting

### With GitHub Token
1. Add `GITHUB_TOKEN` to `.env`
2. Repeat test

**Expected:**
- Much higher rate limit (5000/hour)
- No rate limit errors

---

## Edge Cases

### Test Re-scanning Same Repository
```bash
# Scan once
curl -X POST http://localhost:8000/scan \
  -H "Content-Type: application/json" \
  -d '{"repo": "octocat/Hello-World"}'

# Scan again
curl -X POST http://localhost:8000/scan \
  -H "Content-Type: application/json" \
  -d '{"repo": "octocat/Hello-World"}'
```

**Expected:**
- Old issues are deleted
- New issues are inserted
- No duplicate issues in database

---

## Logging and Error Tracking

During all tests, monitor server logs for:
- Unexpected errors
- Database warnings
- API rate limit warnings
- Performance bottlenecks

---

## Demo Scenario

For a comprehensive demo:

1. **Scan a popular repository**
```bash
curl -X POST http://localhost:8000/scan \
  -H "Content-Type: application/json" \
  -d '{"repo": "microsoft/vscode"}'
```

2. **Perform analysis**
```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "repo": "microsoft/vscode",
    "prompt": "What are the top 3 themes in these issues and which should be prioritized?"
  }'
```

3. **Show interactive docs**
- Open `http://localhost:8000/docs`
- Demonstrate auto-generated API documentation

---

## Success Criteria

All tests pass if:
- ✅ Server starts without errors
- ✅ Both endpoints respond correctly
- ✅ Database operations are atomic
- ✅ Error handling works as expected
- ✅ LLM analysis is relevant and useful
- ✅ Validation catches invalid inputs
- ✅ Documentation is accessible and accurate
