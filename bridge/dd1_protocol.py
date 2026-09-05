"""Durable offline protocol for the DD1 Archipelago prototype."""

from __future__ import annotations

import json
import os
import re
import shutil
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from collections.abc import Iterable


PROTOCOL_VERSION = 1
BRIDGE_STATE_VERSION = 3
PROTOTYPE_LOCATION_ID_BASE = 9_100_000_000


@dataclass(frozen=True)
class CampaignMap:
    tag: str
    filename: str
    name: str


CAMPAIGN_MAPS = (
    CampaignMap("CAMPDW", "DD_Lev_02", "The Deeper Well"),
    CampaignMap("CAMPFF", "DD_Entryway_03", "Foundries and Forges"),
    CampaignMap("CAMPMQ", "TestMap_DD_Shell_04", "Magus Quarters"),
    CampaignMap("CAMPAL", "DD_Lev_04", "Alchemical Laboratory"),
    CampaignMap("CAMPSQ", "ServantsQuarters", "Servants Quarters"),
    CampaignMap("CAMPCA", "DD_Lev_06_WIP_TEST", "Castle Armory"),
    CampaignMap("CAMPHC", "DD_Lev_05", "Hall of Court"),
    CampaignMap("CAMPTR", "DD_ThroneRoom", "The Throne Room"),
    CampaignMap("CAMPRG", "DD_RoyalGardens", "Royal Gardens"),
    CampaignMap("CAMPRP", "DD_TheRamparts", "The Ramparts"),
    CampaignMap("CAMPES", "DD_TheSpires", "Endless Spires"),
    CampaignMap("CAMPTS", "DD_Finale", "The Summit"),
    CampaignMap("CAMPGC", "DD_Caverns", "Glitterhelm Caverns"),
)
MAP_BY_FILENAME = {entry.filename.casefold(): entry for entry in CAMPAIGN_MAPS}
SUMMIT_REQUIRED_CLEAR_TAGS = frozenset(
    entry.tag for entry in CAMPAIGN_MAPS if entry.tag not in {"CAMPTS", "CAMPGC"}
)
START_WAVES = {
    "CAMPDW": 1,
    "CAMPFF": 2,
    "CAMPMQ": 2,
    "CAMPAL": 3,
    "CAMPSQ": 3,
    "CAMPCA": 4,
    "CAMPHC": 4,
    "CAMPTR": 4,
    "CAMPRG": 3,
    "CAMPRP": 4,
    "CAMPES": 4,
    "CAMPTS": 5,
    "CAMPGC": 1,
}
FINAL_WAVES = {
    entry.tag: (10 if entry.tag == "CAMPGC" else START_WAVES[entry.tag] + 4)
    for entry in CAMPAIGN_MAPS
}

DIFFICULTIES = (
    "EGD_EASY",
    "EGD_MEDIUM",
    "EGD_HARD",
    "EGD_INSANE",
    "EGD_NIGHTMARE",
    "EGD_RUTHLESS",
)
DIFFICULTY_INDEX = {name: index for index, name in enumerate(DIFFICULTIES)}


class ProtocolError(ValueError):
    pass


def summit_is_unlocked(observed_location_keys: object, required_maps: int = 11,
                       minimum_difficulty: int = 1) -> bool:
    """Return whether every non-Summit base map has a recorded victory."""
    if not isinstance(observed_location_keys, (dict, list, tuple, set, frozenset)):
        return False
    cleared_tags = {
        key.split(".")[2]
        for key in observed_location_keys
        if isinstance(key, str)
        and key.startswith("dd1.campaign.")
        and ".victory." in key
        and len(key.split(".")) >= 5
        and key.split(".")[4] in {d.removeprefix("EGD_").lower() for d in DIFFICULTIES[minimum_difficulty:]}
    }
    return len(SUMMIT_REQUIRED_CLEAR_TAGS & cleared_tags) >= required_maps


