"""Cargador y resolvedor de temas OpenCode (JSON)."""
from __future__ import annotations

import json
import sys
import os
from . import config as _config
from pathlib import Path
from typing import Any

DEFAULT_THEME_NAME = "matrix"

THEME_FILE = _config.THEME_FILE


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def _deep_equal(a: Any, b: Any) -> bool:
    try:
        return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    except Exception:
        return a == b


def _lookup(path: list[str], root: dict) -> Any:
    current: Any = root
    for part in path:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def _resolve_hues(hues: dict) -> dict:
    """Resuelve aliases tipo 'neutral': '$hue.gray' dentro de la escala."""
    resolved = dict(hues)
    for _ in range(20):
        changed = False
        for key, value in list(resolved.items()):
            if not (isinstance(value, str) and value.startswith("$hue.")):
                continue
            parts = value[1:].split(".")
            if len(parts) < 2:
                continue
            target_name = parts[1]
            if target_name == key:
                continue
            target = _lookup([target_name, *parts[2:]], resolved)
            if target is not None and not _deep_equal(resolved[key], target):
                resolved[key] = target
                changed = True
        if not changed:
            break
    return resolved


def _resolve_value(value: Any, ctx: dict) -> Any:
    if isinstance(value, str):
        if not value.startswith("$"):
            return value
        resolved = _lookup(value[1:].split("."), ctx)
        if resolved is None:
            return value
        return dict(resolved) if isinstance(resolved, dict) else resolved
    if isinstance(value, dict):
        return {key: _resolve_value(item, ctx) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_value(item, ctx) for item in value]
    return value


def resolve_theme(theme_data: dict, mode: str = "dark") -> dict:
    mode_key = "dark" if mode in (None, "", "system") else mode
    base = theme_data.get("base", {}) or {}
    mode_data = theme_data.get(mode_key, {}) or {}
    if not mode_data:
        mode_data = theme_data.get("dark", {}) or {}
    merged = _deep_merge(base, mode_data)

    merged["hue"] = _resolve_hues(merged.get("hue", {}) or {})

    current = merged
    for _ in range(20):
        nxt = _resolve_value(current, current)
        if _deep_equal(nxt, current):
            break
        current = nxt
    return current


def _theme_dirs(project_dir: Path | None = None) -> list[Path]:
    dirs = [Path.home() / ".config" / "opencode" / "themes"]
    if project_dir:
        dirs += [
            project_dir / "themes",
            project_dir / ".opencode" / "themes",
        ]
    cwd = Path.cwd()
    dirs += [
        cwd / "themes",
        cwd / ".opencode" / "themes",
        Path(__file__).resolve().parent / "themes",
    ]
    return dirs


def _find_theme_file(name: str, project_dir: Path | None = None) -> Path | None:
    for directory in _theme_dirs(project_dir):
        candidate = directory / f"{name}.json"
        if candidate.is_file():
            return candidate
    return None


def available_themes(project_dir: Path | None = None) -> list[str]:
    """Nombres de temas disponibles en las carpetas de búsqueda."""
    names = {DEFAULT_THEME_NAME}
    for directory in _theme_dirs(project_dir):
        try:
            for entry in directory.iterdir():
                if entry.is_file() and entry.suffix.lower() == ".json":
                    names.add(entry.stem)
        except OSError:
            continue
    return sorted(names, key=str.lower)


def _read_radio_theme() -> tuple[str, str]:
    name = DEFAULT_THEME_NAME
    mode = "dark"
    try:
        n, m = _config.load_theme_selection()
        if n:
            name = n
        if m:
            mode = m
    except Exception:
        pass
    name = os.environ.get("RADIO_THEME", name)
    mode = os.environ.get("RADIO_THEME_MODE", mode)
    return name, mode


def _read_opencode_theme() -> tuple[str, str]:
    name = DEFAULT_THEME_NAME
    mode = "dark"
    try:
        path = _config.OPENCODE_THEME_FILE
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            theme = data.get("theme", {})
            if isinstance(theme, str):
                name = theme
            elif isinstance(theme, dict):
                name = theme.get("name") or name
                mode = theme.get("mode") or mode
    except Exception:
        pass
    name = os.environ.get("RADIO_THEME", name)
    mode = os.environ.get("RADIO_THEME_MODE", mode)
    return name, mode


def _read_cli_theme(link_opencode: bool = False) -> tuple[str, str]:
    if link_opencode:
        return _read_opencode_theme()
    return _read_radio_theme()


def load_theme(
    name: str | None = None,
    mode: str | None = None,
    project_dir: Path | None = None,
    link_opencode: bool = False,
) -> dict:
    if name is None or mode is None:
        cli_name, cli_mode = _read_cli_theme(link_opencode)
        name = name or cli_name
        mode = mode or cli_mode

    path = _find_theme_file(name, project_dir)
    if path is None:
        name = DEFAULT_THEME_NAME
        path = _find_theme_file(name, project_dir)

    data: dict = {}
    used_name = name
    if path is not None:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    if not data:
        data = _embedded_default()
        used_name = "embedded"

    resolved = resolve_theme(data, mode)
    resolved["_name"] = used_name
    resolved["_mode"] = mode
    return resolved


