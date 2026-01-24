Initial prompt

Act as an expert in software engineering

We're building a Github Issue Analyzer with Local Caching + LLM processing.

Product Overview:
The product that we're building is an MVP, the whole idea of the product is to pull the issues from a repo. Use LLM to analyze the issues.

Product Workflow:
Repo Name -> Fetch Issues -> Store in DB -> Analyze -> Pull the issues from the database + User_Prompt -> LLM -> Response

Tech Requirements:
- Python with FAST API using Pydantic
- SQLLite
- Github Package
- OpenAI Package

Project Architecture:
- src
 - config (folder that holds env variables)
 - database (folder that holds the database connection)
 - models (folder that holds all the models related to the project)
 - libs (folder that holds all the external dependecies)
 - services (folder that holds all the services for the project)
 - app.py (entry point)


Requirements:
1. /scan endpoint:
 a. It will take input in `{owner}/{repo}` format basic validation checks for the format of the string.
 b. Once the input it validation the Scan Service will be called and that will trigger the Github Package in libs to pull all the issues of the repos.
 c. Once the repo issues are fetched store the issues in the database

 Workflow: API call /scan -> validator -> ScanService -> GithubAPI (specific class in Libs folder) -> ScanService -> SQLLite

 DB Schema -> 
    repo schema
        id: string
        name: string
        created_at: date
    issues schema
        id: string
        repo_id: string
        title: string
        body: string
        html_url: string
        created_at: date
 API response:
  {
    "repo": "owner/repository-name",
    "issues_fetched": 42,
    "cached_successfully": true
  }

2. /analyze endpoint:
 a. It will take input in `{owner}/{repo}` format and user_prompt basic validation checks for the format of the string and user input exists or not.
 b. Once the input it validation the Analyze Service will be called and that will trigger the Open Package with available issues fetched from the database for the repository and the user prompt.
 c. Once the LLM response is recieved send return it

 Workflow: API call /analyze -> validator -> AnalyzeService -> OpenAPI (specific class in Libs folder) -> AnalyzeService -> Response

 Failure scenarios:
    - Repo not scanned
    - No issues cached
    - LLM Errors

 API Response:
  {
    "repo": "owner/repository-name",
    "prompt": "Find themes across recent issues and recommend what the maintainers should fix first"
  }

Edge case:
If a repo has 3K issues how are we going to pass in LLM?


Follow up prompts:

1. 
<@/Users/ghost/.cursor/projects/Users-ghost-Developer-github-issues-analyzer/terminals/5.txt:29-32> Got some error which is not visible in the terminal but got in API response, add the logs and fix this issue
{
  "detail": "Failed to analyze issues with LLM: Client.__init__() got an unexpected keyword argument 'proxies'"
}

2. 
This project isn't using async / await @src/services @src/app.py 
- All the services should be class based
- Use the async await for all the servives
- For the Database Operation use SQLAlchemy

3. make the application to use "uv"

4. remove everything related to pip, don't create any files

5. <@/Users/ghost/.cursor/projects/Users-ghost-Developer-github-issues-analyzer/terminals/5.txt:12-59> fix this error while installing the package

6. can't we run main.py with uv?

7. @src/libs/openai_client.py where in this file we're chunking the issues?

8. Don't implement any thing. Now tell me about the possible approaches (for handling large numbers of issues like 3K+)

9. @src/models/issues_model.py this is still in use?

10. @GitHub Issue Analyzer with Local Caching + LLM Processing.md take this file in context and add default for the request @src/services/analyze @src/services/scan as per the documents

11. @src/libs/github_client.py this should fetch only open issues

12. @prompt.txt convert this to a md file

13. @src/services/scan/service.py In this service add the check if a repo exists then return a proper that repo is scanned


Analyze Prompt:
# Create system prompt
system_prompt = (
    "You are an expert at analyzing GitHub issues. "
    "You help maintainers understand patterns, themes, and priorities in their issue tracker. "
    "Provide clear, actionable insights based on the issues provided."
)

# Create user prompt with context
full_prompt = f"""
    Analyze the following GitHub issues and respond to this request:

    User Prompt: {user_prompt}

    Issues to analyze:
    {issues_text}
"""
logger.info(f"Full prompt: {full_prompt}")