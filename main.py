from pathlib import Path
from typing import Annotated
from time import sleep
from datetime import datetime

import config

from russ_swiss_tournament.tournament import Tournament
from russ_swiss_tournament.player import Player
from russ_swiss_tournament.matchup import Matchup, PlayerMatch
from russ_swiss_tournament.round import Round
from russ_swiss_tournament.tie_break import calc_modified_median_solkoff
from russ_swiss_tournament.matchup_assignment import SwissAssigner, RoundRobinAssigner
from russ_swiss_tournament.db import Database
from russ_swiss_tournament.cli import main
from russ_swiss_tournament.service import MatchResult, Color

import htmx.router
from htmx.db import create_db_and_tables, populate_test_data

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

def init_htmx():
    '''Run application with web front-end'''
    global app
    app = FastAPI(default_response_class=HTMLResponse)
    app.include_router(htmx.router.router)
    app.mount("/static", StaticFiles(directory="static"), name="static")

def generate_round_robin_rounds():
    Player.read_players_from_csv()
    t = Tournament.from_toml(
        Path.cwd() / 'tournaments' / 'russ_29' / 'config.toml',
        read_rounds = True,
        db = 'htmx',
    )
    # t.db_write([t])
    return t
    # rra = RoudRobinAssigner(t)
    # rra.prepare_tournament_rounds()
    # for r in t.rounds:
    #     r.write_csv(t.folder / 'rounds', db)

    # # Run app in CLI mode
    # main(t)

def generate_first_swiss_round():
    Player.read_players_from_csv()
    t = Tournament.from_toml(
        Path.cwd() / 'tournaments' / 'test_swiss' / 'config.toml',
        read_rounds = False,
        db = 'htmx',
    )
    t._create_initial_round()
    t.db_write([t])
    return t

def initialize_from_db():
    t = Tournament.from_db(
        [1]
    )
    if not t.players:
        t.players = Player.from_db([], all = True)[0]
    return t

# config.tournament = generate_round_robin_rounds()

# config.tournament = generate_first_swiss_round()


config.tournament = initialize_from_db()
init_htmx()

if __name__ == "__main__":
    create_db_and_tables()
    populate_test_data()