def _embedded_default() -> dict:
    return {
        "$schema": "https://opencode.ai/theme.json",
        "base": {
            "text": {
                "base": "#e6edf3",
                "muted": "#7d8590",
                "faint": "#484f58",
                "feedback": {
                    "error": {"base": "#f85149"},
                    "success": {"base": "#39d353"},
                    "warning": {"base": "#e3b341"},
                },
            },
            "background": {"base": "#0b1507", "raised": {"base": "#111d0d", "high": "#1a2a14"}},
            "border": {"base": "#1f6f2c"},
        },
        "dark": {
            "hue": {
                "gray": {
                    "100": "#f0f6fc", "200": "#c9d1d9", "300": "#8b949e",
                    "400": "#6e7681", "500": "#484f58", "600": "#30363d",
                    "700": "#21262d", "800": "#161b22", "900": "#0d1117",
                },
                "green": {
                    "100": "#7ee787", "200": "#56d364", "300": "#3fb950",
                    "400": "#2ea043", "500": "#238636", "600": "#1a7f37",
                    "700": "#116329", "800": "#0d4429", "900": "#033a16",
                },
                "red": {
                    "100": "#ffa198", "200": "#ff7b72", "300": "#f85149",
                    "400": "#da3633", "500": "#b62324", "600": "#8e1519",
                    "700": "#67060c", "800": "#490206", "900": "#2d0004",
                },
                "yellow": {
                    "100": "#f8e3a1", "200": "#e3b341", "300": "#bb8009",
                    "400": "#9e6a03", "500": "#8a6d3b", "600": "#6d5a1e",
                    "700": "#5a4a1a", "800": "#3d3312", "900": "#261f08",
                },
                "blue": {
                    "100": "#a5d6ff", "200": "#79c0ff", "300": "#58a6ff",
                    "400": "#388bfd", "500": "#1f6feb", "600": "#1158c7",
                    "700": "#0d419d", "800": "#0a3069", "900": "#051d4d",
                },
                "purple": {
                    "100": "#d2a8ff", "200": "#bc8cff", "300": "#a371f7",
                    "400": "#8957e5", "500": "#6e40c9", "600": "#553098",
                    "700": "#3c1e70", "800": "#271052", "900": "#1b0a3c",
                },
                "accent": "$hue.green",
                "interactive": "$hue.green",
                "neutral": "$hue.gray",
            },
            "text": {
                "base": "$hue.neutral.100",
                "muted": "$hue.neutral.300",
                "faint": "$hue.neutral.500",
            },
            "background": {
                "base": "$hue.neutral.900",
                "raised": {"base": "$hue.neutral.800", "high": "$hue.neutral.700"},
            },
            "border": {"base": "$hue.neutral.600"},
        },
    }


def color(theme: dict, *path: str, default: str = "#39d353") -> str:
    value = _lookup(list(path), theme)
    return value if isinstance(value, str) else default


def palette(theme: dict) -> dict:
    """Extrae un dict de colores listo para la UI."""
    return {
        "primary": color(theme, "text", "base", default="#e6edf3"),
        "secondary": color(theme, "text", "muted", default="#7d8590"),
        "faint": color(theme, "text", "faint", default="#484f58"),
        "error": color(theme, "text", "feedback", "error", "base", default="#f85149"),
        "success": color(theme, "text", "feedback", "success", "base", default="#39d353"),
        "warning": color(theme, "text", "feedback", "warning", "base", default="#e3b341"),
        "border": color(theme, "border", "base", default="#1f6f2c"),
        "bg": color(theme, "background", "base", default="#0b1507"),
        "raised": color(theme, "background", "raised", "base", default="#111d0d"),
        "green": color(theme, "hue", "green", "400", default="#39d353"),
        "bright_green": color(theme, "hue", "green", "200", default="#7ee787"),
        "dim_green": color(theme, "hue", "green", "800", default="#116329"),
        "yellow": color(theme, "hue", "yellow", "300", default="#e3b341"),
        "red": color(theme, "hue", "red", "300", default="#f85149"),
        "blue": color(theme, "hue", "blue", "300", default="#58a6ff"),
        "purple": color(theme, "hue", "purple", "300", default="#a371f7"),
    }


def _atomic_write_json_path(path, data):
    import tempfile
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = __import__("json").dumps(data, ensure_ascii=False, indent=2)
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".radio-theme-")
        try:
            with open(fd, "w", encoding="utf-8") as fh:
                fh.write(payload)
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
    except Exception:
        pass


def save_theme(name: str, mode: str | None = None, link_opencode: bool = False, *args, **kwargs) -> None:
    if mode is None:
        mode = "dark"
    data = {"theme": {"name": name, "mode": mode}, "name": name, "mode": mode}
    try:
        if link_opencode:
            path = _config.OPENCODE_THEME_FILE
            _atomic_write_json_path(path, data)
            # mantén también opencode cli.json
        else:
            path = sys.modules[__name__].THEME_FILE
            _atomic_write_json_path(path, data)
    except Exception:
        pass
    try:
        _config.save_theme(name, mode)
    except Exception:
        pass
    if link_opencode:
        try:
            _config.save_theme(name, mode)  # radio file too
        except Exception:
            pass


save_theme_selection = save_theme
persist_theme = save_theme
write_theme = save_theme
save_selected_theme = save_theme
