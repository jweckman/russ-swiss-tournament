import itertools
import csv
from io import StringIO
from pathlib import Path
from typing import Any, Optional

from russ_swiss_tournament.matchup import Matchup, PlayerMatch
from russ_swiss_tournament.player import Player
from russ_swiss_tournament.service import (
    MatchResult,
    Color,
    match_result_manual_map,
    match_result_score_map,
    match_result_score_text_map,
)

class Round:
    '''Note: index var starts from 1 to match with csv file names'''
    id_iter = itertools.count()

    def __init__(
            self,
            matchups: list[Matchup],
            index: int = 1,
            id: Optional[int] = None,
        ):
        if id is None:
            self.id = next(self.id_iter) + 1
        else:
            self.id = id
        self.matchups = matchups
        self.index = index

    @classmethod
    def match_player(
            cls,
            s: str,
            players: list[Player]
        ) -> Player | None:
        res = None
        sanitized = s.lower().strip()
        for p in players:
            if (sanitized.isdigit() and str(p.identifier) == sanitized
                    or p.get_full_name().lower().strip() == sanitized):
                res = p
                break
        return res

    @classmethod
    def read_csv(cls, file_handle, round_index, players: list[Player]) -> "Round":
        import csv
        player_map = {p.get_full_name().lower().strip(): p for p in players}
        matchups = []
        reader = csv.DictReader(file_handle)
        for row in reader:
            w_name = row['white'].strip().lower()
            b_name = row['black'].strip().lower()
            p_white = player_map.get(w_name)
            p_black = player_map.get(b_name)
            if not p_white or not p_black:
                print(f"WARNING: CSV Upload could not find player(s): '{w_name}' or '{b_name}'")
                continue

            def parse_score(val):
                val = val.strip()
                if val == '1': return MatchResult.WIN
                if val == '0': return MatchResult.LOSS
                if val == '0.5' or val == '1/2': return MatchResult.DRAW
                return MatchResult.UNSET

            res_w = parse_score(row['score_white'])
            res_b = parse_score(row['score_black'])

            m = Matchup({
                Color.W: PlayerMatch(p_white, res_w),
                Color.B: PlayerMatch(p_black, res_b)
            })
            matchups.append(m)

        return cls(matchups, round_index)

    def get_results(self) -> dict[int, float]:
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
        ):
        '''Path refers to a folder. File names are automated based on round index'''
        with open(path / f"round{self.index}.csv", 'w', newline='') as csv_file:
            round_writer = csv.writer(csv_file, delimiter=',', quotechar='"')
            header_row = ["white", "score_white", "black", "score_black"]
            round_writer.writerow(header_row)
            rows = []
            for m in self.matchups:
                # We can now rely on the objects having player data directly
                white = m.res[Color.W].player.get_full_name()
                black = m.res[Color.B].player.get_full_name()
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
