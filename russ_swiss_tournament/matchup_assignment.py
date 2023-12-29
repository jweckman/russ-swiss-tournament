from random import shuffle

from russ_swiss_tournament.tournament import Tournament
from russ_swiss_tournament.matchup import Matchup, PlayerMatch
from russ_swiss_tournament.round import Round
from russ_swiss_tournament.service import MatchResult, Color
from russ_swiss_tournament.player import Player

class SwissAssigner:
    '''Matchup colors is main result we want to generate. Following round is generated based on it'''
    def __init__(
            self,
            tournament,
        ):
        self.tournament = tournament
        self.opponents: dict[int,list[int]] = tournament.get_opponents()
        self.players_standing_sort: list | None = None
        self.matchup_colors: list[tuple[int,int]] = []
        self.already_paired: set = set()

    def _assign_matchup_colors(self, higher: int, lower: int) -> tuple[int,int]:
        player_color_counts = self.tournament.get_player_color_counts()
        h_colors = player_color_counts[higher]
        l_colors = player_color_counts[lower]
        white_diff = h_colors[0] - l_colors[0]
        black_diff = h_colors[1] - l_colors[1]
        if white_diff != 0:
            if white_diff > 0:
                white = lower
                black = higher
            elif white_diff < 0:
                black = lower
                white = higher
        elif black_diff != 0:
            if black_diff > 0:
                black = higher
                white = lower
            elif black_diff < 0:
                black = lower
                white = higher
        else:
            player_ids_by_rank = [p.identifier for p in self.tournament.players]
            higher_rank_index = player_ids_by_rank.index(higher)
            lower_rank_index = player_ids_by_rank.index(lower)
            if higher_rank_index < lower_rank_index:
                white = lower
                black = higher
            else:
                white = higher
                black = lower

        return white, black

    def _remove_from_candidates(self, player_ids):
        for p in player_ids:
            self.players_standing_sort.pop(self.players_standing_sort.index(p))

    def _assign_matchup_colors_to_res(self, higher, lower, remove_candidates=True):
        white, black = self._assign_matchup_colors(higher, lower)
        self.matchup_colors.append((white, black))
        self.already_paired.add(white)
        self.already_paired.add(black)
        if remove_candidates:
            self._remove_from_candidates([higher,lower])
        print(f"Matched players: w: {white} b: {black}")
        print(f"Remaining players: {self.players_standing_sort}")

    def _assign_round_colors(self) -> list[tuple[int,int]]:
        '''
        Returns list of player ids white, black.

        Tricky and messy logic used at the moment.

        The main logic works by recursively calling the _find_matchup_pairs_by_standing()
        function until all players are assigned accodring to Swiss sytem rules.
        Rule based assignment typically starts failing towards the later rounds. At
        this stage the _swap_player() method starts being used to try swapping
        out one of the previous players where possible.

        Even the swapping logic will fail in case the round count and player
        count get close enough to each other. To try tackling this, there is
        the option to set the "z" variable higher to attempt brute forcing using
        a randomized player order instead of ordered by standings.

        TODO: Change print statements to debug logging where useful
        TODO: Inform the user of the best acheived result if no result can be found so
        that the last round(s) can be manually corrected.
        TODO: Only works for even player count
        '''
        # set the range to more than 1 to try brute forcing with randomized player order
        if len(self.tournament.players) % 2 != 0:
            raise ValueError(
                "Uneven number of participants is currently not supported"
            )
        for z in range(10):
            self.matchup_colors = []
            self.already_paired = set()

            self.opponents = self.tournament.get_opponents()
            self.players_standing_sort = list(reversed(
                {k: v for k, v in sorted(self.tournament.get_standings().items(), key=lambda item: item[1])}.keys()
            ))
            if z != 0:
                # TODO: inform user of using brute force to generate
                shuffle(self.players_standing_sort)

            def _find_matchup_pairs_by_standing():
                if len(self.players_standing_sort) == 0:
                    return True
                print(f"Attempting to match: {self.players_standing_sort[0]}")
                higher = self.players_standing_sort[0]
                higher_opponents = set(self.opponents[higher])
                print(f"Already played opponents for {higher}: {higher_opponents}")
                print(f"Already paired: {self.already_paired}")
                pool = self.players_standing_sort[1:].copy()
                for i, p in enumerate(pool):
                    forbidden = (
                        self.already_paired
                        | higher_opponents
                    )
                    if p not in forbidden:
                        self._assign_matchup_colors_to_res(
                            higher,
                            p
                        )
                        _find_matchup_pairs_by_standing()
                        break
                    print(f"Pool is {pool}")
                    if p in forbidden and i == len(pool) - 1 :
                        print(f"matchup_colors index: {i}/{len(pool) - 1}")
                        print(f"matchup_colors len before swap: {len(self.matchup_colors)}")
                        successful_swap = self._swap_player(higher, p)
                        print(f"matchup_colors len after swap: {len(self.matchup_colors)}")
                        if successful_swap:
                            successful_swap = _find_matchup_pairs_by_standing()
                        else:
                            return False
            success = _find_matchup_pairs_by_standing()
            if success:
                break

    def _swap_player(self, higher: int, p: int):
        '''
        If a player no longer has valid opponents left after having assigned
        the matches for the higher ranked players, reverse through the previously
        assigned matches and swap out opponents when legally possible.

        param higher: player that gets a new opponent. Only used to see previous opponents.
        param p: the player that we swap out for another one.

        Returns True if successful and False if swap failed.
        '''
        whites = [m[0] for m in self.matchup_colors]
        whites_reversed = list(reversed(whites))
        blacks = [m[1] for m in self.matchup_colors]
        blacks_reversed = list(reversed(blacks))

        {print(f"{k}: {v}") for k,v in self.opponents.items()}
        {print(f"{k}: {v}") for k,v in self.tournament.get_opponents(inverse=True).items()}
        for i, players in enumerate([blacks_reversed, whites_reversed]):
            if i == 0:
                other = whites_reversed
            if i == 1:
                other = blacks_reversed
            for j, swap_candidate in enumerate(players):
                print(f"-----SWAP CANDIDATE: {swap_candidate}-----")
                candidate_current_opponent = other[j]
                if  (
                        swap_candidate not in self.opponents[higher]
                        and p not in self.opponents[candidate_current_opponent]
                    ):
                    actual_index = -1 * (j + 1)
                    assert {swap_candidate, candidate_current_opponent} == set(self.matchup_colors[actual_index])
                    to_modify = self.matchup_colors[actual_index]
                    print(f"replace this: {self.matchup_colors[actual_index]} with: {(candidate_current_opponent,p)} ")
                    self.matchup_colors[actual_index] = (candidate_current_opponent,p)
                    self._assign_matchup_colors_to_res(higher, swap_candidate, remove_candidates=False)
                    self.players_standing_sort.pop(self.players_standing_sort.index(higher))
                    self.players_standing_sort.pop(self.players_standing_sort.index(p))
                    print(f"Swapped player {p} for {swap_candidate} from matchup {to_modify} to {higher,p}")
                    print(f"remaining: {self.players_standing_sort}")
                    return True
        return False

    def create_next_round(self):
        if not self.tournament.rounds:
            self.tournament._create_initial_round()
        else:
            self.players_standing_sort = list(reversed(
                {k: v for k, v in sorted(self.tournament.get_standings().items(), key=lambda item: item[1])}.keys()
            ))
            self.tournament.validate_no_incomplete_match_results_in_rounds()
            self._assign_round_colors()
            matchups = []
            assert len(self.matchup_colors) == len(self.tournament.players) / 2
            for mcs in self.matchup_colors:
                white = [p for p in self.tournament.players if p.identifier == mcs[0]][0]
                black = [p for p in self.tournament.players if p.identifier == mcs[1]][0]
                assert isinstance(white, Player)
                matchups.append(
                    Matchup(
                        {
                            Color.W: PlayerMatch(white),
                            Color.B: PlayerMatch(black)
                        }
                    )
                )
            self.tournament.rounds.append(
                Round(
                    matchups,
                    index = self.tournament.rounds[-1].index + 1),
            )
            # Make sure there are no unevenly assigned matchups
            assert all([len(v) == len(self.tournament.rounds) for v in self.tournament.get_opponents().values()])
            self.tournament.validate_no_duplicate_matchups()

