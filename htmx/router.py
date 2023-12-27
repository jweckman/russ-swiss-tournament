from fastapi import FastAPI, Depends, Request, Query, Form, APIRouter
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from sqlmodel import select, Session, or_

import config

from htmx.db import get_session, create_db_and_tables, populate_test_data
from htmx.models import PlayerModel, RoundModel, TournamentModel

from russ_swiss_tournament.service import match_result_score_map, MatchResult

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

@router.get("/round_input/{round_id}")
async def testing(
        round_id: int,
        *,
        session: Session = Depends(get_session),
        request: Request,
    ):
    # TODO: Add selector for tournaments
    tournament_model_id = 1
    round_model_query = select(RoundModel).where(
        RoundModel.tournament_id == tournament_model_id,
        RoundModel.index == round_id,
    )
    round_model_res = session.exec(round_model_query).first()
    matchups: list = []
    for matchup_data in round_model_res.matchups:
        matchup = dict()
        white_full_name = [p for p in config.tournament.players if p.id == matchup_data.white_id]
        if white_full_name and len(white_full_name) == 1:
            matchup['white_full_name'] = white_full_name[0].get_full_name()
        black_full_name = [p for p in config.tournament.players if p.id == matchup_data.black_id]
        if black_full_name and len(black_full_name) == 1:
            matchup['black_full_name'] = black_full_name[0].get_full_name()
        matchup['white_result'] = match_result_score_map[MatchResult(matchup_data.white_score)]
        matchup['black_result'] = match_result_score_map[MatchResult(matchup_data.white_score)]
        matchup['white_id'] = matchup_data.white_id
        matchup['black_id'] = matchup_data.black_id
        matchups.append(matchup)

    context = {
        "request": request,
        "matchups": matchups,
        "round_id": round_id,
    }
    return templates.TemplateResponse("round_form.html", context)
