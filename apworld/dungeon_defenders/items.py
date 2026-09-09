"""Hero-dependent item catalog with permanent, append-only network IDs."""

from BaseClasses import ItemClassification
from .heroes import HEROES, HERO_BY_KEY, normalize_hero_keys
from .dd1_content import XP_REWARDS, MANA_REWARDS, MODE_ITEMS, DIFFICULTY_ITEMS, SUMMIT_MAP_ITEM, PROGRESSIVE_DIFFICULTY


ITEM_ID_BASE = 9_200_000_000

HERO_ITEMS = {hero.name: hero.key for hero in HEROES}
DEFENSE_ITEMS = {hero.item_name(tool): f"{hero.key}.{tool.key}"
                 for hero in HEROES for tool in hero.defenses}
ABILITY_ITEMS = {hero.item_name(tool): f"{hero.key}.{tool.key}"
                 for hero in HEROES for tool in hero.abilities}

MAP_ITEMS = {
    "The Deeper Well Map": "CAMPDW",
    "Foundries and Forges Map": "CAMPFF",
    "Magus Quarters Map": "CAMPMQ",
    "Alchemical Laboratory Map": "CAMPAL",
    "Servants Quarters Map": "CAMPSQ",
    "Castle Armory Map": "CAMPCA",
    "Hall of Court Map": "CAMPHC",
    "The Throne Room Map": "CAMPTR",
    "Royal Gardens Map": "CAMPRG",
    "The Ramparts Map": "CAMPRP",
    "Endless Spires Map": "CAMPES",
    SUMMIT_MAP_ITEM: "CAMPTS",
}

# Agreed campaign progression bands. They are recorded separately from the
# item table so generation policy can evolve without changing stable item IDs.
MAP_TIERS = (
    (
        "The Deeper Well Map",
        "Foundries and Forges Map",
        "Magus Quarters Map",
        "Alchemical Laboratory Map",
    ),
    (
        "Servants Quarters Map",
        "Castle Armory Map",
        "Hall of Court Map",
    ),
    (
        "The Throne Room Map",
        "Royal Gardens Map",
        "The Ramparts Map",
        "Endless Spires Map",
    ),
)

