from typing import Annotated, Any, cast
from io import StringIO
import os
from pathlib import Path

from fastapi import FastAPI, Depends, Request, Query, Form, APIRouter, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from sqlmodel import Session

import config

from htmx.db import get_session, db_manager, create_db_and_tables
from htmx.seeder import seed_default_tournament, read_players_from_csv
from htmx.repository import TournamentRepository
from htmx.models import PlayerModel

from russ_swiss_tournament.service import match_result_score_map, Color, match_result_manual_map, MatchResult
from russ_swiss_tournament.matchup import Matchup, PlayerMatch
from russ_swiss_tournament.round import Round
from russ_swiss_tournament.tournament import Tournament, RoundSystem, Player
from russ_swiss_tournament.matchup_assignment import SwissAssigner

RESULT_STRING_MAP = {
    "1-0":     (MatchResult.WIN, MatchResult.LOSS),
    "0-1":     (MatchResult.LOSS, MatchResult.WIN),
    "0.5-0.5": (MatchResult.DRAW, MatchResult.DRAW),
    "unset":   (MatchResult.UNSET, MatchResult.UNSET)
}

templates = Jinja2Templates(directory="templates")
templates.env.globals["config"] = config

router = APIRouter()

def save_and_reload_config(session: Session):
    """
    Saves the current tournament state to DB, then immediately RELOADS it.
    This prevents 'Zombie' states where the in-memory object drifts from the DB.
    """
    if config.tournament is None:
        raise ValueError("Attempted to save configuration but no tournament is loaded.")
    tournament = cast(Tournament, config.tournament)

    repo = TournamentRepository(session)
    # 1. Save current state
    repo.save_tournament(tournament)
    # 2. Reload fresh state from DB
    # We must commit first to ensure data is queryable
    session.commit()
    # 3. Refresh the global config object
    # This replaces the 'stale' object with a fresh one from the DB
    refreshed_tournament = repo.get_active_tournament()
    if refreshed_tournament:
        config.tournament = refreshed_tournament
        # Re-link the assigner to the new tournament object
        if config.tournament.round_system == RoundSystem.SWISS:
             config.assigner = SwissAssigner(config.tournament)
    else:
        # Should never happen if save matched, but safety first
        print("CRITICAL WARNING: Could not reload tournament after save.")

def get_tournament_rounds_data(selected_index: int | None = 1) -> list[dict[str, Any]]:
    """
    Generates data for the tabs navigation.
    """
    if not config.tournament:
        return []
    rounds = config.tournament.rounds
    rounds_data = []
    sorted_rounds = sorted(rounds, key=lambda x: x.index)
    for r in sorted_rounds:
        res: dict[str, Any] = dict()
        res['id'] = r.index 
        res['is_complete'] = r.is_complete()
        # If selected_index is None, this will always be False (no round selected)
        res['is_selected'] = r.index == selected_index
        rounds_data.append(res)
    return rounds_data

@router.get("/")
async def index(request: Request):
    """
    Renders the initial page with the Database Manager.
    """
    databases = db_manager.get_available_dbs()
    context = {
        "request": request,
        "databases": databases,
        "current_db": db_manager.current_db_name
    }
    return templates.TemplateResponse("index.html", context)