def summit_settings(slot_data: dict) -> dict[str, int]:
    result = {}
    for name, default, low, high in (
        ("summit_required_maps", 11, 1, 11),
        ("summit_unlock_difficulty", 1, 0, 3),
        ("summit_goal_difficulty", 2, 0, 3),
    ):
        value = slot_data.get(name, default)
        if type(value) is not int or not low <= value <= high:
            raise ProtocolError(f"Invalid {name}: {value!r}")
        result[name] = value
    return result


def recover_observed_victories(
    state: dict[str, Any], checked_location_ids: object
) -> int:
    """Rebuild map-clear history from this slot's server-acknowledged checks.

    This is recovery metadata only: recovered checks are already acknowledged by
    the server, so they must never be added to the pending submission queue.
    """
    if not isinstance(checked_location_ids, (list, tuple, set, frozenset)):
        raise ProtocolError("checked locations must be a collection")
    if not all(isinstance(location_id, int) for location_id in checked_location_ids):
        raise ProtocolError("checked locations must contain only integers")

    checked = set(checked_location_ids)
    recovered = 0
    for map_index, campaign_map in enumerate(CAMPAIGN_MAPS):
        if campaign_map.tag == "CAMPGC":
            continue
        for difficulty in ("EGD_EASY", "EGD_MEDIUM", "EGD_HARD"):
            difficulty_index = DIFFICULTY_INDEX[difficulty]
            location_id = (
                PROTOTYPE_LOCATION_ID_BASE
                + map_index * 10_000
                + difficulty_index * 1_000
                + 900
            )
            if location_id not in checked:
                continue
            difficulty_key = difficulty.removeprefix("EGD_").lower()
            key = f"dd1.campaign.{campaign_map.tag}.victory.{difficulty_key}"
            if key not in state["observed_locations"]:
                state["observed_locations"][key] = {
                    "prototype_location_id": location_id,
                    "source_event": {"event": "server_recovery"},
                }
                recovered += 1
    return recovered


SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9_.-]+$")


def atomic_write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    # Keep one known-good generation.  If Windows, the game, or the machine
    # stops during the final replace, the AP client can recover on reconnect.
    if path.exists():
        shutil.copy2(path, path.with_name(f"{path.name}.bak"))
    temporary.replace(path)


def _atomic_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.tmp")
    shutil.copy2(source, temporary)
    os.replace(temporary, destination)


def switch_hero_profile(tc_root: Path, profiles_root: Path, identity: str) -> str:
    """Activate one recoverable TC hero save per AP seed/team/slot identity."""
    if not isinstance(identity, str) or not identity:
        raise ProtocolError("hero-profile identity must be a non-empty string")
    profile_key = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:32]
    profiles_root.mkdir(parents=True, exist_ok=True)
    marker = profiles_root / "active_profile.json"
    pending = profiles_root / "profile_switch_pending.json"
    active_files = (tc_root / "DunDefHeroes.dun", tc_root / "DunDefHeroes.dun.bak")

    def profile_files(key: str) -> tuple[Path, Path]:
        return (profiles_root / f"{key}.dun", profiles_root / f"{key}.dun.bak")

    def read_key(path: Path, field: str) -> str | None:
        if not path.exists():
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
        key = value.get(field) if isinstance(value, dict) else None
        if not isinstance(key, str) or not re.fullmatch(r"[a-f0-9]{32}|legacy-shared", key):
            raise ProtocolError(f"invalid hero-profile {field}")
        return key

    def install(key: str) -> None:
        stored = profile_files(key)
        for source, destination in zip(stored, active_files):
            if source.exists():
                _atomic_copy(source, destination)
            elif destination.exists():
                destination.unlink()

    # A journal makes interruption between replacing the active save and
    # updating its marker recoverable without overwriting the previous seed.
    pending_key = read_key(pending, "to")
    if pending_key is not None:
        install(pending_key)
        atomic_write_json(marker, {"active": pending_key})
        pending.unlink()

    active_key = read_key(marker, "active")
    if active_key == profile_key:
        return profile_key

    if active_key is not None:
        stored = profile_files(active_key)
        for source, destination in zip(active_files, stored):
            if source.exists():
                _atomic_copy(source, destination)
    elif any(path.exists() for path in active_files):
        # Preserve the pre-feature shared TC save once; never discard it or
        # silently assign its progressed characters to a new randomizer seed.
        stored = profile_files("legacy-shared")
        for source, destination in zip(active_files, stored):
            if source.exists() and not destination.exists():
                _atomic_copy(source, destination)

    atomic_write_json(pending, {"to": profile_key})
    install(profile_key)
    atomic_write_json(marker, {"active": profile_key})
    pending.unlink()
    return profile_key


