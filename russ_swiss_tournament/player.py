import csv
from pathlib import Path
from typing import Self

from sqlmodel import select, col

from htmx.db import get_session
from htmx.models import PlayerModel

class Player:
    def __init__(
            self,
            identifier: int,
            first_name: str,
            last_name: str,
            active: bool = True,
        ):
        # if not isinstance(id, int):
        #     raise ValueError(f"Trying to create player with non-int id: {id}")
        self.identifier = identifier
        self.first_name = first_name
        self.last_name = last_name
        self.active = active

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"

    def __repr__(self):
        return f"[{self.id}]{self.get_full_name()}"

    @classmethod
    def from_db(
            cls,
            selves: list[Self] | list[int],
            all: bool = False,
        ) -> tuple[list[Self], list[PlayerModel]]:
        session = next(get_session())
        if all:
            existing_db = [p for p in session.exec(select(PlayerModel)).all()]
        else:
            is_ids = False
            if isinstance(selves[0], int):
                is_ids = True
            ids = [p.identifier for p in selves] if not is_ids else selves
            existing_db = [p for p in session.exec(select(PlayerModel).where(col(PlayerModel.identifier).in_(ids)))]
            if len(existing_db) != len(selves):
                raise ValueError(
                    f"Trying to create {cls.__name__} from db records but some ids are missing.\n"
                    f"Please make sure that all the following ids are in the db: {ids}"
                )
        objects: list = []
        for record in existing_db:
            objects.append(
                Player(
                    identifier = record.identifier,
                    first_name = record.first_name,
                    last_name = record.last_name,
                )
            )
        return objects, existing_db

    @classmethod
    def db_write(
            self,
            selves: list[Self],
            update: bool = True,
        ) -> list[PlayerModel]:
        '''Writes/updates selves to db'''
        session = next(get_session())
        ids = [p.identifier for p in selves]
        existing_db = [t for t in session.exec(select(PlayerModel).where(col(PlayerModel.identifier).in_(ids)))]
        existing_db_ids = [t.identifier for t in existing_db]
        new_records: list[PlayerModel] = []
        for t_obj in selves:
            if t_obj.identifier in existing_db_ids:
                if update:
                    pass  # TODO
            else:
                new_record = PlayerModel(
                    identifier = t_obj.identifier,
                    first_name = t_obj.first_name,
                    last_name = t_obj.last_name,
                    active = t_obj.active,
                )
                session.add(new_record)
                session.flush()
                session.refresh(new_record)
                if new_record.id is None:
                    raise ValueError("Trying to create a player without an id")
                t_obj.identifier = new_record.identifier
                session.commit()
                new_records.append(new_record)
        return new_records

    @classmethod
    def read_players_from_csv(
            cls,
            path=Path().cwd() / 'player.csv'
        ):
        active_map = {
            'yes': True,
            'no': False,
            '0': False,
            '1': True,
            0: False,
            1: True,
        }
        players = []
        with open(path, 'r', newline='') as csv_file:
            player_reader = csv.reader(csv_file, delimiter=',', quotechar='"')
            headers = next(player_reader, None)
            for line in player_reader:
                player = Player(
                    identifier = int(line[0]),
                    first_name = line[3].strip(),
                    last_name = line[2].strip(),
                    active = active_map[line[1].strip().lower()]
                )
                players.append(player)
        Player.db_write(players)

