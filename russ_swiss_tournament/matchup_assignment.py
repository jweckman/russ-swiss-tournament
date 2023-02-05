from russ_swiss_tournament.tournament import Tournament
from russ_swiss_tournament.matchup import Matchup, PlayerMatch
from russ_swiss_tournament.round import Round
from russ_swiss_tournament.service import MatchResult, Color

class MatchupsAssigner:
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
            player_ids_by_rank = [p.id for p in self.tournament.players]
            higher_rank_index = player_ids_by_rank.index(higher)
            lower_rank_index = player_ids_by_rank.index(lower)
            if higher_rank_index < lower_rank_index:
                white = lower
                black = higher
            else:
                white = higher
                black = lower

        return white, black

    def _assign_matchup_colors_to_res(self, higher, lower):
        white, black = self._assign_matchup_colors(higher, lower)
        self.matchup_colors.append((white, black))
        self.already_paired.add(self.players_standing_sort.pop(self.players_standing_sort.index(white)))
        self.already_paired.add(self.players_standing_sort.pop(self.players_standing_sort.index(black)))

    def _assign_round_colors(self) -> list[tuple[int,int]]:
        '''
        Returns list of player ids white, black
        TODO: Only works for even player count
        '''
        if len(self.tournament.players) % 2 != 0:
            raise ValueError(
                "Uneven number of participants is currently not supported"
            )

        opponents = self.tournament.get_opponents()
        self.players_standing_sort = list(reversed(
            {k: v for k, v in sorted(self.tournament.get_standings().items(), key=lambda item: item[1])}.keys()
        ))
        matchup_colors = []
        self.already_paired = set()
        def _find_matchup_pairs_by_standing():
            if len(self.players_standing_sort) == 0:
                return True
            higher = self.players_standing_sort[0]
            for p in self.players_standing_sort[1:]:
                if p not in (self.already_paired | set(opponents[higher])):
                    self._assign_matchup_colors_to_res(
                        higher,
                        p
                    )
                    _find_matchup_pairs_by_standing
            return False
        completed = _find_matchup_pairs_by_standing()
        if not completed:
            # go backwards through matchup_colors and look for people that can be swapped out
            pass

    def create_next_round(self):
        if not self.tournament.rounds:
            self.tournament._create_initial_round()
        else:
            self.players_standing_sort = list(reversed(
                {k: v for k, v in sorted(self.tournament.get_standings().items(), key=lambda item: item[1])}.keys()
            ))
            self.tournament.validate_no_null_match_results_in_rounds()
            self._assign_round_colors()
            matchups = []
            for mcs in self.matchup_colors:
                matchups.append(Matchup({Color.W: PlayerMatch(mcs[0]), Color.B: PlayerMatch(mcs[1])}))
            self.rounds.append(
                Round(matchups, index = self.rounds[-1].index + 1)
            )

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
                        Color.W: [PlayerMatch(p) for p in self.tournament.players if p.id == matchup_player_ids[0]][0],
                        Color.B: [PlayerMatch(p) for p in self.tournament.players if p.id == matchup_player_ids[1]][0],
                    }
                ))
            self.tournament.rounds.append(Round(round_matchups, i+1))

