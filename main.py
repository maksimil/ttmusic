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
    order: str
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


def generate_order(size, starting, is_random):
    order = None
    if random:
        order = list(range(size))
        random.shuffle(order)

        if starting != "random":
            idx = order.index(int(starting))
            order[0], order[idx] = order[idx], order[0]

    else:
        idx = None

        if starting == "random":
            idx = random.randrange(size)
        else:
            idx = int(starting)

        order = list(range(idx, size))
        order.extend(list(range(idx)))

    return order


class State:
    stack: [Mode]
    config: Config
    stdscr: curses.window

    def __init__(self, config, stdscr):
        self.stack = []
        self.config = config
        self.stdscr = stdscr

    def generate_mode(self, preset: ModePreset) -> Mode:
        playlist_size = len(self.config.playlists[preset.playlist_name].tracks)

        mode = Mode(
            name=preset.name,
            current_idx=0,
            track_order=None,
            playlist_name=preset.playlist_name,
            random_order=preset.order == "random",
            loop=preset.loop,
        )

        if preset.order == "random":
            mode.track_order = generate_order(
                playlist_size, preset.starting_track, True
            )
        elif preset.order == "straight":
            mode.track_order = generate_order(
                playlist_size, preset.starting_track, False
            )
        elif preset.order == "once":
            idx = None

            if preset.starting_track == "random":
                idx = random.randrange(playlist_size)
            else:
                idx = int(preset.starting_track)

            mode.track_order = [idx]

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
            6,
            0,
            "stack: " + ", ".join([x.name for x in self.stack]),
        )

        # --- Current mode ---
        if len(self.stack) > 0:
            mode = self.stack[-1]
            for i in range(len(mode.track_order)):
                if i == mode.current_idx:
                    self.stdscr.addstr(8 + i, 0, "> ")

                name = self.config.playlists[mode.playlist_name].tracks[
                    mode.track_order[i]
                ]
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
        self.stack.pop()

    def skip_track(self):
        if len(self.stack) == 0:
            return

        mode = self.stack[-1]
        mode.current_idx += 1

        playlist_size = len(mode.track_order)
        if mode.current_idx == playlist_size:
            if mode.loop:
                mode.current_idx = 0
                if mode.random_order:
                    mode.track_order = generate_order(
                        playlist_size,
                        "random",
                        True,
                    )
            else:
                self.pop_mode()

    def begin(self):
        self.refresh_stdscr()

        while True:
            key = self.stdscr.getkey()

            if key == "q":
                if len(self.stack) == 0:
                    break
                else:
                    self.pop_mode()

            elif key == "s":
                self.skip_track()

            elif key in self.config.modes:
                self.add_mode(key)

            self.refresh_stdscr()


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
            order=mode_dict["order"],
            loop=mode_dict["loop"],
        )

    return config


def main(stdscr):
    random.seed()
    config = parse_config(CONFIG_FILE)
    state = State(config, stdscr)
    state.begin()


curses.wrapper(main)
