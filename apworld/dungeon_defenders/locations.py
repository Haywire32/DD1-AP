"""Campaign wave/victory locations and stable prototype IDs."""

from .dd1_protocol import (
    CAMPAIGN_MAPS, DIFFICULTY_INDEX, START_WAVES, PROTOTYPE_LOCATION_ID_BASE,
)


DIFFICULTIES = ("Easy", "Medium", "Hard")
CAMPAIGN_MAPS_V1 = tuple(entry for entry in CAMPAIGN_MAPS if entry.tag != "CAMPGC")
def location_id(map_index: int, difficulty: str, *, wave: int | None = None) -> int:
    difficulty_index = DIFFICULTY_INDEX[f"EGD_{difficulty.upper()}"]
    base = PROTOTYPE_LOCATION_ID_BASE + map_index * 10_000 + difficulty_index * 1_000
    return base + (900 if wave is None else wave)


LOCATION_NAME_TO_ID: dict[str, int] = {}
LOCATION_MAP_TAG: dict[str, str] = {}
LOCATION_WAVE: dict[str, int | None] = {}
LOCATION_DIFFICULTY: dict[str, str] = {}

for map_index, campaign_map in enumerate(CAMPAIGN_MAPS_V1):
    for ordinal_wave in range(1, 5):
        displayed_wave = START_WAVES[campaign_map.tag] + ordinal_wave - 1
        name = f"{campaign_map.name} - Wave {displayed_wave}"
        # Wave checks are difficulty-independent and occupy the map's base range.
        LOCATION_NAME_TO_ID[name] = (
            PROTOTYPE_LOCATION_ID_BASE + map_index * 10_000 + ordinal_wave
        )
        LOCATION_MAP_TAG[name] = campaign_map.tag
        LOCATION_WAVE[name] = ordinal_wave
        LOCATION_DIFFICULTY[name] = "Any"
    for difficulty in DIFFICULTIES:
        if campaign_map.tag == "CAMPTS" and difficulty == "Hard":
            continue
        name = f"{campaign_map.name} - {difficulty} Victory"
        LOCATION_NAME_TO_ID[name] = location_id(map_index, difficulty)
        LOCATION_MAP_TAG[name] = campaign_map.tag
        LOCATION_WAVE[name] = None
        LOCATION_DIFFICULTY[name] = difficulty

SUMMIT_MEDIUM_VICTORY = "The Summit - Medium Victory"
