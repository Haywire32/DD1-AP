"""Item table for the first playable Dungeon Defenders world."""

from BaseClasses import ItemClassification


ITEM_ID_BASE = 9_200_000_000

HERO_ITEMS = {
    "Apprentice": "apprentice",
    "Squire": "squire",
    "Huntress": "huntress",
    "Monk": "monk",
}

DEFENSE_ITEMS = {
    "Magic Blockade (Apprentice)": "apprentice.magic_blockade",
    "Magic Missile Tower (Apprentice)": "apprentice.magic_missile_tower",
    "Fireball Tower (Apprentice)": "apprentice.fireball_tower",
    "Lightning Tower (Apprentice)": "apprentice.lightning_tower",
    "Deadly Striker Tower (Apprentice)": "apprentice.deadly_striker_tower",
    "Spike Blockade (Squire)": "squire.spike_blockade",
    "Bouncer Blockade (Squire)": "squire.bouncer_blockade",
    "Harpoon Turret (Squire)": "squire.harpoon_turret",
    "Bowling Ball Turret (Squire)": "squire.bowling_ball_turret",
    "Slice and Dice Blockade (Squire)": "squire.slice_n_dice_blockade",
    "Proximity Mine Trap (Huntress)": "huntress.proximity_mine_trap",
    "Gas Trap (Huntress)": "huntress.gas_trap",
    "Inferno Trap (Huntress)": "huntress.inferno_trap",
    "Darkness Trap (Huntress)": "huntress.darkness_trap",
    "Ethereal Spike Trap (Huntress)": "huntress.ethereal_spike_trap",
    "Ensnare Aura (Monk)": "monk.ensnare_aura",
    "Electric Aura (Monk)": "monk.electric_aura",
    "Healing Aura (Monk)": "monk.healing_aura",
    "Strength Drain Aura (Monk)": "monk.strength_drain_aura",
    "Enrage Aura (Monk)": "monk.enrage_aura",
}

ABILITY_ITEMS = {
    "Overcharge (Apprentice)": "apprentice.overcharge",
    "Mana Bomb (Apprentice)": "apprentice.mana_bomb",
    "Blood Rage (Squire)": "squire.blood_rage",
    "Circular Slice (Squire)": "squire.circular_slice",
    "Invisibility (Huntress)": "huntress.invisibility",
    "Piercing Shot (Huntress)": "huntress.piercing_shot",
    "Tower Boost (Monk)": "monk.tower_boost",
    "Hero Boost (Monk)": "monk.hero_boost",
}

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
FILLER_ITEMS = (XP_FILLER_ITEM, MANA_FILLER_ITEM)
# Keep the retired prototype filler in the table so its numeric ID can never
# be reinterpreted as a real reward when an old test seed reconnects.
LEGACY_NOTHING_ITEM = "Nothing"
ALL_ITEM_NAMES = PROGRESSION_ITEMS + (LEGACY_NOTHING_ITEM,) + FILLER_ITEMS
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

# Defenses that directly damage enemies without requiring another damaging
# tower. Every seed's first-wave guarantee is selected from this set for the
# starting hero. Spike Blockade and the other Squire defenses deal contact or
# attack damage; control/support-only traps and auras are intentionally absent.
DAMAGING_DEFENSES = frozenset({
    "Magic Missile Tower (Apprentice)",
    "Fireball Tower (Apprentice)",
    "Lightning Tower (Apprentice)",
    "Spike Blockade (Squire)",
    "Bouncer Blockade (Squire)",
    "Harpoon Turret (Squire)",
    "Bowling Ball Turret (Squire)",
    "Slice and Dice Blockade (Squire)",
    "Proximity Mine Trap (Huntress)",
    "Inferno Trap (Huntress)",
    "Ethereal Spike Trap (Huntress)",
    "Electric Aura (Monk)",
})

# Broad anti-air-capable opening tools. For this first balance pass, "anti-air"
# means a damaging defense with a useful attack/effect radius rather than only
# a wall or contact attack. Huntress traps need a ground enemy to trigger but
# can damage flying enemies within their effect, matching the intentionally
# permissive capability rule chosen for the prototype.
ANTI_AIR_DEFENSES = frozenset({
    "Magic Missile Tower (Apprentice)",
    "Fireball Tower (Apprentice)",
    "Lightning Tower (Apprentice)",
    "Deadly Striker Tower (Apprentice)",
    "Harpoon Turret (Squire)",
    "Proximity Mine Trap (Huntress)",
    "Inferno Trap (Huntress)",
    "Ethereal Spike Trap (Huntress)",
    "Electric Aura (Monk)",
})
