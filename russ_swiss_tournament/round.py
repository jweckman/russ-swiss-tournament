import itertools
import csv
from russ_swiss_tournament.matchup import Matchup, MatchResult, Color, PlayerMatch
from russ_swiss_tournament.player import Player


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

class Round:
    id_iter = itertools.count()
    def __init__(
            self,
            matchups: list[Matchup],
            index: int = 0,
        ):
        self.id = next(self.id_iter)
        self.matchups = matchups
        self.index = index

    @classmethod
    def match_player(cls, s:str, players: set[Player]) -> int:
        res = None
        try:
            res= int(s)
        except:
            sanitized = s.lower().strip()
            for p in players:
                if p.get_full_name().lower().strip() == sanitized:
                    res = p.id
                    break
        return res

    @classmethod
    def read_csv(
            cls,
            path,
            index,
            players: set[Player] | None = None
        ):
        matchups = []
        with open(path, newline='') as csv_file:
            round_reader = csv.reader(csv_file, delimiter=',', quotechar='"')
            headers = next(round_reader, None)
            for line in round_reader:
                white_id = cls.match_player(line[0], players)
                black_id = cls.match_player(line[2], players)
                if (not all([isinstance(white_id, int), isinstance(black_id, int)])
                        or any([pid not in [x.id for x in players] for pid in [white_id, black_id]])):
                    raise ValueError(
                        f"Could not match player {line[0]} or player {line[2]} "
                        "based on id or full name. Check exact typing from database"
                    )
                matchup = Matchup({
                    Color.W: PlayerMatch(white_id, match_result_manual_map[line[1]]),
                    Color.B: PlayerMatch(black_id, match_result_manual_map[line[3]])
                })
                matchups.append(matchup)
        return cls(matchups, index)

