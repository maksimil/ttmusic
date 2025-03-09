import yaml
from dataclasses import dataclass
import curses
import random


@dataclass
class Playlist:
    name: str
    tracks: [str]


@dataclass
class ModePreset:
    key: str
    name: str
    playlist_name: str
    starting_track: str | int
    random_order: bool
    loop: bool


@dataclass
class Config:
    playlists: {str: Playlist}
    modes: {str: ModePreset}


@dataclass
class Mode:
    name: str
    current_idx: int
    track_order: [int]
    playlist_name: str
    random_order: bool
    loop: bool


class State:
    mode_stack: [Mode]
    config: Config
    stdscr: curses.window

    def __init__(self, config, stdscr):
        self.mode_stack = []
        self.config = config
        self.stdscr = stdscr

    def generate_mode(self, preset: ModePreset) -> Mode:
        playlist_size = len(self.config.playlists[preset.playlist_name].tracks)

        mode = Mode(
            name=preset.name,
            current_idx=0,
            track_order=None,
            playlist_name=preset.playlist_name,
            random_order=preset.random_order,
            loop=preset.random_order,
        )

        if preset.random_order:
            mode.track_order = list(range(playlist_size))
            random.shuffle(mode.track_order)

            if preset.starting_track != "random":
                idx = mode.track_order.index(int(preset.starting_track))
                mode.track_order[0], mode.track_order[idx] = (
                    mode.track_order[idx],
                    mode.track_order[0],
                )
        else:
            idx = None
            if preset.starting_track == "random":
                idx = random.randrange(playlist_size)
            else:
                idx = int(preset.starting_track)

            mode.track_order = list(range(idx, playlist_size))
            mode.track_order.extend(list(range(idx)))

        return mode

    def refresh_stdscr(self):
        self.stdscr.clear()

        # --- Modes ---
        self.stdscr.addstr(0, 0, "modes:")

        for i in range(3):
            for j in range(3):
                y = 1 + i
                x = 20 * j
                idx = str(1 + i + 3 * j)

                if idx in self.config.modes:
                    self.stdscr.addstr(
                        y,
                        x,
                        f"{idx} : {self.config.modes[idx].name}",
                    )

        # --- Stack ---
        self.stdscr.addstr(
            6, 0, "stack: " + ", ".join([x.name for x in self.mode_stack])
        )

        # --- Current mode ---
        mode = self.mode_stack[-1]
        for i in range(len(mode.track_order)):
            if i == mode.current_idx:
                self.stdscr.addstr(8 + i, 0, "> ")

            name = self.config.playlists[mode.playlist_name].tracks[mode.track_order[i]]
            self.stdscr.addstr(8 + i, 2, name)

        # --- Refresh ---
        self.stdscr.move(self.stdscr.getmaxyx()[0] - 1, 0)
        self.stdscr.refresh()

    def add_mode(self, n):
        n = str(n)

        if n not in self.config.modes:
            return

        self.stack.append(self.generate_mode(self.config.modes[n]))

    def pop_mode(self):
        pass

    def skip_track(self):
        mode = self.stack[-1]
        mode.current_idx += 1

        if mode.current_idx == len(mode.track_order):
            if mode.loop:
                mode.current_idx = 0
            else:
                self.pop_mode()

    def begin(self):
        self.refresh_stdscr()
        self.stdscr.getkey()


CONFIG_FILE = "./music.yaml"


def parse_config(config_filename: str):
    config_dict = None
    with open(CONFIG_FILE) as config_file:
        config_dict = yaml.safe_load(config_file)

    config = Config(playlists={}, modes={})

    for key in config_dict["playlists"]:
        tracks = config_dict["playlists"][key]
        key = str(key)
        config.playlists[key] = Playlist(
            name=key,
            tracks=tracks,
        )

    for key in config_dict["modes"]:
        mode_dict = config_dict["modes"][key]
        key = str(key)

        config.modes[key] = ModePreset(
            key=key,
            name=mode_dict["name"],
            playlist_name=mode_dict["playlist"],
            starting_track=mode_dict["starting_track"],
            random_order=mode_dict["random_order"],
            loop=mode_dict["loop"],
        )

    return config


def main(stdscr):
    random.seed()
    config = parse_config(CONFIG_FILE)
    state = State(config, stdscr)
    state.begin()


curses.wrapper(main)
