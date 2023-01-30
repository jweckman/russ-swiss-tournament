import tomli
from pathlib import Path
from collections import Counter
import pprint

from russ_swiss_tournament.round import Round
from russ_swiss_tournament.player import Player
from russ_swiss_tournament.matchup import Matchup, MatchResult, Color, PlayerMatch
from russ_swiss_tournament import tie_break
from russ_swiss_tournament.service import pairwise, split_list


class Tournament:
    '''player list should be sorted by ranking before start of tournament'''
    def __init__(
            self,
            players: list[Player],
            rounds: list[Round],
            tie_break_results: dict[tie_break.TieBreakMethod, dict],
            used_tie_break: tie_break.TieBreakMethod,
            year: int,
            count: int,
            create_players: bool = False,
            folder: Path | None = None,
        ):
        self.players = players
        self.rounds = rounds
        self.tie_break_results = tie_break_results
        self.used_tie_break = used_tie_break
        self.year = year
        self.count = count
        self.folder = folder

    def __repr__(self):
        return pprint.pformat([[m.res for m in r.matchups] for r in self.rounds], indent=4)

    @classmethod
    def create_players(cls, ids, first_names = None, last_names = None):
        players = []
        if ids and not all([first_names, last_names]):
            for i, id in enumerate(ids):
                players.append(Player(id, f"p{i}f", f"p{i}l"))
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
        player_ids = config['players']['ids']
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
            folder = Path().cwd() / 'tournaments' / config['general']['folder'],
        )

    def calculate_tie_break_results(self):
        self.tie_break_results[tie_break.TieBreakMethod.HARKNESS] = tie_break.calc_harkness(
            self.rounds,
            [p.id for p in self.players]
        )

    def get_faced_players(self, until: str | int ='latest') -> dict[int,list[int]]:
        # TODO: add validation if faced twice
        player_ids = [p.id for p in self.players]
        if until == 'latest':
            index = len(self.rounds)
        else:
            index = until
        results = dict(zip(list(player_ids), [[] for i in range(len(player_ids))]))
        for r in self.rounds[:index]:
            for m in r.matchups:
                results[m.res[Color.W].id].append(m.res[Color.B].id)
                results[m.res[Color.B].id].append(m.res[Color.W].id)
        return results

    def get_player_color_counts(self, until: str | int ='latest') -> dict[int,list[int]]:
        player_ids = [p.id for p in self.players]
        if until == 'latest':
            index = len(self.rounds)
        else:
            index = until
        results = dict(zip(list(player_ids), [[0,0] for i in range(len(player_ids))]))
        # TODO: handle walkover not counting
        for r in self.rounds[:index]:
            for m in r.matchups:
                results[m.res[Color.W].id][0] += 1
                results[m.res[Color.B].id][1] += 1
        return results

    def get_standings(self, until: str | int ='latest') -> dict[int,float] | None:
        '''
        Get entire tournament standings until chosen round. Defaults to latest results.
        Round index is 1 based
        '''
        if until == 'latest':
            index = len(self.rounds)
        else:
            index = until
        res = None
        used_rounds = self.rounds[:index]
        for i, r in enumerate(used_rounds):
            if i == 0:
                res = r.get_results()
            else:
                res = dict(Counter(res)+Counter(r.get_results()))
        return res

    def validate_no_null_match_results_in_rounds(self):
        for r in self.rounds:
            for mu in r.matchups:
                if any([v.res == MatchResult.UNSET for v in mu.res.values()]):
                    raise ValueError(
                        f"Round {r.index} containes unset results, aborting new round generation"
                    )

    def _create_initial_round(self):
        # Players list should already be orderd by rank
        player_ids = [p.id for p in self.players]
        middle_index=len(player_ids)//2
        first, second = split_list(player_ids, middle_index)
        matchups = []
        for i, p in enumerate(first):
            matchups.append(Matchup({Color.W: PlayerMatch(second[i]),Color.B: PlayerMatch(p)}))
        self.rounds.append(Round(matchups, index = 1))


