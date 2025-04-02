import importlib.resources
from collections import defaultdict
import itertools
from dataclasses import dataclass
from enum import Enum

from tkinter import *
from tkinter import ttk
from tkinter.filedialog import askopenfilename, askdirectory
import tkinter.scrolledtext as st

from russ_swiss_tournament.round import Round
from russ_swiss_tournament.matchup import Matchup
from russ_swiss_tournament.service import Color, match_result_score_text_map
import config


root = Tk(className='Russ')
root.title = 'RUSS'


theme_file = importlib.resources.files('gui_tkinter').joinpath('azure.tcl')
with importlib.resources.as_file(theme_file) as theme_path:
    root.tk.call("source", theme_path)
    root.tk.call("set_theme", "dark")

class SingleScroll:
    """
    Singleton ScrolledText object.
    To refresh call: SingleScroll._inst.see(END)
    """
    def __new__(cls, master):
        if '_inst' not in vars(cls):  # Create instance?
            scroll = st.ScrolledText(master, width=90, height=15)
            scroll.grid(column=0, row=5, columnspan=6, sticky='W')
            scroll.insert(INSERT, " OK here\n")
            cls._inst = scroll

        return cls._inst

def create_table(parent, data, columns):
    tree = ttk.Treeview(parent, columns=columns, show="headings")
    for col in columns:
        tree.heading(col, text=col)
        tree.column(col, anchor="center")
    for row in data:
        tree.insert("", END, values=row)
    tree.pack(expand=True, fill="both")

def create_rounds_tabs(parent, rounds):
    rounds_notebook = ttk.Notebook(parent)
    rounds_notebook.pack(expand=True, fill="both")
    for rnd in rounds:
        frame = ttk.Frame(rounds_notebook)
        rounds_notebook.add(frame, text=f"Round {rnd.round_index}")
        round_data = []
        for m in rnd.matchups:
            round_data.append((
                m.res[Color.W].player.get_full_name(),
                f"{match_result_score_text_map[m.res[Color.W].res]}-{match_result_score_text_map[m.res[Color.B].res]}",
                m.res[Color.B].player.get_full_name(),
            ))
        create_table(frame, round_data, ["Player 1", "Score", "Player 2"])

def create_standings_view(parent, rounds):
    standings = config.tournament.get_standings()
    players_id_names = config.tournament.get_player_full_names_by_id()
    sorted_standings = [(players_id_names[k], v) for k, v in config.tournament.sort_standings(standings).items()]
    create_table(parent, sorted_standings, ["Player", "Total Score"])

def create_main_tabs(parent, rounds):
    notebook = ttk.Notebook(parent)
    notebook.pack(expand=True, fill="both")
    rounds_tab = ttk.Frame(notebook)
    notebook.add(rounds_tab, text="Rounds")
    standings_tab = ttk.Frame(notebook)
    notebook.add(standings_tab, text="Standings")
    create_rounds_tabs(rounds_tab, rounds)
    create_standings_view(standings_tab, rounds)

def tkinter_main():
    create_main_tabs(root, config.tournament.rounds)
    root.mainloop()


if __name__ == '__main__':
    create_main_tabs(root, config.tournament.rounds)
    tkinter_main()

