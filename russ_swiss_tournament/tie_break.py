from enum import Enum

from russ_swiss_tournament.round import Round
from russ_swiss_tournament.matchup import MatchResult, Color, PlayerMatch

class TieBreakMethodSwiss(Enum):
    MODIFIED_MEDIAN = 1
    SOLKOFF = 2

class TieBreakMethodRoundRobin(Enum):
    SONNEBORN_BERGER = 1
    KOYA = 2

def modified_median_solkoff_model_scores(rounds, player_ids):
    res_valuation = {
        MatchResult.WIN: 1,
        MatchResult.LOSS: 0,
        MatchResult.DRAW: 0.5,
        MatchResult.UNSET: 0,
        MatchResult.WALKOVER: 0.5,
    }
    pms = dict(zip(list(player_ids), [0 for x in range(len(player_ids))]))
    for r in rounds:
        for m in r.matchups:
            winner_loser_colors, is_walkover = m.get_winner_loser_colors()
            if winner_loser_colors:
                winner_color, loser_color = winner_loser_colors

            if is_walkover:
                pms[m.res[winner_color].id] += res_valuation[
                    MatchResult.WALKOVER
                ]
                pms[m.res[loser_color].id] += res_valuation[
                    MatchResult.LOSS
                ]
            else:
                for color, player_match in m.res.items():
                    pms[player_match.id] += res_valuation[player_match.res]

    return pms

def calc_modified_median_solkoff(rounds:list[Round], player_ids: set, opponents: dict):
    '''
    First calculate model scores for each player.
    Solkoff is actually Modified Median without filtering
    '''
    player_model_scores = modified_median_solkoff_model_scores(rounds, player_ids)

    player_total_gains = dict(zip(list(player_ids), [[] for i in range(len(player_ids))]))

    for player, ops in opponents.items():
        for opponent in ops:
            player_total_gains[player].append(player_model_scores[opponent])

    nine_or_more_rounds = len(rounds) > 8
    modified_median = dict(zip(list(player_ids), [0 for i in range(len(player_ids))]))
    solkoff = dict(zip(list(player_ids), [0 for i in range(len(player_ids))]))
    tournament_max_score = len(rounds)
    tournament_half_score = tournament_max_score / 2
    for player, scores in player_total_gains.items():
        player_score = player_model_scores[player]

        mod_med_scores = scores.copy()
        if player_score > tournament_half_score:
            mod_med_scores.pop(mod_med_scores.index(min(mod_med_scores)))
            if nine_or_more_rounds:
                mod_med_scores.pop(mod_med_scores.index(min(mod_med_scores)))
        elif player_score < tournament_half_score:
            mod_med_scores.pop(mod_med_scores.index(max(mod_med_scores)))
            if nine_or_more_rounds:
                mod_med_scores.pop(mod_med_scores.index(max(mod_med_scores)))
        else:
            mod_med_scores.pop(mod_med_scores.index(max(mod_med_scores)))
            mod_med_scores.pop(mod_med_scores.index(min(mod_med_scores)))
            if nine_or_more_rounds:
                mod_med_scores.pop(mod_med_scores.index(max(mod_med_scores)))
                mod_med_scores.pop(mod_med_scores.index(min(mod_med_scores)))

        modified_median[player] = sum(mod_med_scores)
        solkoff[player] = sum(scores)

    return modified_median, solkoff

def calc_sonne_koya(
        player_defeated_drawn: dict[int,list[list,list]],
        player_defeated_drawn_scores: dict[int,dict[int,float]],
        player_standings: dict[int,float],
        round_count,
    ):
    '''
    Sonneborn-Berger: the sum of the scores of the opponents a player has
    defeated and half the scores of the players with whom he has drawn.
    Koya System: the number of points achieved against all opponents who have achieved 50% or more.
    '''
    tournament_max_score = round_count
    tournament_half_score = tournament_max_score / 2
    sonne = dict(zip(list(player_standings.keys()), [0 for i in range(len(player_standings.keys()))]))
    koya = dict(zip(list(player_standings.keys()), [0 for i in range(len(player_standings.keys()))]))
    for p, dd in player_defeated_drawn.items():
        sonne[p] += sum([player_standings[x] or 0 for x in dd[0]])
        sonne[p] += sum([player_standings[x] * 0.5 or 0 for x in dd[1]])
    for p, dd in player_defeated_drawn.items():
        good_opp_scores = 0
        for def_drawn_player in dd[0] + dd[1]:
            is_good_opp = player_standings[def_drawn_player] >= tournament_half_score
            if is_good_opp:
                good_opp_scores += player_defeated_drawn_scores[p][def_drawn_player]
        koya[p] = good_opp_scores
    return sonne, koya

