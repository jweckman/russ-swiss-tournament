class Player:
    def __init__(
            self,
            id: int,
            first_name: str,
            last_name:str,
        ):
        self.id = id
        self.first_name = first_name
        self.last_name = last_name

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"
