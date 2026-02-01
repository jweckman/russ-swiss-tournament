from typing import Optional
from sqlmodel import Session, select
from sqlalchemy.orm import selectinload
import os

from htmx.models import TournamentModel, RoundModel, PlayerTournamentStartOrder
from russ_swiss_tournament.tournament import Tournament
# Import your mappers (we will write these next)
from htmx import mappers 
import config

class TournamentRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_active_tournament(self) -> Optional[Tournament]:
        """
        Loads the active tournament with EAGER loading (no session errors).
        """
        # 1. Fetch the DB Model with all children loaded
        statement = (
            select(TournamentModel)
            .limit(1)
            .options(
                selectinload(TournamentModel.rounds).selectinload(RoundModel.matchups),
                selectinload(TournamentModel.players)
            )
        )
        db_obj = self.session.exec(statement).first()
        if not db_obj:
            return None

        # 2. Fetch Start Order (The "Side Table" logic)
        start_orders = self.session.exec(
            select(PlayerTournamentStartOrder)
            .where(PlayerTournamentStartOrder.tournament_id == db_obj.id)
        ).all()
        # 3. Use Mapper to convert DB -> Domain
        return mappers.to_domain_tournament(db_obj, start_orders)

    def save_tournament(self, tournament: "Tournament"):
        """
        Saves the ENTIRE tournament tree with a SAFETY LOCK against DB contamination.
        """
        # --- ABSOLUTE SAFEGUARD START ---
        # We check the actual file path this session is connected to.
        # If it does not match the global config.db_name, we ABORT immediately.
        if config.db_name:
            # SQLAlchemy SQLite URLs store the path in .database
            # e.g. /absolute/path/to/tournaments/russ_31.sqlite
            db_path = self.session.bind.url.database
            if db_path and db_path != ':memory:':
                current_db_filename = os.path.basename(db_path)
                # Check if the session's DB file matches the global context
                if current_db_filename != config.db_name:
                    raise RuntimeError(
                        f"CRITICAL DATA SAFETY ERROR: \n"
                        f"Attempted to save tournament '{tournament.name}' \n"
                        f"Target Context: '{config.db_name}' \n"
                        f"Actual Database Connection: '{current_db_filename}' \n"
                        f"Transaction Aborted to prevent corruption."
                    )
        # --- ABSOLUTE SAFEGUARD END ---

        # 1. Convert Domain -> DB Model
        db_model = mappers.to_db_tournament(tournament)
        # 2. Magic Merge
        merged_obj = self.session.merge(db_model)
        # 3. Commit
        self.session.commit()
        # 4. Update ID
        tournament.id = merged_obj.id
