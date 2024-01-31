
import pytest
from pathlib import Path
from random import choices, seed

from russ_swiss_tournament.tournament import Tournament
from russ_swiss_tournament.player import Player
from russ_swiss_tournament.matchup import Matchup, PlayerMatch
from russ_swiss_tournament.round import Round
from russ_swiss_tournament.tie_break import calc_modified_median_solkoff, calc_sonne_koya, TieBreakMethodSwiss, TieBreakMethodRoundRobin
from russ_swiss_tournament.matchup_assignment import SwissAssigner, RoundRobinAssigner
from russ_swiss_tournament.db import Database
from russ_swiss_tournament.service import MatchResult, Color

# PLAYER
def test_should_get_player_name():
    p = Player(1, 'Joakim', 'Weckman')
    full_name = p.get_full_name()
    assert full_name == f"{p.first_name} {p.last_name}"

# MATCHUP
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

# ROUND
def test_should_create_valid_round():
    players = create_players(10)
    m1 = Matchup({Color.W: PlayerMatch(players[0], MatchResult.WIN), Color.B: PlayerMatch(players[1], MatchResult.LOSS)})
    m2 = Matchup({Color.W: PlayerMatch(players[2], MatchResult.LOSS), Color.B: PlayerMatch(players[3], MatchResult.WIN)})
    m3 = Matchup({Color.W: PlayerMatch(players[4], MatchResult.WIN), Color.B: PlayerMatch(players[5], MatchResult.LOSS)})
    m4 = Matchup({Color.W: PlayerMatch(players[6], MatchResult.LOSS), Color.B: PlayerMatch(players[7], MatchResult.WIN)})
    m5 = Matchup({Color.W: PlayerMatch(players[8], MatchResult.DRAW), Color.B: PlayerMatch(players[9], MatchResult.DRAW)})
    matchups = [m1, m2, m3, m4, m5]
    r = Round(matchups)
    assert r.index == 1
    r = Round(matchups, 2)
    assert r.index == 2

# # TIE-BREAK

def create_players(count):
    players = []
    for i in range(count):
        val = i + 1
        players.append(Player(val, f"p{val}f", f"p{val}l"))
    return players

def create_random_round(matchup_count):
    round_matchups = []
    matchup_results = [
        [MatchResult.WIN, MatchResult.LOSS],
        [MatchResult.LOSS, MatchResult.WIN],
        [MatchResult.WIN, MatchResult.WALKOVER],
        [MatchResult.DRAW, MatchResult.DRAW],
    ]
    first = 1
    second = 2
    for i in range(matchup_count):
        mr = choices(matchup_results, [20, 15, 50, 15])[0]
        round_matchups.append(Matchup({
            Color.W: PlayerMatch(first, mr[0]),
            Color.B: PlayerMatch(second, mr[1])
        }))
        first += 2
        second += 2
    return Round(round_matchups)

def fill_round_with_random_values(round: Round):
    random_round = create_random_round(len(round.matchups))
    for i, m in enumerate(round.matchups.copy()):
        round.matchups[i].res[Color.W].res = random_round.matchups[i].res[Color.W].res
        round.matchups[i].res[Color.B].res = random_round.matchups[i].res[Color.B].res

def create_rounds(t, count, round_matchups=None):
    rounds = []
    if not round_matchups:
        for r_id in range(count):
            print(f"-------------- Round: {r_id + 1}-----------------")
            m = SwissAssigner(t)
            m.create_next_round()
            fill_round_with_random_values(t.rounds[-1])
    else:
        for i, m in enumerate(round_matchups):
            rounds.append(Round(i + 1, m))

    return rounds

def test_should_generate_round_robin_rounds_correctly():
    t = Tournament.from_toml(Path.cwd() / 'tournaments' / 'test_round_robin' / 'config.toml', create_players=True)
    db = Database()
    db.read_players()
    rra = RoundRobinAssigner(t)
    rra.prepare_tournament_rounds()
    (Path.cwd() / 'tournaments' / 'test_round_robin' / 'rounds').mkdir(exist_ok=True)
    for r in t.rounds:
        r.write_csv(Path.cwd() / 'tournaments' / 'test_round_robin' / 'rounds', db)

def test_should_calculate_sonne_koya_correctly():
    t = Tournament.from_toml(
        Path.cwd() / 'tournaments' / 'test_round_robin' / 'config.toml',
        read_rounds = True,
        create_players=True,
    )
    # Use random generator if desired
    # rra = RoundRobinAssigner(t)
    # rra.prepare_tournament_rounds()
    # [fill_round_with_random_values(r) for r in t.rounds]
    sonne, koya = calc_sonne_koya(
        *t.get_player_defeated_drawn(),
        t.get_standings(),
        len(t.rounds),
    )
    print(f"Sonne: {sonne}")
    print(f"Koya: {koya}")
    assert sonne[9] == 30
    assert koya[9] == 1.5


def test_should_generate_swiss_rounds_correctly(count_mode=True):
    '''
    Brute force test that creates a large number of random swiss
    tournaments to see if there is a failure. As the round count approaches
    player count, generating gets increasingly difficult and may fail.

    The main reason for failures are color related, i.e a player gets assigned
    the same color four times. Getting the color_fail_count down to 0 means that
    everything works all the time. With 20 players failure rate seems to be at
    around 7%, which is very good. More debugging is needed to find those cases that
    cause these failures. Using 12 players (worst case) the percentage drops lower when
    all 100 runs pass but the majority of the time there is a mysterious assertion error
    that should be looked into.
    '''
    color_fail_count = 0
    for i in range(100):
        t = Tournament.from_toml(
            Path.cwd() / 'tournaments' / 'test_swiss' / 'config.toml',
            create_players = True,
            read_rounds = False,
        )
        try:
            create_rounds(t, t.round_count)
        except ValueError as e:
            if count_mode:
                if 'color' in str(e):
                    color_fail_count += 1
                    continue
            else:
                raise e
    assert color_fail_count == 0

def test_should_calculate_modified_median_solkoff_correctly():
    players = [
        Player(0, 'win', 'all'),
        Player(1, 'lose', 'all'),
        Player(2, 'draw', 'all'),
        Player(3, 'p', 'a'),
        Player(4, 'p', 'b'),
        Player(5, 'p', 'c'),
        Player(6, 'p', 'd'),
        Player(7, 'p', 'e'),
    ]
    t = Tournament.from_toml(
        Path.cwd() / 'tournaments' / 'test_tie_break' / 'config.toml',
        create_players = False,
        read_rounds = False,
        players_manual = players,
    )
    t.rounds = t.read_rounds(t.round_folder, t.players)
    # sa = SwissAssigner(t)
    # create_rounds(t, sa, t.round_count)
    tbm, tbs = t.get_tie_break_results_swiss()
    assert tbm[0] == 3.5
    assert tbs[0] == 4
    assert tbm[1] == 3.5
    assert tbs[1] == 5.5
    assert tbm[2] == 1.5
    assert tbs[2] == 3.5

# # DATABASE
# def test_read_players_from_csv_db():
#     db = Database()
#     db.read_players()
#     assert isinstance(db.players[0], Player)

