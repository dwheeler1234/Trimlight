"""Controller-independent custom pattern draft and validation."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field


def bounded_int(value, low: int, high: int, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= value <= high or int(value) != value:
        raise ValueError(f"{label} must be a whole number between {low} and {high}")
    return int(value)


def blank_pixels() -> list[dict]:
    return [{"index": i, "count": 1 if i == 0 else 0, "color": 0xFFFFFF, "disable": False} for i in range(30)]


@dataclass
class PatternDraft:
    name: str = "New Pattern"
    mode: int = 0
    speed: int = 100
    brightness: int = 200
    pixels: list[dict] = field(default_factory=blank_pixels)
    selected_index: int = 0
    last_saved_id: int | None = None
    source_id: int | None = None

    @property
    def selected_pixel(self) -> dict:
        return self.pixels[self.selected_index]

    def set_name(self, name: str) -> None:
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 64:
            raise ValueError("Pattern name must contain 1 to 64 characters")
        self.name = name.strip()

    def set_number(self, key: str, value) -> None:
        limits = {"selected_index": (0, 29), "count": (0, 60), "speed": (0, 255), "brightness": (0, 255), "mode": (0, 16)}
        if key not in limits:
            raise ValueError("Unknown pattern field")
        value = bounded_int(value, *limits[key], key)
        if key == "count":
            self.selected_pixel[key] = value
        else:
            setattr(self, key, value)

    def set_rgb(self, rgb) -> None:
        if not isinstance(rgb, (list, tuple)) or len(rgb) != 3:
            raise ValueError("Color must contain red, green and blue values")
        r, g, b = [bounded_int(v, 0, 255, "Color channel") for v in rgb]
        self.selected_pixel["color"] = (r << 16) | (g << 8) | b

    @classmethod
    def from_effect(cls, effect: dict) -> PatternDraft:
        if effect.get("category") not in (1, 2):
            raise ValueError("Select a custom preset before loading a pattern")
        draft = cls()
        source_id = effect.get("id")
        if isinstance(source_id, int) and not isinstance(source_id, bool) and source_id >= 0:
            draft.source_id = source_id
        draft.set_name(effect.get("name") or "Pattern Copy")
        for key in ("mode", "speed", "brightness"):
            draft.set_number(key, effect.get(key, getattr(draft, key)))
        pixels = effect.get("pixels")
        if not isinstance(pixels, list) or not pixels or len(pixels) > 30:
            raise ValueError("The controller must report 1 to 30 pattern entries")
        draft.pixels = [{"index": i, "count": 0, "color": 0, "disable": False} for i in range(30)]
        used = set()
        for pixel in pixels:
            if not isinstance(pixel, dict):
                raise ValueError("Invalid pattern entry")
            index = bounded_int(pixel.get("index"), 0, 29, "Entry index")
            if index in used:
                raise ValueError("Pattern entry indexes must be unique")
            used.add(index)
            count = bounded_int(pixel.get("count"), 0, 60, "Pixel count")
            color = bounded_int(pixel.get("color"), 0, 0xFFFFFF, "Color")
            disabled = pixel.get("disable", False)
            if not isinstance(disabled, bool):
                raise ValueError("Disabled must be true or false")
            draft.pixels[index] = {"index": index, "count": count, "color": color, "disable": disabled}
        return draft

    def effect(self) -> dict:
        """A new ID is mandatory: editing never overwrites a saved effect."""
        self.set_name(self.name)
        if not any(p["count"] > 0 and not p["disable"] for p in self.pixels):
            raise ValueError("Enable at least one entry with a nonzero pixel count")
        return {"id": -1, "name": self.name, "category": 2, "mode": self.mode,
                "speed": self.speed, "brightness": self.brightness, "pixels": deepcopy(self.pixels)}