def canonicalize_event(event: dict[str, Any]) -> tuple[str, int]:
    if event.get("protocol") != PROTOCOL_VERSION:
        raise ProtocolError("unsupported event protocol")
    event_type = event.get("event")
    if event_type not in {"wave_complete", "level_victory"}:
        raise ProtocolError("event is not an Archipelago location")

    raw_map = event.get("map")
    raw_difficulty = event.get("detail")
    wave = event.get("wave")
    if not isinstance(raw_map, str) or not isinstance(raw_difficulty, str):
        raise ProtocolError("map and difficulty must be strings")
    if not isinstance(wave, int):
        raise ProtocolError("wave must be an integer")

    campaign_map = MAP_BY_FILENAME.get(Path(raw_map).stem.casefold())
    if campaign_map is None:
        raise ProtocolError(f"unknown campaign map: {raw_map}")
    difficulty_index = DIFFICULTY_INDEX.get(raw_difficulty)
    if difficulty_index is None:
        raise ProtocolError(f"unknown difficulty: {raw_difficulty}")

    map_index = CAMPAIGN_MAPS.index(campaign_map)
    location_base = PROTOTYPE_LOCATION_ID_BASE + map_index * 10_000 + difficulty_index * 1_000
    difficulty_key = raw_difficulty.removeprefix("EGD_").lower()
    if event_type == "wave_complete":
        first_wave = START_WAVES[campaign_map.tag]
        final_wave = FINAL_WAVES[campaign_map.tag]
        if not first_wave <= wave < final_wave:
            raise ProtocolError(
                f"wave is not one of the four non-final campaign waves: {wave}"
            )
        ordinal_wave = wave - first_wave + 1
        return (
            f"dd1.campaign.{campaign_map.tag}.wave.{ordinal_wave}",
            PROTOTYPE_LOCATION_ID_BASE + map_index * 10_000 + ordinal_wave,
        )
    return f"dd1.campaign.{campaign_map.tag}.victory.{difficulty_key}", location_base + 900


def canonicalize_event_locations(event: dict[str, Any]) -> list[tuple[str, int]]:
    """Expand a completion to its current and lower supported difficulties."""
    raw_difficulty = event.get("detail")
    location_difficulties = ("EGD_EASY", "EGD_MEDIUM", "EGD_HARD")
    difficulty_tier = {
        "EGD_EASY": 0,
        "EGD_MEDIUM": 1,
        "EGD_HARD": 2,
        # Insane, Nightmare, and Ruthless do not add locations. They count as
        # Hard-or-higher and cascade through the existing three tiers.
        "EGD_INSANE": 2,
        "EGD_NIGHTMARE": 2,
        "EGD_RUTHLESS": 2,
    }
    if raw_difficulty not in difficulty_tier:
        raise ProtocolError(f"difficulty is outside the first-version rules: {raw_difficulty}")
    raw_map = event.get("map")
    campaign_map = MAP_BY_FILENAME.get(Path(raw_map).stem.casefold()) if isinstance(raw_map, str) else None
    if campaign_map is None or campaign_map.tag == "CAMPGC":
        raise ProtocolError(f"map is outside the 12-map first-version rules: {raw_map}")
    wave = event.get("wave")
    if event.get("event") == "wave_complete":
        if not isinstance(wave, int):
            raise ProtocolError("wave must be an integer")
        # EndedCombatPhase can also fire for the fifth/final combat wave.
        # Victory is emitted separately by DoLevelVictory and is the only
        # difficulty-specific check, so never turn this event into victory.
        if wave >= FINAL_WAVES[campaign_map.tag]:
            return []
        return [canonicalize_event(event)]

    highest = difficulty_tier[raw_difficulty]
    expanded: list[tuple[str, int]] = []
    for difficulty in location_difficulties[: highest + 1]:
        lower_event = dict(event)
        lower_event["detail"] = difficulty
        # Summit Hard-or-higher is the goal signal, not an item-bearing check.
        if campaign_map.tag == "CAMPTS" and difficulty == "EGD_HARD":
            continue
        expanded.append(canonicalize_event(lower_event))
    return expanded


