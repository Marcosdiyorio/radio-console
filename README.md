# 🎙️ Radio Console (Radio Agent)

Terminal radio player: station list, recents with shortcuts, "now playing" metadata and a
7-band VU meter. Colors come from OpenCode themes.

<img width="981" height="437" alt="image" src="https://github.com/user-attachments/assets/2d6b1745-2cbd-41c4-93df-2118febbf3d1" />

---

## English

### Requirements
- Python 3.10+ and `rich>=13`
- `ffmpeg`
- An audio sink: `pw-cat` (PipeWire), `pacat` (PulseAudio), `aplay` (ALSA) or `ffplay`
- Terminal at least 80×24

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
# or, if installed
radio-agent
```

### Controls
| Key | Action |
|---|---|
| `↑` `↓` | Move selection (wraps around) |
| `Enter` | Play / stop selected station |
| `Space`, `m` | Mute / unmute |
| `t` | Rotate to the next available theme |
| `l` | Toggle linking with OpenCode (default off) |
| `h` | Show/hide help popup |
| `a`–`e` | Play recent 1–5 (letter shown in the list) |
| `1`–`9` | Play station N from the catalog |
| `←` `→` | Stop playback |
| `q`, `Esc` | Quit |

Mute does not cut the stream: it keeps reading and sends silence to the sink, so the
VU drops to zero and you resume at the same point when unmuting. Mute state persists
across stations. Recents are shown first with letters (`a`–`e`); below them the full
catalog keeps its `stations.json` order with fixed numbers `1`…`N`, so a number always
plays the same station. Playing a station makes it the most recent: it moves to `a`
and the cursor follows it there. The `▶` marks the playing station in the recents block;
the catalog row is shown in bold.

Metadata ("now playing") comes from ICY/SHOUTcast for direct streams and from ID3 tags
inside the segments for HLS (`.m3u8`) streams. If the metadata is missing or the
connection drops, it retries automatically while the station plays.

Stations can point to `.pls` or `.m3u` playlists: Radio resolves them to the real stream
URL before connecting (`.m3u8` HLS links are used as-is).

### CLI
```bash
./radio_agent.py --list             # list the catalog with URLs
./radio_agent.py --check-deps       # verify ffmpeg and the audio sink
./radio_agent.py --station 4        # start playing the 4th catalog station
./radio_agent.py --theme tokyonight # choose an OpenCode theme
./radio_agent.py --theme matrix --mode light
./radio_agent.py --version
```

### Themes
Searched in this order:
1. `~/.config/opencode/themes/<name>.json`
2. `./themes/<name>.json`
3. `./.opencode/themes/<name>.json`
4. Bundled `radio/themes/<name>.json` (`matrix`, `tokyonight`, `dracula`, `gruvbox`, `nord`)

Default name/mode are read from `~/.config/opencode/cli.json` (`theme.name`,
`theme.mode`). Override with `RADIO_THEME`, `RADIO_THEME_MODE`, `--theme` / `--mode`.
Inside the TUI, `t` rotates through every theme found (including ones you add to the
search folders), keeping the current `dark`/`light` mode. The selected theme is now
persisted between runs. `l` toggles linking with OpenCode (off by default), so by
default Radio keeps its own theme file.

### Stations and recents
The catalog lives in `radio/stations.json` (JSON: `name`, `url`, `genre`, `city`).
If the file is missing, the defaults from `radio/config.py` (`DEFAULT_STATIONS`) are
used. Override the path with `RADIO_STATIONS_FILE=/path/stations.json`.
You can also edit `radio/config.py` → `DEFAULT_STATIONS`.

The last five recents are stored in `~/.radio_agent_recent.json`. Override the path
with `RADIO_RECENT_FILE=/path/file.json`.

### Project layout
```
radio/
  app.py         state, keys and main loop
  config.py      stations, constants and recents
  stations.json  editable radio catalog
  deps.py        ffmpeg and audio sink detection
  input.py       non-blocking keyboard input
  metadata.py    ICY/SHOUTcast y ID3 (HLS) metadata, con reintentos
  playlist.py    resuelve playlists .pls/.m3u a la URL del stream
  player.py      ffmpeg -> PCM -> sink + levels/VU
  theme.py       OpenCode theme loader and resolver
  ui.py          rich TUI rendering
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
# o, si lo instalaste
radio-agent
```

### Controles
| Tecla | Acción |
|---|---|
| `↑` `↓` | Mover la selección (con vuelta al principio/final) |
| `Enter` | Reproducir / detener la estación seleccionada |
| `Espacio`, `m` | Silenciar / quitar el silencio (mute) |
| `t` | Rotar al siguiente tema disponible |
| `l` | Activar/desactivar enlace con OpenCode (por defecto desactivado) |
| `h` | Mostrar/ocultar ventana de ayuda |
| `a` – `e` | Reproducir el reciente 1–5 (letra que figura en la lista) |
| `1` – `9` | Reproducir la estación N del catálogo visible |
| `←` `→` | Detener la reproducción |
| `q`, `Esc` | Salir |

El mute no corta el stream: sigue sonando internamente en silencio y el VU baja a
cero, así al desmutear seguís en el mismo punto. El estado de mute se mantiene al
cambiar de estación. Los recientes se muestran primero con letras (`a`–`e`); debajo
queda el catálogo completo en el orden de `stations.json` con números fijos `1`…`N`,
así un número siempre reproduce la misma estación. Al reproducir una estación pasa a
ser el reciente más reciente: se mueve a `a` y el cursor la sigue. El `▶` marca la
emisora que suena en el bloque de recientes; en el catálogo aparece en negrita.

La metadata ("now playing") sale de ICY/SHOUTcast en streams directos y de tags ID3
dentro de los segmentos en streams HLS (`.m3u8`). Si falta o se corta la conexión,
reintenta automáticamente mientras la estación suena.

Las emisoras pueden apuntar a playlists `.pls` o `.m3u`: Radio las resuelve a la URL
real del stream antes de conectar (los enlaces HLS `.m3u8` se usan tal cual).

### CLI
```bash
./radio_agent.py --list             # listar el catálogo con sus URLs
./radio_agent.py --check-deps       # verificar ffmpeg y el sink de audio
./radio_agent.py --station 4        # arrancar reproduciendo la 4.ª del catálogo
./radio_agent.py --theme tokyonight # elegir tema OpenCode
./radio_agent.py --theme matrix --mode light
./radio_agent.py --version
```

### Temas
Se buscan en este orden:
1. `~/.config/opencode/themes/<nombre>.json`
2. `./themes/<nombre>.json`
3. `./.opencode/themes/<nombre>.json`
4. Tema empaquetado `radio/themes/<nombre>.json` (`matrix`, `tokyonight`, `dracula`, `gruvbox`, `nord`)

El nombre y el modo por defecto se leen de `~/.config/opencode/cli.json`
(`theme.name` y `theme.mode`). Se pueden pisar con las variables de entorno
`RADIO_THEME` y `RADIO_THEME_MODE`, o con `--theme` / `--mode`. Dentro de la TUI,
`t` rota por todos los temas encontrados (incluidos los que agregues en las
carpetas de búsqueda) manteniendo el modo `dark`/`light`. El tema seleccionado ahora
se persiste entre ejecuciones. `l` activa/desactiva el enlace con OpenCode (desactivado
por defecto), así por defecto Radio usa su propio archivo de tema.

### Estaciones y recientes
El catálogo está en `radio/stations.json` (formato JSON: `name`, `url`, `genre`,
`city`). Si el archivo no existe, se usan las estaciones por defecto de
`radio/config.py` (`DEFAULT_STATIONS`). Podés cambiar el archivo con
`RADIO_STATIONS_FILE=/ruta/stations.json`. También podés agregar estaciones en
`radio/config.py` → `DEFAULT_STATIONS`.

Los últimos cinco recientes se guardan en `~/.radio_agent_recent.json`.
Se puede cambiar la ruta con `RADIO_RECENT_FILE=/ruta/archivo.json`.

### Estructura
```
radio/
  app.py         estado, teclas y bucle principal
  config.py      estaciones, constantes y recientes
  stations.json  catálogo editable de radios
  deps.py        detección de ffmpeg y sink de audio
  input.py       lectura no bloqueante del teclado
  metadata.py    metadata ICY/SHOUTcast y ID3 (HLS), con reintentos
  playlist.py    resuelve playlists .pls/.m3u a la URL del stream
  player.py      pipeline ffmpeg → PCM → sink + niveles/VU
  theme.py       carga y resolución de temas OpenCode
  ui.py          render de la TUI con rich
  themes/        temas empaquetados
tests/           tests con unittest (compatibles con pytest)
```

### Tests
```bash
python3 -m unittest discover -s tests -t . -v
# opcional, si tenés pytest:
python3 -m pytest -q
```
No necesitan red, audio ni una TTY.
