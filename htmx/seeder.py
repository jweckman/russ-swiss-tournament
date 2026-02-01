import csv
from pathlib import Path
from sqlmodel import Session
from russ_swiss_tournament.tournament import Tournament, Player
from htmx.repository import TournamentRepository

DEFAULT_TOML_PATH = Path("tournaments/test_swiss/config.toml")

def seed_default_tournament(session: Session) -> Tournament:
    if not DEFAULT_TOML_PATH.exists():
        raise FileNotFoundError(f"Default config not found at {DEFAULT_TOML_PATH}")

    # 1. Load from TOML (In-Memory only)
    t = Tournament.from_toml(
        DEFAULT_TOML_PATH,
        read_rounds=False,
        create_players=True
    )
    # 2. Generate the first round
    t._create_initial_round()

    # 3. Write to Database using REPOSITORY
    repo = TournamentRepository(session)
    repo.save_tournament(t)
    return t

def read_players_from_csv(path: Path = Path("player.csv")) -> list[Player]:
    """
    Reads players from the CSV Source of Truth.
    Expected format: [ID, Active(0/1/yes/no), LastName, FirstName, ...]
    """
    # Verify file exists, try plural if singular missing
    if not path.exists():
        alt_path = Path("players.csv")
        if alt_path.exists():
            path = alt_path
        else:
            print(f"WARNING: Could not find player CSV at {path} or {alt_path}")
            return []

    active_map = {
        'yes': True,
        'no': False,
        '0': False,
        '1': True,
        0: False,
        1: True,
    }
    players = []
    try:
        # encoding='utf-8-sig' handles potentially annoying BOM characters from Excel
        with open(path, 'r', newline='', encoding='utf-8-sig') as csv_file:
            player_reader = csv.reader(csv_file, delimiter=',', quotechar='"')
            # Skip Header
            headers = next(player_reader, None)
            for line in player_reader:
                if not line: continue # Skip empty lines
                # Use your specific index mapping
                try:
                    p_id = int(line[0])
                    active_status = active_map.get(line[1].strip().lower(), True)
                    last_name = line[2].strip()
                    first_name = line[3].strip()
                    player = Player(
                        identifier=p_id,
                        first_name=first_name,
                        last_name=last_name,
                        active=active_status
                    )
                    players.append(player)
                except (ValueError, IndexError) as e:
                    print(f"Skipping invalid line in CSV: {line} - Error: {e}")
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return []

    return players