def empty_bridge_state() -> dict[str, Any]:
    return {
        "protocol": PROTOCOL_VERSION,
        "state_version": BRIDGE_STATE_VERSION,
        "slot_identity": None,
        "last_received_index": -1,
        "received_items": [],
        "goal_complete": False,
        "processed_files": [],
        "observed_locations": {},
        "pending_location_ids": [],
        "acknowledged_location_ids": [],
    }


def load_bridge_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return empty_bridge_state()
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        backup = path.with_name(f"{path.name}.bak")
        if not backup.exists():
            raise
        value = json.loads(backup.read_text(encoding="utf-8"))
    legacy_required = {
        "protocol",
        "processed_files",
        "observed_locations",
        "pending_location_ids",
        "acknowledged_location_ids",
    }
    if not isinstance(value, dict):
        raise ProtocolError("invalid bridge-state shape")
    if set(value) == legacy_required:
        value = {
            **value,
            "state_version": BRIDGE_STATE_VERSION,
            "slot_identity": None,
            "last_received_index": -1,
            "received_items": [],
            "goal_complete": False,
        }
    elif isinstance(value, dict) and value.get("state_version") == 2 and "goal_complete" not in value:
        value = {**value, "state_version": BRIDGE_STATE_VERSION, "goal_complete": False}
    required = legacy_required | {
        "state_version",
        "slot_identity",
        "last_received_index",
        "received_items",
        "goal_complete",
    }
    if set(value) - {"summit_settings", "victory_history"} != required:
        raise ProtocolError("invalid bridge-state shape")
    summit_settings(value.get("summit_settings", {}))
    if not isinstance(value.get("victory_history", {}), dict):
        raise ProtocolError("invalid victory history")
    if value["protocol"] != PROTOCOL_VERSION:
        raise ProtocolError("unsupported bridge-state protocol")
    if value["state_version"] != BRIDGE_STATE_VERSION:
        raise ProtocolError("unsupported bridge-state version")
    if not isinstance(value["goal_complete"], bool):
        raise ProtocolError("goal_complete must be a boolean")
    _validate_slot_identity(value["slot_identity"])
    if not isinstance(value["last_received_index"], int) or value["last_received_index"] < -1:
        raise ProtocolError("last_received_index must be at least -1")
    if not isinstance(value["received_items"], list):
        raise ProtocolError("received_items must be a list")
    for item in value["received_items"]:
        _validate_received_item(item)
    indices = [item["index"] for item in value["received_items"]]
    if indices != sorted(set(indices)):
        raise ProtocolError("received item indices must be unique and sorted")
    expected_last = indices[-1] if indices else -1
    if value["last_received_index"] != expected_last:
        raise ProtocolError("last_received_index does not match received_items")
    if not isinstance(value["processed_files"], list):
        raise ProtocolError("processed_files must be a list")
    if not isinstance(value["observed_locations"], dict):
        raise ProtocolError("observed_locations must be an object")
    for field in ("pending_location_ids", "acknowledged_location_ids"):
        if not isinstance(value[field], list) or not all(isinstance(item, int) for item in value[field]):
            raise ProtocolError(f"{field} must be an integer list")
    return value


