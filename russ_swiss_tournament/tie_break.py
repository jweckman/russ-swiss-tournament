from enum import Enum

from russ_swiss_tournament.round import Round
from russ_swiss_tournament.matchup import MatchResult, Color, PlayerMatch

class TieBreakMethod(Enum):
    HARKNESS = 1

def harkness_model_scores_player_wins(rounds, player_ids):
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
            winner_loser_colors = m.get_winner_loser_colors()

            if winner_loser_colors:
                wbp[m.res[winner_loser_colors[0]].id].append(m.res[winner_loser_colors[1]].id)
            if ({m.res[Color.W].res, m.res[Color.B].res} == {MatchResult.WIN, MatchResult.WALKOVER}
                    and winner_loser_colors ):
                pms[m.res[winner_loser_colors[0]].id] = res_valuation[m.res[winner_loser_colors[1]].res]
                pms[m.res[winner_loser_colors[1]].id] = 0
            else:
                pms[m.res[Color.W].id].append(res_valuation[m.res[Color.W].res])
                pms[m.res[Color.B].id].append(res_valuation[m.res[Color.B].res])

    pms = {k:(sum(v) or 0) for k,v in pms.items()}
    return pms, wbp

def calc_harkness(rounds:list[Round], player_ids: set):
    '''
    First calculate model scores for each player.
    Then populate a wins by player with which players have been won against.
    Sum scores of wins, removing top and bottom values depending on round count.
    Real rules arbitrarily only kick in after 5 rounds and up (makes testing easier)
    '''
    player_model_scores, wins_by_player = harkness_model_scores_player_wins(rounds, player_ids)

    player_total_gains = dict(zip(list(player_ids), [[] for i in range(len(player_ids))]))

    nine_or_more_rounds = len(rounds) > 8
    for player, defeated_players in wins_by_player.items():
        for dp in defeated_players:
            player_total_gains[player].append(player_model_scores[dp])

    res = dict(zip(list(player_ids), [0 for i in range(len(player_ids))]))
    for player, scores in player_total_gains.items():
        if len(rounds) > 4:
            scores.pop(scores.index(max(scores)))
            scores.pop(scores.index(min(scores)))
            if nine_or_more_rounds:
                scores.pop(scores.index(max(scores)))
                scores.pop(scores.index(min(scores)))
        res[player] = sum(scores)

    return res
