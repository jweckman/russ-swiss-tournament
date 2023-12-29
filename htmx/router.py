from typing import Annotated
from datetime import datetime, timedelta, date

from fastapi import FastAPI, Depends, Request, Query, Form, APIRouter
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from sqlmodel import select, Session, or_

import config

from htmx.db import get_session, create_db_and_tables, populate_test_data
from htmx.models import PlayerModel, RoundModel, TournamentModel


from russ_swiss_tournament.service import match_result_score_map, MatchResult, Color, match_result_manual_map
from russ_swiss_tournament.matchup import Matchup

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
async def round_input(
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
        white_full_name = [p for p in config.tournament.players if p.identifier == matchup_data.white_identifier]
        if white_full_name and len(white_full_name) == 1:
            matchup['white_full_name'] = white_full_name[0].get_full_name()
        black_full_name = [p for p in config.tournament.players if p.identifier == matchup_data.black_identifier]
        if black_full_name and len(black_full_name) == 1:
            matchup['black_full_name'] = black_full_name[0].get_full_name()
        matchup['white_score'] = match_result_score_map[MatchResult(matchup_data.white_score)]
        matchup['black_score'] = match_result_score_map[MatchResult(matchup_data.white_score)]
        matchup['white_identifier'] = matchup_data.white_identifier
        matchup['black_identifier'] = matchup_data.black_identifier
        matchups.append(matchup)

    round = config.tournament.get_round_by_index(round_id)
    if round:
        is_complete = round.is_complete()
    else:
        is_complete = False

    context = {
        "request": request,
        "matchups": matchups,
        "round_id": round_id,
        "is_complete": is_complete,
    }
    return templates.TemplateResponse("round_form.html", context)

@router.post("/round_update/{round_id}")
async def round_update(
        round_id: int,
        request: Request,
    ):
    round = config.tournament.get_round_by_index(round_id)
    form_data = await request.form()
    matchups: list = []
    for player, result in form_data.items():
        player_parts = player.split('_')
        player_identifier = player_parts[-1]
        is_black = player_parts[-2] == 'black'
        matchup = round.get_player_matchup(player_identifier)
        if is_black:
            matchup.res[Color.B].res = match_result_manual_map[result]
        else:
            matchup.res[Color.W].res = match_result_manual_map[result]
        matchups.append(matchup)
    # TODO: fix matchup update to db
    Matchup.db_write(matchups)

    config.tournament.validate_no_incomplete_match_results_in_rounds()

    # TODO: repetition, make prettier
    if round:
        is_complete = round.is_complete()
    else:
        is_complete = False

    context = {
        "request": request,
        "status": "finished" if is_complete else "in progress"
    }
    return templates.TemplateResponse("round_status.html", context)
