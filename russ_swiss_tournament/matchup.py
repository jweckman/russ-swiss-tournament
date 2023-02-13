from enum import Enum
from dataclasses import dataclass
import itertools

from russ_swiss_tournament.player import Player
from russ_swiss_tournament.service import  MatchResult, Color, match_result_manual_map, match_result_score_map, match_result_score_text_map


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
        self.id = next(self.id_iter)
        self.res = res

    @property
    def res(self):
        return self._res

    @res.setter
    def res(self, value):
        self.validate_result(value)
        self._res = value

    def __str__(self):
        white = self.res[Color.W]
        black = self.res[Color.B]
        white_name = white.player.get_full_name() or white.player.id
        black_name = black.player.get_full_name() or white.player.id
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
            white_res:MatchResult,
            black_res:MatchResult,
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
        return self.res[Color.W].player.id, self.res[Color.B].player.id

