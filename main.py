from pathlib import Path

from russ_swiss_tournament.tournament import Tournament
from russ_swiss_tournament.player import Player
from russ_swiss_tournament.matchup import Matchup, PlayerMatch
from russ_swiss_tournament.round import Round
from russ_swiss_tournament.tie_break import calc_modified_median_solkoff
from russ_swiss_tournament.matchup_assignment import MatchupsAssigner, RoundRobinAssigner
from russ_swiss_tournament.db import Database
from russ_swiss_tournament.cli import main
from russ_swiss_tournament.service import MatchResult, Color

def generate_round_robin_rounds():
    db = Database()
    db.read_players()
    t = Tournament.from_toml(
        Path.cwd() / 'tournaments' / 'dummy' / 'config.toml',
        read_rounds = True,
        db=db
    )
    # rra = RoundRobinAssigner(t)
    # rra.prepare_tournament_rounds()
    # for r in t.rounds:
    #     r.write_csv(t.folder / 'rounds', db)
    main(t)

generate_round_robin_rounds()

if __name__ == '__main__':
    pass
