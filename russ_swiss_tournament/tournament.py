import tomli
from pathlib import Path

from russ_swiss_tournament.round import Round
from russ_swiss_tournament.player import Player
from russ_swiss_tournament import tie_break

class Tournament:
    def __init__(
            self,
            players: set[Player],
            rounds: list[Round],
            tie_break_results: dict[tie_break.TieBreakMethod, dict],
            used_tie_break: tie_break.TieBreakMethod,
            year: int,
            count: int,
            create_players: bool = False,
        ):
        self.players = players
        self.rounds = rounds
        self.tie_break_results = tie_break_results
        self.used_tie_break = used_tie_break
        self.year = year
        self.count = count

    @classmethod
    def create_players(cls, ids, first_names = None, last_names = None):
        players = set()
        if ids and not all([first_names, last_names]):
            for i, id in enumerate(ids):
                players.add(Player(id, f"p{i}f", f"p{i}l"))
        else:
            # TODO: allow creating based on names as well
            pass
        return players

    @classmethod
    def read_rounds(cls, toml_path, players):
        rdir = Path(toml_path).parent / 'rounds'
        csv_files = [rf for rf in rdir.iterdir() if rf.suffix == '.csv']
        csv_files = sorted(csv_files, key = lambda x: int(''.join(c for c in x.stem if c.isdigit())))

        rounds = []
        for i, f in enumerate(csv_files):
            rounds.append(Round.read_csv(f, i, players))
        return rounds

    @classmethod
    def from_toml(cls, path, read_rounds = True, create_players = False):
        with open(path, mode="rb") as fp:
            config = tomli.load(fp)

        rounds = []
        player_ids = set(config['players']['ids'])
        if create_players:
            players = cls.create_players(player_ids)
        if read_rounds:
            rounds = cls.read_rounds(path, players)

        return cls(
            players = players,
            rounds = rounds,
            tie_break_results = dict(),
            used_tie_break = getattr(tie_break.TieBreakMethod, config['general']['tie_break_method'].upper()),
            year = config['general']['year'],
            count = config['general']['count'],
        )

    def calculate_tie_break_results(self):
        self.tie_break_results[tie_break.TieBreakMethod.HARKNESS] = tie_break.calc_harkness(self.rounds, set([p.id for p in self.players]))
