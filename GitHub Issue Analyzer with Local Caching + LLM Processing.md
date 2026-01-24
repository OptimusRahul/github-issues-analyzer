# **GitHub Issue Analyzer with Local Caching \+ LLM Processing**

## **Overview**

Build a small service with two endpoints that can:

* Fetch and locally cache GitHub issues from a repository  
* Analyze the cached issues using a natural-language prompt and an LLM

You are encouraged to use AI coding tools like Cursor, Claude Code, ChatGPT, etc.  
**Please note that we expect the coding assignment to be in a working state. In the first round, we'll do a live demo and testing of this coding assignment.**  
---

## **What You Need to Build**

You will build a server (any language or framework is fine) that provides the following:  
---

## **1\. Endpoint: POST /scan**

### **Purpose**

Fetch all **open issues** from a given GitHub repository and cache them locally.

### **Request format**

`{`  
  `"repo": "owner/repository-name"`  
`}`

### **Expected behavior**

* Fetch all **open issues** from the GitHub REST API.  
* Extract and store at minimum:  
* `id`  
* `title`  
* `body`  
* `html_url`  
* `created_at`  
* Cache these issues locally using **one storage approach of your choice**:

### **Allowed storage options**

You must choose *one* of:

* **In-memory storage**  
* Fast, simple  
* Clears when server restarts  
* **JSON file storage**  
* Easy to inspect  
* Slower for large datasets  
* **SQLite**  
* Most durable  
* Slightly more setup

Document your choice and reasoning briefly in the README.

### **Response**

Return a summary:  
`{`  
  `"repo": "owner/repository-name",`  
  `"issues_fetched": 42,`  
  `"cached_successfully": true`  
`}`  
---

## **2\. Endpoint: POST /analyze**

### **Purpose**

Take a repo name and a natural-language prompt, retrieve cached issues for that repo, and analyze them using an LLM.

### **Request format**

`{`  
  `"repo": "owner/repository-name",`  
  `"prompt": "Find themes across recent issues and recommend what the maintainers should fix first"`  
`}`

### **Expected behavior**

* Look up cached issues for the given repo  
* Combine the prompt \+ cached issues into an LLM request  
* Let the LLM generate the analysis (no keyword classification; fully natural-language interpretation)  
* Return the LLM’s output in a readable response

### **Requirements**

* You may use any LLM provider or local model  
* Keep context size in mind (chunking is acceptable if needed)  
* Handle edge cases such as:  
* Repo not yet scanned  
* No issues cached  
* LLM errors

### **Response example**

`{`  
  `"analysis": "<LLM-generated text here>"`  
`}`  
**No UI is needed; this is strictly a backend task.**  
---

# **4\. Deliverables**

* A public GitHub repository containing:  
* Source code  
* README with:  
* How to run the server  
* Why you chose the specific local storage option  
* A list of prompts you used while building this project, including: (you can add this in README)  
* Prompts you sent to AI coding tools for help  
* Prompts used to design the code, fix errors, or generate logic  
* Prompts used for constructing the final LLM request inside the analyze endpoint (They don’t have to be perfect; this is for understanding your workflow.)

