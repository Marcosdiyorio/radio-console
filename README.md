# 🎙️ Radio Console (Radio Agent)

A small terminal radio for working or studying with music in the background.
One command, a few tens of megabytes of RAM and about a fifth of one CPU core, no browser
and no Electron: it stays out of your way while your streams play, and it still shows what
is on air, a 7-band meter and a theme that matches your terminal.

> Una radio de consola liviana para trabajar o estudiar con música de fondo.
> Un solo comando, pocos recursos (unas decenas de MB de RAM y alrededor de un quinto de un núcleo), sin navegador: queda tranquila de fondo y te muestra
> qué suena, un VU de 7 bandas y un tema que combina con tu terminal.
<img width="858" height="439" alt="image" src="https://github.com/user-attachments/assets/62b4e266-c34c-4afd-ad69-9b91e2b15653" />

---

## English

### Why
- **Low footprint:** one Python process, `ffmpeg` decoding and your audio sink. The
  meter and the screen are throttled (12 fps) and the spectrum is computed with a
  small pure-Python FFT, so it is meant to run in the background next to your editor.
- **Focus-friendly:** no ads, no feeds, no notifications. Keys do one thing, the
  screen shows what matters and the help popup (`h`) is one key away.
- **Your catalog:** a plain JSON file with your stations, plus a recents block so the
  ones you use are always one letter away.

### Features
- Station list with **recents on top** (`a`–`e`) and the full catalog below with
  **fixed numbers** (`1`…`N`) that never move.
- **Now playing**: track and artist from ICY/SHOUTcast for direct streams and from ID3
  tags inside the segments for HLS (`.m3u8`) streams. Metadata retries on its own while
  the station plays.
- **Playlists**: stations pointing to `.pls` or `.m3u` files are resolved to the real
  stream before connecting.
- **7-band VU meter** in dBFS (−60 … 0 dB) with frequency labels
  (`60 190 460 1k 2k 4k 11k`), peak hold, and a gray gradient while muted.
- **Volume** from the keyboard (5 % steps), saved between runs and shown in the status
  line.
- **Mute** that keeps the stream running, so you resume at the same point.
- **Themes** from OpenCode (`~/.config/opencode/themes`) or bundled ones
  (`matrix`, `tokyonight`, `dracula`, `gruvbox`, `nord`), in dark or light mode. The
  choice is remembered.
- **Optional link with OpenCode** (`l`): off by default, so Radio keeps its own theme;
  turn it on to read and write OpenCode's `cli.json`.
- Help popup (`h`) that does not stop the music.

### Requirements
- Python 3.10+ and `rich>=13`
- `ffmpeg`
- An audio sink: `pw-cat` (PipeWire), `pacat` (PulseAudio), `aplay` (ALSA) or `ffplay`
- A terminal of at least 80×24

```bash
# Debian/Ubuntu
sudo apt install ffmpeg pipewire-bin        # PipeWire
# or
sudo apt install ffmpeg pulseaudio-utils    # PulseAudio
# or
sudo apt install ffmpeg alsa-utils          # ALSA
pip install -r requirements.txt
```

### Run
```bash
./radio_agent.py
# or
python3 -m radio
# or, after `pip install .`
radio-agent
```

### Controls
| Key | Action |
|---|---|
| `↑` `↓` | Move the selection (wraps around) |
| `Enter` | Play / stop the selected station |
| `Space`, `m` | Mute / unmute (the meter keeps moving in gray) |
| `←` `→` or `+` `-` (or `=`) | Volume down / up, 5 % steps, saved between runs |
| `a`–`e` | Play recent 1–5 |
| `1`–`9` | Play station N from the catalog (fixed numbers) |
| `t` | Next theme (keeps dark/light mode) |
| `l` | Toggle the link with OpenCode (default: off) |
| `h` | Show / hide the help popup |
| `q`, `Esc` | Quit |

Playing a station makes it the most recent: it moves to `a` and the cursor follows it.
The `▶` marks the station on air in the recents block; the catalog row is shown in bold.
Mute does not cut the stream: it keeps reading and sends silence to the sink, so you
resume at the same point when unmuting. Mute state persists across stations.

