from typing import cast

class Player:
    def __init__(
        self, 
        identifier: int, 
        first_name: str, 
        last_name: str, 
        active: bool = True,
        db_id: int | tuple | None = None
    ):
        self.identifier = identifier
        self.first_name = first_name
        self.last_name = last_name
        self.active = active

        if isinstance(db_id, tuple):
            self.db_id: int | None = db_id[0] if len(db_id) > 0 else None
        else:
            self.db_id = cast(int | None, db_id)

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"

    def __repr__(self):
        return f"[{self.identifier}] {self.get_full_name()}"
