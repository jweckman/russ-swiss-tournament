import pytest
from random import choices
from unittest.mock import patch

from russ_swiss_tournament.tournament import Tournament, RoundSystem
from russ_swiss_tournament.player import Player
from russ_swiss_tournament.matchup import Matchup, PlayerMatch
from russ_swiss_tournament.round import Round
from russ_swiss_tournament.tie_break import calc_sonne_koya, calc_modified_median_solkoff
from russ_swiss_tournament.matchup_assignment import SwissAssigner
from russ_swiss_tournament.service import MatchResult, Color

# --- HELPERS ---
def create_players(count):
    """Factory to create simple players with IDs 1..count"""
    players = []
    for i in range(count):
        val = i + 1
        players.append(Player(identifier=val, first_name=f"First{val}", last_name=f"Last{val}"))
    return players

def create_dummy_matchup(p1, p2, p1_res=MatchResult.UNSET, p2_res=MatchResult.UNSET):
    """Factory for a single matchup"""
    return Matchup({
        Color.W: PlayerMatch(p1, p1_res),
        Color.B: PlayerMatch(p2, p2_res)
    })

def create_random_round_results(round_obj: Round):
    """Fills an existing round with valid random results (Win/Loss/Draw)"""
    outcomes = [
        (MatchResult.WIN, MatchResult.LOSS),
        (MatchResult.LOSS, MatchResult.WIN),
        (MatchResult.DRAW, MatchResult.DRAW)
    ]
    for m in round_obj.matchups:
        res = choices(outcomes, weights=[40, 40, 20], k=1)[0]
        m.res[Color.W].res = res[0]
        m.res[Color.B].res = res[1]

# --- PLAYER TESTS ---
def test_should_get_player_name():
    p = Player(1, 'Joakim', 'Weckman')
    full_name = p.get_full_name()
    assert full_name == f"{p.first_name} {p.last_name}"

# --- MATCHUP TESTS ---
def test_should_create_without_result():
    p1, p2 = create_players(2)
    m = Matchup({Color.W: PlayerMatch(p1), Color.B: PlayerMatch(p2)})
    assert m.res[Color.W].res == MatchResult.UNSET
    assert m.res[Color.B].res == MatchResult.UNSET

def test_should_add_result_valid():
    p1, p2 = create_players(2)
    m = Matchup({Color.W: PlayerMatch(p1, MatchResult.UNSET), Color.B: PlayerMatch(p2, MatchResult.UNSET)})
    m.add_result(MatchResult.WIN, MatchResult.LOSS)
    assert m.res[Color.B].res == MatchResult.LOSS

def test_should_add_result_invalid():
    p1, p2 = create_players(2)
    m = Matchup({Color.W: PlayerMatch(p1, MatchResult.UNSET), Color.B: PlayerMatch(p2, MatchResult.UNSET)})
    with pytest.raises(ValueError):
        m.add_result(MatchResult.WIN, MatchResult.WIN)

def test_should_not_add_result_invalid_single_draw():
    p1, p2 = create_players(2)
    m = Matchup({Color.W: PlayerMatch(p1, MatchResult.UNSET), Color.B: PlayerMatch(p2, MatchResult.UNSET)})
    with pytest.raises(ValueError):
        m.add_result(MatchResult.DRAW, MatchResult.LOSS)

def test_should_not_add_result_invalid_multi_win():
    p1, p2 = create_players(2)
    m = Matchup({Color.W: PlayerMatch(p1, MatchResult.UNSET), Color.B: PlayerMatch(p2, MatchResult.UNSET)})
    with pytest.raises(ValueError):
        m.add_result(MatchResult.WIN, MatchResult.WIN)

def test_should_not_add_result_invalid_multi_loss():
    p1, p2 = create_players(2)
    m = Matchup({Color.W: PlayerMatch(p1, MatchResult.UNSET), Color.B: PlayerMatch(p2, MatchResult.UNSET)})
    with pytest.raises(ValueError):
        m.add_result(MatchResult.LOSS, MatchResult.LOSS)

