#!/usr/bin/env python3
"""
Main FastAPI application entry point.
This file creates the app object that uvicorn references in run_api.py
"""

from .rag_api_server import app

# Export the app for uvicorn
__all__ = ['app']