PROGRESSION_ITEMS = tuple(HERO_ITEMS) + tuple(DEFENSE_ITEMS) + tuple(ABILITY_ITEMS) + tuple(MAP_ITEMS)
XP_FILLER_ITEM = "Two Hero Levels"
MANA_FILLER_ITEM = "25,000 Bank Mana"
FILLER_ITEMS = tuple(XP_REWARDS) + tuple(MANA_REWARDS)
# Keep the retired prototype filler in the table so its numeric ID can never
# be reinterpreted as a real reward when an old test seed reconnects.
LEGACY_NOTHING_ITEM = "Nothing"
# Never reorder, insert into, or rename this published 0.3.x ID list. New
# heroes/actions are appended after its 46 entries, including retired Nothing.
LEGACY_ITEM_NAMES = (
    "Apprentice", "Squire", "Huntress", "Monk",
    "Magic Blockade (Apprentice)", "Magic Missile Tower (Apprentice)",
    "Fireball Tower (Apprentice)", "Lightning Tower (Apprentice)",
    "Deadly Striker Tower (Apprentice)", "Spike Blockade (Squire)",
    "Bouncer Blockade (Squire)", "Harpoon Turret (Squire)",
    "Bowling Ball Turret (Squire)", "Slice and Dice Blockade (Squire)",
    "Proximity Mine Trap (Huntress)", "Gas Trap (Huntress)",
    "Inferno Trap (Huntress)", "Darkness Trap (Huntress)",
    "Ethereal Spike Trap (Huntress)", "Ensnare Aura (Monk)",
    "Electric Aura (Monk)", "Healing Aura (Monk)",
    "Strength Drain Aura (Monk)", "Enrage Aura (Monk)",
    "Overcharge (Apprentice)", "Mana Bomb (Apprentice)",
    "Blood Rage (Squire)", "Circular Slice (Squire)",
    "Invisibility (Huntress)", "Piercing Shot (Huntress)",
    "Tower Boost (Monk)", "Hero Boost (Monk)",
    "The Deeper Well Map", "Foundries and Forges Map", "Magus Quarters Map",
    "Alchemical Laboratory Map", "Servants Quarters Map", "Castle Armory Map",
    "Hall of Court Map", "The Throne Room Map", "Royal Gardens Map",
    "The Ramparts Map", "Endless Spires Map", "Nothing", "Two Hero Levels", "25,000 Bank Mana",
)
# Keep the 0.4.0 additions fixed too. Future items go at the END, regardless
# of where their hero/action belongs in the presentation registry.
V040_ITEM_NAMES = (
    "Adept",
    "Countess",
    "Ranger",
    "Initiate",
    "Barbarian",
    "Series EV",
    "Summoner",
    "Jester",
    "Hermit",
    "Gunwitch",
    "Warden",
    "Guardian",
    "Mortar Turret (Squire)",
    "Oil Trap (Huntress)",
    "Magic Blockade (Adept)",
    "Magic Missile Tower (Adept)",
    "Fireball Tower (Adept)",
    "Lightning Tower (Adept)",
    "Deadly Striker Tower (Adept)",
    "Spike Blockade (Countess)",
    "Bouncer Blockade (Countess)",
    "Harpoon Turret (Countess)",
    "Bowling Ball Turret (Countess)",
    "Slice and Dice Blockade (Countess)",
    "Mortar Turret (Countess)",
    "Proximity Mine Trap (Ranger)",
    "Gas Trap (Ranger)",
    "Inferno Trap (Ranger)",
    "Darkness Trap (Ranger)",
    "Ethereal Spike Trap (Ranger)",
    "Oil Trap (Ranger)",
    "Ensnare Aura (Initiate)",
    "Electric Aura (Initiate)",
    "Healing Aura (Initiate)",
    "Strength Drain Aura (Initiate)",
    "Enrage Aura (Initiate)",
    "Proton Beam (Series EV)",
    "Physical Beam (Series EV)",
    "Reflection Beam (Series EV)",
    "Shock Beam (Series EV)",
    "Tower Buff Beam (Series EV)",
    "SAM Unit (Series EV)",
    "Archer Minion (Summoner)",
    "Spider Minion (Summoner)",
    "Orc Minion (Summoner)",
    "Mage Minion (Summoner)",
    "Warrior Minion (Summoner)",
    "Ogre Minion (Summoner)",
    "Jack-in-the-Box (Jester)",
    "Party Popper (Jester)",
    "Small Present (Jester)",
    "Deluxe Present (Jester)",
    "Extravagant Present (Jester)",
    "Extra-Deluxe Present (Jester)",
    "Seed Bomb Tower (Hermit)",
    "Web Wall (Hermit)",
    "Nature Pylon (Hermit)",
    "Mushroom Spore Tower (Hermit)",
    "Forest Golem (Hermit)",
    "Angry Blossom (Warden)",
    "Sludge Launcher (Warden)",
    "Cloud Tower (Warden)",
    "Wisp Den (Warden)",
    "Shroom Pit (Warden)",
    "Holy Cannon (Guardian)",
    "Obelisk (Guardian)",
    "Owl Nest (Guardian)",
    "Empowering Shrine (Guardian)",
    "Holy Bulwark (Guardian)",
    "Shadow Step (Huntress)",
    "Upgrade Aura (Adept)",
    "Purity Bomb (Adept)",
    "Call to Arms (Countess)",
    "Joust (Countess)",
    "Invisibility Field (Ranger)",
    "Piercing Spreadshot (Ranger)",
    "Remote Defense Boost (Initiate)",
    "Enemy Drain (Initiate)",
    "Battle Leap (Barbarian)",
    "Battle Pound (Barbarian)",
    "Tornado Stance (Barbarian)",
    "Lightning Stance (Barbarian)",
    "Siphon Stance (Barbarian)",
    "Turtle Stance (Barbarian)",
    "Hawk Stance (Barbarian)",
    "Holographic Decoy (Series EV)",
    "Proton Charge Blast (Series EV)",
    "Phase Shift / Overlord Mode (Summoner)",
    "Flash Heal (Summoner)",
    "Move Tower (Jester)",
    "Wheel O' Fortuna (Jester)",
    "Thorn Shot (Hermit)",
    "Nature's Gift (Hermit)",
    "Icy Needle (Gunwitch)",
    "Vroom Broom (Gunwitch)",
    "Two for the Price of One (Gunwitch)",
    "Witch's Curse (Gunwitch)",
    "Broom Nado (Gunwitch)",
    "Blunder Broom Buster (Gunwitch)",
    "Wrath (Warden)",
    "Forest's Protection (Warden)",
    "Shield Bash (Guardian)",
    "Divine Judgement (Guardian)",
)
V050_ITEM_NAMES = (tuple(DIFFICULTY_ITEMS.values()) + tuple(MODE_ITEMS.values())
                  + tuple(n for n in FILLER_ITEMS if n not in LEGACY_ITEM_NAMES)
                  + (SUMMIT_MAP_ITEM, PROGRESSIVE_DIFFICULTY))
