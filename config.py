from typing import TYPE_CHECKING, cast, Optional
from sqlmodel import Session

# Import the repository
from htmx.repository import TournamentRepository 

if TYPE_CHECKING:
    from russ_swiss_tournament.tournament import Tournament
    from russ_swiss_tournament.matchup_assignment import SwissAssigner, RoundRobinAssigner

# --- Global State ---
tournament: Optional["Tournament"] = None
assigner: Optional["SwissAssigner | RoundRobinAssigner"] = None
db_name: Optional[str] = None

def load_tournament_context(session: Session) -> bool:
    """
    Reloads the global 'tournament' and 'assigner' objects 
    from the provided database session using the Repository.
    """
    global tournament, assigner
    from russ_swiss_tournament.matchup_assignment import SwissAssigner

    # NEW: Use Repository to load
    repo = TournamentRepository(session)
    loaded_tournament = repo.get_active_tournament()

    if loaded_tournament:
        tournament = loaded_tournament
        # Re-initialize the assigner with the new tournament data
        assigner = SwissAssigner(tournament) 
        return True
    else:
        # DB exists but is empty (new file)
        tournament = None
        assigner = None
        return False
