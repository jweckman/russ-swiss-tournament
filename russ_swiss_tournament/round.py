import itertools
import csv
from typing import Self
from io import StringIO
from pathlib import Path

from sqlmodel import select, col

from russ_swiss_tournament.matchup import Matchup, PlayerMatch
from russ_swiss_tournament.player import Player
from russ_swiss_tournament.db import Database
from russ_swiss_tournament.service import MatchResult, Color, match_result_manual_map, match_result_score_map, match_result_score_text_map
from config import tournament

from htmx.db import get_session
from htmx.models import TournamentModel, RoundModel

match_result_manual_map = {
    1: MatchResult.WIN,
    '1': MatchResult.WIN,
    0: MatchResult.LOSS,
    '0': MatchResult.LOSS,
    0.5: MatchResult.DRAW,
    '0.5': MatchResult.DRAW,
    "0,5": MatchResult.DRAW,
    "wo": MatchResult.WALKOVER,
    "walkover": MatchResult.WALKOVER,
    None: MatchResult.UNSET,
    "": MatchResult.UNSET,
    False: MatchResult.UNSET,
}

match_result_score_map = {
    MatchResult.WIN:  1,
    MatchResult.LOSS: 0,
    MatchResult.DRAW: 0.5,
    MatchResult.UNSET: None,
    MatchResult.WALKOVER: 0,
}

match_result_score_text_map = {
    MatchResult.WIN:  1,
    MatchResult.LOSS: 0,
    MatchResult.DRAW: 0.5,
    MatchResult.UNSET: None,
    MatchResult.WALKOVER: 'wo',
}

