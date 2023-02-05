from pathlib import Path
from dataclasses import dataclass
from typing import Callable

from russ_swiss_tournament.tournament import Tournament, RoundSystem

@dataclass
class Command:
    func: Callable
    aliases: list
    help: str

def update(t):
    # TODO
    # update rounds from csv
    t.calculate_tie_break_results_round_robin()
    # t.calculate_tie_break_results_swiss()

def standings(t, player_id = None):
    s = t.get_standings()
    full_names = {p.id: p.get_full_name() for p in t.players}
    tie_breaks = t.tie_break_results_round_robin
    for k,v in s.items():
        n = full_names[k]
        if isinstance(v, float):
            if v.is_integer():
                v = int(v)
        res = f"{n.ljust(20)} {str(v).ljust(5)} ("
        for tb, trs in tie_breaks.items():
            res = f"{res}{str(trs[k])}, "
        res = res[:-2] + ")"
        print(res)

def round(t, number):
    r_index = int(number)
    rounds = [r for r in t.rounds if r.index == r_index]
    if len(rounds) > 1:
        raise ValidationError(
            "Multiple rounds have the same index. That should not happen. Check code"
        )
    if len(rounds) == 1:
        for mu in rounds[0].matchups:
            print(f"\n{mu}")
    raise ValidationError(
        f"Round {number} could not be found. Is it registered? Did you type an integer?"
    )

cmd_update = Command(
    update,
    ['update', 'u'],
    (
        "Updates all the tournament information based on the latest inserted data.\n"
        "This includes standings and tie-break results.\nNote that updates are only "
        "made based on all completed consecutive rounds. Any missing round data in a round "
        "will mean that only the previous complete rounds are included in updated calculations."
        "\n\nShorthand command: u"
    ),
)
cmd_standings = Command(
    standings,
    ['standings', 's'],
    (
        "Shows the current standings. Two things to note:\n1. Run the update command first if you "
        "have any new completed rounds since the last round.\n2. Specify a player id after the command "
        "to see the player specific matchup results and other relevant standing related information."
        "\n\nShorthand command: s (or 's %player_id%)"
    ),
)
cmd_round = Command(
    round,
    ['round', 'r'],
    (
        "Shows the specified round, regardless of status. Note that an uncompleted round "
        "that has data inserted but not updated will most likely show up as empty unless "
        "the update command is run before."
        "\n\nShorthand command: r %num%"
    ),
)

AVAILABLE_COMMANDS = [cmd_update, cmd_standings, cmd_round]

def _get_init_text(t: Tournament):

    NOTHING_LOADED = (
        "It seems that you have no data loaded. Consider starting "
        "the program by specifying a .toml file with all the required "
        "information such as used round system and tie break methods."
    )
    TOML_NOTES = (
        "Toml file parsed successfully.\nKeep in mind that payer ids need "
        "to be added in the starting ranking order of the tournament.\n"
    )
    STATE_INFO_ROUND_ROBIN = (
        f"Tournament initialized with {len(t.rounds)} {t.round_system.name.lower()} rounds "
        f"generated with {len(t.players)} players.\nCsv score input files are ready in "
        f"{t.round_folder}\n\n To proceed, fill in the round files chronologically "
        "and follow up by using the 'update' and 'standings' commands."
    )
    STATE_INFO_SWISS = (
        "TODO: THERE IS NO INFO MESSAGE FOR SWISS TOURNAMENTS YET"
    )
    WELCOME = (
        "\nWelcome to the RUSS tournament generator!\n"
    )
    if not t.players or not t.rounds:
        WELCOME = '\n'.join([WELCOME, NOTHING_LOADED])
        return WELCOME
    if t.round_system == RoundSystem.BERGER:
        WELCOME = '\n'.join([
            WELCOME,
            TOML_NOTES,
            STATE_INFO_ROUND_ROBIN,
        ])
    if t.round_system == RoundSystem.SWISS:
        WELCOME = '\n'.join([
            WELCOME,
            TOML_NOTES,
            STATE_INFO_SWISS,
        ])
    return WELCOME

def _normalize_input_str(s):
    return s.lower().strip()

def _get_command(t: Tournament, s: str, run: bool=True):
    '''
    Run boolean determines whether command is run or help string is printed.
    '''
    s = s.replace('help', '')
    parts = s.split()
    for i, p in enumerate(parts):
        for c in AVAILABLE_COMMANDS:
            if any(a == p for a in c.aliases):
                if run:
                    arg_count = c.func.__code__.co_argcount
                    args = None
                    args = [a for a in parts[i+1:]]
                    if args:
                        res = c.func(t, *args)
                    else:
                        res = c.func(t)
                else:
                    print(c.help)

def main(
        t: Tournament
    ):
    '''
    starting up should say:
    - what the program is
    - mention the help command
    - give information about current program state
    - suggest actions
    - inform about important toml file details
    help menu should list available commands

    needed commands(RR):
    - [u]pdate: read latests rounds and update all other state
    - [s]tandings: latest complete round,name[id], scores, tie-break scores in order, count black and white,
    - [s]tandings [id]: all matchups so far, tournament ranking, points, tie break results
    - [h]elp

    TODO: needed commands(Swiss):
    '''
    print(_get_init_text(t))
    t.get_standings()
    while True:
        s = input("\nType 'h' for help: ")
        s = _normalize_input_str(s)
        if 'help' in s:
            _get_command(t, s, False)
        else:
            _get_command(t, s, True)


