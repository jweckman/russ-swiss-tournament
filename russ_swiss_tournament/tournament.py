import tomli
from pathlib import Path
from collections import Counter
import pprint
from enum import Enum
from typing import Self
import itertools

from sqlmodel import select, col

from russ_swiss_tournament.round import Round, match_result_score_map
from russ_swiss_tournament.player import Player
from russ_swiss_tournament.matchup import Matchup, PlayerMatch
from russ_swiss_tournament import tie_break
from russ_swiss_tournament.service import MatchResult, Color, pairwise, split_list

from htmx.db import get_session
from htmx.models import TournamentModel, RoundModel, PlayerModel, MatchupModel

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
            tie_break_results_swiss: dict[tie_break.TieBreakMethodSwiss, dict],
            tie_break_results_round_robin: dict[tie_break.TieBreakMethodRoundRobin, dict],
            year: int,
            count: int,
            id: int = -1,
            create_players: bool = False,
            folder: Path | None = None,
            round_folder: Path | None = None,
        ):
        if id == -1:
            self.id = next(self.id_iter)
        else:
            self.id = id
        self.name = name
        self.players = players
        self.rounds = rounds
        self.round_count = round_count
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
    def db_write(
            self,
            selves: list[Self],
            update: bool = True,
        ) -> list[TournamentModel]:
        '''Writes/updates selves to db'''
        session = next(get_session())
        ids = [t.id for t in selves]
        existing_db = [t for t in session.exec(select(TournamentModel).where(col(TournamentModel.id).in_(ids)))]
        print(session.exec(select(TournamentModel)).all())
        existing_db_ids = [t.id for t in existing_db]
        new_records: list[TournamentModel] = []
        for t_obj in selves:
            if t_obj.id in existing_db_ids:
                if update:
                    pass  # TODO
            else:
                new_record = TournamentModel(
                    name = t_obj.name,
                    year = t_obj.year,
                    count = t_obj.count,
                    round_count = t_obj.round_count,
                    round_system = t_obj.round_system.value,
                    # TODO test this out
                    players = Player.db_write(t_obj.players),
                    rounds = Round.db_write(t_obj.rounds),
                )
                session.add(new_record)
                session.flush()
                session.refresh(new_record)
                if new_record.id is None:
                    raise ValueError("Trying to create a tournament without an id")
                t_obj.id = new_record.id
                session.commit()
                new_records.append(new_record)
        return new_records

    @classmethod
    def from_db(
            cls,
            selves: list[Self] | list[int],
        ) -> Self:
        '''Writes/updates selves to db'''
        session = next(get_session())
        is_ids = False
        if isinstance(selves[0], int):
            is_ids = True
        ids = [t.id for t in selves] if not is_ids else selves
        tournament_model = [t for t in session.exec(select(TournamentModel).where(col(TournamentModel.id).in_(ids)))][0]
        tournament = Tournament(
            id = tournament_model.id,
            name = tournament_model.name,
            players = [], # TODO: instantiate players 
            rounds = Round.from_db([r.index for r in tournament_model.rounds])[0],
            round_count = tournament_model.round_count,
            round_system = RoundSystem.SWISS,
            tie_break_results_swiss = dict(),
            tie_break_results_round_robin = dict(),
            year = tournament_model.year,
            count = 30,  # TODO hard coded,
        )
        return tournament


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
            players = Player.from_db(player_ids)[1]
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
            name = config['general']['title'],
            players = players,
            rounds = rounds,
            round_count = config['general']['rounds'],
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
            [p.identifier for p in self.players],
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

    def get_opponents(
            self,
            until: str | int ='latest',
            inverse: bool = False,
        ) -> dict[int,list[int]]:
        '''
        Possible to get unplayed by setting inverse boolean to True.
        '''
        # TODO: add validation if faced twice
        player_ids = [p.identifier for p in self.players]
        if until == 'latest':
            index = len(self.rounds)
        else:
            index = until
        results = dict(zip(list(player_ids), [[] for i in range(len(player_ids))]))
        for r in self.rounds[:index]:
            for m in r.matchups:
                results[m.res[Color.W].player.id].append(m.res[Color.B].player.id)
                results[m.res[Color.B].player.id].append(m.res[Color.W].player.id)
        if inverse:
            for player, opponents in results.copy().items():
                players_minus_self = [p for p in player_ids if p != player]
                results[player] = [p for p in players_minus_self if p not in opponents]

        return results

    def get_player_defeated_drawn(self) -> (dict[int,list[list,list]], dict[int,dict[int,float]]):
        '''
        Returns 
        1.  dict with player id as key and list of lists with
            defeated players ids in the first one and drawn in the second.
        2.  dict with player id as key and dict containins match results by opponent.
        '''
        player_ids = [p.identifier for p in self.players]
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
        player_ids = [p.identifier for p in self.players]
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
            if p.identifier not in res:
                res[p.identifier] = 0
        return res

    def validate_no_incomplete_match_results_in_rounds(self):
        for round in self.rounds:
            if not round.is_complete():
                raise ValueError(
                    f"Round {round.index} contains unset results, cannot continue."
                )

    def validate_no_duplicate_matchups(self):
        '''
        Checks the added rounds for duplicate matchups.
        In case one is found, the last round is discarded.
        '''
        matchups = []
        for round in self.rounds:
            for mu in round.matchups:
                player_ids = set(mu.get_player_ids())
                if player_ids in matchups:
                    raise ValueError(
                        f"Round {round.index}\n{mu}\nis a duplicate.\n"
                        "This is not allowed in Swiss tournament generation.\n"
                        "Last tournament round was removed from the tournament."
                    )
                    self.rounds.pop(-1)
                else:
                    matchups.append(player_ids)

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
            print(f"Warning: Tried to access round index {index} that does not exist")
            return None
        return round

    def _create_initial_round(self):
        # Players list should already be orderd by rank
        middle_index=len(self.players)//2
        first, second = split_list(self.players.copy(), middle_index)
        matchups = []
        for i, p in enumerate(first):
            matchups.append(Matchup({Color.W: PlayerMatch(second[i]),Color.B: PlayerMatch(p)}))
        self.rounds.append(Round(matchups, index = 1))

    def get_player_matchups(self, player_id: str | int):
        player_matchups = []
        for r in self.rounds:
            player_matchups.append(r.get_player_matchup(player_id))
        return player_matchups

