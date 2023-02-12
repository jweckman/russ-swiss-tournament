import tomli
from pathlib import Path
from collections import Counter
import pprint
from enum import Enum

from russ_swiss_tournament.round import Round, match_result_score_map
from russ_swiss_tournament.player import Player
from russ_swiss_tournament.matchup import Matchup, PlayerMatch
from russ_swiss_tournament import tie_break
from russ_swiss_tournament.service import MatchResult, Color, pairwise, split_list

class RoundSystem(Enum):
    SWISS = 1
    BERGER = 2

round_system_tie_break_map = {
    RoundSystem.SWISS: tie_break.TieBreakMethodSwiss,
    RoundSystem.BERGER: tie_break.TieBreakMethodRoundRobin,
}

class Tournament:
    '''player list should be sorted by ranking before start of tournament'''
    def __init__(
            self,
            players: list[Player],
            rounds: list[Round],
            round_system: RoundSystem,
            tie_break_results_swiss: dict[tie_break.TieBreakMethodSwiss, dict],
            tie_break_results_round_robin: dict[tie_break.TieBreakMethodRoundRobin, dict],
            year: int,
            count: int,
            create_players: bool = False,
            folder: Path | None = None,
            round_folder: Path | None = None,
        ):
        self.players = players
        self.rounds = rounds
        self.round_system = round_system
        self.tie_break_results_swiss = tie_break_results_swiss
        self.tie_break_results_round_robin = tie_break_results_round_robin
        self.year = year
        self.count = count
        self.folder = folder
        self.round_folder = round_folder

    def __repr__(self):
        return pprint.pformat([[m.res for m in r.matchups] for r in self.rounds], indent=4)

    @property
    def rounds(self):
        return self._rounds

    @rounds.setter
    def rounds(self, value):
        for i, round in enumerate(value):
            if not round.index == i + 1:
                raise ValueError(
                    "Round object indicies not in same order as tournament "
                    "level list object. This means some part of the code is "
                    "not respecting this ordering and should be fixed."
                )
        self._rounds = value

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
    def read_rounds(cls, round_folder, players):
        rdir = round_folder
        csv_files = [rf for rf in rdir.iterdir() if rf.suffix == '.csv']
        csv_files = sorted(csv_files, key = lambda x: int(''.join(c for c in x.stem if c.isdigit())))

        rounds = []
        for i, f in enumerate(csv_files):
            rounds.append(Round.read_csv(f, i+1, players))
        return rounds

    @classmethod
    def from_toml(
            cls,
            path,
            read_rounds = True,
            create_players = False,
            db = None
        ):
        with open(path, mode="rb") as fp:
            config = tomli.load(fp)
        round_path = Path().cwd() / 'tournaments' / config['general']['folder'] / config['general']['round_folder']

        rounds = []
        player_ids = config['players']['ids']
        if create_players:
            players = cls.create_players(player_ids)
        elif db:
            players = [db.get_player_by_id(pid) for pid in player_ids]
        if read_rounds:
            rounds = cls.read_rounds(round_path, players)
        swiss_tie_break = config['general'].get('tie_break_methods_swiss')
        round_robin_tie_break = config['general'].get('tie_break_methods_round_robin')
        try:
            if swiss_tie_break:
                used_swiss = [getattr(tie_break.TieBreakMethodSwiss, x.upper()) for x in swiss_tie_break]
            else:
                used_swiss = []
            if round_robin_tie_break:
                used_round_robin = [getattr(tie_break.TieBreakMethodRoundRobin, x.upper()) for x in round_robin_tie_break]
            else:
                used_round_robin = []
        except AttributeError as e:
            raise AttributeError(
                "Misspelled tie break method. Available values are: "
                f"{', '.join([x.name.lower() for x in tie_break.TieBreakMethodSwiss])}"
                f", {', '.join([x.name.lower() for x in tie_break.TieBreakMethodRoundRobin])}"
            ) from e
        rs = getattr(RoundSystem, config['general']['round_system'].upper())

        return cls(
            players = players,
            rounds = rounds,
            round_system = rs,
            tie_break_results_swiss = {x: None for x in used_swiss},
            tie_break_results_round_robin = {x: None for x in used_round_robin},
            year = config['general']['year'],
            count = config['general']['count'],
            folder = Path().cwd() / 'tournaments' / config['general']['folder'],
            round_folder = round_path
        )

    def calculate_tie_break_results_swiss(self):
        mm, solk = tie_break.calc_modified_median_solkoff(
            self.rounds[:self.get_last_complete_round_index()],
            [p.id for p in self.players],
            self.get_opponents()
        )
        self.tie_break_results_swiss[tie_break.TieBreakMethodSwiss.MODIFIED_MEDIAN] = mm
        self.tie_break_results_swiss[tie_break.TieBreakMethodSwiss.SOLKOFF] = solk

    def calculate_tie_break_results_round_robin(self):
        sonne, koya = tie_break.calc_sonne_koya(
            *self.get_player_defeated_drawn(),
            self.get_standings(),
            len(self.rounds),
        )
        self.tie_break_results_round_robin[tie_break.TieBreakMethodRoundRobin.SONNEBORN_BERGER] = sonne
        self.tie_break_results_round_robin[tie_break.TieBreakMethodRoundRobin.KOYA] = koya

    def get_opponents(self, until: str | int ='latest') -> dict[int,list[int]]:
        # TODO: add validation if faced twice
        player_ids = [p.id for p in self.players]
        if until == 'latest':
            index = len(self.rounds)
        else:
            index = until
        results = dict(zip(list(player_ids), [[] for i in range(len(player_ids))]))
        for r in self.rounds[:index]:
            for m in r.matchups:
                results[m.res[Color.W].player.id].append(m.res[Color.B].player.id)
                results[m.res[Color.B].player.id].append(m.res[Color.W].player.id)
        return results

    def get_player_defeated_drawn(self) -> (dict[int,list[list,list]], dict[int,dict[int,float]]):
        '''
        Returns 
        1.  dict with player id as key and list of lists with
            defeated players ids in the first one and drawn in the second.
        2.  dict with player id as key and dict containins match results by opponent.
        '''
        player_ids = [p.id for p in self.players]
        pdd = dict(zip(list(player_ids), [[[],[]] for i in range(len(player_ids))]))
        pdd_scores = dict(zip(list(player_ids), [dict() for i in range(len(player_ids))]))
        for r in self.rounds[:self.get_last_complete_round_index()]:
            for m in r.matchups:
                score_white = match_result_score_map[m.res[Color.W].res]
                score_black = match_result_score_map[m.res[Color.B].res]
                if score_white == 1:
                    pdd[m.res[Color.W].player.id][0].append(m.res[Color.B].player.id)
                if score_white == 0.5:
                    pdd[m.res[Color.W].player.id][1].append(m.res[Color.B].player.id)
                pdd_scores[m.res[Color.W].player.id][m.res[Color.B].player.id] = score_white
                if score_black == 1:
                    pdd[m.res[Color.B].player.id][0].append(m.res[Color.W].player.id)
                if score_white == 0.5:
                    pdd[m.res[Color.B].player.id][1].append(m.res[Color.W].player.id)
                pdd_scores[m.res[Color.B].player.id][m.res[Color.W].player.id] = score_black
        return pdd, pdd_scores


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
                results[m.res[Color.W].player.id][0] += 1
                results[m.res[Color.B].player.id][1] += 1
        return results

    def get_standings(
            self,
            until: str | int = 'latest_complete'
        ) -> dict[int,float] | None:
        '''
        Get entire tournament standings until chosen round. Defaults to latest complete results.
        Ascending sort of result dictionary.
        Round index is 1 based
        '''
        if until == 'latest':
            index = len(self.rounds)
        elif until == 'latest_complete':
            index = self.get_last_complete_round_index()
            if not index:
                raise ValueError(
                    "No completed rounds yet, standings could not be calculated"
                )
        else:
            index = until
        res = None
        used_rounds = self.rounds[:index]
        # TODO fix recursion error with tie break inside get_standings()
        # self.calculate_tie_break_results_round_robin()
        # self.calculate_tie_break_results_swiss()
        # TODO sort by standings and tie break
        for i, r in enumerate(used_rounds):
            if i == 0:
                res = r.get_results()
            else:
                res = dict(Counter(res)+Counter(r.get_results()))
        res = {k: v for k, v in sorted(res.items(), key=lambda item: item[1], reverse=True)}
        for p in self.players:
            if p.id not in res:
                res[p.id] = 0
        return res

    def validate_no_incomplete_match_results_in_rounds(self):
        for round in self.rounds:
            if not round.is_complete():
                raise ValueError(
                    f"Round {round.index} contains unset results, cannot continue."
                )
    def get_last_complete_round_index(self) -> int | None:
        if not self.rounds:
            return None
        sorted_rounds = sorted(self.rounds, key = lambda x: x.index)
        complete_rounds = [r for r in sorted_rounds if r.is_complete()]
        if complete_rounds:
            return complete_rounds[-1].index
        else:
            return None

    def _create_initial_round(self):
        # Players list should already be orderd by rank
        middle_index=len(self.players)//2
        first, second = split_list(self.players.copy(), middle_index)
        matchups = []
        for i, p in enumerate(first):
            matchups.append(Matchup({Color.W: PlayerMatch(second[i]),Color.B: PlayerMatch(p)}))
        self.rounds.append(Round(matchups, index = 1))

    def get_player_matchups(self, player_id):
        player_matchups = []
        for r in self.rounds:
            player_matchups.append(r.get_player_matchup(player_id))
        return player_matchups