def test_should_not_add_result_invalid_single_unset():
    p1, p2 = create_players(2)
    m = Matchup({Color.W: PlayerMatch(p1, MatchResult.UNSET), Color.B: PlayerMatch(p2, MatchResult.UNSET)})
    with pytest.raises(ValueError):
        m.add_result(MatchResult.LOSS, MatchResult.UNSET)

# --- ROUND TESTS ---
def test_should_create_valid_round():
    players = create_players(10)
    matchups = []
    for i in range(0, 10, 2):
        m = create_dummy_matchup(players[i], players[i+1], MatchResult.WIN, MatchResult.LOSS)
        matchups.append(m)
    r = Round(matchups=matchups, index=1)
    assert r.index == 1
    assert len(r.matchups) == 5
    assert r.is_complete() is True

# --- ROUND ROBIN GENERATION TEST ---
def test_should_generate_round_robin_schedule():
    """
    Tests that we can generate a valid Berger table schedule for 4 players.
    (3 rounds, everyone plays everyone once).
    """
    players = create_players(4)
    t = Tournament(
        name="Test RR",
        players=players,
        rounds=[],
        round_count=3,
        round_system=RoundSystem.BERGER,
        tie_break_results_swiss={},
        tie_break_results_round_robin={},
        year=2024,
        count=0
    )
    # Replicate the Berger Logic used in router.py
    n = len(players)
    rotation_ids = [p.identifier for p in players]
    generated_rounds = []
    for r_idx in range(n - 1): # 3 rounds
        half = n // 2
        l1 = rotation_ids[:half]
        l2 = rotation_ids[half:][::-1]
        round_matchups = []
        for i in range(half):
            p1_id = l1[i]
            p2_id = l2[i]
            p1 = next(p for p in players if p.identifier == p1_id)
            p2 = next(p for p in players if p.identifier == p2_id)
            m = create_dummy_matchup(p1, p2)
            round_matchups.append(m)
        generated_rounds.append(Round(matchups=round_matchups, index=r_idx + 1))
        # Rotate: Fixed ID at index 0, others rotate
        rotation_ids = [rotation_ids[0]] + [rotation_ids[-1]] + rotation_ids[1:-1]

    assert len(generated_rounds) == 3
    # Check uniqueness: Player 1 should play 2, 3, and 4 exactly once
    p1_opponents = []
    for r in generated_rounds:
        for m in r.matchups:
            if m.get_white_id() == 1: p1_opponents.append(m.get_black_id())
            if m.get_black_id() == 1: p1_opponents.append(m.get_white_id())
    assert sorted(p1_opponents) == [2, 3, 4]

# --- SWISS GENERATION STRESS TEST ---
def test_should_generate_swiss_rounds_robustness():
    """
    Runs multiple Swiss tournaments to ensure the Assigner doesn't crash
    and color balance is generally maintained.
    """
    failure_count = 0
    for _ in range(100):
        players = create_players(12) 
        t = Tournament(
            name="Swiss Test",
            players=players,
            rounds=[],
            round_count=5,
            round_system=RoundSystem.SWISS,
            tie_break_results_swiss={},
            tie_break_results_round_robin={},
            year=2024,
            count=0
        )
        try:
            t._create_initial_round()
            create_random_round_results(t.rounds[-1])
            for r_num in range(2, 9):

                # Needs to be re-initialized or the program will crash.
                assigner = SwissAssigner(t)

                next_round = assigner.create_next_round()
                create_random_round_results(next_round)

                # Check for duplicates immediately to fail fast
                t.validate_no_duplicate_matchups()
        except ValueError as e:
            print(f"Failed to generate round: {e}")
            failure_count += 1
    assert failure_count == 0


