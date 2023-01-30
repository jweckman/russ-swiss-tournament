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

match_result_score_map = {
    MatchResult.WIN:  1,
    MatchResult.LOSS: 0,
    MatchResult.DRAW: 0.5,
    MatchResult.UNSET: None,
    MatchResult.WALKOVER: 0,
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
    def match_player(cls, s:str, players: list[Player]) -> int:
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
            players: list[Player] | None = None
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

    @classmethod
    def create_initial(self):
        # TODO initial round gen
        pass

    @classmethod
    def create_next(self, standings):
        prs = prev_round.get_results()
        pass

    def get_results(self) -> dict[int,float]:
        player_ids = self.get_player_ids()
        results = dict(zip(list(player_ids), [0 for i in range(len(player_ids))]))
        for m in self.matchups:
            results[m.res[Color.W].id] = match_result_score_map[m.res[Color.W].res]
            results[m.res[Color.B].id] = match_result_score_map[m.res[Color.B].res]
        return results

    def get_player_ids(self):
        player_ids = set()
        for m in self.matchups:
            rps = [p.id for p in m.res.values()]
            for p in rps:
                player_ids.add(p)
        return player_ids

    def write_csv(
            self,
            path,
        ):
        with open(path / f"round{self.index}.csv", 'w', newline='') as csv_file:
            round_writer = csv.writer(csv_file, delimiter=',', quotechar='"')
            header_row = ["white", "score_white", "black", "score_black"]
            round_writer.writerow(header_row)
            # TODO: add support for writing full name not just id
            rows = []
            for m in self.matchups:
                row = [
                    m.res[Color.W].id,
                    match_result_score_map[m.res[Color.W].res],
                    m.res[Color.B].id,
                    match_result_score_map[m.res[Color.B].res],
                ]
                rows.append(row)
            round_writer.writerows(rows)


