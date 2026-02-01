import os
from pathlib import Path
from typing import Generator
from sqlmodel import Session, SQLModel, create_engine
import config

DB_FOLDER = Path("databases")
DEFAULT_DB = "tournament.sqlite"

# Ensure the folder exists
DB_FOLDER.mkdir(exist_ok=True)

class NoDatabaseSelectedError(Exception):
    """Raised when an operation requires a DB connection but none is active."""
    pass

class DatabaseManager:
    def __init__(self):
        self.engine = None
        self.current_db_name = None
        # Initialize with default if available, or None
        if config.db_name:
            self.set_db(config.db_name)

    def _update_engine(self):
        """Updates the internal engine based on the current_db_name."""
        db_path = DB_FOLDER / self.current_db_name
        sqlite_url = f"sqlite:///{db_path}"
        connect_args = {"check_same_thread": False}

        # Dispose of the old engine if it exists to release locks
        if self.engine:
            self.engine.dispose()

        self.engine = create_engine(
            sqlite_url,
            echo=False,
            connect_args=connect_args
        )
    def set_db(self, db_name: str):
        """
        Switches the active database engine. 
        DISPOSES of the old engine to ensure no stale connections remain.
        """
        # 1. Dispose of old engine if it exists
        if self.engine:
            self.engine.dispose()
        # 2. Update Path
        self.current_db_name = db_name
        db_folder = "databases"
        os.makedirs(db_folder, exist_ok=True)
        db_path = f"{db_folder}/{db_name}"
        sqlite_url = f"sqlite:///{db_path}"

        # 3. Create NEW Engine
        # check_same_thread=False is needed for FastAPI handling requests in different threads
        self.engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})
        print(f"--- DB SWITCHED: Engine now pointing to {db_path} ---")

    def get_available_dbs(self):
        if not os.path.exists("databases"):
            return []
        return sorted([f for f in os.listdir("databases") if f.endswith(".sqlite") or f.endswith(".db")])

    def create_new_db(self, db_name: str):
        """Creates a new empty database file."""
        if not db_name.endswith(".sqlite"):
            db_name += ".sqlite"
        (DB_FOLDER / db_name).touch()
        return db_name

# Global Singleton instance
db_manager = DatabaseManager()

def get_engine():
    """Returns the current active engine."""
    return db_manager.engine

def get_session() -> Generator[Session, None, None]:
    """
    Dependency for FastAPI.
    CRITICAL: This must access db_manager.engine dynamically.
    """
    if not db_manager.engine:
        raise NoDatabaseSelectedError("No database selected.")
    with Session(db_manager.engine) as session:
        yield session

def create_db_and_tables():
    """
    Creates tables ONLY if a database engine is currently active.
    Safe to call on startup even if no DB is selected.
    """
    if db_manager.engine:
        SQLModel.metadata.create_all(db_manager.engine)
    else:
        print("INFO: Skipping table creation (no database selected yet).")

