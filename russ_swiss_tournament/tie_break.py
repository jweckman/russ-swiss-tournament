from enum import Enum

from russ_swiss_tournament.round import Round
from russ_swiss_tournament.matchup import MatchResult, Color, PlayerMatch

class TieBreakMethod(Enum):
    HARKNESS = 1

def calc_harkness(rounds:list[Round], player_ids: set):
    '''
    First calculate model scores for each player.
    Then populate a wins by player dict.
    Sum scores of wins, removing top and bottom values depending on round count
    '''

    res_valuation = {
        MatchResult.WIN: 1,
        MatchResult.LOSS: 0,
        MatchResult.DRAW: 0,
        MatchResult.UNSET: 0,
        MatchResult.WALKOVER: 0.5,
    }
    # player_id_model_scores
    pms = dict(zip(list(player_ids), [[] for i in range(len(player_ids))]))
    # wins by player
    wbp = dict(zip(list(player_ids), [[] for i in range(len(player_ids))]))
    for r in rounds:
        for m in r.matchups:
            res_black = m.res[Color.B].res
            res_white = m.res[Color.W].res
            white = m.res[Color.W].id
            black = m.res[Color.W].id

            winner = None
            if res_white == MatchResult.WIN:
                winner = white
                winner_res = res_white
                loser = black
                loser_res = res_black
            elif res_black == MatchResult.WIN:
                winner = black
                winner_res = res_black
                loser = white
                loser_res = res_white
            if winner:
                wbp[winner].append(loser)
            if {loser_res, winner_res} == {MatchResult.WIN, MatchResult.WALKOVER}:
                pms[winner] = res_valuation[loser_res]
                pms[loser] = 0
            else:
                pms[white].append(res_valuation[res_white])
                pms[black].append(res_valuation[res_black])

    pms = {k:(sum(v) or 0) for k,v in pms.items()}
    # player_total_gains
    ptg = dict(zip(list(player_ids), [[] for i in range(len(player_ids))]))

    nine_or_more_rounds = len(rounds) > 8
    for player, defeated_players in wbp.items():
        for dp in defeated_players:
            ptg[player].append(pms[dp])

    res = dict(zip(list(player_ids), [0 for i in range(len(player_ids))]))
    for player, scores in ptg.items():
        if len(rounds) > 2:
            scores.pop(scores.index(max(scores)))
            scores.pop(scores.index(min(scores)))
            if nine_or_more_rounds:
                scores.pop(scores.index(max(scores)))
                scores.pop(scores.index(min(scores)))
        res[player] = sum(scores)

    return res