### CLI
```bash
./radio_agent.py --list             # list the catalog with URLs
./radio_agent.py --check-deps       # verify ffmpeg and the audio sink
./radio_agent.py --station 4        # start playing the 4th catalog station
./radio_agent.py --theme tokyonight # choose a theme (remembered)
./radio_agent.py --theme matrix --mode light
./radio_agent.py --version
```

### Stations
The catalog lives in `radio/stations.json` (a JSON list of `name`, `url`, `genre`,
`city`; the list form `[name, url, genre, city]` also works). Radio looks for the first
valid file in this order:
1. `RADIO_STATIONS_FILE=/path/stations.json`
2. `./stations.json` in the folder you run it from
3. `~/.config/radio-agent/stations.json`
4. `radio/stations.json` (bundled)

If none is valid, the defaults in `radio/config.py` (`DEFAULT_STATIONS`) are used.
**To add a station**, add an entry to the JSON and restart Radio: it shows up at the
end of the catalog with the next free number.

Metadata depends on the stream, not on the station entry: if the stream sends ICY
titles or ID3 tags inside its segments, they appear while it plays. Some HLS streams
(for example those with `.m4s` segments and no ID3) never send track info.

### Themes and OpenCode
Themes are searched in this order:
1. `~/.config/opencode/themes/<name>.json`
2. `./themes/<name>.json`
3. `./.opencode/themes/<name>.json`
4. Bundled `radio/themes/<name>.json`

Theme and mode are chosen in this order: `--theme`/`--mode`, then `RADIO_THEME` /
`RADIO_THEME_MODE`, then the last choice saved by Radio, then `matrix` / `dark`.
Pressing `t` in the TUI saves the new theme in `~/.radio_agent_theme.json`.

The header shows `link on` or `link off`:
- **off (default):** Radio reads and writes only its own theme file. OpenCode's settings
  are never touched.
- **on:** the theme is read from and saved to OpenCode's `~/.config/opencode/cli.json`
  (`theme.name`, `theme.mode`).

### Files and environment variables
| File | Content | Override |
|---|---|---|
| `~/.radio_agent_recent.json` | last five stations played | `RADIO_RECENT_FILE` |
| `~/.radio_agent_volume.json` | volume (0–100) | `RADIO_VOLUME_FILE` |
| `~/.radio_agent_theme.json` | theme and mode chosen in Radio | `RADIO_THEME_FILE` |
| `~/.radio_agent_link.json` | link with OpenCode on/off | `RADIO_LINK_FILE` |
| `~/.config/opencode/cli.json` | OpenCode theme (only with link on) | `RADIO_OPENCODE_THEME_FILE` |

Also: `RADIO_THEME`, `RADIO_THEME_MODE`, `RADIO_STATIONS_FILE`.

### Performance notes
- Only one Python thread does the audio analysis (RMS and a 1024-point spectrum); ffmpeg
  does the decoding in native code.
- The screen redraws 12 times per second.
- Measured on the development machine: about 20 % of one core while a station plays.
  Numbers depend on your hardware and stream bitrate.

### Project layout
```
radio/
  app.py         state, keys and main loop
  config.py      stations, constants, recents, volume and link preferences
  stations.json  editable radio catalog
  deps.py        ffmpeg and audio sink detection
  input.py       non-blocking keyboard input
  metadata.py    ICY/SHOUTcast and ID3 (HLS) metadata, with retries
  playlist.py    resolves .pls/.m3u playlists to stream URLs
  player.py      ffmpeg -> PCM -> volume -> sink, levels and the 7-band spectrum
  theme.py       OpenCode theme loader and resolver
  ui.py          rich TUI rendering (station list, now playing, VU, help)
  themes/        bundled themes
tests/           unittest tests (pytest-compatible)
```

### Tests
```bash
python3 -m unittest discover -s tests -t . -v
# optional, if you have pytest:
python3 -m pytest -q
```
No network, audio or TTY required.

---

## Español

### Para qué sirve
- **Pocos recursos:** un proceso de Python, `ffmpeg` decodificando y tu sink de audio.
  La pantalla se redibuja 12 veces por segundo y el espectro usa una FFT pequeña en
  Python puro, pensada para correr de fondo al lado de tu editor.