@router.post("/upload_round_csv/{round_id}")
async def upload_round_csv(
        round_id: int,
        *,
        file: Annotated[bytes, File()],
        session: Session = Depends(get_session),
        request: Request,
    ):
    tournament = cast(Tournament, config.tournament)
    content = file.decode()
    file_text = StringIO(content)
    new_round_obj = Round.read_csv(file_text, round_id, tournament.players)
    found = False
    for i, r in enumerate(tournament.rounds):
        if r.index == round_id:
            new_round_obj.id = r.id 
            tournament.rounds[i] = new_round_obj
            found = True
            break
    if not found:
        tournament.rounds.append(new_round_obj)
    try:
        save_and_reload_config(session)
    except Exception as e:
        print(f"Error saving CSV upload: {e}")
        return HTMLResponse("<div>Error saving data. Check server logs.</div>")

    context = get_round_input_context(round_id, session=session, request=request)
    return templates.TemplateResponse("round_form.html", context)

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
    round_index: int,
    request: Request,
    session: Session, 
) -> dict[str, Any]:
    """
    Builds the dictionary for the round form template.
    Refactored to read from config.tournament (Domain Object) instead of DB.
    """
    if not config.tournament:
         return {"request": request, "error": "No tournament loaded"}
    tournament = cast(Tournament, config.tournament)

    round_domain = tournament.get_round_by_index(round_index)

    if not round_domain:
        return {
            "request": request,
            "matchups": [],
            "round_id": round_index,
            "is_complete": False,
            "rounds": get_tournament_rounds_data(round_index),
            "is_last_round": False
        }
    matchups: list[dict[str, Any]] = []
    standings = tournament.get_sorted_standings(until=round_index - 1)
    player_ranks: list[int] = []
    if standings:
        player_ranks = list(standings.keys())
    for mu in round_domain.matchups:
        white_id = mu.get_white_id()
        black_id = mu.get_black_id()
        w_rank = 999
        b_rank = 999
        if player_ranks:
            if white_id in player_ranks: 
                w_rank = player_ranks.index(white_id)
            if black_id in player_ranks: 
                b_rank = player_ranks.index(black_id)
        top_ranked_index = min(w_rank, b_rank)

        w_res_enum = mu.res[Color.W].res
        b_res_enum = mu.res[Color.B].res
        matchup_data = {
            'top_ranked_index': top_ranked_index,
            'white_full_name': mu.res[Color.W].player.get_full_name(),
            'black_full_name': mu.res[Color.B].player.get_full_name(),
            'white_score': match_result_score_map.get(w_res_enum, 'unset'),
            'black_score': match_result_score_map.get(b_res_enum, 'unset'),
            'white_identifier': white_id,
            'black_identifier': black_id,
        }
        matchups.append(matchup_data)

    if round_index != 1 and player_ranks:
        matchups = sorted(matchups, key=lambda m: m['top_ranked_index'])

    context = {
        "request": request,
        "matchups": matchups,
        "round_id": round_index,
        "is_complete": round_domain.is_complete(),
        "rounds": get_tournament_rounds_data(round_index),
        "is_last_round": len(tournament.rounds) == tournament.round_count
    }
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
    if not config.tournament:
        raise ValueError("Tournament is not initialized.")
    tournament = cast(Tournament, config.tournament)
    round_domain = tournament.get_round_by_index(round_id)
    if not round_domain:
        raise ValueError(f"Round {round_id} not found.")

    form_data = await request.form()
    for key, value in form_data.items():
        if not key.startswith("result_"):
            continue
        parts = key.split('_')
        if len(parts) != 3:
            continue
        white_id = int(parts[1])
        matchup = round_domain.get_player_matchup(white_id)
        if matchup and value in RESULT_STRING_MAP:
            w_res, b_res = RESULT_STRING_MAP[value]
            matchup.res[Color.W].res = w_res
            matchup.res[Color.B].res = b_res
    save_and_reload_config(session)

    context = get_round_input_context(round_id, request=request, session=session)
    return templates.TemplateResponse("round_form.html", context)

@router.get("/generate_round/{round_id}")
async def round_generate(
    round_id: int,
    request: Request,
    session: Session = Depends(get_session),
):
    tournament = cast(Tournament, config.tournament)
    prev_round: Round = tournament.get_round_by_index(round_id - 1)
    config.assigner = SwissAssigner(tournament)
    if not isinstance(config.assigner, SwissAssigner):
        raise ValueError("Can only generate new round with SwissAssigner mapped to config")
    new_round: Round = config.assigner.create_next_round()
    repo = TournamentRepository(session)
    repo.save_tournament(tournament)

    context = get_round_input_context(round_id, request=request, session=session)
    return templates.TemplateResponse("round_form.html", context)

