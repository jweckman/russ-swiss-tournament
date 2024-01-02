from enum import Enum

class MatchResult(Enum):
    WIN = 1
    LOSS = 2
    DRAW = 3
    UNSET = 4
    WALKOVER = 5

class Color(Enum):
    W = 1
    B = 2

match_result_manual_map = {
    1: MatchResult.WIN,
    '1': MatchResult.WIN,
    0: MatchResult.LOSS,
    '0': MatchResult.LOSS,
    0.5: MatchResult.DRAW,
    '0.5': MatchResult.DRAW,
    "0,5": MatchResult.DRAW,
    "wo": MatchResult.WALKOVER,
    "walkover": MatchResult.WALKOVER,
    None: MatchResult.UNSET,
    "": MatchResult.UNSET,
    False: MatchResult.UNSET,
    "unset": MatchResult.UNSET,
}

match_result_score_map = {
    MatchResult.WIN:  1,
    MatchResult.LOSS: 0,
    MatchResult.DRAW: 0.5,
    MatchResult.UNSET: None,
    MatchResult.WALKOVER: 0,
}

match_result_score_text_map = {
    MatchResult.WIN:  1,
    MatchResult.LOSS: 0,
    MatchResult.DRAW: '½',
    MatchResult.UNSET: '~',
    MatchResult.WALKOVER: 'wo',
}

def pairwise(iterable):
    "s -> (s0, s1), (s2, s3), (s4, s5), ..."
    a = iter(iterable)
    return zip(a, a)

def split_list(input_list,n):
    first_half=input_list[:n]
    sec_half=input_list[n:]
    return first_half,sec_half

def matchup_to_dict(matchup, players):
    matchup = dict()
    white_full_name = [p for p in players if p.identifier == matchup.white_identifier]
    if white_full_name and len(white_full_name) == 1:
        matchup['white_full_name'] = white_full_name[0].get_full_name()
    black_full_name = [p for p in players if p.identifier == matchup.black_identifier]
    if black_full_name and len(black_full_name) == 1:
        matchup['black_full_name'] = black_full_name[0].get_full_name()
    matchup['white_score'] = match_result_score_map[MatchResult(matchup.white_score)]
    matchup['black_score'] = match_result_score_map[MatchResult(matchup.black_score)]
    matchup['white_identifier'] = matchup.white_identifier
    matchup['black_identifier'] = matchup.black_identifier
    return matchup