class RoundRobinAssigner:
    def __init__(
            self,
            tournament,
        ):
        self.tournament = tournament
        self.players = list(range(1, len(tournament.players) + 1))
        self.player_count = len(tournament.players)
        self.half = int(self.player_count / 2)
        self.berger_result = None

        # 5 or 6 players:
        # Rd 1: 1-6, 2-5, 3-4.
        # Rd 2: 6-4, 5-3, 1-2.
        # Rd 3: 2-6, 3-1, 4-5.
        # Rd 4: 6-5, 1-4, 2-3.
        # Rd 5: 3-6, 4-2, 5-1.

        # 9 or 10 players:
        # Rd 1: 1-10, 2-9, 3-8, 4-7, 5-6.
        # Rd 2: 10-6, 7-5, 8-4, 9-3, 1-2.
        # Rd 3: 2-10, 3-1, 4-9, 5-8, 6-7.
        # Rd 4: 10-7, 8-6, 9-5, 1-4, 2-3.
        # Rd 5: 3-10, 4-2, 5-1, 6-9, 7-8.
        # Rd 6: 10-8, 9-7, 1-6, 2-5, 3-4.
        # Rd 7: 4-10, 5-3, 6-2, 7-1, 8-9.
        # Rd 8: 10-9, 1-8, 2-7, 3-6, 4-5.
        # Rd 9: 5-10, 6-4, 7-3, 8-2, 9-1.


    def generate_berger_round(self, r):
        matchups_tuples = []
        if r % 2 == 1:
            for i in range(self.half):
                matchups_tuples.append((self.players[i],self.players[self.player_count-1-i]))
        else:
            matchups_tuples.append((self.players[self.player_count-1],self.players[0]))
            for i in range(1,self.half):
                matchups_tuples.append((self.players[i],self.players[self.player_count-1-i]))
        return matchups_tuples

    def create_berger_rounds(self):
        '''https://en.wikipedia.org/wiki/Round-robin_tournament#Berger_tables'''

        tuple_rounds = []
        self.players=[x for x in range(1,self.player_count+1)]
        tuple_rounds.append(self.generate_berger_round(1))
        for x in range(2,self.player_count):
            j = self.players[self.player_count-1]
            del self.players[self.player_count-1]
            self.players.extend(x for x in self.players[0:self.half])
            self.players[0:self.half-1] = self.players[self.half:self.player_count-1]
            del self.players[self.half-1:self.player_count-1]
            self.players.append(j)
            tuple_rounds.append(self.generate_berger_round(x))
        self.berger_result = tuple_rounds

    def replace_berger_ranks_with_player_ids(self):
        if not self.berger_result:
            raise ValueError(
                "You need to calculate the berger_result before replacing the rank "
                "values with player ids."
            )
        # berger_result_player_id
        brpid = []
        for round in self.berger_result:
            r = []
            for matchup in round:
                r.append(
                    (
                        self.tournament.players[matchup[0] - 1].id,
                        self.tournament.players[matchup[1] - 1].id)
                )
            brpid.append(r)
        return brpid

    def prepare_tournament_rounds(self):
        '''
        This is the main method to run.
        Adds all the rounds to the attached tournament.
        '''
        self.create_berger_rounds()
        brpid = self.replace_berger_ranks_with_player_ids()
        for i, round in enumerate(brpid):
            round_matchups = []
            for matchup_player_ids in round:
                # TODO: add player id validation
                round_matchups.append(Matchup(
                    {
                        Color.W: [PlayerMatch(p) for p in self.tournament.players if p.identifier == matchup_player_ids[0]][0],
                        Color.B: [PlayerMatch(p) for p in self.tournament.players if p.identifier == matchup_player_ids[1]][0],
                    }
                ))
            self.tournament.rounds.append(Round(round_matchups, i+1))