@router.get("/standings")
async def standings_get(
    request: Request,
    session: Session = Depends(get_session),
):
    tournament = cast(Tournament, config.tournament)
    res: list = []
    t: Tournament = tournament
    s = t.get_sorted_standings()
    if not s:
        raise ValueError("Could not get standings. Probably no complete rounds yet")
    full_names = {p.identifier: p.get_full_name() for p in t.players}
    sonne, koya = tournament.get_tie_break_results_round_robin()
    modified_median, solkoff = tournament.get_tie_break_results_swiss()
    for id, score in s.items():
        name = full_names[id]
        info: dict[str, Any] = {'name': name}
        if isinstance(score, float):
            if score.is_integer():
                score = int(score)
        info['identifier'] = id
        info['score'] = score
        info['tie_breaks'] = dict()
        info['tie_breaks']['Sonneborn-Berger'] = sonne[id]
        info['tie_breaks']['Koya'] = koya[id]
        info['tie_breaks']['Modified Median'] = modified_median[id]
        info['tie_breaks']['Solkoff'] = solkoff[id]
        res.append(info)
    columns: list[str] = ['#', 'Player', 'Score', 'Sonneborn-Berger', 'Koya', 'Modified Median', 'Solkoff']

    context = {
        "request": request,
        "standings": res,
        "columns": columns,
        # FIX 1: Explicitly pass None so NO round tabs are highlighted
        "rounds": get_tournament_rounds_data(selected_index=None),
        # FIX 2: Add a flag so the template knows to highlight the Standings tab
        "is_standings": True 
    }
    return templates.TemplateResponse("standings.html", context)

@router.get("/player_rounds_modal/{player_identifier}")
async def player_rounds_modal(
    player_identifier: int,
    request: Request,
    session: Session = Depends(get_session),
):
    tournament = cast(Tournament, config.tournament)
    res: list[dict] = []
    t: Tournament = tournament
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

@router.post("/db_select")
async def select_database(
    request: Request,
    db_name: Annotated[str, Form()],
):
    print(f"--- RESETTING CONTEXT TO: {db_name} ---")
    tournament = cast(Tournament, config.tournament)

    # 1. HARD RESET: Clear Global Memory State
    config.tournament = None
    config.assigner = None
    config.db_name = db_name  # Set the new name immediately

    # 2. HARD RESET: Database Engine
    # This disposes the old connection and creates a fresh one pointing to the new file
    db_manager.set_db(db_name)
    # 3. Initialize Tables (Safe to run if they exist, ensures file validity)
    create_db_and_tables()

    # 4. HARD RESET: Reload Data from the NEW Engine
    # We explicitly open a session from the manager we just updated
    with Session(db_manager.engine) as session:
        # Verify we are reading the right file
        current_db_path = session.bind.url.database
        if db_name not in current_db_path:
            raise RuntimeError(f"Engine Mismatch! Tried to load {db_name} but engine has {current_db_path}")

        found = config.load_tournament_context(session)
        if not found:
            print(f"Database {db_name} is empty. Seeding from default TOML...")
            new_tournament = seed_default_tournament(session)
            # Re-save to ensure it's persisted in the new file
            repo = TournamentRepository(session)
            repo.save_tournament(new_tournament)
            session.commit()
            # Update global config with the fresh object
            config.tournament = new_tournament
            config.assigner = SwissAssigner(new_tournament)
        else:
            print(f"Successfully loaded tournament: {tournament.name}")

    context = {
        "request": request,
        "current_db": db_name,
        "config": config 
    }
    return templates.TemplateResponse("tournament_container.html", context)

@router.post("/db_create")
async def create_database(
    request: Request,
    new_db_name: Annotated[str, Form()]
):
    safe_name = "".join([c for c in new_db_name if c.isalnum() or c in (' ', '_', '-')]).strip()
    if not safe_name.endswith('.sqlite'):
        safe_name += '.sqlite'
    db_manager.create_new_db(safe_name)
    db_manager.set_db(safe_name)

    # Since a new DB is empty, we probably want to return a "New Tournament Form"
    # rather than the generic container. But for now, let's just reload the manager
    # so the user sees their new DB in the list.

    databases = db_manager.get_available_dbs()
    context = {
        "request": request,
        "databases": databases,
        "current_db": safe_name
    }
    return templates.TemplateResponse("db_manager.html", context)

