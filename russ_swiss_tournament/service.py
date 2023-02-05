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
    MatchResult.UNSET: None,
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
