from typing import Optional

class Player:
    def __init__(
            self,
            identifier: int,
            first_name: str,
            last_name: str,
            active: bool = True,
            db_id: Optional[int] = None
        ):
        # Double check to prevent tuples creeping in from bad initializations
        if isinstance(id, tuple) and len(id) > 0:
            self.db_id = db_id[0]
        else:
            self.db_id = db_id
        self.identifier = identifier
        self.first_name = first_name
        self.last_name = last_name
        self.active = active

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"

    def __repr__(self):
        return f"[{self.identifier}] {self.get_full_name()}"