@router.post("/db_delete")
async def db_delete(request: Request, db_name: str = Form(...)):
    """Deletes a tournament database file."""
    # Safety Check: Cannot delete the active database
    if config.db_name == db_name:
        # We can return a simple alert or just reload the list
        print(f"Attempted to delete active database {db_name}. Blocked.")
        return await db_manager_get(request)

    db_folder = "databases"
    db_path = os.path.join(db_folder, db_name)
    # Security: Ensure we don't traverse directories
    if not os.path.abspath(db_path).startswith(os.path.abspath(db_folder)):
         return await db_manager_get(request)

    try:
        if os.path.exists(db_path):
            os.remove(db_path)
            print(f"Deleted database: {db_path}")
    except Exception as e:
        print(f"Error deleting file: {e}")

    return await db_manager_get(request)

@router.get("/db_manager")
async def db_manager_get(request: Request):
    """Lists all available tournament databases."""
    db_folder = "databases"
    os.makedirs(db_folder, exist_ok=True)
    files = [f for f in os.listdir(db_folder) if f.endswith(('.sqlite'))]
    files.sort()
    return templates.TemplateResponse("db_manager.html", {
        "request": request, 
        "databases": files, 
        "current_db": config.db_name
    })

@router.get("/create_tournament_form")
async def create_tournament_form_get(request: Request):
    """Returns the comprehensive creation form."""
    return templates.TemplateResponse("create_tournament_form.html", {"request": request})