def _validate_slot_identity(value: object) -> None:
    if value is None:
        return
    required = {"seed_name", "slot", "team", "slot_data_version"}
    if not isinstance(value, dict) or set(value) != required:
        raise ProtocolError("invalid slot identity")
    for field in ("seed_name", "slot"):
        if not isinstance(value[field], str) or not value[field]:
            raise ProtocolError(f"slot identity {field} must be a non-empty string")
    for field in ("team", "slot_data_version"):
        if not isinstance(value[field], int) or value[field] < 0:
            raise ProtocolError(f"slot identity {field} must be a non-negative integer")


def bind_slot_identity(
    state: dict[str, Any], *, seed_name: str, slot: str, team: int, slot_data_version: int
) -> None:
    identity = {
        "seed_name": seed_name,
        "slot": slot,
        "team": team,
        "slot_data_version": slot_data_version,
    }
    _validate_slot_identity(identity)
    existing = state["slot_identity"]
    if existing is None:
        state["slot_identity"] = identity
    elif existing != identity:
        raise ProtocolError(
            "bridge state belongs to a different seed or slot; use a separate state file"
        )


def _validate_received_item(value: object) -> None:
    required = {"index", "item_id", "location_id", "player"}
    if not isinstance(value, dict) or set(value) != required:
        raise ProtocolError("invalid received item")
    for field in required:
        if not isinstance(value[field], int) or (field != "location_id" and value[field] < 0):
            qualifier = "an integer" if field == "location_id" else "a non-negative integer"
            raise ProtocolError(f"received item {field} must be {qualifier}")


def record_received_items(state: dict[str, Any], items: list[dict[str, int]]) -> int:
    """Append normalized AP items by delivery index, tolerating exact replay."""
    existing = {item["index"]: item for item in state["received_items"]}
    added = 0
    for item in sorted(items, key=lambda entry: entry.get("index", -1)):
        _validate_received_item(item)
        prior = existing.get(item["index"])
        if prior is not None:
            if prior != item:
                raise ProtocolError(f"conflicting replay at received item index {item['index']}")
            continue
        expected = state["last_received_index"] + 1
        if item["index"] != expected:
            raise ProtocolError(
                f"received item gap: expected index {expected}, got {item['index']}"
            )
        normalized = dict(item)
        state["received_items"].append(normalized)
        state["last_received_index"] = item["index"]
        existing[item["index"]] = normalized
        added += 1
    return added


def record_location(
    state: dict[str, Any], source_file: str, event: dict[str, Any]
) -> tuple[str, int, bool]:
    recorded = record_locations(state, source_file, event)
    return recorded[-1]


def record_locations(
    state: dict[str, Any], source_file: str, event: dict[str, Any]
) -> list[tuple[str, int, bool]]:
    canonical_locations = canonicalize_event_locations(event)
    settings = summit_settings(state.get("summit_settings", {}))
    raw_map = event.get("map")
    raw_difficulty = event.get("detail")
    campaign_map = MAP_BY_FILENAME.get(Path(raw_map).stem.casefold()) if isinstance(raw_map, str) else None
    if (
        campaign_map is not None
        and campaign_map.tag == "CAMPTS"
        and event.get("event") == "level_victory"
        and isinstance(event.get("wave"), int)
        and event["wave"] >= FINAL_WAVES[campaign_map.tag]
        and DIFFICULTY_INDEX.get(raw_difficulty, -1) >= settings["summit_goal_difficulty"]
    ):
        state["goal_complete"] = True
    if (campaign_map is not None and event.get("event") == "level_victory"
            and isinstance(event.get("wave"), int)
            and event["wave"] >= FINAL_WAVES[campaign_map.tag]):
        key = f"dd1.campaign.{campaign_map.tag}.victory.{raw_difficulty.removeprefix('EGD_').lower()}"
        state.setdefault("victory_history", {})[key] = True
    recorded: list[tuple[str, int, bool]] = []
    for key, location_id in canonical_locations:
        already_seen = key in state["observed_locations"]
        if not already_seen:
            state["observed_locations"][key] = {
                "prototype_location_id": location_id,
                "source_event": event,
            }
            if location_id not in state["acknowledged_location_ids"]:
                state["pending_location_ids"].append(location_id)
                state["pending_location_ids"] = sorted(set(state["pending_location_ids"]))
        recorded.append((key, location_id, not already_seen))
    if source_file not in state["processed_files"]:
        state["processed_files"].append(source_file)
        state["processed_files"].sort()
    return recorded


