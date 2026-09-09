"""Shared hero catalog and deterministic roster/opening policy.

This module has no Archipelago or game dependencies. New hero capability tags
are planning assumptions awaiting runtime verification, not a support claim.
Normal weapon attacks and common repair/upgrade/sell controls are not items.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
import re
from typing import Iterable, Mapping


STARTING_DEFENSE_MANA_CAP = 140


@dataclass(frozen=True)
class Action:
    name: str
    key: str
    damaging: bool = False
    anti_air: bool = False
    generic_damage: bool = False
    mana_cost: int | None = None


def action(name: str, key: str = "", *, damaging: bool = False,
           anti_air: bool = False, generic: bool = False,
           mana_cost: int | None = None) -> Action:
    return Action(name, key or re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_"),
                  damaging, anti_air, generic, mana_cost)


def is_starting_defense(tool: Action) -> bool:
    # Unknown costs must not accidentally become first-wave rewards when adding
    # new heroes. This filters placement only; it never changes in-game costs.
    return (tool.damaging and tool.mana_cost is not None
            and 0 <= tool.mana_cost <= STARTING_DEFENSE_MANA_CAP)


@dataclass(frozen=True)
class Hero:
    name: str
    key: str
    family: str
    defenses: tuple[Action, ...]
    abilities: tuple[Action, ...]
    experimental: bool = True

    @property
    def builder(self) -> bool:
        return bool(self.defenses)

    def item_name(self, ability: Action) -> str:
        return f"{ability.name} ({self.name})"


# Candidate costs read from shipped tower archetypes on 7 September 2026.
# See work/starting-mana-audit-040/costs.log for the local read-only audit.
MAGE_DEFENSES = (
    action("Magic Blockade"),
    action("Magic Missile Tower", damaging=True, anti_air=True, generic=True, mana_cost=40),
    action("Fireball Tower", damaging=True, anti_air=True, mana_cost=80),
    action("Lightning Tower", damaging=True, anti_air=True, mana_cost=120),
    # Retain the existing first-wave candidate policy: not an early damage roll.
    action("Deadly Striker Tower", anti_air=True, generic=True),
)
SQUIRE_DEFENSES = (
    action("Spike Blockade", damaging=True, generic=True, mana_cost=30),
    action("Bouncer Blockade", damaging=True, generic=True, mana_cost=40),
    action("Harpoon Turret", damaging=True, anti_air=True, generic=True, mana_cost=80),
    action("Bowling Ball Turret", damaging=True, generic=True, mana_cost=100),
    action("Slice and Dice Blockade", "slice_n_dice_blockade", damaging=True, generic=True, mana_cost=140),
    action("Mortar Turret", damaging=True, generic=True, mana_cost=150),
)
HUNTRESS_DEFENSES = (
    action("Proximity Mine Trap", damaging=True, anti_air=True, generic=True, mana_cost=40),
    action("Gas Trap"),
    action("Inferno Trap", damaging=True, anti_air=True, mana_cost=60),
    action("Darkness Trap"),
    action("Ethereal Spike Trap", damaging=True, anti_air=True, mana_cost=80),
    action("Oil Trap"),
)
MONK_DEFENSES = (
    action("Ensnare Aura"),
    action("Electric Aura", damaging=True, anti_air=True, mana_cost=50),
    action("Healing Aura"),
    action("Strength Drain Aura"),
    action("Enrage Aura"),
)


HEROES = (
    Hero("Apprentice", "apprentice", "apprentice", MAGE_DEFENSES,
         (action("Overcharge"), action("Mana Bomb")), False),
    Hero("Squire", "squire", "squire", SQUIRE_DEFENSES,
         (action("Blood Rage"), action("Circular Slice")), False),
    Hero("Huntress", "huntress", "huntress", HUNTRESS_DEFENSES,
         (action("Invisibility"), action("Piercing Shot"), action("Shadow Step")), False),
    Hero("Monk", "monk", "monk", MONK_DEFENSES,
         (action("Tower Boost"), action("Hero Boost")), False),
    Hero("Adept", "adept", "apprentice", MAGE_DEFENSES,
         (action("Upgrade Aura"), action("Purity Bomb"))),
    Hero("Countess", "countess", "squire", SQUIRE_DEFENSES,
         (action("Call to Arms"), action("Joust"))),
    Hero("Ranger", "ranger", "huntress", HUNTRESS_DEFENSES,
         (action("Invisibility Field"), action("Piercing Spreadshot"))),
    Hero("Initiate", "initiate", "monk", MONK_DEFENSES,
         (action("Remote Defense Boost"), action("Enemy Drain"))),
    Hero("Barbarian", "barbarian", "barbarian", (), (
        action("Battle Leap"), action("Battle Pound"), action("Tornado Stance"),
        action("Lightning Stance"), action("Siphon Stance"), action("Turtle Stance"),
        action("Hawk Stance"),
    )),
    Hero("Series EV", "series_ev", "series_ev", (
        action("Proton Beam", damaging=True, generic=True, mana_cost=40), action("Physical Beam"),
        action("Reflection Beam"), action("Shock Beam", damaging=True, mana_cost=55),
        action("Tower Buff Beam"), action("SAM Unit", damaging=True, anti_air=True, mana_cost=150),
    ), (action("Holographic Decoy"), action("Proton Charge Blast"))),
    Hero("Summoner", "summoner", "summoner", (
        action("Archer Minion", damaging=True, anti_air=True, generic=True, mana_cost=40),
        action("Spider Minion", damaging=True, mana_cost=80), action("Orc Minion", damaging=True, generic=True, mana_cost=140),
        action("Mage Minion", damaging=True, anti_air=True, mana_cost=180),
        action("Warrior Minion", damaging=True, generic=True, mana_cost=300),
        action("Ogre Minion", damaging=True, generic=True, mana_cost=500),
    ), (action("Phase Shift / Overlord Mode", "phase_shift_overlord"), action("Flash Heal"))),
    Hero("Jester", "jester", "jester", (
        action("Jack-in-the-Box", damaging=True, generic=True, mana_cost=40),
        action("Party Popper", damaging=True, anti_air=True, mana_cost=50),
        action("Small Present"), action("Deluxe Present"),
        action("Extravagant Present"), action("Extra-Deluxe Present"),
    ), (action("Move Tower"), action("Wheel O' Fortuna"))),
    Hero("Hermit", "hermit", "hermit", (
        action("Seed Bomb Tower", damaging=True, anti_air=True, generic=True, mana_cost=40),
        action("Web Wall"), action("Nature Pylon"),
        action("Mushroom Spore Tower", damaging=True, mana_cost=120),
        action("Forest Golem", damaging=True, mana_cost=300),
    ), (action("Thorn Shot"), action("Nature's Gift"))),
    Hero("Gunwitch", "gunwitch", "gunwitch", (), (
        action("Icy Needle"), action("Vroom Broom"), action("Two for the Price of One"),
        action("Witch's Curse"), action("Broom Nado"), action("Blunder Broom Buster"),
    )),
    Hero("Warden", "warden", "warden", (
        action("Angry Blossom", damaging=True, anti_air=True, generic=True, mana_cost=30),
        action("Sludge Launcher", damaging=True, anti_air=True, mana_cost=80),
        action("Cloud Tower", damaging=True, anti_air=True, mana_cost=100),
        action("Wisp Den", damaging=True, anti_air=True, mana_cost=120),
        action("Shroom Pit", damaging=True, mana_cost=180),
    ), (action("Wrath"), action("Forest's Protection"))),
    Hero("Guardian", "guardian", "guardian", (
        action("Holy Cannon", damaging=True, anti_air=True, generic=True, mana_cost=40),
        action("Obelisk", damaging=True, anti_air=True, mana_cost=130),
        action("Owl Nest", damaging=True, anti_air=True, mana_cost=180), action("Empowering Shrine"),
        action("Holy Bulwark", damaging=True, mana_cost=300),
    ), (action("Shield Bash"), action("Divine Judgement"))),
)

HERO_BY_KEY = {hero.key: hero for hero in HEROES}
DEFAULT_HERO_KEYS = ("apprentice", "squire", "huntress", "monk")
MIN_ACTIVE_HEROES = 2
MAX_ACTIVE_HEROES = 16
ITEM_CHECK_COUNT = 83
SUMMIT_FILLER_COUNT = 6
PLACED_MAP_COUNT = 10
STARTING_SUMMONER_MINIONS = frozenset({"archer_minion", "spider_minion", "orc_minion"})


def normalize_hero_keys(values: str | Iterable[str]) -> tuple[str, ...]:
    """Canonicalize user text without using set iteration for seeded decisions."""
    if isinstance(values, Mapping):
        raise ValueError("Active heroes must be a list or comma-separated names, not a weighted mapping.")
    if isinstance(values, str):
        values = values.split(",")
    try:
        raw = list(values)
    except TypeError as error:
        raise ValueError("Active heroes must be a list of hero names.") from error
    names: set[str] = set()
    for value in raw:
        if not isinstance(value, str):
            raise ValueError("Every active hero must be a name, not a number or object.")
        key = re.sub(r"[\s_-]+", "_", value.strip().casefold())
        if key not in HERO_BY_KEY:
            valid = ", ".join(hero.name for hero in HEROES)
            raise ValueError(f"Unknown active hero {value!r}. Choose from: {valid}.")
        names.add(key)
    return tuple(hero.key for hero in HEROES if hero.key in names)


def roster_progression_count(keys: Iterable[str], *, starting_minion: bool = False) -> int:
    """Counts placed items, excluding the starter hero/map and optional minion."""
    heroes = [HERO_BY_KEY[key] for key in keys]
    return (len(heroes) - 1 + PLACED_MAP_COUNT
            + sum(len(hero.defenses) + len(hero.abilities) for hero in heroes)
            - int(starting_minion))


def validate_roster(values: str | Iterable[str], *,
                    starter_readiness: Mapping[str, bool] | None = None) -> tuple[str, ...]:
    keys = normalize_hero_keys(values)
    if not MIN_ACTIVE_HEROES <= len(keys) <= MAX_ACTIVE_HEROES:
        raise ValueError(f"Choose {MIN_ACTIVE_HEROES} to {MAX_ACTIVE_HEROES} different active heroes.")
    if not any(HERO_BY_KEY[key].builder for key in keys):
        raise ValueError("Choose at least one hero who builds defenses or minions.")
    # The world validates the selected check budget before drawing a starter.
    if starter_readiness is not None:
        pending = [HERO_BY_KEY[key].name for key in keys if not starter_readiness.get(key, False)]
        if pending:
            raise ValueError("Starting support has not been verified for: " + ", ".join(pending))
    return keys


@dataclass(frozen=True)
class Opening:
    starting_hero: str
    second_hero: str
    first_wave_reward: str | None
    starting_minion: str | None
    extra_defenses: tuple[str, str]
    anti_air: str


def _opening_packages(keys: tuple[str, ...], starter: Hero, first_action: Action):
    plans: dict[str, tuple[tuple[str, str], ...]] = {}
    first_name = starter.item_name(first_action)
    for second_key in keys:
        second = HERO_BY_KEY[second_key]
        if second.key == starter.key or (not starter.builder and not second.builder):
            continue
        candidates = [
            (hero.item_name(defense), hero.key, defense)
            for hero in (starter, second) for defense in hero.defenses
            if hero.item_name(defense) != first_name
        ]
        pairs = []
        for left, right in combinations(candidates, 2):
            if second.builder and second.key not in {left[1], right[1]}:
                continue
            defense_actions = [left[2], right[2]]
            if starter.builder:
                defense_actions.append(first_action)
            # Non-builders retain ordinary weapon damage, by the approved
            # opening policy. Builders-only openings retain a generic defense.
            generic = (not starter.builder or not second.builder
                       or any(tool.generic_damage for tool in defense_actions))
            if generic and any(tool.anti_air for tool in defense_actions):
                pairs.append((left[0], right[0]))
        if pairs:
            plans[second.key] = tuple(pairs)
    return plans


def choose_opening(values: str | Iterable[str], rng, *,
                   starter_readiness: Mapping[str, bool] | None = None) -> Opening:
    keys = validate_roster(values, starter_readiness=starter_readiness)
    all_plans = {}
    for key in keys:
        starter = HERO_BY_KEY[key]
        if not starter.builder:
            first_actions = starter.abilities
        elif key == "summoner":
            # Approved level-six choices: Archer 40, Spider 80, Orc 140 mana.
            first_actions = tuple(tool for tool in starter.defenses
                                  if tool.key in STARTING_SUMMONER_MINIONS
                                  and is_starting_defense(tool))
        else:
            first_actions = tuple(tool for tool in starter.defenses if is_starting_defense(tool))
        plans = [(tool, _opening_packages(keys, starter, tool)) for tool in first_actions]
        viable = [(tool, packages) for tool, packages in plans if packages]
        if not viable or (key == "summoner" and len(viable) != len(first_actions)):
            raise ValueError(
                f"This roster cannot provide an affordable opening defense and anti-air tools when "
                f"{starter.name} starts. Choose another compatible builder; the starter "
                "will not be silently excluded or rerolled."
            )
        all_plans[key] = viable

    # Every selected hero has exactly one entry, regardless of kit size or how
    # many feasible defense combinations that hero has.
    starter_key = rng.choice(keys)
    starter = HERO_BY_KEY[starter_key]
    first_action, second_plans = rng.choice(all_plans[starter_key])
    second_key = rng.choice(tuple(second_plans))
    pair = rng.choice(second_plans[second_key])
    first_name = starter.item_name(first_action)
    selected_defenses = {hero.item_name(tool): tool for hero in HEROES for tool in hero.defenses}
    tools = ((first_name,) if starter.builder else ()) + pair
    anti_air = next(name for name in tools if selected_defenses[name].anti_air)
    return Opening(starter_key, second_key,
                   None if starter_key == "summoner" else first_name,
                   first_name if starter_key == "summoner" else None, pair, anti_air)
