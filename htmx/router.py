from typing import Annotated, Any
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
from russ_swiss_tournament.round import Round
from russ_swiss_tournament.tournament import Tournament
from russ_swiss_tournament.tournament import Player
from russ_swiss_tournament.matchup_assignment import SwissAssigner

templates = Jinja2Templates(directory="templates")

router = APIRouter()

def get_tournament_rounds_data(selected_id=1) -> list[dict[str, Any]]:
    rounds: list[Round] = config.tournament.rounds
    rounds_data = []
    for r in rounds:
        res: dict[str, Any] = dict()
        res['id'] = r.id
        res['is_complete'] = r.is_complete()
        res['is_selected'] = r.id == selected_id
        rounds_data.append(res)
    return rounds_data

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

@router.get("/load_all_tabs/{selected_id}")
async def load_all_tabs(
        selected_id: int,
        *,
        session: Session = Depends(get_session),
        request: Request,
    ):
    # TODO: Add selector for tournaments
    rounds_data = get_tournament_rounds_data(selected_id)
    context = {
        "request": request,
        "rounds": rounds_data,
    }
    return templates.TemplateResponse("tab_all.html", context)

def get_round_input_context(
        round_id: int,
        request: Request,
        session: Session,
    ) -> dict:
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
        matchup['black_score'] = match_result_score_map[MatchResult(matchup_data.black_score)]
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
        "rounds": get_tournament_rounds_data(round_id)
    }
    print(f"rounds len: {len(config.tournament.rounds)}, round_count: {config.tournament.round_count}")
    context['is_last_round'] = len(config.tournament.rounds) == config.tournament.round_count
    return context

@router.get("/round_input/{round_id}")
async def round_input(
        round_id: int,
        *,
        session: Session = Depends(get_session),
        request: Request,
    ):
    # TODO: Add selector for tournaments
    context = get_round_input_context(round_id, session=session, request=request)
    return templates.TemplateResponse("round_form.html", context)

@router.post("/round_update/{round_id}")
async def round_update(
        round_id: int,
        request: Request,
        session: Session = Depends(get_session),
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
        if matchup.id not in [m.id for m in matchups]:
            matchups.append(matchup)
    Matchup.db_write(matchups, update=True)

    config.tournament.validate_no_incomplete_match_results_in_rounds()
    context = get_round_input_context(round_id, request=request, session=session)

    return templates.TemplateResponse("round_form.html", context)

    # TODO: repetition, make prettier
    if round:
        is_complete = round.is_complete()
    else:
        is_complete = False

    context = {
        "request": request,
        "round": {
            "is_complete": is_complete,
            "id": round.id,
            "is_selected": True,
        },
        "rounds": get_tournament_rounds_data(round_id)
    }
    return templates.TemplateResponse("tab_round.html", context)


@router.get("/generate_round/{round_id}")
async def round_generate(
        round_id: int,
        request: Request,
        session: Session = Depends(get_session),
    ):
    prev_round: Round = config.tournament.get_round_by_index(round_id - 1)
    if not isinstance(config.assigner, SwissAssigner):
        raise ValueError("Can only generate new round with SwissAssigner mapped to config")
    new_round: Round = config.assigner.create_next_round()
    Round.db_write([new_round])

    context = get_round_input_context(round_id, request=request, session=session)
    return templates.TemplateResponse("round_form.html", context)

@router.get("/standings")
async def standings_get(
        request: Request,
        session: Session = Depends(get_session),
    ):
    res: list = []
    t: Tournament = config.tournament
    t.calculate_tie_break_results_swiss()
    t.calculate_tie_break_results_round_robin()
    s = t.get_standings()
    full_names = {p.identifier: p.get_full_name() for p in t.players}
    for id, score in s.items():
        name = full_names[id]
        info: dict[str, Any] = {'name': name}
        if isinstance(score, float):
            if score.is_integer():
                score = int(score)
        info['identifier'] = id
        info['score'] = score
        info['tie_breaks'] = dict()
        if (t.tie_break_results_swiss and t.tie_break_results_round_robin):
            for tb, trs in t.tie_break_results_round_robin.items():
                info['tie_breaks'][tb.name] = trs[id]
            for tb, trs in t.tie_break_results_swiss.items():
                info['tie_breaks'][tb.name] = trs[id]
        res.append(info)
    columns: list[str] = ['#', 'Player', 'Score'] + \
        [k.name.replace('_', ' ').capitalize() for k in t.tie_break_results_round_robin.keys()] + \
        [k.name.replace('_', ' ').capitalize() for k in t.tie_break_results_swiss.keys()]

    context = {
        "request": request,
        "standings": res,
        "columns": columns,
        "rounds": get_tournament_rounds_data()
    }
    return templates.TemplateResponse("standings.html", context)

@router.get("/player_rounds_modal/{player_identifier}")
async def player_rounds_modal(
        player_identifier: int,
        request: Request,
        session: Session = Depends(get_session),
    ):
    res: list[dict] = []
    t: Tournament = config.tournament
    player = t.get_player_by_id(player_identifier)
    for round in t.rounds:
        mu = round.get_player_matchup(player_identifier)
        if mu:
            res.append(mu.to_dict())

    context = {
        "request": request,
        "matchups": res,
        "player_name": player.get_full_name()
    }
    return templates.TemplateResponse("player_rounds_modal.html", context)
