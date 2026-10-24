"""Orquestación principal de la aplicación."""
from __future__ import annotations

import argparse
import sys
import threading
import time

from rich.console import Console
from rich.live import Live

from .config import MAX_RECENT, RENDER_FPS, STATIONS, add_recent, load_recents, ordered_stations
from .deps import check_deps
from .input import read_key_nonblocking
from .metadata import IcyMetadataFetcher
from .player import AudioPlayer
from .theme import DEFAULT_THEME_NAME, available_themes, load_theme, palette
from .ui import render
from . import __version__


class AppState:
    def __init__(self, stations, theme_name=None, theme_mode=None):
        self.all_stations = list(stations)
        self.recents = load_recents()
        self.selected = 0
        self.player = AudioPlayer()
        self.running = True
        self.theme = load_theme(theme_name, theme_mode)
        self.pal = palette(self.theme)
        self.metadata: dict = {}
        self.meta_lock = threading.Lock()
        self.fetcher = IcyMetadataFetcher(self._on_meta)
        self.stations: list = []
        self.n_recents = 0
        self.rebuild()

    # --- metadata -----------------------------------------------------
    def _on_meta(self, info):
        with self.meta_lock:
            self.metadata = info or {}

    def get_metadata(self) -> dict:
        with self.meta_lock:
            return dict(self.metadata)

    def clear_metadata(self) -> None:
        with self.meta_lock:
            self.metadata = {}

    # --- lista visible ------------------------------------------------
    def rebuild(self, keep_name: str | None = None) -> None:
        """Reordena recientes primero y conserva la selección por nombre."""
        current = keep_name
        if current is None and self.stations and 0 <= self.selected < len(self.stations):
            current = self.stations[self.selected][0]
        valid = {st[0] for st in self.all_stations}
        deduped: list[str] = []
        for name in self.recents:
            if name in valid and name not in deduped:
                deduped.append(name)
        self.recents = deduped[:MAX_RECENT]
        self.stations = ordered_stations(self.all_stations, self.recents)
        self.n_recents = len(self.recents)
        if current is not None:
            self.selected = next(
                (i for i, st in enumerate(self.stations) if st[0] == current), 0
            )
        if self.stations:
            self.selected = max(0, min(self.selected, len(self.stations) - 1))
        else:
            self.selected = 0

    # --- reproducción -------------------------------------------------
    def is_playing_index(self, index: int) -> bool:
        if not (0 <= index < len(self.stations)):
            return False
        name = self.stations[index][0]
        return bool(self.player.playing and self.player.current_name == name)

    def start(self, index: int) -> None:
        if not (0 <= index < len(self.stations)):
            return
        name, url, *_ = self.stations[index]
        self.selected = index
        self.player.play(name, url)
        add_recent(self.recents, name)
        self.rebuild(keep_name=name)
        self.fetcher.start(url, name)

    def stop(self) -> None:
        self.player.stop()
        self.fetcher.stop()
        self.clear_metadata()

    def toggle(self, index: int | None = None) -> None:
        idx = self.selected if index is None else index
        if not (0 <= idx < len(self.stations)):
            return
        if self.is_playing_index(idx):
            self.stop()
        else:
            self.start(idx)

    def toggle_mute(self) -> bool:
        return self.player.toggle_mute()

    def cycle_theme(self) -> str | None:
        """Rota al siguiente tema disponible y recarga la paleta."""
        names = available_themes()
        if len(names) <= 1:
            return None
        current = self.theme.get("_name", DEFAULT_THEME_NAME)
        try:
            index = names.index(current)
        except ValueError:
            index = -1
        name = names[(index + 1) % len(names)]
        mode = self.theme.get("_mode") or "dark"
        self.theme = load_theme(name, mode)
        self.pal = palette(self.theme)
        return self.theme.get("_name", name)

    def play_key(self, key: str) -> bool:
        """Teclas a-e (recientes) y 1-9 (catálogo). Devuelve True si la usó."""
        if len(key) != 1:
            return False
        ch = key.lower()
        if "a" <= ch <= "e":
            idx = ord(ch) - ord("a")
            if idx < self.n_recents:
                self.start(idx)
                return True
            return False
        if ch.isdigit():
            number = int(ch)
            if number >= 1:
                idx = self.n_recents + number - 1
                if idx < len(self.stations):
                    self.start(idx)
                    return True
        return False


