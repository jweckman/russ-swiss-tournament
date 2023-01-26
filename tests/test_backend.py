
# # https://handbook.fide.com/chapter/C0401
# # The following rules are valid for each Swiss system unless explicitly stated otherwise.
# # a) The number of rounds to be played is declared beforehand.
# # b) Two players shall not play against each other more than once.
# # c) Should the number of players to be paired be odd, one player is unpaired. This player receives a pairing-allocated bye: no opponent, no colour and as many points as are rewarded for a win, unless the rules of the tournament state otherwise.
# #
# # d) A player who has already received a pairing-allocated bye, or has already scored a (forfeit) win due to an opponent not appearing in time, shall not receive the pairing-allocated bye.
# # e) In general, players are paired to others with the same score.
# # f) For each player the difference between the number of black and the number of white games shall not be greater than 2 or less than –2.
# # Each system may have exceptions to this rule in the last round of a tournament.
# #
# # g) No player shall receive the same colour three times in a row.
# # Each system may have exceptions to this rule in the last round of a tournament.
# # h)
# # 1) In general, a player is given the colour with which he played less games.
# # 2) If colours are already balanced, then, in general, the player is given the colour that alternates from the last one with which he played.
# # i) The pairing rules must be such transparent that the person who is in charge for the pairing can explain them.
#
# # https://en.wikipedia.org/wiki/Tie-breaking_in_Swiss-system_tournaments
#
# 1. starting point is always:
#     - tournament (class)
#         - set of player class
#         - list of round class
#         - set of tie-break results
#         - used_tie_break_id
#         - year
#         - count
#     - player (class)
#         - id
#         - first_name
#         - last_name
#         - get_full_name()
#
#     - round (class)
#         - index (same as tournament list index but just to be sure)
#         - set of matchup class
#     - matchup (class)
#         - player_white_id_res
#         - player_black_id_res
#         - def check_valid_result()
#         - add_result()
#     - tie-break (class)
#         - method_id(enum)
#         - player_id_results
#         - calculate_results()
#         - calculate_method_harkness()
#
#     - previous ranking
#         - player id and previous ranking based
#         - previous ranking should be determined by method that can change
#             - currently: player id + previous year ranking
# 2. generate first round based on data
#     - player halves constitute groups a and b sorted by ranking
#     - pattern: group a first plays with black agains group b first
# 3. following rounds are generated using:
#     - In general, players are paired to others with the same score.
#     - In general, a player is given the colour with which he played less games (track color per player)
#     - If tied, give white to the lower rated player (RUSS, not FIDE rules)
# 3. Points and tiebrakes
#     - Points go by obvious chess rules
#     - tie brakes should architecturally support any algorithm
#     - implement Median/Harkness first:
#         For each player, this system sums the number of points earned by the player's opponents, excluding the highest and lowest. If there are nine or more rounds, the top two and bottom two scores are discarded. Unplayed games by the opponents count ½ point. Unplayed games by the player count zero points. 

import pytest
from pathlib import Path

from russ_swiss_tournament.tournament import Tournament
from russ_swiss_tournament.player import Player
from russ_swiss_tournament.matchup import Matchup, MatchResult, Color, PlayerMatch
from russ_swiss_tournament.round import Round
from russ_swiss_tournament.tie_break import calc_harkness

# PLAYER
def test_should_get_player_name():
    p = Player(1, 'Joakim', 'Weckman')
    full_name = p.get_full_name()
    assert full_name == f"{p.first_name} {p.last_name}"

# MATCHUP
def test_should_create_without_result():
    m = Matchup({Color.W: PlayerMatch(1),Color.B: PlayerMatch(2)})
    assert m.res[Color.W].res == MatchResult.UNSET
    assert m.res[Color.B].res == MatchResult.UNSET

def test_should_add_result_valid():
    m = Matchup({Color.W: PlayerMatch(1,MatchResult.UNSET),Color.B: PlayerMatch(2,MatchResult.UNSET)})
    m.add_result(MatchResult.WIN, MatchResult.LOSS)
    assert m.res[Color.B].res == MatchResult.LOSS

def test_should_add_result_invalid():
    m = Matchup({Color.W: PlayerMatch(1,MatchResult.UNSET),Color.B: PlayerMatch(2,MatchResult.UNSET)})
    with pytest.raises(ValueError):
        m.add_result(MatchResult.WIN, MatchResult.WIN)

