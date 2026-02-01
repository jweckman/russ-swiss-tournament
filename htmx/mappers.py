from typing import Any

from htmx.models import TournamentModel, RoundModel, MatchupModel, PlayerModel, PlayerTournamentStartOrder
from russ_swiss_tournament.tournament import Tournament, Round, Matchup, Player, RoundSystem

from russ_swiss_tournament.matchup import PlayerMatch
from russ_swiss_tournament.service import MatchResult, Color, match_result_score_text_map

def ensure_int(value: Any) -> int | None:
    """Helper to unwrap single-item tuples or enforce int type."""
    if value is None:
        return None
    if isinstance(value, tuple) or isinstance(value, list):
        if len(value) > 0:
            return int(value[0])
        return None
    return int(value)

# --- TO DOMAIN (Reading) ---

def to_domain_tournament(
    db_model: TournamentModel, 
    start_orders: list[PlayerTournamentStartOrder]
) -> Tournament:
    domain_players = [to_domain_player(p) for p in db_model.players]
    player_map = {p.identifier: p for p in domain_players}
    sorted_orders = sorted(start_orders, key=lambda x: x.start_order)
    start_order_ids = [x.player_identifier for x in sorted_orders]
    domain_rounds = [to_domain_round(r, player_map) for r in db_model.rounds]
    try:
        round_system = RoundSystem(db_model.round_system)
    except ValueError:
        round_system = RoundSystem.SWISS # Default fallback

    # TODO: DB model currently doesn't store tie break configs, 
    # so we initialize empty dicts or defaults.
    return Tournament(
        id=ensure_int(db_model.id),
        name=db_model.name,
        players=domain_players,
        rounds=domain_rounds,
        round_count=db_model.round_count,
        round_system=round_system,
        tie_break_results_swiss={},
        tie_break_results_round_robin={},
        year=db_model.year,
        count=db_model.count,
        player_tournament_start_order=start_order_ids,
        # TODO: folders are runtime paths, usually not stored in DB, defaulting to None
        folder=None,
        round_folder=None
    )

def to_domain_round(db_model: RoundModel, player_map: dict[int, Player]) -> Round:
    return Round(
        id=ensure_int(db_model.id),
        index=db_model.index,
        matchups=[to_domain_matchup(m, player_map) for m in db_model.matchups],
    )

def to_domain_player(db_model: PlayerModel) -> Player:
    safe_id = ensure_int(db_model.id)
    return Player(
        id=db_model.id,
        identifier=db_model.identifier,
        first_name=db_model.first_name,
        last_name=db_model.last_name,
        active=db_model.active
    )

def to_domain_matchup(db_model: MatchupModel, player_map: dict[int, Player]) -> Matchup:
    """
    Converts DB model to Domain object.
    Requires a map of {identifier: PlayerObject} to link the players correctly.
    """
    white_player = player_map.get(db_model.white_identifier)
    black_player = player_map.get(db_model.black_identifier)

    if not white_player or not black_player:
        raise ValueError(f"Matchup {db_model.id} refers to missing players: {db_model.white_identifier}, {db_model.black_identifier}")

    res_dict = {
        Color.W: PlayerMatch(
            player=white_player,
            res=MatchResult(db_model.white_score)
        ),
        Color.B: PlayerMatch(
            player=black_player,
            res=MatchResult(db_model.black_score)
        )
    }

    return Matchup(
        id=ensure_int(db_model.id),
        res=res_dict
    )


# --- TO DB (Writing) ---

def to_db_tournament(domain: Tournament) -> TournamentModel:
    # Ensure domain.id is set (it should be, but safety first)
    if domain.id is None:
        raise ValueError("Cannot save tournament without an ID")
    return TournamentModel(
        id=domain.id,
        name=domain.name,
        year=domain.year,
        count=domain.count,
        round_count=domain.round_count,
        round_system=domain.round_system.value,
        # Cascade mapping for children
        players=[to_db_player(p) for p in domain.players],
        rounds=[to_db_round(r, domain.id) for r in domain.rounds]
    )

def to_db_round(domain: Round, tournament_id: int) -> RoundModel:
    return RoundModel(
        id=domain.id,
        index=domain.index,
        matchups=[to_db_matchup(m, domain.id) for m in domain.matchups],
        tournament_id=tournament_id,
    )

def to_db_matchup(domain: Matchup, round_id: int) -> MatchupModel:
    return MatchupModel(
        id=domain.id,
        white_identifier=domain.get_white_id(),
        black_identifier=domain.get_black_id(),
        white_score=domain.get_white_score_int(),
        black_score=domain.get_black_score_int(),
        # round_id is handled by SQLAlchemy relationship back_population
    )

def to_db_player(domain: Player) -> PlayerModel:
    return PlayerModel(
        identifier=domain.identifier,
        first_name=domain.first_name,
        last_name=domain.last_name,
        active=domain.active,
        id=domain.id,
    )

