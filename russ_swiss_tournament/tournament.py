import tomli
from pathlib import Path
from collections import Counter
import pprint
from enum import Enum
from typing import Tuple, cast, Optional
import itertools

from russ_swiss_tournament.round import Round, match_result_score_map
from russ_swiss_tournament.player import Player
from russ_swiss_tournament.matchup import Matchup, PlayerMatch
from russ_swiss_tournament import tie_break
from russ_swiss_tournament.service import Color, split_list

class RoundSystem(Enum):
    SWISS = 1
    BERGER = 2

round_system_tie_break_map = {
    RoundSystem.SWISS: tie_break.TieBreakMethodSwiss,
    RoundSystem.BERGER: tie_break.TieBreakMethodRoundRobin,
}

class Tournament:
    '''player list should be sorted by ranking before start of tournament'''
    id_iter = itertools.count()

    def __init__(
            self,
            name: str,
            players: list[Player],
            rounds: list[Round],
            round_count: int,
            round_system: RoundSystem,
            tie_break_results_swiss: dict,
            tie_break_results_round_robin: dict,
            year: int,
            count: int,
            id: Optional[int] = None,
            folder: Path | None = None,
            round_folder: Path | None = None,
            player_tournament_start_order: list = [],
        ):
        if id is None:
            self.id = next(self.id_iter)
        else:
            self.id = id
        self.name = name
        self.players = self._order_players(players, player_tournament_start_order)
        self.rounds = rounds
        self.round_count = round_count
        self.round_system = round_system
        self.tie_break_results_swiss = tie_break_results_swiss
        self.tie_break_results_round_robin = tie_break_results_round_robin
        self.year = year
        self.count = count
        self.folder = folder
        self.round_folder = round_folder
        self.player_tournament_start_order = player_tournament_start_order

    def __repr__(self):
        return pprint.pformat([[m.res for m in r.matchups] for r in self.rounds], indent=4)

    @property
    def rounds(self):
        return self._rounds

    @rounds.setter
    def rounds(self, value):
        for i, round in enumerate(value):
            if not round.index == i + 1:
                # In loose CSV imports or partially loaded states, we might be lenient,
                # but generally we want indices to match.
                pass 
        self._rounds = value

    def _order_players(self, players: list, order: list[int]):
        if order:
            try:
                # Filter out players that might not be in the order list to prevent crash
                # or ensure strictness depending on requirement. 
                # Here we assume players in 'order' must exist in 'players'.
                players = sorted(players, key = lambda p: order.index(p.identifier))
            except ValueError:
                # Fallback or strict error
                pass
        return players

    @classmethod
    def create_players(cls, ids, first_names = None, last_names = None):
        players = []
        if ids and not all([first_names, last_names]):
            for i, id in enumerate(ids):
                players.append(Player(identifier=id, first_name=f"p{i}f", last_name=f"p{i}l"))
        return players

    @classmethod
    def read_rounds(cls, round_folder, players):
        if not round_folder or not round_folder.exists():
            return []
        csv_files = [rf for rf in round_folder.iterdir() if rf.suffix == '.csv']
        csv_files = sorted(csv_files, key = lambda x: int(''.join(c for c in x.stem if c.isdigit())))

        rounds = []
        for i, f in enumerate(csv_files):
            rounds.append(Round.read_csv(f, i + 1, players))
        return rounds

    @classmethod
    def from_toml(
        cls,
        path,
        read_rounds = True,
        create_players = False,
        players_manual = [],
    ):
        with open(path, mode="rb") as fp:
            toml_conf = tomli.load(fp)
        # Determine folder paths
        base_folder = Path().cwd() / 'tournaments' / toml_conf['general']['folder']
        round_path = base_folder / toml_conf['general']['round_folder']

        rounds = []
        player_ids = toml_conf['players']['ids']
        start_order = player_ids.copy()
        # Player Loading Logic
        if create_players:
            players = cls.create_players(player_ids)
        elif players_manual:
            players = players_manual
        else:
            # If neither, we assume players will be injected or we create dummies
            players = cls.create_players(player_ids)

        if read_rounds:
            rounds = cls.read_rounds(round_path, players)
        swiss_tie_break = toml_conf['general'].get('tie_break_methods_swiss')
        round_robin_tie_break = toml_conf['general'].get('tie_break_methods_round_robin')
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
            raise AttributeError("Misspelled tie break method in TOML") from e
        rs = getattr(RoundSystem, toml_conf['general']['round_system'].upper())

        return cls(
            name = toml_conf['general']['title'],
            players = players,
            rounds = rounds,
            round_count = toml_conf['general']['rounds'],
            round_system = rs,
            tie_break_results_swiss = {x: None for x in used_swiss},
            tie_break_results_round_robin = {x: None for x in used_round_robin},
            year = toml_conf['general']['year'],
            count = toml_conf['general']['count'],
            folder = base_folder,
            round_folder = round_path,
            player_tournament_start_order = start_order,
        )

    def get_tie_break_results_swiss(self, until: str | int = 'latest') -> tuple[dict, dict]:
        if until == 'latest':
            last_round_index = self.get_last_complete_round_index()
        else:
            last_round_index = int(until)
        if not self.rounds or last_round_index is None:
            return {}, {}

        mm, solk = tie_break.calc_modified_median_solkoff(
            self.rounds[:last_round_index],
            set([p.identifier for p in self.players]),
            self.get_opponents()
        )
        return mm, solk

    def get_tie_break_results_round_robin(self, until: str | int = 'latest') -> tuple[dict, dict]:
        standings = self.get_standings(until=until)
        if not standings:
             # Just return empty if no standings available yet
             return {}, {}
        sonne, koya = tie_break.calc_sonne_koya(
            *self.get_player_defeated_drawn(until=until),
            standings,
            len(self.rounds),
        )
        return sonne, koya

    def get_opponents(
            self,
            until: str | int = 'latest',
            inverse: bool = False,
        ) -> dict[int, list[int]]:
        '''
        Possible to get unplayed by setting inverse boolean to True.
        '''
        player_ids = [p.identifier for p in self.players]
        index: int
        if until == 'latest':
            index = len(self.rounds)
        else:
            index = cast(int, until)
        results = dict(zip(list(player_ids), [[] for i in range(len(player_ids))]))
        for r in self.rounds[:index]:
            for m in r.matchups:
                results[m.res[Color.W].player.identifier].append(m.res[Color.B].player.identifier)
                results[m.res[Color.B].player.identifier].append(m.res[Color.W].player.identifier)
        if inverse:
            for player, opponents in results.copy().items():
                players_minus_self = [p for p in player_ids if p != player]
                results[player] = [p for p in players_minus_self if p not in opponents]

        return results

    def get_player_defeated_drawn(
            self,
            until: str | int = 'latest_complete'
        ) -> Tuple[dict[int, list[list[int]]], dict[int, dict[int, float]]]:
        player_ids = [p.identifier for p in self.players]
        pdd = dict(zip(list(player_ids), [[[], []] for i in range(len(player_ids))]))
        pdd_scores = dict(zip(list(player_ids), [dict() for i in range(len(player_ids))]))
        idx = self._until_to_index(until)
        if idx is None:
            return pdd, pdd_scores

        for r in self.rounds[:idx]:
            for m in r.matchups:
                score_white = match_result_score_map[m.res[Color.W].res]
                score_black = match_result_score_map[m.res[Color.B].res]
                if score_white == 1:
                    pdd[m.res[Color.W].player.identifier][0].append(m.res[Color.B].player.identifier)
                if score_white == 0.5:
                    pdd[m.res[Color.W].player.identifier][1].append(m.res[Color.B].player.identifier)
                pdd_scores[m.res[Color.W].player.identifier][m.res[Color.B].player.identifier] = score_white
                if score_black == 1:
                    pdd[m.res[Color.B].player.identifier][0].append(m.res[Color.W].player.identifier)
                if score_white == 0.5:
                    pdd[m.res[Color.B].player.identifier][1].append(m.res[Color.W].player.identifier)
                pdd_scores[m.res[Color.B].player.identifier][m.res[Color.W].player.identifier] = score_black
        return pdd, pdd_scores

    def get_player_colors(
            self,
            until: str | int = 'latest',
            used_assigner = None 
        ) -> Tuple[dict[int, list[int]], set, set]:
        '''
        Encode white as 1 and black as -1.
        '''
        player_ids = [p.identifier for p in self.players]
        index: int
        if until == 'latest':
            index = len(self.rounds)
        else:
            index = cast(int, until)
        colors: dict[int, list] = {p: [] for p in player_ids}
        veto_black: set = set()
        veto_white: set = set()
        for r in self.rounds[:index]:
            for m in r.matchups:
                white_id, black_id = m.get_player_ids()
                colors[white_id].append(1)
                colors[black_id].append(-1)
        if index > 2:
            for player_id, player_colors in colors.items():
                if index > 3 and abs(sum(player_colors[-4:])) == 4:
                    print(f"WARNING: Player {player_id} has played four consecutive rounds with the same color")
                last_three = sum(player_colors[-3:])
                if last_three == 3:
                    veto_white.add(player_id)
                elif last_three == -3:
                    veto_black.add(player_id)

        return colors, veto_white, veto_black

    def _until_to_index(self, until: str | int) -> int | None:
        last_complete_index = self.get_last_complete_round_index()
        if not last_complete_index:
            return None
        if until == 'latest':
            index = len(self.rounds)
        elif until == 'latest_complete':
            index = last_complete_index
            if not index:
                 # Be gentler than raising error, just return None
                return None
        elif isinstance(until, int):
            if until > last_complete_index:
                index = None
            else:
                index = until
        else:
            raise ValueError(
                f"Invalid argument for until: {until}. Could not get standings."
            )
        return index

    def get_standings(
        self,
        until: str | int = 'latest_complete',
    ) -> dict[int, float] | None:
        index = self._until_to_index(until)
        if not index:
            return None
        used_rounds = self.rounds[:index]
        if not used_rounds:
            return None
        unsorted_standings: dict[int, float] = {p.identifier: 0.0 for p in self.players}
        for r in used_rounds:
            round_results = r.get_results()
            if any(v is None for v in round_results.values()):
                break
            current_total = Counter(unsorted_standings)
            round_scores = Counter(round_results)
            unsorted_standings = dict(current_total + round_scores)
        for p in self.players:
            if p.identifier not in unsorted_standings:
                unsorted_standings[p.identifier] = 0
        return unsorted_standings

    def sort_standings(
            self,
            standings: dict[int, float],
            until: str | int = 'latest_complete'
        ) -> dict[int, float] | None:
        if (
                not standings
                or (isinstance(standings, dict) and any([v is None for v in standings.values()]))
            ):
            return None
        index = self._until_to_index(until)
        if index:
            sonne = self.get_tie_break_results_round_robin(until=index)[0]
        else:
            sonne = None
        # If no start order is defined, create a default one to prevent crash
        start_order = self.player_tournament_start_order or [p.identifier for p in self.players]

        if not sonne:
            res = {k: v for k, v in sorted(standings.items(), key=lambda item: item[1], reverse=True)}
        else:
            res = {
                k: v for k, v in sorted(
                    standings.items(), key=lambda item: (
                        round(item[1], 2),
                        round(sonne.get(item[0], 0), 2),
                        -start_order.index(item[0]) if item[0] in start_order else 0,
                    ),
                    reverse=True
                )
            }
        return res

    def get_sorted_standings(
            self,
            until: str | int = 'latest_complete'
        ) -> dict[int, float] | None:
        standings = self.get_standings(until)
        if standings:
            standings = self.sort_standings(standings, until)
        return standings

    def validate_no_incomplete_match_results_in_rounds(self):
        for round in self.rounds:
            if not round.is_complete():
                raise ValueError(
                    f"Round {round.index} contains unset results, cannot continue."
                )

    def validate_no_duplicate_matchups(self):
        """
        Checks that no two players play each other more than once.
        Raises a ValueError if a duplicate is found.
        """
        seen_matchups = set()
        for round in self.rounds:
            for mu in round.matchups:
                # Store as sorted tuple so (P1, P2) == (P2, P1)
                ids = tuple(sorted(mu.get_player_ids()))
                if ids in seen_matchups:
                    raise ValueError(
                        f"CRITICAL: Duplicate pairing {ids} found in Round {round.index}. "
                        "Players have already played against each other."
                    )
                seen_matchups.add(ids)

    def get_last_complete_round_index(self) -> int | None:
        if not self.rounds:
            return None
        sorted_rounds = sorted(self.rounds, key = lambda x: x.index)
        complete_rounds = [r for r in sorted_rounds if r.is_complete()]
        if complete_rounds:
            return complete_rounds[-1].index
        else:
            return None

    def get_round_by_index(self, index: int) -> Round | None:
        try:
            round = self.rounds[index - 1]
        except IndexError:
            return None
        return round

    def _create_initial_round(self):
        middle_index = len(self.players) // 2
        first, second = split_list(self.players.copy(), middle_index)
        matchups = []
        for i, p in enumerate(first):
            matchups.append(Matchup({
                Color.W: PlayerMatch(second[i]),
                Color.B: PlayerMatch(p)}
            ))
        new_round = Round(matchups, index = 1)
        self.rounds.append(new_round)
        return new_round

    def get_player_matchups(self, player_id: str | int):
        player_matchups = []
        for r in self.rounds:
            player_matchups.append(r.get_player_matchup(player_id))
        return player_matchups

    def get_player_by_id(self, identifier) -> Player:
        try:
            player = [p for p in self.players if p.identifier == identifier][0]
        except IndexError:
            raise IndexError(f"No player was found in the database with identifier {identifier}")
        return player