@router.post("/create_tournament")
async def create_tournament_post(
    request: Request,
    title: str = Form(...),
    year: int = Form(...),
    round_count: int = Form(...),
    round_system: str = Form(...),
    selected_player_ids_str: str = Form(""), 
    tie_break_swiss: list[str] = Form(default=[]),
    tie_break_rr: list[str] = Form(default=[])
):
    selected_player_ids = set()
    if selected_player_ids_str:
        try:
            selected_player_ids = {int(x) for x in selected_player_ids_str.split(',') if x.strip()}
        except ValueError:
            pass
    if not selected_player_ids or len(selected_player_ids) < 2:
         return HTMLResponse("Error: Need at least 2 players selected.")

    if round_system == 'swiss':
        n_playing = len(selected_player_ids)
        max_possible = n_playing if n_playing % 2 != 0 else n_playing - 1
        if round_count > max_possible:
             return HTMLResponse(f"Error: Too many rounds for {n_playing} players (max {max_possible}).")

    safe_filename = "".join([c for c in title if c.isalnum() or c in (' ', '-', '_')]).rstrip()
    safe_filename = safe_filename.replace(' ', '_').lower()
    db_name = f"{safe_filename}.sqlite"

    unique_players_map = {}
    for p in read_players_from_csv():
        try:
            pid = int(p.identifier)
            unique_players_map[pid] = p
        except (ValueError, TypeError):
            pass

    final_roster = []
    for pid in sorted(unique_players_map.keys()):
        p = unique_players_map[pid]
        is_selected = pid in selected_player_ids
        new_p = Player(
            identifier=pid,
            first_name=p.first_name,
            last_name=p.last_name,
            active=is_selected 
        )
        final_roster.append(new_p)

    print(f"--- CREATING & SWITCHING TO: {db_name} ---")
    db_folder = Path("databases")
    db_folder.mkdir(exist_ok=True)
    db_path = db_folder / db_name
    if db_path.exists():
        try:
            # Dispose engine if it's currently locking this file
            if config.db_name == db_name:
                db_manager.engine.dispose()
            os.remove(db_path)
            print(f"Deleted existing database: {db_name}")
        except Exception as e:
            print(f"Error deleting old DB: {e}")

    config.db_name = db_name
    db_manager.set_db(db_name)
    create_db_and_tables()

    with Session(db_manager.engine) as session:
        from htmx.mappers import to_db_player

        for p in final_roster:
            db_p = to_db_player(p)
            db_p = session.merge(db_p)
            session.flush()
            p.db_id = db_p.id

        active_roster = [p for p in final_roster if p.active]
        rs_enum = RoundSystem.SWISS if round_system == 'swiss' else RoundSystem.BERGER

        # SQLAlchemy will only create link-table rows for these players.
        new_tourney = Tournament(
            name=title,
            players=active_roster, 
            rounds=[], 
            round_count=round_count,
            round_system=rs_enum,
            tie_break_results_swiss={},
            tie_break_results_round_robin={},
            year=year,
            count=0,
            player_tournament_start_order=[p.identifier for p in active_roster]
        )
        if rs_enum == RoundSystem.SWISS:
            new_tourney._create_initial_round()
        elif rs_enum == RoundSystem.BERGER:
            # --- BERGER (ROUND ROBIN) LOGIC ---
            n = len(active_roster)
            rotation_ids = [p.identifier for p in active_roster]
            # If odd number of players, add a "ghost" to make even pairs
            if n % 2 != 0:
                rotation_ids.append(None)
                n += 1
            # Berger standard is N-1 rounds
            total_rr_rounds = n - 1
            # Update tournament count to match reality
            new_tourney.round_count = total_rr_rounds

            for r_idx in range(total_rr_rounds):
                half = n // 2
                l1 = rotation_ids[:half]
                l2 = rotation_ids[half:][::-1]
                round_matchups = []
                for i in range(half):
                    p1_id = l1[i]
                    p2_id = l2[i]
                    # If neither ID is None (Ghost), create a match
                    if p1_id is not None and p2_id is not None:
                        p1 = next(p for p in active_roster if p.identifier == p1_id)
                        p2 = next(p for p in active_roster if p.identifier == p2_id)
                        # Alternating Colors Logic
                        if r_idx % 2 == 0: 
                            w, b = p1, p2
                        else: 
                            w, b = p2, p1
                        round_matchups.append(Matchup({
                            Color.W: PlayerMatch(w), 
                            Color.B: PlayerMatch(b)
                        }))
                # Create the Round
                new_tourney.rounds.append(Round(matchups=round_matchups, index=r_idx + 1))
                # Rotate players: Keep index 0 fixed, rotate the rest clockwise
                rotation_ids = [rotation_ids[0]] + [rotation_ids[-1]] + rotation_ids[1:-1]
            # --- END BERGER LOGIC ---

        # SAVE TOURNAMENT
        repo = TournamentRepository(session)
        # This will merge the tournament and link the players in 'new_tourney.players'
        repo.save_tournament(new_tourney)
        session.commit()
        # Update Global Config
        config.tournament = new_tourney
        if rs_enum == RoundSystem.SWISS:
             config.assigner = SwissAssigner(new_tourney)

    rounds_data = get_tournament_rounds_data(1)

    return templates.TemplateResponse("tournament_container.html", {
        "request": request,
        "current_db": db_name,
        "rounds": rounds_data,
        "config": config
    })

@router.post("/search_players")
async def search_players(
    request: Request,
    search: str = Form(""),
    selected_player_ids_str: str = Form(""),
):
    if not search:
        return HTMLResponse("")

    all_players = read_players_from_csv()

    query = search.lower()
    try:
        current_ids = [int(x) for x in selected_player_ids_str.split(',') if x.strip()]
    except ValueError:
        current_ids = []

    matches = [
        p for p in all_players 
        if (query in p.get_full_name().lower() or query in str(p.identifier))
        and p.identifier not in current_ids
    ]
    matches = matches[:5]

    html = ""
    for p in matches:
        html += f"""
        <div class="p-2 hover:bg-gray-100 cursor-pointer border-b border-gray-100 flex justify-between items-center group"
             hx-post="/player_selection/add?id={p.identifier}"
             hx-target="#player-selection-container"
             hx-include="#current-selection-state"
             onclick="let self=this; setTimeout(function(){{ 
                 document.querySelector('input[name=search]').value=''; 
                 document.querySelector('#search-results').innerHTML=''; 
             }}, 100);">
            <span class="font-medium text-gray-800">{p.get_full_name()}</span>
            <span class="text-xs text-gray-400 group-hover:text-gray-600">ID: {p.identifier}</span>
        </div>
        """
    return HTMLResponse(html)

