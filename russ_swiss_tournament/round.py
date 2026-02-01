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
    def read_csv(
            cls,
            path: str | Path | StringIO,
            index,
            players: list[Player] = []
        ):
        matchups = []
        csv_file: Any
        if isinstance(path, str) or isinstance(path, Path):
            csv_file = open(path, newline='')
        elif isinstance(path, StringIO):
            csv_file = path
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
            if isinstance(path, str) or isinstance(path, Path):
                csv_file.close()
        return cls(matchups, index)

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