def acknowledge_locations(state: dict[str, Any], location_ids: list[int]) -> None:
    acknowledgements = set(state["acknowledged_location_ids"])
    acknowledgements.update(location_ids)
    state["acknowledged_location_ids"] = sorted(acknowledgements)
    state["pending_location_ids"] = [
        value for value in state["pending_location_ids"] if value not in acknowledgements
    ]


def validate_unlock_state(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ProtocolError("unlock state must be an object")
    required = {"protocol", "revision", "slot", "unlocked"}
    if set(value) != required or value["protocol"] != PROTOCOL_VERSION:
        raise ProtocolError("invalid unlock-state envelope")
    if not isinstance(value["revision"], int) or value["revision"] < 0:
        raise ProtocolError("revision must be a non-negative integer")
    if not isinstance(value["slot"], str) or not value["slot"]:
        raise ProtocolError("slot must be a non-empty string")
    if not SAFE_IDENTIFIER.fullmatch(value["slot"]):
        raise ProtocolError("slot contains unsupported characters")

    unlocked = value["unlocked"]
    expected = {"heroes", "defenses", "abilities", "maps", "max_equipment_quality"}
    if not isinstance(unlocked, dict) or set(unlocked) != expected:
        raise ProtocolError("invalid unlocked-state shape")
    for field in ("heroes", "defenses", "abilities", "maps"):
        if not isinstance(unlocked[field], list) or not all(
            isinstance(item, str) and item for item in unlocked[field]
        ):
            raise ProtocolError(f"{field} must be a list of non-empty strings")
        if not all(SAFE_IDENTIFIER.fullmatch(item) for item in unlocked[field]):
            raise ProtocolError(f"{field} contains an unsupported identifier")
        unlocked[field] = sorted(set(unlocked[field]))
    quality = unlocked["max_equipment_quality"]
    if not isinstance(quality, int) or not 0 <= quality <= 19:
        raise ProtocolError("max_equipment_quality must be between 0 and 19")
    return value


def write_unlock_ini(path: Path, value: object, *, level_six_heroes: Iterable[str] = ()) -> None:
    state = validate_unlock_state(value)
    unlocked = state["unlocked"]
    lines = [
        "[DD1Archipelago.APUnlockState]",
        f"Revision={state['revision']}",
        f"Slot={state['slot']}",
        f"MaxEquipmentQuality={unlocked['max_equipment_quality']}",
    ]
    field_names = (
        ("UnlockedHeroes", "heroes"),
        ("UnlockedDefenses", "defenses"),
        ("UnlockedAbilities", "abilities"),
        ("UnlockedMaps", "maps"),
    )
    for ini_name, state_name in field_names:
        lines.extend(f"{ini_name}={item}" for item in unlocked[state_name])

    allowed_heroes = {'apprentice', 'squire', 'huntress', 'monk'}
    lines.extend(f"LevelSixHeroes={hero}" for hero in dict.fromkeys(level_six_heroes)
                 if hero in allowed_heroes)

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write("\n".join(lines) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)