@router.get("/get_player_selection_row/{player_identifier}")
async def get_player_selection_row(player_identifier: int):
    """Returns the HTML for a single row in the 'Selected Players' list."""
    if not config.tournament:
        return HTMLResponse("")

    player = config.tournament.get_player_by_id(player_identifier)
    return HTMLResponse(f"""
    <div class="player-row flex items-center justify-between bg-white p-2 rounded border border-gray-200 shadow-sm animate-fadeIn">
        <input type="hidden" name="selected_player_ids" value="{player.identifier}">
        <div class="flex items-center gap-3">
            <div class="bg-gray-100 text-gray-500 text-xs font-mono px-2 py-1 rounded">#{player.identifier}</div>
            <span class="font-bold text-gray-700">{player.get_full_name()}</span>
        </div>

        <div class="flex items-center gap-1">
            <button type="button" 
                    class="p-1 hover:bg-gray-100 rounded text-gray-400 hover:text-gray-700"
                    _="on click 
                       set row to closest .player-row 
                       set prev to row.previousElementSibling 
                       if prev and not prev.matches('.empty-msg') 
                          put row before prev
                       end">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m18 15-6-6-6 6"/></svg>
            </button>
            <button type="button" 
                    class="p-1 hover:bg-gray-100 rounded text-gray-400 hover:text-gray-700"
                    _="on click 
                       set row to closest .player-row 
                       set next to row.nextElementSibling 
                       if next 
                          put row after next
                       end">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg>
            </button>
            <button type="button" 
                    class="p-1 hover:bg-red-50 rounded text-gray-400 hover:text-red-600 ml-1"
                    _="on click remove closest .player-row">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>
            </button>
        </div>
    </div>
    """)

def render_player_selection_list(request: Request, ids_str: str, highlight_id: int | None = None):
    if not ids_str:
        return templates.TemplateResponse("player_selection_list.html", {
            "request": request, "selected_players": [], "selected_ids_str": "", "highlight_id": None
        })
    try:
        id_list = [int(x) for x in ids_str.split(',') if x.strip()]
    except ValueError:
        id_list = []

    players_map = {}
    if config.tournament:
        for p in config.tournament.players:
            players_map[p.identifier] = p
    csv_players = read_players_from_csv()
    for p in csv_players:
        if p.identifier not in players_map:
            players_map[p.identifier] = p

    ordered_players = []
    valid_ids = []
    for pid in id_list:
        if pid in players_map:
            ordered_players.append(players_map[pid])
            valid_ids.append(pid)
    new_ids_str = ",".join(map(str, valid_ids))

    return templates.TemplateResponse("player_selection_list.html", {
        "request": request,
        "selected_players": ordered_players,
        "selected_ids_str": new_ids_str,
        "highlight_id": highlight_id
    })

@router.post("/player_selection/add")
async def player_selection_add(
    request: Request,
    id: int,
    selected_player_ids_str: str = Form("")
):
    current_ids = [str(x) for x in selected_player_ids_str.split(',') if x.strip()]
    if str(id) not in current_ids:
        current_ids.append(str(id))
        return render_player_selection_list(request, ",".join(current_ids), highlight_id=id)
    return render_player_selection_list(request, ",".join(current_ids), highlight_id=id)

@router.post("/player_selection/remove")
async def player_selection_remove(
    request: Request,
    id: int,
    selected_player_ids_str: str = Form("")
):
    current_ids = [str(x) for x in selected_player_ids_str.split(',') if x.strip()]
    if str(id) in current_ids:
        current_ids.remove(str(id))
    return render_player_selection_list(request, ",".join(current_ids))

