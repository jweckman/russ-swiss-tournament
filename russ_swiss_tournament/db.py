from pathlib import Path
import csv

from russ_swiss_tournament.player import Player

class Database:
    def __init__(
            self,
            players: list[Player] = [],
            players_csv_path = Path().cwd() / 'player.csv',
        ):
        self.players_csv_path = players_csv_path

    def read_players(self):
        active_map = {
            'yes': True,
            'no': False,
            '0': False,
            '1': True,
            0: False,
            1: True,
        }
        players = []
        with open(self.players_csv_path, 'r', newline='') as csv_file:
            player_reader = csv.reader(csv_file, delimiter=',', quotechar='"')
            headers = next(player_reader, None)
            for line in player_reader:
                players.append(Player(
                    id = int(line[0]),
                    first_name = line[3].strip(),
                    last_name = line[2].strip(),
                    active = active_map[line[1].strip().lower()]
                ))
        self.players = players

    def get_player_by_id(self, id) -> Player:
        try:
            match = [p for p in self.players if p.id == id][0]
        except IndexError:
            raise IndexError(f"No player was found in the database with id {id}")
        return match


