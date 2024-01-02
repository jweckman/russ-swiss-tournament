from enum import Enum
from dataclasses import dataclass
import itertools
from typing import Self, Any

from sqlmodel import select, col

from russ_swiss_tournament.player import Player
from russ_swiss_tournament.service import  MatchResult, Color, match_result_manual_map, match_result_score_map, match_result_score_text_map

from htmx.db import get_session
from htmx.models import MatchupModel, RoundModel


@dataclass
class PlayerMatch:
    player: Player
    res: MatchResult = MatchResult.UNSET

class Matchup:
    id_iter = itertools.count()
    def __init__(
            self,
            res: dict[Color, PlayerMatch],
        ):
        self.id = next(self.id_iter) + 1
        self.res = res

    @property
    def res(self):
        return self._res

    @res.setter
    def res(self, value):
        self.validate_result(value)
        self._res = value

    @classmethod
    def from_db(
            cls,
            selves: list[Self] | list[int],
        ) -> tuple[list[Self], list[MatchupModel]]:
        is_ids = False
        if isinstance(selves[0], int):
            is_ids = True
        session = next(get_session())
        ids = [m.id for m in selves] if not is_ids else selves
        existing_db = [m for m in session.exec(select(MatchupModel).where(col(MatchupModel.id).in_(ids)))]
        if len(existing_db) != len(selves):
            raise ValueError(
                f"Trying to create {cls.__name__} from db records but some ids are missing.\n"
                f"Please make sure that all the following ids are in the db: {ids}"
            )
        objects: list = []
        for record in existing_db:
            matchup = {
                Color.W: PlayerMatch(Player.from_db([record.white_identifier])[1][0], MatchResult(record.white_score)),
                Color.B: PlayerMatch(Player.from_db([record.black_identifier])[1][0], MatchResult(record.black_score))
            }
            objects.append(
                Matchup(
                    res = matchup,
                )
            )
        session.close()
        return objects, existing_db

    @classmethod
    def db_write(
            self,
            selves: list[Self],
            update: bool = False,
        ) -> list[MatchupModel]:
        '''Writes/updates selves to db'''
        session = next(get_session())
        ids = [m.id for m in selves]
        existing_db = [m for m in session.exec(select(MatchupModel).where(col(MatchupModel.id).in_(ids)))]
        existing_db_ids = [m.id for m in existing_db]
        if existing_db and not update:
            raise ValueError(
                "Writing existing ids to db without update flag enabled. Terminating."
            )
        if update and len(existing_db_ids) != len(ids):
            raise ValueError(
                "Trying to update and create matchup model at the same time which is not allowed.\n"
                f"Trying to create: {[id for id in ids if id not in existing_db_ids]}"
            )
        db_records: list = []
        for t_obj in selves:
            if t_obj.id in existing_db_ids:
                matchup_model = existing_db[existing_db_ids.index(t_obj.id)]
                matchup_model.white_score = t_obj.res[Color.W].res.value
                matchup_model.black_score = t_obj.res[Color.B].res.value
                session.add(matchup_model)
                session.commit()
                session.refresh(matchup_model)
            else:
                new_record = MatchupModel(
                    white_identifier = t_obj.res[Color.W].player.identifier,
                    black_identifier = t_obj.res[Color.B].player.identifier,
                    white_score = t_obj.res[Color.W].res.value,
                    black_score = t_obj.res[Color.B].res.value,
                )
                session.add(new_record)
                session.flush()
                session.refresh(new_record)
                if new_record.id is None:
                    raise ValueError("Trying to create a matchup without an id")
                t_obj.id = new_record.id
                session.commit()
                db_records.append(new_record)
        session.close()
        return db_records

    def __str__(self):
        white = self.res[Color.W]
        black = self.res[Color.B]
        white_name = white.player.get_full_name() or white.player.identifier
        black_name = black.player.get_full_name() or white.player.identifier
        res_white = match_result_score_text_map[white.res]
        res_black = match_result_score_text_map[black.res]
        w = f"{white_name.ljust(20)} {str(res_white).ljust(2)}"
        b = f"{black_name.ljust(20)} {str(res_black).ljust(2)}"
        res = f"{w} -    {b}"
        return res

    def validate_result(self, value):
        ok = [
            {MatchResult.WIN, MatchResult.LOSS},
            {MatchResult.WIN, MatchResult.WALKOVER},
            {MatchResult.WALKOVER, MatchResult.WALKOVER},
            {MatchResult.DRAW, MatchResult.DRAW},
            {MatchResult.UNSET, MatchResult.UNSET},
        ]
        raise_error = False
        if isinstance(value, dict):
            first = value[Color.W].res
            second = value[Color.B].res
            if {first, second} not in ok:
                raise_error = True
        if isinstance(value, tuple):
            first = value[0]
            second = value[1]
            if {first, second} not in ok:
                raise_error = True
        if raise_error:
            raise ValueError(
                f"Unable to add invalid matchup result {first} + {second}"
            )

    def add_result(
            self,
            white_res: MatchResult,
            black_res: MatchResult,
        ):
        '''
        IMPORTANT: Requires that instance has been instantiated with
        players already
        '''
        self.validate_result((white_res, black_res))
        self.res[Color.W].res = white_res
        self.res[Color.B].res = black_res

    def get_winner_loser_colors(self) -> (tuple[Color,Color] | None, bool) :
        '''None means no winner. Winner first loser/walkover second in returned tuple'''
        winner_loser_colors = None
        is_walkover = {self.res[Color.W].res, self.res[Color.B].res} == {MatchResult.WIN, MatchResult.WALKOVER}
        if self.res[Color.W].res == MatchResult.WIN:
            winner_loser_colors = (Color.W, Color.B)
        elif self.res[Color.B].res == MatchResult.WIN:
            winner_loser_colors = (Color.B, Color.W)
        return winner_loser_colors, is_walkover

    def get_player_ids(self):
        return self.res[Color.W].player.identifier, self.res[Color.B].player.identifier

    def to_dict(self) -> dict[str, Any]:
        # TODO: make sure that matchup.res.player is Player and not PlayerModel!
        res = dict()
        white = self.res[Color.W]
        black = self.res[Color.B]
        res['white_identifier'] = white.player.identifier
        res['black_identifier'] = black.player.identifier
        res['white_name'] = white.player.get_full_name()
        res['black_name'] = black.player.get_full_name()
        res['white_score'] = match_result_score_text_map[white.res]
        res['black_score'] = match_result_score_text_map[black.res]
        return res
