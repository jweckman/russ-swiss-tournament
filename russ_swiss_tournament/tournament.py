import tomli
from pathlib import Path
from collections import Counter
import pprint

from russ_swiss_tournament.round import Round
from russ_swiss_tournament.player import Player
from russ_swiss_tournament.matchup import Matchup, MatchResult, Color, PlayerMatch
from russ_swiss_tournament import tie_break
from russ_swiss_tournament.service import pairwise

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
        ):
        self.players = players
        self.rounds = rounds
        self.tie_break_results = tie_break_results
        self.used_tie_break = used_tie_break
        self.year = year
        self.count = count

    def __repr__(self):
        return pprint.pformat([[m.res for m in r.matchups] for r in self.rounds], indent=4)

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

    def generate_round(self):
        if not self.rounds:
            self._create_initial_round()
        else:
            self.validate_no_null_match_results_in_rounds()
            self._create_next_round()

    def _create_initial_round(self):
        # TODO: initial round generation
        pass

    def _assign_matchup_colors(self, higher: int, lower: int) -> tuple[int,int]:
        player_color_counts = self.get_player_color_counts()
        h_colors = player_color_counts[higher]
        l_colors = player_color_counts[lower]
        white_diff = h_colors[0] - l_colors[0]
        black_diff = h_colors[1] - l_colors[1]
        if white_diff != 0:
            if white_diff > 0:
                white = lower
                black = higher
            elif white_diff < 0:
                black = lower
                white = higher
        elif black_diff != 0:
            if black_diff > 0:
                black = higher
                white = lower
            elif black_diff < 0:
                black = lower
                white = higher
        else:
            player_ids_by_rank = [p.id for p in self.players]
            higher_rank_index = player_ids_by_rank.index(higher)
            lower_rank_index = player_ids_by_rank.index(lower)
            if higher_rank_index < lower_rank_index:
                white = lower
                black = higher
            else:
                white = higher
                black = lower

        return white, black

    def _assign_round_colors(self) -> list[tuple[int,int]]:
        '''
        Returns list of player ids white, black
        TODO: Only works for even player count
        '''
        faced_players = self.get_faced_players()
        players_standing_sort = list(reversed(
            {k: v for k, v in sorted(self.get_standings().items(), key=lambda item: item[1])}.keys()
        ))
        results = []
        already_paired = set()
        def _find_matchup_pair():
            if len(players_standing_sort) == 0:
                return
            higher = players_standing_sort[0]
            for p in players_standing_sort[1:]:
                if p not in (already_paired | set(faced_players[higher])):
                    lower = p
                    break
            white, black = self._assign_matchup_colors(higher, lower)
            results.append((white, black))
            already_paired.add(players_standing_sort.pop(players_standing_sort.index(white)))
            already_paired.add(players_standing_sort.pop(players_standing_sort.index(black)))
            _find_matchup_pair()
        _find_matchup_pair()
        return results

    def _create_next_round(self):
        matchup_colors = self._assign_round_colors()
        matchups = []
        for mcs in matchup_colors:
            matchups.append(Matchup({Color.W: PlayerMatch(mcs[0]), Color.B: PlayerMatch(mcs[1])}))
        self.rounds.append(
            Round(matchups, index = self.rounds[-1].index + 1)
        )

