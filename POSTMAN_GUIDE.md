# Postman Collection Guide

This guide explains how to use the Postman collection for testing the GitHub Issues Analyzer API.

## Import the Collection

1. **Open Postman**
2. **Click "Import"** in the top left
3. **Select the file**: `GitHub-Issues-Analyzer.postman_collection.json`
4. **Click "Import"**

The collection will appear in your Postman workspace with all endpoints ready to use.

## Collection Structure

The collection includes 11 requests organized as follows:

### Health Check
- **GET /** - Verify the API is running

### Scan Endpoints (5 requests)
- **Scan Repository - Small (Hello World)** - Test with a small repo
- **Scan Repository - Large (VS Code)** - Test with a large repo (100+ issues)
- **Scan Repository - Custom** - Scan any repo using variables
- **Scan Repository - Invalid Format (Error)** - Test validation errors
- **Scan Repository - Not Found (Error)** - Test error handling

### Analyze Endpoints (5 requests)
- **Analyze - Theme Analysis** - Identify common themes
- **Analyze - Priority Recommendation** - Get prioritization advice
- **Analyze - Sentiment Analysis** - Analyze sentiment and urgency
- **Analyze - Custom Prompt** - Use custom repository and prompt
- **Analyze - No Cached Issues (Error)** - Test error when repo not scanned

## Configuration Variables

The collection uses variables that you can customize:

| Variable | Default Value | Description |
|----------|---------------|-------------|
| `base_url` | `http://localhost:8000` | API server URL |
| `custom_repo` | `facebook/react` | Repository for custom requests |
| `custom_prompt` | `What are the main issues users are facing?` | Prompt for custom analysis |

### How to Change Variables

1. **Click on the collection name** in Postman
2. **Select the "Variables" tab**
3. **Edit the "Current Value" column**
4. **Click "Save"**

## Quick Start Workflow

### 1. Start the Server

```bash
uvicorn main:app --reload
```

Verify it's running at `http://localhost:8000`

### 2. Test Health Check

Run the **Health Check** request to verify connectivity.

**Expected Response:**
```json
{
  "name": "GitHub Issues Analyzer",
  "version": "1.0.0",
  "endpoints": { ... }
}
```

### 3. Scan a Repository

Run **Scan Repository - Small (Hello World)**

**Expected Response:**
```json
{
  "repo": "octocat/Hello-World",
  "issues_fetched": <number>,
  "cached_successfully": true
}
```

### 4. Analyze Issues

Run **Analyze - Theme Analysis**

**Expected Response:**
```json
{
  "analysis": "<LLM-generated analysis text>"
}
```

## Automated Tests

Several requests include automated tests that run after the response is received:

### Scan Requests Tests
- ✅ Status code is 200
- ✅ Response has required fields (repo, issues_fetched, cached_successfully)
- ✅ Caching was successful

### Analyze Requests Tests
- ✅ Status code is 200
- ✅ Response has analysis field
- ✅ Analysis is a non-empty string

### Error Handling Tests
- ✅ Invalid format returns 422 (Validation Error)
- ✅ Not found returns 400 (Bad Request)
- ✅ Unscanned repo returns 404 (Not Found)

View test results in the **Test Results** tab after running a request.

## Example Usage Scenarios

### Scenario 1: Analyze a New Repository

1. **Set custom repository**:
   - Edit `custom_repo` variable to your target repo (e.g., `nodejs/node`)

2. **Scan the repository**:
   - Run **Scan Repository - Custom**
   - Wait for completion (may take 10-30 seconds for large repos)

3. **Analyze with different prompts**:
   - Edit `custom_prompt` variable
   - Run **Analyze - Custom Prompt**
   - Try different prompts:
     - "What are the critical bugs?"
     - "Which features are most requested?"
     - "Summarize user pain points"

### Scenario 2: Compare Multiple Repositories

1. **Scan first repository**:
   ```
   Set custom_repo = "facebook/react"
   Run Scan Repository - Custom
   ```

2. **Analyze first repository**:
   ```
   Set custom_prompt = "What are the top 3 themes?"
   Run Analyze - Custom Prompt
   ```

3. **Repeat for second repository**:
   ```
   Set custom_repo = "vuejs/vue"
   Run Scan Repository - Custom
   Run Analyze - Custom Prompt
   ```

### Scenario 3: Test Error Handling

Run the error test requests in sequence:
1. **Scan Repository - Invalid Format (Error)** - Should return 422
2. **Scan Repository - Not Found (Error)** - Should return 400
3. **Analyze - No Cached Issues (Error)** - Should return 404

## Tips & Best Practices

### 1. Use Environments
Create different environments for local, staging, and production:
- **Local**: `base_url = http://localhost:8000`
- **Production**: `base_url = https://your-domain.com`

### 2. Save Responses
Use the **Save Response** button to keep interesting analyses for later reference.

### 3. Collections Runner
Run multiple requests in sequence:
1. Click the collection name
2. Click **Run**
3. Select requests to run
4. Click **Run GitHub Issues Analyzer**

This is useful for regression testing.

### 4. Chain Requests
You can automatically run analyze after scan using Postman's test scripts:

Add to **Scan Repository** test:
```javascript
// After successful scan, run analyze
if (pm.response.code === 200) {
    postman.setNextRequest("Analyze - Theme Analysis");
}
```

## Troubleshooting

### Error: "Could not get response"
- **Check**: Is the server running? (`uvicorn main:app --reload`)
- **Check**: Is the base_url correct?

### Error: "GitHub API rate limit exceeded"
- **Solution**: Add `GITHUB_TOKEN` to your `.env` file
- **Info**: Without token: 60 requests/hour, With token: 5000 requests/hour

### Error: "OpenAI API error"
- **Check**: Is `OPENAI_API_KEY` set in `.env`?
- **Check**: Is the API key valid?

### Error: "No cached issues"
- **Solution**: Run a `/scan` request first before `/analyze`
- **Note**: Each repository must be scanned before analysis

## Advanced Features

### Pre-request Scripts

Add custom logic before requests run:

```javascript
// Set dynamic repository based on date
const repos = ["facebook/react", "vuejs/vue", "angular/angular"];
const index = new Date().getDate() % repos.length;
pm.collectionVariables.set("custom_repo", repos[index]);
```

### Response Visualization

View analysis in a nicer format:
1. Go to **Visualize** tab
2. Add this script in Tests:

```javascript
var template = `
<div style="font-family: Arial; padding: 20px;">
    <h2>Analysis Result</h2>
    <pre>{{response.analysis}}</pre>
</div>
`;

pm.visualizer.set(template, {
    response: pm.response.json()
});
```

## Collection Statistics

Run the collection and view:
- **Total Requests**: 11
- **Expected Pass Rate**: 91% (10/11 pass, 1 error test included)
- **Average Response Time**: Scan ~5-15s, Analyze ~10-30s
- **Coverage**: All endpoints, success and error cases

## Export & Share

To share this collection:
1. Right-click the collection
2. Select **Export**
3. Choose **Collection v2.1**
4. Share the JSON file

## Support

For issues or questions:
- Check the main README.md
- Review TESTING.md for detailed test cases
- Check server logs for error details