class Round:
    '''Note: index var starts from 1 to match with csv file names'''
    id_iter = itertools.count()
    def __init__(
            self,
            matchups: list[Matchup],
            index: int = 1,
            id: int = -1,
        ):
        if id == -1:
            self.id = next(self.id_iter) + 1
        else:
            self.id = id
        self.matchups = matchups
        self.index = index

    @classmethod
    def db_write(
            cls,
            selves: list[Self],
            update: bool = True,
        ):
        '''Writes/updates selves to db'''
        session = next(get_session())
        ids = [r.index for r in selves]
        existing_db = [r for r in session.exec(select(RoundModel).where(col(RoundModel.id).in_(ids)))]
        existing_db_ids = [r.index for r in existing_db]

        new_records: list[RoundModel] = []
        for r_obj in selves:
            db_round = None
            if r_obj.index in existing_db_ids:
                if update and len(existing_db) == 1:
                    db_round = existing_db[0]
                    [session.delete(m) for m in db_round.matchups]
                    session.commit()
                else:
                    # TODO: implement multi-delete
                    return []
            if db_round:
                Matchup.db_write(r_obj.matchups, round_id = db_round.id)
            else:
                new_record = RoundModel(
                    index = r_obj.index,
                    matchups = Matchup.db_write(r_obj.matchups),
                    tournament_id = 1,  # TODO: hard coded
                )
                session.add(new_record)
                session.flush()
                session.refresh(new_record)
                if new_record.id is None:
                    raise ValueError("Trying to create a matchup without an id")
                r_obj.id = new_record.id
                session.commit()
                new_records.append(new_record)
        return new_records

    @classmethod
    def from_db(
            cls,
            selves: list[Self] | list[int],
        ) -> tuple[list[Self], list[RoundModel]]:
        is_ids = False
        if isinstance(selves[0], int):
            is_ids = True
        session = next(get_session())
        ids = [t.index for t in selves] if not is_ids else selves
        existing_db = [t for t in session.exec(select(RoundModel).where(col(RoundModel.id).in_(ids)))]
        if len(existing_db) != len(selves):
            raise ValueError(
                f"Trying to create {cls.__name__} from db records but some ids are missing.\n"
                f"Please make sure that all the following ids are in the db: {ids}"
            )
        objects: list = []
        for record in existing_db:
            objects.append(
                Round(
                    id = record.id,
                    index = record.index,
                    matchups = Matchup.from_db(record.matchups)[0]
                )
            )
        if not objects:
            raise ValueError(f"Could not create {cls.__name__}, no matching records in db")
        return objects, existing_db

    @classmethod
    def match_player(cls, s:str, players: list[Player]) -> Player:
        res = None
        sanitized = s.lower().strip()
        for p in players:
            if (sanitized.isdigit() and str(p.identifier) == sanitized
                    or p.get_full_name().lower().strip() == sanitized):
                res = p
                break
        return res

    @classmethod
    def read_csv(
            cls,
            path: str | Path | StringIO,
            index,
            players: list[Player] | None = None
        ):
        matchups = []
        if isinstance(path, str) or isinstance(path, Path):
            csv_file = open(path, newline='')
        elif isinstance(path, StringIO):
            csv_file = path
        # with open(path, newline='') as csv_file:
        try:
            round_reader = csv.reader(csv_file, delimiter=',', quotechar='"')
            headers = next(round_reader, None)
            for line in round_reader:
                white_player = cls.match_player(line[0], players)
                black_player = cls.match_player(line[2], players)
                if (white_player is None
                        or black_player is None
                        or any([pid not in [x.identifier for x in players] for pid in [white_player.identifier, black_player.identifier]])):
                    raise ValueError(
                        f"Could not match player {line[0]} or player {line[2]} "
                        "based on id or full name. Check exact typing from database"
                    )
                matchup = Matchup({
                    Color.W: PlayerMatch(white_player, match_result_manual_map[line[1]]),
                    Color.B: PlayerMatch(black_player, match_result_manual_map[line[3]])
                })
                matchups.append(matchup)
        finally:
            if isinstance(csv_file, str) or isinstance(csv_file, Path):
                csv_file.close()
        return cls(matchups, index)

    def get_results(self) -> dict[int,float]:
        player_ids = self.get_player_ids()
        results = dict(zip(list(player_ids), [0 for i in range(len(player_ids))]))
        for m in self.matchups:
            results[m.res[Color.W].player.identifier] = match_result_score_map[m.res[Color.W].res]
            results[m.res[Color.B].player.identifier] = match_result_score_map[m.res[Color.B].res]
        return results

    def get_player_ids(self):
        player_ids = set()
        for m in self.matchups:
            rps = [p.player.identifier for p in m.res.values()]
            for p in rps:
                player_ids.add(p)
        return player_ids

    def get_player_matchup(self, player_id: int | str) -> None | Matchup:
        for m in self.matchups:
            player_ids = [str(pm.player.identifier) for pm in m.res.values()]
            if str(player_id) in player_ids:
                return m
        return None

    def write_csv(
            self,
            path,
            db: Database | None = None,
        ):
        '''Path refers to a folder. File names are automated based on round index'''
        with open(path / f"round{self.index}.csv", 'w', newline='') as csv_file:
            round_writer = csv.writer(csv_file, delimiter=',', quotechar='"')
            header_row = ["white", "score_white", "black", "score_black"]
            round_writer.writerow(header_row)
            rows = []
            for m in self.matchups:
                if db:
                    white = db.get_player_by_id(m.res[Color.W].player.identifier).get_full_name()
                    black = db.get_player_by_id(m.res[Color.B].player.identifier).get_full_name()
                else:
                    white = m.res[Color.W].player.identifier
                    black = m.res[Color.B].player.identifier
                row = [
                    white,
                    match_result_score_text_map[m.res[Color.W].res],
                    black,
                    match_result_score_text_map[m.res[Color.B].res],
                ]
                rows.append(row)
            round_writer.writerows(rows)

    def is_complete(self):
        if any([MatchResult.UNSET in [x.res for x in v.res.values()] for v in self.matchups]):
            return False
        return True

