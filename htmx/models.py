from datetime import date, datetime, timedelta
from typing import Optional, List

from sqlmodel import Field, SQLModel, Relationship, select, Session

class PlayerTournamentLink(SQLModel, table=True):
    player_id: Optional[int] = Field(
        default=None, foreign_key="playermodel.id", primary_key=True
    )
    tournament_id: Optional[int] = Field(
        default=None, foreign_key="tournamentmodel.id", primary_key=True
    )

class PlayerModel(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    identifier: int
    first_name: str
    last_name: str
    active: bool

    tournaments: List["TournamentModel"] = Relationship(back_populates="players", link_model=PlayerTournamentLink)

class TournamentModel(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    year: int
    count: int
    round_count: int
    round_system: int

    players: List["PlayerModel"] = Relationship(back_populates="tournaments", link_model=PlayerTournamentLink)
    rounds: List["RoundModel"] = Relationship(back_populates="tournament")


class RoundModel(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    index: int
    matchups: List["MatchupModel"] = Relationship(back_populates="rounds")

    tournament_id: Optional[int] = Field(default=None, foreign_key="tournamentmodel.id")
    tournament: Optional[TournamentModel] = Relationship(back_populates='rounds')

class MatchupModel(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    white_identifier: int
    white_score: int
    black_identifier: int
    black_score: int

    round_id: Optional[int] = Field(default=None, foreign_key="roundmodel.id")
    rounds: Optional[RoundModel] = Relationship(back_populates='matchups')
