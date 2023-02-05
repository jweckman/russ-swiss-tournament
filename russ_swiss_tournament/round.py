import itertools
import csv
from russ_swiss_tournament.matchup import Matchup, PlayerMatch
from russ_swiss_tournament.player import Player
from russ_swiss_tournament.db import Database
from russ_swiss_tournament.service import MatchResult, Color, match_result_manual_map, match_result_score_map, match_result_score_text_map

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
        ):
        self.id = next(self.id_iter)
        self.matchups = matchups
        self.index = index

    @classmethod
    def match_player(cls, s:str, players: list[Player]) -> Player:
        res = None
        sanitized = s.lower().strip()
        for p in players:
            if (sanitized.isdigit() and str(p.id) == sanitized
                    or p.get_full_name().lower().strip() == sanitized):
                res = p
                break
        return res

    @classmethod
    def read_csv(
            cls,
            path,
            index,
            players: list[Player] | None = None
        ):
        matchups = []
        with open(path, newline='') as csv_file:
            round_reader = csv.reader(csv_file, delimiter=',', quotechar='"')
            headers = next(round_reader, None)
            for line in round_reader:
                white_player = cls.match_player(line[0], players)
                black_player = cls.match_player(line[2], players)
                if not (any([white_player, black_player])
                        or any([pid not in [x.id for x in players] for pid in [white_player.id, black_player.id]])):
                    raise ValueError(
                        f"Could not match player {line[0]} or player {line[2]} "
                        "based on id or full name. Check exact typing from database"
                    )
                matchup = Matchup({
                    Color.W: PlayerMatch(white_player, match_result_manual_map[line[1]]),
                    Color.B: PlayerMatch(black_player, match_result_manual_map[line[3]])
                })
                matchups.append(matchup)
        return cls(matchups, index)

    def get_results(self) -> dict[int,float]:
        player_ids = self.get_player_ids()
        results = dict(zip(list(player_ids), [0 for i in range(len(player_ids))]))
        for m in self.matchups:
            results[m.res[Color.W].player.id] = match_result_score_map[m.res[Color.W].res]
            results[m.res[Color.B].player.id] = match_result_score_map[m.res[Color.B].res]
        return results

    def get_player_ids(self):
        player_ids = set()
        for m in self.matchups:
            # TODO BUG IS HERE. ID still set somewhere
            rps = [p.player.id for p in m.res.values()]
            for p in rps:
                player_ids.add(p)
        return player_ids

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
            # TODO: add support for writing full name not just id
            rows = []
            for m in self.matchups:
                if db:
                    white = db.get_player_by_id(m.res[Color.W].player.id).get_full_name()
                    black = db.get_player_by_id(m.res[Color.B].player.id).get_full_name()
                else:
                    white = m.res[Color.W].player.id
                    black = m.res[Color.B].player.id
                row = [
                    white,
                    match_result_score_text_map[m.res[Color.W].res],
                    black,
                    match_result_score_text_map[m.res[Color.B].res],
                ]
                rows.append(row)
            round_writer.writerows(rows)
    def pretty_print(self):
        res = ""