def handle_key(state: AppState, key: str) -> None:
    if key in ("q", "Q", "ESC"):
        state.running = False
        return
    if not state.stations:
        return
    if key == "UP":
        state.selected = (state.selected - 1) % len(state.stations)
    elif key == "DOWN":
        state.selected = (state.selected + 1) % len(state.stations)
    elif key == "ENTER":
        state.toggle()
    elif key in ("SPACE", "m", "M"):
        state.toggle_mute()
    elif key in ("t", "T"):
        state.cycle_theme()
    elif key in ("RIGHT", "LEFT"):
        if state.player.playing:
            state.stop()
    elif state.play_key(key):
        return


def _print_deps(console: Console, problems: list[str]) -> None:
    console.print("[bold red]⚠  Faltan dependencias:[/]")
    for problem in problems:
        console.print(f"   [yellow]•[/] {problem}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="radio-agent", description="Radio TUI por consola")
    parser.add_argument("--version", action="version", version=f"radio-agent {__version__}")
    parser.add_argument("--theme", help="Nombre del tema OpenCode a usar")
    parser.add_argument("--mode", choices=["system", "dark", "light"], help="Modo del tema")
    parser.add_argument("--station", type=int, help="Índice (1-based) de estación a reproducir al iniciar")
    parser.add_argument("--list", action="store_true", help="Listar estaciones y salir")
    parser.add_argument("--check-deps", action="store_true", help="Verificar dependencias y salir")
    args = parser.parse_args(argv)

    console = Console()

    if args.list:
        try:
            for i, st in enumerate(STATIONS, 1):
                name, url = st[0], st[1]
                console.print(f"{i:2d}. {name}  {url}")
        except BrokenPipeError:
            # Ejemplo: `radio-agent --list | head`
            try:
                sys.stdout.close()
            except Exception:
                pass
        return 0

    problems = check_deps()
    if args.check_deps:
        if problems:
            _print_deps(console, problems)
            return 1
        console.print("[bold green]✓ Todas las dependencias OK[/]")
        return 0

    if args.station is not None and not (1 <= args.station <= len(STATIONS)):
        console.print(f"[red]Estación fuera de rango: {args.station} (1-{len(STATIONS)})[/]")
        return 2

    if not sys.stdin.isatty():
        console.print("[red]Este programa necesita una terminal interactiva (TTY).[/]")
        return 1

    if problems:
        _print_deps(console, problems)
        return 1

    try:
        import termios
        import tty
    except ImportError:
        console.print("[red]Este programa necesita una terminal POSIX (Linux/macOS).[/]")
        return 1

    state = AppState(STATIONS, theme_name=args.theme, theme_mode=args.mode)

    if args.station is not None:
        target = STATIONS[args.station - 1][0]
        index = next(
            (i for i, st in enumerate(state.stations) if st[0] == target), 0
        )
        state.start(index)

    fd = sys.stdin.fileno()
    old_attr = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        with Live(
            render(state, state.pal),
            console=console,
            screen=True,
            refresh_per_second=RENDER_FPS,
        ) as live:
            while state.running:
                key = read_key_nonblocking()
                if key:
                    handle_key(state, key)
                live.update(render(state, state.pal))
                time.sleep(1.0 / RENDER_FPS)
    except KeyboardInterrupt:
        pass
    finally:
        state.stop()
        termios.tcsetattr(fd, termios.TCSADRAIN, old_attr)

    console.print("[bold green]👋  ¡Hasta luego![/]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
