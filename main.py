from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session
import uvicorn

import config
import htmx.router
from htmx.router import router, templates
from htmx.db import create_db_and_tables, db_manager, NoDatabaseSelectedError

from russ_swiss_tournament.matchup_assignment import SwissAssigner

# --- Lifespan Manager ---
# Runs automatically when FastAPI starts.
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application Startup Logic.
    """
    # 1. Initialize DB tables (Safe: checks internally if engine exists)
    create_db_and_tables()

    # 2. Try to load the tournament context ONLY if a DB is selected
    if db_manager.engine:
        try:
            with Session(db_manager.engine) as session:
                print(f"INFO: Auto-loading tournament from {config.db_name}...")
                loaded = config.load_tournament_context(session)
                if loaded:
                    print(f"INFO: Successfully loaded '{config.tournament.name}'")
                else:
                    print("INFO: Database is empty or valid tournament not found.")
        except Exception as e:
            print(f"WARNING: Could not auto-load tournament: {e}")
    else:
        # This is the normal state for a fresh install or when no DB is selected in config
        print("INFO: No database auto-selected. Waiting for user input via Database Manager.")

    yield
    # Shutdown logic (if any) goes here

# --- App Initialization ---
app = FastAPI(
    default_response_class=HTMLResponse,
    lifespan=lifespan
)

@app.exception_handler(NoDatabaseSelectedError)
async def no_db_exception_handler(request: Request, exc: NoDatabaseSelectedError):
    """
    Intercepts any request that fails due to missing DB context.
    Renders the DB Manager with a warning banner.
    """
    databases = db_manager.get_available_dbs()
    # If this is an HTMX request (e.g., clicking a tab), we render just the content.
    # If it's a full page load, the TemplateResponse works for that too.
    return templates.TemplateResponse("db_manager.html", {
        "request": request,
        "databases": databases,
        "current_db": None,
        "warning": "Please select a tournament database to continue."
    })

# --- Routing ---
app.include_router(htmx.router.router)
app.mount("/static", StaticFiles(directory="static"), name="static")


if __name__ == "__main__":
    # Allows running `python main.py` directly for development
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