- **Pensada para concentrarse:** sin publicidad, sin feeds ni notificaciones. Cada tecla
  hace una sola cosa, la pantalla muestra lo importante y la ayuda (`h`) está a una tecla.
- **Tu catálogo:** un JSON simple con tus emisoras y un bloque de recientes para tener
  a mano las que más usás.

### Qué hace
- Lista de emisoras con **recientes arriba** (`a`–`e`) y el catálogo completo debajo con
  **números fijos** (`1`…`N`) que nunca se mueven.
- **Ahora suena:** título y artista desde ICY/SHOUTcast en streams directos y desde tags
  ID3 dentro de los segmentos en streams HLS (`.m3u8`). La metadata reintenta sola
  mientras la emisora suena.
- **Playlists:** las emisoras que apuntan a archivos `.pls` o `.m3u` se resuelven a la
  URL real del stream antes de conectar.
- **VU de 7 bandas** en dBFS (−60 … 0 dB) con etiquetas de frecuencia
  (`60 190 460 1k 2k 4k 11k`), retención de picos y degradé gris al mutear.
- **Volumen** desde el teclado (pasos de 5 %), guardado entre ejecuciones y visible en la
  línea de estado.
- **Mute** que no corta el stream: al desmutear seguís en el mismo punto.
- **Temas** de OpenCode (`~/.config/opencode/themes`) o los incluidos (`matrix`,
  `tokyonight`, `dracula`, `gruvbox`, `nord`), en modo oscuro o claro. La elección se
  recuerda.
- **Enlace opcional con OpenCode** (`l`): desactivado por defecto, así Radio usa su propio
  tema; activalo para leer y escribir el `cli.json` de OpenCode.
- Ventana de ayuda (`h`) que no detiene la música.

### Requisitos
- Python 3.10+ y `rich>=13`
- `ffmpeg`
- Un sink de audio: `pw-cat` (PipeWire), `pacat` (PulseAudio), `aplay` (ALSA) o `ffplay`
- Terminal de al menos 80×24

```bash
# Debian/Ubuntu
sudo apt install ffmpeg pipewire-bin        # PipeWire
# o
sudo apt install ffmpeg pulseaudio-utils    # PulseAudio
# o
sudo apt install ffmpeg alsa-utils          # ALSA
pip install -r requirements.txt
```

### Ejecutar
```bash
./radio_agent.py
# o
python3 -m radio
# o, tras `pip install .`
radio-agent
```

### Controles
| Tecla | Acción |
|---|---|
| `↑` `↓` | Mover la selección (con vuelta al principio/final) |
| `Enter` | Reproducir / detener la emisora seleccionada |
| `Espacio`, `m` | Silenciar / quitar el silencio (la VU sigue moviéndose en gris) |
| `←` `→` o `+` `-` (o `=`) | Bajar / subir el volumen, pasos de 5 %, se guarda entre ejecuciones |
| `a` – `e` | Reproducir el reciente 1–5 |
| `1` – `9` | Reproducir la emisora N del catálogo (números fijos) |
| `t` | Siguiente tema (mantiene el modo oscuro/claro) |
| `l` | Activar / desactivar el enlace con OpenCode (por defecto: desactivado) |
| `h` | Mostrar / ocultar la ventana de ayuda |
| `q`, `Esc` | Salir |

Al reproducir una emisora, pasa a ser la más reciente: se mueve a `a` y el cursor la sigue.
El `▶` marca la emisora que suena en el bloque de recientes; en el catálogo aparece en
negrita. El mute no corta el stream: sigue leyéndolo y manda silencio al sink, así que al
desmutear seguís en el mismo punto. El estado de mute se mantiene al cambiar de emisora.

### CLI
```bash
./radio_agent.py --list             # listar el catálogo con sus URLs
./radio_agent.py --check-deps       # verificar ffmpeg y el sink de audio
./radio_agent.py --station 4        # arrancar reproduciendo la 4.ª del catálogo
./radio_agent.py --theme tokyonight # elegir un tema (queda recordado)
./radio_agent.py --theme matrix --mode light
./radio_agent.py --version
```

