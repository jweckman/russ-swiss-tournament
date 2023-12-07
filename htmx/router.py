from fastapi import FastAPI, Depends, Request, Query, Form, APIRouter
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from sqlmodel import select, Session

from htmx.db import get_session, create_db_and_tables, populate_test_data
from htmx.models import PlayerModel

templates = Jinja2Templates(directory="templates")

router = APIRouter()

@router.get("/")
async def index(
        *,
        session: Session = Depends(get_session),
        request: Request,
    ):
    context = {
        "request": request,
    }
    return templates.TemplateResponse("index.html", context)

@router.get("/testing")
async def testing(
        *,
        session: Session = Depends(get_session),
        request: Request,
    ):
    context = {
        "request": request,
    }
    return templates.TemplateResponse("base.html", context)
