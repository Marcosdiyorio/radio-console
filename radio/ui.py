"""Render de la TUI con rich: lista de estaciones + VU meter de 7 bandas."""
from __future__ import annotations

import re
import shutil
import time

from rich.align import Align
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text

from .config import CHANNELS, MAX_VISIBLE, NUM_BANDS, SAMPLE_RATE, station_info
from .player import VU_FLOOR_DB
from . import __version__

BAND_LABELS = ["60", "190", "460", "1k", "2k", "4k", "11k"]
DB_MARKS = [0, -6, -12, -20, -30, -40, -60]
LABEL_WIDTH = max(len(label) for label in BAND_LABELS)
SLOT_MIN = LABEL_WIDTH + 1


def _bitrate(name: str) -> str:
    match = re.search(r"(\d+)\s*k", name, re.I)
    return f"{match.group(1)} kbps" if match else ""


def _blend_hex(a: str, b: str, t: float) -> str:
    ar, ag, ab = (int(a[i:i + 2], 16) for i in (1, 3, 5))
    br, bg, bb = (int(b[i:i + 2], 16) for i in (1, 3, 5))
    r = round(ar + (br - ar) * t)
    g = round(ag + (bg - ag) * t)
    blue = round(ab + (bb - ab) * t)
    return f"#{r:02x}{g:02x}{blue:02x}"


def _green_gradient(pal: dict, steps: int = 8) -> list[str]:
    anchors = [pal["dim_green"], pal["green"], pal["bright_green"]]
    out = []
    for i in range(steps):
        t = i / max(1, steps - 1)
        if t <= 0.5:
            out.append(_blend_hex(anchors[0], anchors[1], t / 0.5))
        else:
            out.append(_blend_hex(anchors[1], anchors[2], (t - 0.5) / 0.5))
    return out

def _clip(value: str, max_length: int) -> str:
    if max_length <= 1:
        return ""
    if len(value) <= max_length:
        return value
    return value[: max_length - 1] + "…"


def _vu_outer_width(width: int) -> int:
    """Ancho del panel VU: proporción 2/5, con mínimo para que quepan las etiquetas."""
    # Panel: 2 de borde + 2 de padding horizontal; 5 de eje + bandas.
    minimum = 4 + 5 + NUM_BANDS * SLOT_MIN
    return max(minimum, int(width * 2 / 5))


def _vu_geometry(width: int, height: int) -> tuple[int, int, int]:
    """Devuelve (filas, ancho de celda, separación entre bandas)."""
    inner = _vu_outer_width(width) - 4
    cell, gap = 1, SLOT_MIN - 1
    for candidate_cell in range(6, 0, -1):
        for candidate_gap in (2, 1):
            slot = candidate_cell + candidate_gap
            if slot < SLOT_MIN:
                continue
            if 5 + NUM_BANDS * slot <= inner:
                cell, gap = candidate_cell, candidate_gap
                break
        else:
            continue
        break
    rows = max(3, min(16, height - 14))
    return rows, cell, gap


def _db_rows(rows: int) -> dict[int, str]:
    """Fila (0 = abajo) → etiqueta de dB, ubicada según el valor real."""
    marks: dict[int, str] = {}
    for mark in DB_MARKS:
        fraction = (mark - VU_FLOOR_DB) / -VU_FLOOR_DB
        row = round(fraction * (rows - 1))
        marks.setdefault(row, str(mark))
    return marks


def _render_vu(player, pal: dict, rows: int, cell: int, gap: int) -> Text:
    levels = player.get_levels()
    bands = [max(0.0, min(1.0, value)) for value in levels.get("bands", [])]
    peaks = [max(0.0, min(1.0, value)) for value in levels.get("peak_bands", [])]
    bands = (bands + [0.0] * NUM_BANDS)[:NUM_BANDS]
    peaks = (peaks + [0.0] * NUM_BANDS)[:NUM_BANDS]

    gradient = _green_gradient(pal)
    steps = len(gradient)
    muted = pal["secondary"]
    text = Text()
    slot = cell + gap
    lead = (slot - cell) // 2
    trail = slot - cell - lead
    db_rows = _db_rows(rows)

    for row in range(rows - 1, -1, -1):
        fraction = (row + 0.5) / rows
        if row in db_rows:
            text.append(f"{db_rows[row]:>3s} │", style=muted)
        else:
            text.append(" " * 4 + "│", style=muted)
        bar_style = gradient[min(steps - 1, max(0, int(fraction * (steps - 1))))]
        for band in range(NUM_BANDS):
            text.append(" " * lead)
            if bands[band] >= fraction:
                text.append("█" * cell, style=bar_style)
            elif peaks[band] >= fraction:
                text.append("▒" * cell, style=pal["red"])
            else:
                text.append(" " * cell)
            text.append(" " * trail)
        text.append("\n")

    text.append("    ┴", style=muted)
    text.append("─" * (slot * NUM_BANDS), style=muted)
    text.append("\n")

    text.append("     ")
    for label in BAND_LABELS:
        text.append(f"{label:^{slot}s}", style=muted)

    return text


