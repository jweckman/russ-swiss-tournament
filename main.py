from pathlib import Path

import config

from russ_swiss_tournament.tournament import Tournament, RoundSystem
from russ_swiss_tournament.player import Player
from russ_swiss_tournament.matchup import Matchup
from russ_swiss_tournament.matchup_assignment import SwissAssigner, RoundRobinAssigner
from gui_tkinter.gui import tkinter_main
from russ_swiss_tournament.service import StartupMode


def generate_round_robin_rounds():
    Player.read_players_from_csv()
    t = Tournament.from_toml(
        Path.cwd() / 'tournaments' / 'russ_29' / 'config.toml',
        read_rounds = True,
        db = 'htmx',
    )
    config.tournament = t
    # t.db_write([t])
    # rra = RoudRobinAssigner(t)
    # rra.prepare_tournament_rounds()
    # for r in t.rounds:
    #     r.write_csv(t.folder / 'rounds', db)

    # # Run app in CLI mode
    # main(t)

def generate_first_swiss_round():
    Player.read_players_from_csv()
    t = Tournament.from_toml(
        Path.cwd() / 'tournaments' / 'russ_31' / 'config.toml',
        read_rounds = False,
        db = 'htmx',
    )
    t._create_initial_round()
    t.db_write([t])
    config.tournament = t

def initialize_from_db():
    t = Tournament.from_db(
        [1]
    )
    if t.round_system == RoundSystem.SWISS:
        config.assigner = SwissAssigner(t)
    elif t.round_system == RoundSystem.BERGER:
        config.assigner = RoundRobinAssigner(t)

    config.tournament = t

def startup():
    if config.mode == StartupMode.START_FROM_DB:
        initialize_from_db()
        tkinter_main()
    if config.mode == StartupMode.INIT_SWISS:
        config.tournament = generate_first_swiss_round()
    if config.mode == StartupMode.INIT_ROUND_ROBIN:
        config.tournament = generate_round_robin_rounds()
    if config.mode == StartupMode.INIT_DB_TABLES:
        create_db_and_tables()
    if config.mode == StartupMode.INIT_DB_TABLES_WITH_TEST_DATA:
        create_db_and_tables()
        populate_test_data()


if __name__ == "__main__":
    startup()
