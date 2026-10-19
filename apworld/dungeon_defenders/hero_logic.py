"""Broad hero-development requirements used by campaign areas and challenges."""

from collections.abc import Callable, Iterable

from .heroes import HERO_BY_KEY


AREA_REQUIREMENTS = {
    # Area 1 deliberately has no additional requirement beyond the opening.
    "CAMPSQ": (6, 12),
    "CAMPCA": (6, 12),
    "CAMPHC": (6, 12),
    "CAMPTR": (6, 12),
    "CAMPRG": (8, 16),
    "CAMPRP": (8, 16),
    "CAMPES": (8, 16),
    "CAMPTS": (10, 20),
}


# Each group is an independent OR requirement. Disabled heroes must never add
# an impossible prerequisite, and a defense only counts with its OWN hero.
HIGH_DIFFICULTY_SUPPORT = (
    (("monk", "Strength Drain Aura"), ("initiate", "Strength Drain Aura"),
     ("huntress", "Darkness Trap"), ("ranger", "Darkness Trap")),
    (("series_ev", "Tower Buff Beam"), ("hermit", "Nature Pylon")),
)


def high_difficulty_support_groups(active_keys: Iterable[str], action_owners=None) -> tuple[tuple[tuple[str, str], ...], ...]:
    """Eligible (hero item, defense item) pairs, omitting empty groups."""
    active = set(active_keys)
    original = tuple(pairs for group in HIGH_DIFFICULTY_SUPPORT if (pairs := tuple(
        (HERO_BY_KEY[key].name, HERO_BY_KEY[key].item_name(next(
            action for action in HERO_BY_KEY[key].defenses if action.name == defense)))
        for key, defense in group if key in active)))
    return tuple(tuple((action_owners.get(item, hero), item) for hero, item in group)
                 for group in original) if action_owners is not None else original


def has_high_difficulty_support(active_keys: Iterable[str], has_item: Callable[[str], bool], action_owners=None) -> bool:
    return all(any(has_item(hero) and has_item(defense) for hero, defense in group)
               for group in high_difficulty_support_groups(active_keys, action_owners))


def hero_action_names(active_keys: Iterable[str]) -> tuple[str, ...]:
    """All defense, minion and ability items belonging to the selected roster."""
    return tuple(
        hero.item_name(action)
        for key in active_keys
        for hero in (HERO_BY_KEY[key],)
        for action in hero.defenses + hero.abilities
    )


def area_requirements(map_tag: str, active_keys: Iterable[str]) -> tuple[int, int]:
    """Return scaled usable-hero and action minimums for one campaign area."""
    keys = tuple(active_keys)
    requested_heroes, requested_actions = AREA_REQUIREMENTS.get(map_tag, (0, 0))
    scaled_heroes = min(requested_heroes, len(keys))
    return (
        scaled_heroes,
        min(requested_actions, len(keys) * 4, len(hero_action_names(keys))),
    )


def count_usable_heroes(active_keys: Iterable[str], has_item: Callable[[str], bool], action_owners=None) -> int:
    """Count unlocked heroes that can fight or own an unlocked damaging defense."""
    usable = 0
    if action_owners is not None:
        damaging = [(h.item_name(d), action_owners[h.item_name(d)])
                    for key in active_keys for h in (HERO_BY_KEY[key],)
                    for d in h.defenses if d.damaging]
        return sum(has_item(HERO_BY_KEY[key].name) and (not HERO_BY_KEY[key].builder or any(
            owner == HERO_BY_KEY[key].name and has_item(item) for item, owner in damaging))
                   for key in active_keys)
    for key in active_keys:
        hero = HERO_BY_KEY[key]
        if not has_item(hero.name):
            continue
        # Weapon-focused heroes remain combat-capable without an ability item.
        if not hero.builder or any(
            defense.damaging and has_item(hero.item_name(defense))
            for defense in hero.defenses
        ):
            usable += 1
    return usable


ACTION_HERO = {hero.item_name(action): hero.name
               for hero in HERO_BY_KEY.values()
               for action in hero.defenses + hero.abilities}


def action_has_hero(state, item):
    if item is None or item.game != 'Dungeon Defenders':
        return True
    world = state.multiworld.worlds[item.player]
    hero = getattr(world, 'action_owners', ACTION_HERO).get(item.name)
    return hero is None or state.has(hero, item.player)


def install_hero_order_rule(location):
    """Recipient-side prerequisites, including DD1 actions in other games.

    Check the candidate during fill and the actual item during sphere searches.
    Wrapping an instance leaves other worlds' class implementations untouched.
    No physical pickup is blocked; this defines when the check is in logic.
    """
    if getattr(location, '_dd1_hero_order', False):
        return
    original_rule, original_fill = location.access_rule, location.can_fill

    def access_rule(state):
        return original_rule(state) and action_has_hero(state, location.item)

    def can_fill(state, item, check_access=True):
        # Original can_fill may test access using the item being replaced.
        # Temporarily supply the candidate, restoring it even on exceptions.
        previous = location.item
        try:
            location.item = item
            return ((not check_access or action_has_hero(state, item))
                    and original_fill(state, item, check_access))
        finally:
            location.item = previous

    location.access_rule = access_rule
    location.can_fill = can_fill
    location._dd1_hero_order = True