def test_should_not_add_result_invalid_single_draw():
    m = Matchup({Color.W: PlayerMatch(1,MatchResult.UNSET),Color.B: PlayerMatch(2,MatchResult.UNSET)})
    with pytest.raises(ValueError):
        m.add_result(MatchResult.DRAW, MatchResult.LOSS)

def test_should_not_add_result_invalid_multi_win():
    m = Matchup({Color.W: PlayerMatch(1,MatchResult.UNSET),Color.B: PlayerMatch(2,MatchResult.UNSET)})
    with pytest.raises(ValueError):
        m.add_result(MatchResult.WIN, MatchResult.WIN)

def test_should_not_add_result_invalid_multi_loss():
    m = Matchup({Color.W: PlayerMatch(1,MatchResult.UNSET),Color.B: PlayerMatch(2,MatchResult.UNSET)})
    with pytest.raises(ValueError):
        m.add_result(MatchResult.LOSS, MatchResult.LOSS)

def test_should_not_add_result_invalid_single_unset():
    m = Matchup({Color.W: PlayerMatch(1,MatchResult.UNSET),Color.B: PlayerMatch(2,MatchResult.UNSET)})
    with pytest.raises(ValueError):
        m.add_result(MatchResult.LOSS, MatchResult.UNSET)

# ROUND
def test_should_create_valid_round():
    m1 = Matchup({Color.W: PlayerMatch(1,MatchResult.WIN),Color.B: PlayerMatch(2,MatchResult.LOSS)})
    m2 = Matchup({Color.W: PlayerMatch(3,MatchResult.LOSS),Color.B: PlayerMatch(4,MatchResult.WIN)})
    m3 = Matchup({Color.W: PlayerMatch(5,MatchResult.WIN),Color.B: PlayerMatch(6,MatchResult.LOSS)})
    m4 = Matchup({Color.W: PlayerMatch(7,MatchResult.LOSS),Color.B: PlayerMatch(8,MatchResult.WIN)})
    m5 = Matchup({Color.W: PlayerMatch(9,MatchResult.DRAW),Color.B: PlayerMatch(10,MatchResult.DRAW)})
    matchups = [m1,m2,m3,m4,m5]
    r = Round(matchups)
    assert r.index == 0
    r = Round(matchups, 1)
    assert r.index == 1

# # TIE-BREAK

# def create_players(count):
#     players = []
#     for i in range(count):
#         val = i + 1
#         players.append(Player(val, f"p{val}f", f"p{val}l"))
#     return players

# def create_round_matchups(data:dict):
#     '''(player_id, player_id): ('WIN','LOSS') UNFINISHED'''
#     round_matchups = []
#     for i, (k,v) in enumerate(data.items()):
#         round_matchups.append(Matchup(i+1, (k, MatchResult(v), (k, MatchResult(v)))))
#
# def create_rounds(players, count, round_matchups=None):
#     rounds = []
#     if not round_matchups:
#         for r_id in range(count):
#             pass
#     else:
#         for i,m in enumerate(round_matchups):
#             rounds.append(Round(i+1, m))
#
#     return rouBds

def test_should_calculate_harkness_correctly():
    t = Tournament.from_toml(Path.cwd() / 'tournaments' / 'russ_24' / 'config.toml', create_players=True)
    t.calculate_tie_break_results()

    # round_matchups.append([m13,m14,m15,m16,m17,m18,m19,m20,m21,m22,m23,m24])
    # for m in round_matchups[0]:
    #     print(m.player_white_id_res, m.player_black_id_res)

    # rounds = create_rounds(players, 24, round_matchups)
    # player_scores = calc_harkness(rounds, set([p.id for p in players]))
    # TODO: check why not all players have 2 values and outcomes seem weird
    assert True == False


# # TOURNAMENT
def test_should_create_tournament_from_toml():
    t = Tournament.from_toml(Path.cwd() / 'tournaments' / 'russ_24' / 'config.toml', create_players=True)
    assert t.year == 2015
#
# # DATABASE
# # read from toml and csv
# # write to csv
#
# def test_read_players_from_csv_db():
#     pass
#
# def test_read_round_from_csv():
#     pass
#
# def test_generate_round_robin_rounds():
#     pass
#
# def test_generate_swiss_round_first():
#     pass
#
# def test_generate_swiss_round_middle():
#     pass
#
# def test_generate_swiss_round_last():
#     pass
#
#
