from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from russ_swiss_tournament.tournament import Tournament
    from russ_swiss_tournament.matchup_assignment import SwissAssigner, RoundRobinAssigner

from russ_swiss_tournament.service import StartupMode

mode = StartupMode.START_FROM_DB
# mode = StartupMode.INIT_SWISS
# mode = StartupMode.INIT_DB_TABLES

tournament = cast("Tournament", None)
assigner = cast("SwissAssigner | RoundRobinAssigner", None)

