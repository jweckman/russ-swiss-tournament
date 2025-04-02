import sqlite3
from dataclasses import dataclass, asdict
from typing import Type, TypeVar, List

T = TypeVar("T")

db_path = "database.sqlite3"

@dataclass
class PlayerModel:
    identifier: int
    first_name: str
    last_name: str
    active: bool

@dataclass
class TournamentModel:
    id: int
    name: str
    year: int
    count: int
    round_count: int
    round_system: int

@dataclass
class RoundModel:
    id: int
    round_index: int
    tournament_id: int

@dataclass
class MatchupModel:
    id: int
    white_identifier: int
    white_score: int
    black_identifier: int
    black_score: int
    round_id: int

@dataclass
class PlayerTournamentStartOrder:
    start_order: int
    player_identifier: int | None
    tournament_id: int

    id: int | None = None


def get_connection():
    return sqlite3.connect(db_path)

def ensure_tables():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.executescript(
            """
            PRAGMA foreign_keys = ON;

            CREATE TABLE IF NOT EXISTS PlayerModel (
                --id INTEGER PRIMARY KEY AUTOINCREMENT,
                identifier INTEGER UNIQUE NOT NULL,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                active BOOLEAN NOT NULL
            );

            CREATE TABLE IF NOT EXISTS TournamentModel (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                year INTEGER NOT NULL,
                count INTEGER NOT NULL,
                round_count INTEGER NOT NULL,
                round_system INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS PlayerTournamentLink (
                player_identifier INTEGER NOT NULL,
                tournament_id INTEGER NOT NULL,
                PRIMARY KEY (player_identifier, tournament_id),
                FOREIGN KEY (player_identifier) REFERENCES PlayerModel(identifier) ON DELETE CASCADE,
                FOREIGN KEY (tournament_id) REFERENCES TournamentModel(identifier) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS RoundModel (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                round_index INTEGER NOT NULL,
                tournament_id INTEGER NOT NULL,
                FOREIGN KEY (tournament_id) REFERENCES TournamentModel(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS MatchupModel (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                white_identifier INTEGER NOT NULL,
                white_score INTEGER NOT NULL,
                black_identifier INTEGER NOT NULL,
                black_score INTEGER NOT NULL,
                round_id INTEGER NOT NULL,
                FOREIGN KEY (round_id) REFERENCES RoundModel(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS PlayerTournamentStartOrder (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_order INTEGER NOT NULL,
                player_identifier INTEGER,
                tournament_id INTEGER NOT NULL,
                FOREIGN KEY (player_identifier) REFERENCES PlayerModel(identifier) ON DELETE SET NULL,
                FOREIGN KEY (tournament_id) REFERENCES TournamentModel(id) ON DELETE CASCADE
            );
            """
        )

def get_tournament_players(tournament_id: int) -> list[int]:
    with get_connection() as conn:
        cursor = conn.cursor()
        print(tournament_id)
        cursor.execute(
            """
                SELECT
                    pm.identifier
                FROM PlayerModel as pm
                LEFT JOIN PlayerTournamentLink ptl ON pm.identifier = ptl.player_identifier
                WHERE
                    ptl.tournament_id = ?

            """,
            (tournament_id,)
        )
        rows = cursor.fetchall()
        return [x[0] for x in rows]

def get_tournament_rounds(tournament_id: int) -> list[int]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
                SELECT
                    rm.id
                FROM RoundModel as rm
                WHERE
                    rm.tournament_id = ?

            """,
            (tournament_id,)
        )
        rows = cursor.fetchall()
        return [x[0] for x in rows]

def get_round_matchups(round_id: int) -> list[int]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
                SELECT
                    id
                FROM MatchupModel
                WHERE
                    round_id = ?

            """,
            (round_id,)
        )
        rows = cursor.fetchall()
        return [x[0] for x in rows]

def add_player_to_tournament(player_id: int, tournament_id: int):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO PlayerTournamentLink (player_identifier, tournament_id)
            VALUES (?, ?)
            ON CONFLICT DO NOTHING
            """,
            (player_id, tournament_id)
        )
        conn.commit()

def get_records_by_id(model: Type[T], ids: List[int] | bool) -> List[T]:
    print(f"getting {model}: {ids}")
    table_name = model.__name__
    if model is PlayerModel:
        id_field = "identifier"
    else:
        id_field = "id"
    with get_connection() as conn:
        cursor = conn.cursor()
        if ids is True:
            cursor.execute(f"SELECT * FROM {table_name}")
        else:
            placeholders = ", ".join("?" for _ in ids)
            cursor.execute(f"SELECT * FROM {table_name} WHERE {id_field} IN ({placeholders})", ids)
        rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    return [model(**dict(zip(columns, row))) for row in rows]

def upsert_records(model: Type[T], records: List[T]):
    print(f"upserting {records}")
    table_name = model.__name__
    id_field = "identifier" if model is PlayerModel else "id"
    with get_connection() as conn:
        cursor = conn.cursor()
        for record in records:
            data = asdict(record)
            if data.get('id', False) is None:
                data.pop('id')
            columns = ", ".join(data.keys())
            placeholders = ", ".join(["?" for _ in data])
            update_set = ", ".join(f"{key} = ?" for key in data.keys())
            values = list(data.values())
            cursor.execute(
                f"""
                INSERT INTO {table_name} ({columns})
                VALUES ({placeholders})
                ON CONFLICT({id_field}) DO UPDATE SET {update_set}
                """,
                values + values,
            )
        conn.commit()

def get_start_order_sorted(
    tournament_id: int,
    player_ids: list[int],
) -> list[PlayerTournamentStartOrder]:
    with get_connection() as conn:
        cursor = conn.cursor()
        placeholders = ", ".join("?" for _ in player_ids)
        cursor.execute(
            f"""
                SELECT
                    *
                FROM
                    {PlayerTournamentStartOrder.__name__}
                WHERE
                    tournament_id = {tournament_id}
                    AND player_identifier IN ({placeholders})
                """,
            player_ids,
        )
        rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    records = [PlayerTournamentStartOrder(**dict(zip(columns, row))) for row in rows]
    return sorted(records, key=lambda x: x.start_order)


ensure_tables()
