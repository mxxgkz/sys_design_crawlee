#!/usr/bin/env python3
"""
Common setup for all RAG app scripts.

This module ensures all scripts use the correct working directory and paths.
Import this at the top of any RAG app script to avoid path issues.

Usage:
    from rag_app.common_setup import setup_environment
    setup_environment()
"""

import sys
import os
from pathlib import Path


def setup_environment():
    """
    Set up the environment for RAG app scripts.
    This should be called at the beginning of every RAG app script.
    """
    # Get project root directory
    project_root = Path(__file__).parent.parent
    
    # Add project root to Python path
    sys.path.insert(0, str(project_root))
    
    # Change to project root directory so all paths work correctly
    os.chdir(project_root)
    
    return project_root


def get_project_root():
    """Get the project root directory."""
    return Path(__file__).parent.parent


def get_storage_path():
    """Get the storage directory path."""
    return get_project_root() / "storage"


def get_database_path():
    """Get the database file path."""
    return get_storage_path() / "table_data.db"


def get_vector_db_path():
    """Get the vector database path."""
    return get_storage_path() / "vector_db"


# Auto-setup when imported
setup_environment()