@router.post("/player_selection/reorder")
async def player_selection_reorder(
    request: Request,
    id: int,
    direction: str,
    selected_player_ids_str: str = Form("")
):
    current_ids = [int(x) for x in selected_player_ids_str.split(',') if x.strip()]
    try:
        idx = current_ids.index(id)
        if direction == "up" and idx > 0:
            current_ids[idx], current_ids[idx-1] = current_ids[idx-1], current_ids[idx]
        elif direction == "down" and idx < len(current_ids) - 1:
            current_ids[idx], current_ids[idx+1] = current_ids[idx+1], current_ids[idx]
    except ValueError:
        pass 
    return render_player_selection_list(request, ",".join(map(str, current_ids))) # No highlight

@router.get("/players")
async def players_get(request: Request):
    """Renders the main player management view."""
    if not config.tournament:
        return HTMLResponse("No tournament loaded.", status_code=400)
    # Sort players by ID for clean display
    sorted_players = sorted(config.tournament.players, key=lambda p: p.identifier)
    return templates.TemplateResponse("players.html", {
        "request": request,
        "players": sorted_players,
        "current_db": config.db_name
    })

@router.post("/players/add")
async def player_add(
    request: Request,
    identifier: int = Form(...),
    first_name: str = Form(...),
    last_name: str = Form(""),
    session: Session = Depends(get_session)
):
    if not config.tournament:
        return HTMLResponse("")

    if any(p.identifier == identifier for p in config.tournament.players):
        return HTMLResponse(f"<tr><td class='text-red-600'>Error: ID {identifier} exists</td></tr>")

    new_player = Player(
        identifier=identifier,
        first_name=first_name,
        last_name=last_name,
        active=True
    )
    config.tournament.players.append(new_player)
    try:
        save_and_reload_config(session)
    except RuntimeError as e:
        print(e)
        return HTMLResponse("<tr><td>Database Error. Refresh page.</td></tr>")
    saved_player = config.tournament.get_player_by_id(identifier)
    return templates.TemplateResponse("player_row.html", {
        "request": request,
        "player": saved_player
    })

@router.delete("/players/{player_id}")
async def player_delete(
    player_id: int,
    session: Session = Depends(get_session)
):
    if not config.tournament:
        return HTMLResponse("")
    tournament = cast(Tournament, config.tournament)

    try:
        player = tournament.get_player_by_id(player_id)
    except (IndexError, ValueError):
        return HTMLResponse("")

    has_played = any(
        player_id in m.get_player_ids()
        for r in tournament.rounds
        for m in r.matchups
    )

    if has_played:
        player.active = False
    else:
        if player in tournament.players:
            tournament.players.remove(player)
        if player.db_id:
            db_row = session.get(PlayerModel, player.db_id)
            if db_row:
                session.delete(db_row)

    save_and_reload_config(session)
    return HTMLResponse("")

@router.get("/players/{player_id}/edit")
async def player_edit_get(player_id: int, request: Request):
    """Returns the row in 'Edit Mode'."""
    if not config.tournament:
        return HTMLResponse("")
    player = config.tournament.get_player_by_id(player_id)
    return templates.TemplateResponse("player_row_edit.html", {
        "request": request,
        "player": player
    })

@router.get("/players/{player_id}/row")
async def player_row_get(player_id: int, request: Request):
    """Returns the row in standard 'Read Mode' (for Cancel action)."""
    if not config.tournament:
        return HTMLResponse("")
    player = config.tournament.get_player_by_id(player_id)
    return templates.TemplateResponse("player_row.html", {
        "request": request,
        "player": player
    })

@router.put("/players/{player_id}")
async def player_update(
    request: Request,
    player_id: int,
    first_name: str = Form(...),
    last_name: str = Form(""),
    session: Session = Depends(get_session)
):
    if not config.tournament:
        return HTMLResponse("")
    player = config.tournament.get_player_by_id(player_id)
    if player:
        player.first_name = first_name
        player.last_name = last_name
        # Save to DB
        repo = TournamentRepository(session)
        repo.save_tournament(config.tournament)
        session.commit()
    # Return the row in 'Read Mode' with updated data
    return templates.TemplateResponse("player_row.html", {
        "request": request,
        "player": player
    })
