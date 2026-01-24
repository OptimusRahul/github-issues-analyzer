"""FastAPI application for GitHub Issues Analyzer."""

import logging
from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager

from src.database.connection import init_db
from src.services.scan.service import scan_repository
from src.services.scan.schema import ScanRequest, ScanResponse
from src.services.analyze.service import analyze_repository
from src.services.analyze.schema import AnalyzeRequest, AnalyzeResponse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    logger.info("Starting GitHub Issues Analyzer application...")
    try:
        init_db()
        logger.info("Application startup complete")
    except Exception as e:
        logger.error(f"Failed to initialize application: {str(e)}", exc_info=True)
        raise
    yield
    logger.info("Application shutting down...")


app = FastAPI(
    title="GitHub Issues Analyzer",
    description="Fetch and analyze GitHub issues using LLMs",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/")
def root():
    """Root endpoint with API information."""
    logger.info("Root endpoint accessed")
    return {
        "name": "GitHub Issues Analyzer",
        "version": "1.0.0",
        "endpoints": {
            "POST /scan": "Fetch and cache issues from a GitHub repository",
            "POST /analyze": "Analyze cached issues using LLM",
            "GET /docs": "Interactive API documentation"
        }
    }


@app.post("/scan", response_model=ScanResponse)
def scan_endpoint(request: ScanRequest):
    """
    Fetch all open issues from a GitHub repository and cache them locally.
    
    This endpoint:
    - Fetches open issues from the GitHub REST API
    - Stores them in the local SQLite database
    - Returns a summary of the operation
    """
    logger.info(f"Scan endpoint called for repository: {request.repo}")
    try:
        result = scan_repository(request.repo)
        logger.info(f"Scan completed successfully for {request.repo}")
        return ScanResponse(**result)
    except ValueError as e:
        # Repository not found or invalid format
        logger.warning(f"Validation error for {request.repo}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Other errors (API, database, etc.)
        logger.error(f"Error scanning {request.repo}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze_endpoint(request: AnalyzeRequest):
    """
    Analyze cached GitHub issues using a natural language prompt.
    
    This endpoint:
    - Retrieves cached issues from the database
    - Sends them to an LLM with the user's prompt
    - Returns the LLM's analysis
    
    Note: You must run /scan first to cache issues before analyzing.
    """
    logger.info(f"Analyze endpoint called for repository: {request.repo}")
    try:
        result = analyze_repository(request.repo, request.prompt)
        logger.info(f"Analysis completed successfully for {request.repo}")
        return AnalyzeResponse(**result)
    except ValueError as e:
        # Repository not found in cache
        logger.warning(f"Repository not found in cache: {request.repo}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        # Other errors (API, database, etc.)
        logger.error(f"Error analyzing {request.repo}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
