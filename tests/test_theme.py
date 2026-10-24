import json
import tempfile
import unittest
from pathlib import Path

from radio.theme import available_themes, load_theme, palette, resolve_theme


class ThemeResolutionTests(unittest.TestCase):
    def test_resolve_refs(self):
        data = {
            "base": {
                "text": {"base": "$hue.neutral.100", "muted": "$hue.neutral.300"},
                "border": {"base": "$text.muted"},
            },
            "dark": {
                "hue": {
                    "gray": {"100": "#aaa", "300": "#bbb"},
                    "neutral": "$hue.gray",
                }
            },
        }
        resolved = resolve_theme(data, "dark")
        self.assertEqual(resolved["text"]["base"], "#aaa")
        self.assertEqual(resolved["text"]["muted"], "#bbb")
        self.assertEqual(resolved["border"]["base"], "#bbb")

    def test_alias_chain(self):
        data = {
            "dark": {
                "hue": {
                    "gray": {"100": "#111111"},
                    "neutral": "$hue.gray",
                    "muted": "$hue.neutral.100",
                }
            }
        }
        resolved = resolve_theme(data, "dark")
        self.assertEqual(resolved["hue"]["neutral"]["100"], "#111111")
        self.assertEqual(resolved["hue"]["muted"], "#111111")

    def test_light_mode(self):
        data = {
            "dark": {"text": {"base": "#000"}},
            "light": {"text": {"base": "#fff"}},
        }
        self.assertEqual(resolve_theme(data, "light")["text"]["base"], "#fff")

    def test_system_uses_dark(self):
        data = {
            "dark": {"text": {"base": "#000"}},
            "light": {"text": {"base": "#fff"}},
        }
        self.assertEqual(resolve_theme(data, "system")["text"]["base"], "#000")

    def test_json_roundtrip_theme_file(self):
        data = {
            "base": {"text": {"base": "$hue.green.300"}},
            "dark": {"hue": {"green": {"300": "#abcdef"}}},
        }
        with tempfile.TemporaryDirectory() as tmp:
            themes = Path(tmp) / "themes"
            themes.mkdir()
            (themes / "custom.json").write_text(json.dumps(data))
            resolved = load_theme("custom", "dark", project_dir=Path(tmp))
        self.assertEqual(resolved["text"]["base"], "#abcdef")
        self.assertEqual(resolved["_name"], "custom")


class LoadThemeTests(unittest.TestCase):
    def test_load_default(self):
        theme = load_theme("matrix", "dark")
        colors = palette(theme)
        for key in ("primary", "green", "bg"):
            self.assertTrue(colors[key].startswith("#"))

    def test_all_bundled_themes_have_palette(self):
        for name in ("matrix", "tokyonight", "dracula", "gruvbox", "nord"):
            for mode in ("dark", "light"):
                theme = load_theme(name, mode)
                self.assertEqual(theme["_name"], name)
                colors = palette(theme)
                for key in ("primary", "green", "border", "bg", "red", "yellow"):
                    self.assertRegex(colors[key], r"^#[0-9a-fA-F]{6}$")

    def test_available_themes_scans_project_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            themes = Path(tmp) / "themes"
            themes.mkdir()
            (themes / "custom.json").write_text("{}")
            names = available_themes(Path(tmp))
        self.assertIn("custom", names)
        self.assertIn("matrix", names)

    def test_available_themes_is_sorted(self):
        names = available_themes()
        self.assertEqual(names, sorted(names, key=str.lower))

    def test_fallback_missing(self):
        theme = load_theme("no-such-theme-xyz", "dark")
        colors = palette(theme)
        self.assertTrue(colors["primary"].startswith("#"))
        self.assertEqual(theme["_name"], "matrix")

    def test_light_palette(self):
        colors = palette(load_theme("matrix", "light"))
        self.assertTrue(colors["primary"].startswith("#"))


if __name__ == "__main__":
    unittest.main()