def _render_stations(state, pal: dict, visible: int) -> Text:
    stations = state.stations
    total = len(stations)
    if total == 0:
        return Text("Sin estaciones", style=pal["secondary"])

    visible = max(1, min(visible, total))
    selected = state.selected
    start = max(0, selected - visible // 2)
    start = min(start, max(0, total - visible))
    end = min(total, start + visible)

    recent_count = state.n_recents
    text = Text()
    for index in range(start, end):
        name, _url, genre, city = station_info(stations[index])
        is_selected = index == selected
        is_playing = state.is_playing_index(index)
        if index < recent_count:
            label = chr(ord("a") + index)
            label_style = pal["blue"]
        else:
            label = str(index - recent_count + 1)
            label_style = pal["secondary"]

        if index > start:
            text.append("\n")
        if is_selected:
            text.append("▸ ", style=f"bold {pal['bright_green']}")
        else:
            text.append("  ")
        if is_playing and index < recent_count:
            text.append("▶ ", style=f"bold {pal['bright_green']}")
        else:
            text.append("  ")
        text.append(f"{label}. ", style=label_style)
        name_style = pal["bright_green"] if is_selected else pal["green"]
        if is_playing:
            name_style = f"bold {pal['bright_green']}"
        text.append(name, style=name_style)
        if genre:
            text.append(f"  {genre}", style=pal["secondary"])
        if city:
            text.append(f" · {city}", style=pal["faint"])
    return text


def render(state, pal: dict, width: int | None = None, height: int | None = None) -> Layout:
    if width is None or height is None:
        size = shutil.get_terminal_size((100, 34))
        width = width or size.columns
        height = height or size.lines

    border = pal["border"]
    text_color = pal["primary"]
    muted = pal["secondary"]
    bright = pal["bright_green"]

    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="now", size=4),
        Layout(name="body", ratio=1),
        Layout(name="footer", size=3),
    )
    layout["body"].split_row(
        Layout(name="stations", ratio=3),
        Layout(name="vu", size=_vu_outer_width(width)),
    )

    if getattr(state, "show_help", False):
        help_text = Text()
        help_text.append("Ayuda rápida\n\n", style=f"bold {bright}")
        help_text.append("↑/↓ mover selección · Enter play/stop · Esp/m mute\n", style=text_color)
        help_text.append("t cambia de tema · l activa/desactiva enlace con OpenCode\n", style=text_color)
        help_text.append("a-e tocan recientes · 1-9 tocan estaciones del catálogo\n", style=text_color)
        help_text.append("←/→ detiene la reproducción · q/Esc salir\n\n", style=text_color)
        help_text.append("Para cargar nuevas emisoras: editá radio/stations.json\n", style=muted)
        help_text.append("(o RADIO_STATIONS_FILE / DEFAULT_STATIONS en radio/config.py)\n\n", style=muted)
        help_text.append(f"Versión: radio-agent {__version__}\n", style=muted)
        help_text.append("Creado con ❤ diyorio.com.ar", style=f"bold {bright}")
        layout["stations"].update(Panel(help_text, title="[bold]AYUDA (h para cerrar)[/]", border_style=border))
        layout["vu"].update(Panel("", border_style=border))

    theme_name = state.theme.get("_name", "")
    theme_mode = state.theme.get("_mode", "")
    link_state = "link on" if getattr(state, "link_opencode", False) else "link off"
    header = Text.assemble(
        ("♪  radio agent", f"bold {bright}"),
        ("   ·   console edition", muted),
        (f"   ·   {theme_name}/{theme_mode}", pal["faint"]),
        (f"   ·   {link_state}", pal["faint"]),
    )
    layout["header"].update(
        Panel(Align.center(header, vertical="middle"), border_style=border)
    )

    player = state.player
    metadata = state.get_metadata()

    now = Text()
    now.append("NOW PLAYING: ", style=f"bold {bright}")
    max_title = max(10, width - 4 - len("NOW PLAYING: "))
    max_status = max(10, width - 4)
    if player.playing and player.current_name:
        if metadata.get("artist") or metadata.get("track"):
            title = metadata.get("track", "")
            artist = metadata.get("artist", "")
            if artist and title:
                label = f"{artist} — {title}"
            else:
                label = title or player.current_name
            if player.current_name and player.current_name not in label:
                label = f"{label} - {player.current_name}"
        else:
            label = player.current_name
        now.append(_clip(label, max_title), style=text_color)
        now.append("\n")
        details = [
            _bitrate(player.current_name),
            "Stereo" if CHANNELS == 2 else "Mono",
            f"{SAMPLE_RATE / 1000:.1f} kHz",
        ]
        genre = metadata.get("genre", "")
        if genre:
            details.append(genre)
        muted = bool(getattr(player, "muted", False))
        dot = "●" if int(time.time() * 2) % 2 == 0 else "○"
        word = "MUTED" if muted else "PLAYING"
        status = f"STATUS: {dot} {word} · " + " · ".join(d for d in details if d)
        status_style = f"bold {pal['yellow']}" if muted else f"bold {pal['green']}"
        now.append(_clip(status, max_status), style=status_style)
    else:
        now.append("Detenido", style=muted)
        now.append("\nSTATUS: ○ STOPPED", style=muted)
    layout["now"].update(Panel(now, border_style=border))

    rows, cell, gap = _vu_geometry(width, height)
    if player.error:
        rows = max(3, rows - 1)
    vu = _render_vu(player, pal, rows, cell, gap)
    if player.error:
        vu_width = max(10, _vu_outer_width(width) - 4)
        vu.append(f"\n⚠  {_clip(player.error, vu_width - 3)}", style=f"bold {pal['red']}")
    vu_title = "[bold]VU · 7 bandas[/]"
    if getattr(player, "muted", False):
        vu_title += "  [yellow]MUTE[/]"
    layout["vu"].update(
        Panel(vu, title=vu_title, border_style=border)
    )

    body_height = max(4, height - 10 - 2)
    station_rows = max(3, min(MAX_VISIBLE, body_height - 2))
    if not getattr(state, "show_help", False):
        stations = _render_stations(state, pal, station_rows)
        total = len(state.stations)
        position = f"{state.selected + 1}/{total}" if total else "0/0"
        layout["stations"].update(
            Panel(
                stations,
                title=f"[bold]STATIONS[/]  [dim]{position}[/]",
                border_style=border,
            )
        )
    else:
        help_text = Text()
        help_text.append("Ayuda rápida\n\n", style=f"bold {bright}")
        help_text.append("↑/↓ mover selección · Enter play/stop · Esp/m mute\n", style=text_color)
        help_text.append("t cambia de tema · l activa/desactiva enlace con OpenCode\n", style=text_color)
        help_text.append("a-e tocan recientes · 1-9 tocan estaciones del catálogo\n", style=text_color)
        help_text.append("←/→ detiene la reproducción · q/Esc salir\n\n", style=text_color)
        help_text.append("Para cargar nuevas emisoras: editá radio/stations.json\n", style=muted)
        help_text.append("(o RADIO_STATIONS_FILE / DEFAULT_STATIONS en radio/config.py)\n\n", style=muted)
        help_text.append(f"Versión: radio-agent {__version__}\n", style=muted)
        help_text.append("Creado con ❤ diyorio.com.ar", style=f"bold {bright}")
        layout["stations"].update(Panel(help_text, title="[bold]AYUDA (h para cerrar)[/]", border_style=border))


    footer = Text.assemble(
        ("↑↓", f"bold {bright}"), (" mover  ", pal["green"]),
        ("Enter", f"bold {bright}"), (" play/stop  ", pal["green"]),
        ("Esp/m", f"bold {bright}"), (" mute  ", pal["green"]),
        ("t", f"bold {bright}"), (" tema  ", pal["green"]),
        ("l", f"bold {bright}"), (" link  ", pal["green"]),
        ("h", f"bold {bright}"), (" ayuda  ", pal["green"]),
        ("a-e", f"bold {bright}"), (" rec.  ", pal["green"]),
        ("q", f"bold {bright}"), (" salir", pal["green"]),
    )
    layout["footer"].update(
        Panel(Align.center(footer, vertical="middle"), border_style=border)
    )
    return layout
