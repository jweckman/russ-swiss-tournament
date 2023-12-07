from typing import Self

from sqlmodel import select, col

from htmx.db import get_session
from htmx.models import PlayerModel

class Player:
    def __init__(
            self,
            id: int,
            first_name: str,
            last_name: str,
            active: bool = True,
        ):
        if not isinstance(id, int):
            raise ValueError(f"Trying to create player with non-int id: {id}")
        self.id = id
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
        ) -> tuple[list[Self], list[PlayerModel]]:
        is_ids = False
        if isinstance(selves[0], int):
            is_ids = True
        session = next(get_session())
        ids = [t.id for t in selves] if not is_ids else selves
        existing_db = [t for t in session.exec(select(PlayerModel).where(col(PlayerModel.id).in_(ids)))]
        if len(existing_db) != len(selves):
            raise ValueError(
                f"Trying to create {cls.__name__} from db records but some ids are missing.\n"
                f"Please make sure that all the following ids are in the db: {ids}"
            )
        objects: list = []
        for record in existing_db:
            objects.append(
                Player(
                    id = record.id,
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
        ids = [t.id for t in selves]
        existing_db = [t for t in session.exec(select(PlayerModel).where(col(PlayerModel.id).in_(ids)))]
        existing_db_ids = [t.id for t in existing_db]
        new_records: list[PlayerModel] = []
        for t_obj in selves:
            if t_obj.id in existing_db_ids:
                if update:
                    pass  # TODO
            else:
                new_record = PlayerModel(
                    first_name = t_obj.first_name,
                    last_name = t_obj.last_name,
                    active = t_obj.active,
                )
                session.add(new_record)
                session.flush()
                session.refresh(new_record)
                if new_record.id is None:
                    raise ValueError("Trying to create a player without an id")
                t_obj.id = new_record.id
                session.commit()
                new_records.append(new_record)
        return new_records