ALL_ITEM_NAMES = LEGACY_ITEM_NAMES + V040_ITEM_NAMES + V050_ITEM_NAMES
if len(set(ALL_ITEM_NAMES)) != len(ALL_ITEM_NAMES) or set(PROGRESSION_ITEMS) - set(ALL_ITEM_NAMES):
    raise ValueError("Every catalog item needs exactly one permanent, append-only item ID.")
ITEM_NAME_TO_ID = {name: ITEM_ID_BASE + index for index, name in enumerate(ALL_ITEM_NAMES)}
ITEM_CLASSIFICATIONS = {
    name: (
        ItemClassification.filler
        if name in FILLER_ITEMS or name == LEGACY_NOTHING_ITEM
        else ItemClassification.progression
    )
    for name in ALL_ITEM_NAMES
}

ITEM_TO_UNLOCK = {
    **{name: ("heroes", key) for name, key in HERO_ITEMS.items()},
    **{name: ("defenses", key) for name, key in DEFENSE_ITEMS.items()},
    **{name: ("abilities", key) for name, key in ABILITY_ITEMS.items()},
    **{name: ("maps", key) for name, key in MAP_ITEMS.items()},
}
ITEM_ID_TO_UNLOCK = {
    ITEM_NAME_TO_ID[name]: unlock for name, unlock in ITEM_TO_UNLOCK.items()
}

DEFENSE_OWNER = {
    name: unlock_key.split(".", 1)[0] for name, unlock_key in DEFENSE_ITEMS.items()
}

DAMAGING_DEFENSES = frozenset(hero.item_name(tool) for hero in HEROES
                               for tool in hero.defenses if tool.damaging)
ANTI_AIR_DEFENSES = frozenset(hero.item_name(tool) for hero in HEROES
                              for tool in hero.defenses if tool.anti_air)
GENERIC_DAMAGE_DEFENSES = frozenset(hero.item_name(tool) for hero in HEROES
                                    for tool in hero.defenses if tool.generic_damage)


def progression_items_for_heroes(values, *, include_summit=False) -> tuple[str, ...]:
    """The selected kits only; catalog IDs remain available for old received items."""
    selected = tuple(HERO_BY_KEY[key] for key in normalize_hero_keys(values))
    return (tuple(hero.name for hero in selected)
            + tuple(hero.item_name(tool) for hero in selected for tool in hero.defenses)
            + tuple(hero.item_name(tool) for hero in selected for tool in hero.abilities)
            + tuple(n for n in MAP_ITEMS if include_summit or n != SUMMIT_MAP_ITEM))
