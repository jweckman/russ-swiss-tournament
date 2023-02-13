class Player:
    def __init__(
            self,
            id: int,
            first_name: str,
            last_name:str,
            active: bool = True,
        ):
        self.id = id
        self.first_name = first_name
        self.last_name = last_name
        self.active = active

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"

    def __repr__(self):
        return f"[{self.id}]{self.get_full_name()}"
