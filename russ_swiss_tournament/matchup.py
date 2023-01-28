from enum import Enum
from dataclasses import dataclass
import itertools

class MatchResult(Enum):
    WIN = 1
    LOSS = 2
    DRAW = 3
    UNSET = 4
    WALKOVER = 5

class Color(Enum):
    W = 1
    B = 2

@dataclass
class PlayerMatch:
    id: int
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

    def get_winner_loser_colors(self) -> tuple[Color,Color] | None:
        '''None means no winner. Winner first loser second in returned tuple'''
        winner_loser_colors = None
        if self.res[Color.W].res == MatchResult.WIN:
            winner_loser_colors = (Color.W, Color.B)
        elif self.res[Color.B].res == MatchResult.WIN:
            winner_loser_colors = (Color.B, Color.W)
        return winner_loser_colors