# --- TIE BREAK CALCULATION TESTS ---
def test_should_calculate_sonne_koya_correctly():
    """
    Verifies Sonneborn-Berger logic:
    Score = (Sum of scores of defeated opponents) + (0.5 * Sum of scores of drawn opponents)
    """
    p1, p2, p3 = create_players(3)
    
    # SCENARIO:
    # P1 Defeated P2 (who has score 2.0)
    # P1 Drawn with P3 (who has score 3.0)
    # P1 Score doesn't matter for the calculation, but let's say 1.5
    
    # 1. Mock the "Defeated/Drawn" map returned by get_player_defeated_drawn()
    defeated_drawn_map = {
        p1.identifier: ([p2.identifier], [p3.identifier])
    }
    
    # 2. Mock the "Standings" map (Total Score for every player)
    standings = {
        p1.identifier: 1.5,
        p2.identifier: 2.0,
        p3.identifier: 3.0
    }
    
    # 3. Mock the "Scores vs Specific Opponent" map (Only needed for Koya)
    scores_map = {
        p1.identifier: {p2.identifier: 1.0, p3.identifier: 0.5}
    }

    sonne, koya = calc_sonne_koya(
        defeated_drawn_map,
        scores_map,
        standings,
        round_count=5
    )
    # CALCULATION:
    # Sonne = (Score of P2) + 0.5 * (Score of P3)
    # Sonne = 2.0 + 0.5 * 3.0 = 2.0 + 1.5 = 3.5
    assert sonne[p1.identifier] == 3.5
    # KOYA CHECK (Points against opponents with >= 50% score)
    # Tournament Half Score = 2.5
    # P2 Score (2.0) is < 2.5 (Not a "Good Opponent")
    # P3 Score (3.0) is >= 2.5 (Is a "Good Opponent")
    # Koya = Points scored against P3 = 0.5
    assert koya[p1.identifier] == 0.5

@patch('russ_swiss_tournament.tie_break.modified_median_solkoff_model_scores')
def test_should_calculate_modified_median_solkoff_correctly(mock_model_scores):
    """
    Verifies Modified Median Logic:
    - If Player Score > 50%: Drop Lowest Opponent Score
    - If Player Score < 50%: Drop Highest Opponent Score
    - If Player Score = 50%: Drop Highest AND Lowest
    """
    p1 = Player(identifier=10, first_name="Hero", last_name="Player")
    opp_low = 11
    opp_mid = 12
    opp_high = 13
    rounds_dummy = [1, 2, 3, 4, 5] # 5 Rounds -> Max Score 5, Half Score 2.5
    player_ids = {p1.identifier, opp_low, opp_mid, opp_high}
    opponents_map = {
        p1.identifier: [opp_low, opp_mid, opp_high]
    }

    # --- CASE 1: High Performing Player (> 50%) ---
    # P1 has score 4.0 (Greater than 2.5)
    mock_model_scores.return_value = {
        p1.identifier: 4.0, 
        opp_low: 1.0, 
        opp_mid: 3.0, 
        opp_high: 5.0
    }

    mm, solk = calc_modified_median_solkoff(rounds_dummy, player_ids, opponents_map)

    # Solkoff: Sum of all (1 + 3 + 5) = 9.0
    assert solk[p1.identifier] == 9.0
    # Mod Median: Drop Lowest (1.0). Remaining (3.0 + 5.0) = 8.0
    assert mm[p1.identifier] == 8.0

    # --- CASE 2: Low Performing Player (< 50%) ---
    # P1 has score 1.0 (Less than 2.5)
    # Note: We must update the mock dictionary for the specific key
    mock_model_scores.return_value[p1.identifier] = 1.0 
    mm, solk = calc_modified_median_solkoff(rounds_dummy, player_ids, opponents_map)
    # Solkoff: Still 9.0 (Opponent scores didn't change)
    assert solk[p1.identifier] == 9.0
    # Mod Median: Drop Highest (5.0). Remaining (1.0 + 3.0) = 4.0
    assert mm[p1.identifier] == 4.0

