from pathlib import Path

from russ_swiss_tournament.tournament import Tournament, RoundSystem

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

def _get_help_text(t: Tournament):
    pass
    # TODO

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
    while True:
        print(_get_init_text(t))
        s = input("\nType 'h' for help: ")
