"""
Main FastAPI application entry point.
Configures CORS, includes routers, and sets up the application.
"""

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text

from src.routes.auth import router as auth_router
from src.routes.datasets import router as datasets_router
from src.database import get_db

app = FastAPI(
    title="Analytics Platform API",
    description="Multi-tenant analytics platform for CSV data analysis",
    version="1.0.0"
)

# Configure CORS - allow credentials for HttpOnly cookies
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Frontend URL
    allow_credentials=True,  # Required for cookies
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(datasets_router)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "Ready", "service": "Analytics Platform API"}


@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """
    Detailed health check that verifies database connectivity.
    Returns status of all system components.
    """
    health_status = {
        "status": "healthy",
        "version": "1.0.0",
        "components": {
            "api": "healthy",
            "database": "healthy"
        }
    }

    # Check database connectivity
    try:
        db.execute(text("SELECT 1"))
        health_status["components"]["database"] = "healthy"
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["components"]["database"] = f"unhealthy: {str(e)}"

    return health_status
