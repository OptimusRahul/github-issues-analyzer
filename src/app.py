"""FastAPI application entry point with async support"""

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import close_database, get_db_session, init_database
from src.services.analyze import AnalyzeService
from src.services.analyze.schema import AnalyzeRequest, AnalyzeResponse
from src.services.scan import ScanService
from src.services.scan.schema import ScanRequest, ScanResponse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup and cleanup on shutdown"""
    logger.info("Initializing database...")
    await init_database()
    logger.info("Database initialized successfully")
    yield
    logger.info("Closing database connections...")
    await close_database()
    logger.info("Application shutdown complete")


# Initialize FastAPI application
app = FastAPI(
    title="GitHub Issues Analyzer",
    description="Analyze GitHub issues using LLM with local caching - Async Version",
    version="2.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
scan_service = ScanService()
analyze_service = AnalyzeService()


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle uncaught exceptions"""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500, content={"detail": "An internal server error occurred", "error": str(exc)}
    )


# @app.get("/")
# async def root():
#     """Root endpoint with API information"""
#     return {
#         "name": "GitHub Issues Analyzer API",
#         "version": "2.0.0",
#         "architecture": "Async with SQLAlchemy",
#         "endpoints": {
#             "/scan": "POST - Scan and cache GitHub repository issues",
#             "/analyze": "POST - Analyze cached issues using LLM",
#             "/health": "GET - Health check endpoint",
#         },
#     }


# @app.get("/health")
# async def health_check():
#     """Health check endpoint"""
#     return {
#         "status": "healthy",
#         "service": "github-issues-analyzer",
#         "version": "2.0.0",
#         "async": True,
#     }


@app.post("/scan", response_model=ScanResponse)
async def scan(request: ScanRequest, db: AsyncSession = Depends(get_db_session)):
    """
    Scan a GitHub repository and cache its issues

    Args:
        request: ScanRequest with repository in 'owner/repo' format
        db: Database session

    Returns:
        ScanResponse with scan results

    Raises:
        HTTPException: If validation fails or GitHub API errors occur
    """
    try:
        logger.info(f"Scanning repository: {request.repo}")
        result = await scan_service.scan_repository(request.repo, db)
        logger.info(f"Successfully scanned {request.repo}: {result.issues_fetched} issues cached")
        return result
    except ValueError as e:
        logger.error(f"Scan failed for {request.repo}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error scanning {request.repo}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest, db: AsyncSession = Depends(get_db_session)):
    """
    Analyze cached GitHub issues using LLM

    Args:
        request: AnalyzeRequest with repository and user prompt
        db: Database session

    Returns:
        AnalyzeResponse with LLM analysis

    Raises:
        HTTPException: If repository not scanned, no issues found, or LLM errors occur
    """
    try:
        logger.info(f"Analyzing repository: {request.repo}")
        result = await analyze_service.analyze_repository(request.repo, request.prompt, db)
        logger.info(f"Successfully analyzed {request.repo}")
        return result
    except HTTPException:
        # Re-raise HTTP exceptions as-is (they already have proper status codes)
        raise
    except Exception as e:
        logger.error(f"Unexpected error analyzing {request.repo}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
