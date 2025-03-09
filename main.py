import yaml
from dataclasses import dataclass
import curses
import random
import time
import pyaudio
import av

CONFIG_FILE = "./music.yaml"
LOOP_PERIOD = 50  # ms


def get_audio_data(frame):
    audio_data = frame.to_ndarray().astype("float32")
    interleaved_data = audio_data.T.flatten().tobytes()
    return interleaved_data


class AudioPlayer:
    p: pyaudio.PyAudio

    is_playing: bool

    def __init__(self):
        self.p = pyaudio.PyAudio()

    def __del__(self):
        self.p.terminate()

    def play_file(self, filename):
        container = av.open(filename)
        audio_stream = container.streams.best("audio")
        frame_iterator = container.decode(audio=0)
        channels = audio_stream.channels

        bytesdata = b""
        idx = 0

        def callback(in_data, frame_count, time_info, status):
            nonlocal bytesdata, idx

            print(f"{len(bytesdata) / 1024} Kb")

            offset = 4 * channels * frame_count

            while idx + offset > len(bytesdata):
                if frame_iterator:
                    frame = next(frame_iterator)
                    bytesdata += get_audio_data(frame)
                else:
                    bytesdata[idx:], pyaudio.paComplete

            bytesdata = bytesdata[idx:]
            idx = offset
            return bytesdata[:idx], pyaudio.paContinue

        device = self.p.open(
            format=pyaudio.paFloat32,
            channels=channels,
            rate=audio_stream.rate,
            output=True,
            stream_callback=callback,
        )

        time.sleep(10)

        audio_stream.close()
        container.close()
        device.stop_stream()
        device.close()


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
    #  audio: AudioPlayer

    def __init__(self, config, stdscr):
        self.stack = []
        self.config = config
        self.stdscr = stdscr
        #  self.audio = AudioPlayer()

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

    def pause_track(self):
        pass

    def process_key(self, keycode):
        if keycode == ord("q"):
            if len(self.stack) == 0:
                return True
            else:
                self.pop_mode()

        elif keycode == ord("s"):
            self.skip_track()

        elif keycode == ord(" "):
            self.pause_track()

        elif keycode in [ord(x) for x in self.config.modes]:
            self.add_mode(chr(keycode))

        self.refresh_stdscr()

        return False

    def begin(self):
        self.stdscr.nodelay(True)
        self.refresh_stdscr()

        while True:
            keycode = self.stdscr.getch()

            while keycode != curses.ERR:
                do_exit = self.process_key(keycode)

                if do_exit:
                    return

                keycode = self.stdscr.getch()

            time.sleep(LOOP_PERIOD / 1000)


def parse_config(config_filename: str):
    config_dict = None
    with open(config_filename) as config_file:
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


#  curses.wrapper(main)

audio = AudioPlayer()

audio.play_file("./Burzum - Emptiness.mp3")
