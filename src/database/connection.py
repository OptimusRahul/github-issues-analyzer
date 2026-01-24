"""Database connection management."""

import sqlite3
import logging
from pathlib import Path
from typing import Optional

from src.config.settings import settings
from src.models.database import SCHEMA

# Configure logger
logger = logging.getLogger(__name__)


def get_db_connection() -> sqlite3.Connection:
    """
    Get a connection to the SQLite database.
    
    Enables WAL mode for better concurrency and foreign key constraints.
    
    Returns:
        sqlite3.Connection: Database connection object
    """
    try:
        logger.debug(f"Connecting to database: {settings.database_path}")
        conn = sqlite3.connect(settings.database_path)
        
        # Enable WAL mode for better concurrency
        conn.execute("PRAGMA journal_mode=WAL")
        logger.debug("Enabled WAL mode for database")
        
        # Enable foreign key constraints
        conn.execute("PRAGMA foreign_keys=ON")
        logger.debug("Enabled foreign key constraints")
        
        # Return rows as sqlite3.Row objects for dict-like access
        conn.row_factory = sqlite3.Row
        
        logger.debug("Database connection established successfully")
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to database: {str(e)}", exc_info=True)
        raise


def init_db() -> None:
    """
    Initialize the database by creating tables and indexes if they don't exist.
    
    This should be called once when the application starts.
    """
    logger.info("Initializing database...")
    conn = get_db_connection()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {str(e)}", exc_info=True)
        raise
    finally:
        conn.close()