### Emisoras
El catálogo está en `radio/stations.json` (lista JSON con `name`, `url`, `genre`, `city`;
también sirve la forma `[nombre, url, género, ciudad]`). Radio busca el primer archivo
válido en este orden:
1. `RADIO_STATIONS_FILE=/ruta/stations.json`
2. `./stations.json` en la carpeta desde la que lo ejecutás
3. `~/.config/radio-agent/stations.json`
4. `radio/stations.json` (incluido)

Si ninguno es válido, se usan las emisoras por defecto de `radio/config.py`
(`DEFAULT_STATIONS`). **Para agregar una emisora**, sumá una entrada al JSON y reiniciá
Radio: aparece al final del catálogo con el siguiente número libre.

La metadata depende del stream, no de la entrada de la emisora: si el stream manda
títulos ICY o tags ID3 dentro de sus segmentos, se muestran mientras suena. Algunos
streams HLS (por ejemplo los que usan segmentos `.m4s` sin ID3) nunca envían el tema.

### Temas y OpenCode
Los temas se buscan en este orden:
1. `~/.config/opencode/themes/<nombre>.json`
2. `./themes/<nombre>.json`
3. `./.opencode/themes/<nombre>.json`
4. `radio/themes/<nombre>.json` (incluidos)

Tema y modo se eligen en este orden: `--theme`/`--mode`, luego `RADIO_THEME` /
`RADIO_THEME_MODE`, luego la última elección guardada por Radio, y por último `matrix` /
`dark`. Al pulsar `t` en la TUI, el nuevo tema se guarda en `~/.radio_agent_theme.json`.

El encabezado muestra `link on` o `link off`:
- **off (por defecto):** Radio lee y escribe solo su propio archivo de tema. La
  configuración de OpenCode no se toca.
- **on:** el tema se lee y se guarda en `~/.config/opencode/cli.json` de OpenCode
  (`theme.name`, `theme.mode`).

### Archivos y variables de entorno
| Archivo | Contenido | Cambiarlo con |
|---|---|---|
| `~/.radio_agent_recent.json` | las últimas cinco emisoras reproducidas | `RADIO_RECENT_FILE` |
| `~/.radio_agent_volume.json` | volumen (0–100) | `RADIO_VOLUME_FILE` |
| `~/.radio_agent_theme.json` | tema y modo elegidos en Radio | `RADIO_THEME_FILE` |
| `~/.radio_agent_link.json` | enlace con OpenCode activado/desactivado | `RADIO_LINK_FILE` |
| `~/.config/opencode/cli.json` | tema de OpenCode (solo con el enlace activado) | `RADIO_OPENCODE_THEME_FILE` |

Además: `RADIO_THEME`, `RADIO_THEME_MODE` y `RADIO_STATIONS_FILE`.

### Notas de rendimiento
- Un solo hilo de Python hace el análisis de audio (RMS y un espectro de 1024 puntos);
  ffmpeg hace la decodificación en código nativo.
- La pantalla se redibuja 12 veces por segundo.
- Medido en el equipo de desarrollo: unos 20 % de un núcleo mientras suena una emisora.
  Depende de tu hardware y del bitrate del stream.

### Estructura
```
radio/
  app.py         estado, teclas y bucle principal
  config.py      emisoras, constantes, recientes, volumen y preferencia de enlace
  stations.json  catálogo editable de radios
  deps.py        detección de ffmpeg y sink de audio
  input.py       lectura no bloqueante del teclado
  metadata.py    metadata ICY/SHOUTcast e ID3 (HLS), con reintentos
  playlist.py    resuelve playlists .pls/.m3u a URLs de stream
  player.py      ffmpeg → PCM → volumen → sink, niveles y espectro de 7 bandas
  theme.py       carga y resolución de temas OpenCode
  ui.py          render de la TUI con rich (lista, ahora suena, VU, ayuda)
  themes/        temas incluidos
tests/           tests con unittest (compatibles con pytest)
```

### Tests
```bash
python3 -m unittest discover -s tests -t . -v
# opcional, si tenés pytest:
python3 -m pytest -q
```
No necesitan red, audio ni una TTY.
