#!/usr/bin/env python3
"""
Refactored RAG-Anything API Server - Main Entry Point
Clean, focused FastAPI application setup with proper dependency injection
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.settings import get_settings
from config.cors import get_cors_config
from core.lifecycle import startup_handler, shutdown_handler
from api.v1 import router as api_v1_router
from middleware.error_handler import ErrorHandlingMiddleware
from middleware.logging_middleware import LoggingMiddleware

# Create FastAPI app instance
settings = get_settings()
app = FastAPI(
    title="RAG-Anything API",
    version="2.0.0",
    description="Modular RAG API with multimodal document processing",
)

# Add middleware
cors_config = get_cors_config()
app.add_middleware(CORSMiddleware, **cors_config)
app.add_middleware(ErrorHandlingMiddleware)
app.add_middleware(LoggingMiddleware)

# Register API routes
app.include_router(api_v1_router, prefix="/api/v1")

# Register lifecycle events
app.add_event_handler("startup", startup_handler)
app.add_event_handler("shutdown", shutdown_handler)

# Health check endpoint (simple, no dependencies)
@app.get("/health")
async def health_check():
    """Basic health check endpoint"""
    return {
        "status": "healthy",
        "message": "RAG-Anything API is running",
        "version": "2.0.0"
    }

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting Refactored RAG-Anything API Server")
    print(f"📋 API Documentation: http://{settings.host}:{settings.port}/docs")
    print(f"🔍 Health Check: http://{settings.host}:{settings.port}/health")
    
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level
    )