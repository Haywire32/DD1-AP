"""Seed-generated Skill Shuffle loadouts.

Item names remain source-qualified; their owning/usable hero follows the seed
assignment. A seed mapping is authoritative, never rerolled by the client.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, replace
import hashlib
import json
import random
from .heroes import HERO_BY_KEY, is_starting_defense, Opening
from .hero_logic import HIGH_DIFFICULTY_SUPPORT, area_requirements
from itertools import combinations
from collections import Counter

SCHEMA = 3

# These use native hero/weapon callbacks or hero-specific animation notifies.
# Keep them on the original hero instead of adding fragile cross-hero adapters.
# APChaosConfig.uc enforces this same list at the game boundary (parity tested).
LEGACY_NATIVE_ONLY_ACTIONS = frozenset({
    'apprentice.overcharge',
    'squire.circular_slice',
    'countess.joust',
    'series_ev.proton_charge_blast',
    'barbarian.battle_leap',
    'barbarian.battle_pound',
    'barbarian.tornado_stance',
    'barbarian.lightning_stance',
    'barbarian.siphon_stance',
    'barbarian.turtle_stance',
    'barbarian.hawk_stance',
})
NATIVE_ONLY_ACTIONS = (LEGACY_NATIVE_ONLY_ACTIONS - {'barbarian.turtle_stance'}) | {'summoner.phase_shift_overlord'}


def recipient_allowed(source, action, recipient, schema=SCHEMA):
    native_only = LEGACY_NATIVE_ONLY_ACTIONS if schema == 2 else NATIVE_ONLY_ACTIONS
    return source == recipient or f'{source}.{action}' not in native_only


@dataclass(frozen=True)
class Assignment:
    source: str
    action: str
    recipient: str
    slot: int

    @property
    def key(self):
        return f"{self.source}.{self.action}"

    @property
    def definition(self):
        hero = HERO_BY_KEY[self.source]
        return next(a for a in hero.defenses + hero.abilities if a.key == self.action)

    @property
    def item(self):
        return HERO_BY_KEY[self.source].item_name(self.definition)


def recipient_item_names(assignments):
    """Slot-local display aliases, never replacements for network item IDs.

    A hero can receive both counterpart versions of one defense. Qualify only
    those collisions so that every unlock in this loadout remains identifiable.
    """
    counts = Counter((a.definition.name, a.recipient) for a in assignments)
    names = {}
    for a in assignments:
        name = f'{a.definition.name} ({HERO_BY_KEY[a.recipient].name})'
        if counts[a.definition.name, a.recipient] > 1:
            name += f' [{HERO_BY_KEY[a.source].name} version]'
        names[a.item] = name
    return names


def roster(keys):
    selected = tuple(sorted(keys))
    if not selected or len(set(selected)) != len(selected):
        raise ValueError("Select a non-empty roster without duplicate heroes.")
    if any(key not in HERO_BY_KEY for key in selected):
        raise ValueError("Unknown hero in roster.")
    return selected


def action_kind(hero_key, action_key):
    return 'defense' if any(a.key == action_key for a in HERO_BY_KEY[hero_key].defenses) else 'ability'


def validate_mode(mode):
    if mode not in ('mixed', 'separate'):
        raise ValueError('Unknown Chaos shuffle mode')
    return mode


def generate(seed: str, player: int, keys, mode='mixed', schema=SCHEMA):
    """One complete permutation; preserve each recipient's original slot count.

    Reserve native-only actions first, then shuffle the transferable pool.
    Runtime preflight independently rejects incompatible assignments.
    """
    keys = roster(keys)
    if schema not in (2, SCHEMA) or (schema == 2 and 'summoner' in keys):
        raise ValueError('Unsupported Chaos schema/roster')
    native_only = LEGACY_NATIVE_ONLY_ACTIONS if schema == 2 else NATIVE_ONLY_ACTIONS
    validate_mode(mode)
    if player < 1:
        raise ValueError("Player must be a positive AP slot number.")
    # Keep the existing mixed-mode identity byte-for-byte for current seeds.
    identity_parts = [schema, str(seed), player, keys]
    if mode != 'mixed':
        identity_parts.append(mode)
    identity = json.dumps(identity_parts, separators=(",", ":"))
    rng = random.Random(int.from_bytes(hashlib.sha256(identity.encode()).digest(), "big"))
    actions = [(key, a.key) for key in keys
               for a in HERO_BY_KEY[key].defenses + HERO_BY_KEY[key].abilities
               if f'{key}.{a.key}' not in native_only]
    rng.shuffle(actions)
    pools = {'mixed': actions}
    if mode == 'separate':
        pools = {kind: [pair for pair in actions if action_kind(*pair) == kind]
                 for kind in ('defense', 'ability')}
    result = []
    for key in keys:
        for slot, native in enumerate(HERO_BY_KEY[key].defenses + HERO_BY_KEY[key].abilities):
            source, action = ((key, native.key) if f'{key}.{native.key}' in native_only
                              else pools['mixed' if mode == 'mixed' else action_kind(key, native.key)].pop())
            result.append(Assignment(source, action, key, slot))
    # Preserve the existing usable-hero principle: a builder cannot be assigned
    # only support/non-building actions and become permanently uncountable even
    # with every item. Swap within this permutation; do not add/remove items.
    for key in keys:
        if not HERO_BY_KEY[key].builder or any(a.recipient == key and a.definition.damaging for a in result):
            continue
        counts = {k: sum(a.recipient == k and a.definition.damaging for a in result) for k in keys}
        donors = [i for i, a in enumerate(result) if a.definition.damaging
                  and (counts[a.recipient] > 1 or not HERO_BY_KEY[a.recipient].builder)]
        targets = [i for i, a in enumerate(result) if a.recipient == key and a.key not in native_only
                   and (mode == 'mixed' or action_kind(a.source, a.action) == 'defense')]
        if mode == 'separate':
            donors = [i for i in donors if action_kind(result[i].source, result[i].action) == 'defense']
        if not donors or not targets:
            raise ValueError("Roster cannot satisfy usable-hero requirements with this action pool.")
        i, j = rng.choice(donors), rng.choice(targets)
        a, b = result[i], result[j]
        result[i] = replace(b, recipient=a.recipient, slot=a.slot)
        result[j] = replace(a, recipient=b.recipient, slot=b.slot)
    return tuple(result)


def encode(seed, player, keys, assignments, mode='mixed'):
    validate_mode(mode)
    document = {"schema": SCHEMA, "seed": str(seed), "player": player,
                "heroes": list(roster(keys)), "assignments": [asdict(a) for a in assignments]}
    if mode != 'mixed':
        document['shuffle_mode'] = mode
    decode(document, seed, player)  # Refuse incomplete/ambiguous payloads before export.
    return document


def decode(document, seed, player):
    required = {'schema', 'seed', 'player', 'heroes', 'assignments'}
    if not isinstance(document, dict) or set(document) not in (required, required | {'shuffle_mode'}):
        raise ValueError('Invalid Chaos document fields')
    mode = validate_mode(document.get('shuffle_mode', 'mixed'))
    if type(document['schema']) is not int or type(document['player']) is not int or type(player) is not int:
        raise ValueError('Chaos schema and player must be integers')
    if not isinstance(document['heroes'], list) or not all(isinstance(k, str) for k in document['heroes']):
        raise ValueError('Invalid Chaos hero list')
    if not isinstance(document['assignments'], list):
        raise ValueError('Invalid Chaos assignments')
    for row in document['assignments']:
        if (not isinstance(row, dict) or set(row) != {'source', 'action', 'recipient', 'slot'} or
                any(not isinstance(row[key], str) for key in ('source', 'action', 'recipient')) or
                type(row['slot']) is not int):
            raise ValueError('Invalid Chaos assignment fields')
    if document['schema'] not in (2, SCHEMA) or (document.get("seed"), document.get("player")) != (str(seed), player):
        raise ValueError("Wrong schema, seed or player; do not reuse another slot's mapping.")
    keys = roster(document["heroes"])
    if document['schema'] == 2 and 'summoner' in keys:
        raise ValueError('Legacy Chaos mapping cannot include Summoner')
    assignments = tuple(Assignment(**a) for a in document["assignments"])
    expected = {(k, a.key) for k in keys for a in HERO_BY_KEY[k].defenses + HERO_BY_KEY[k].abilities}
    expected_slots = {(k, i) for k in keys for i in range(len(HERO_BY_KEY[k].defenses + HERO_BY_KEY[k].abilities))}
    if (len(assignments) != len(expected) or
            {(a.source, a.action) for a in assignments} != expected or
            {(a.recipient, a.slot) for a in assignments} != expected_slots):
        raise ValueError("Mapping must contain every selected action and recipient slot exactly once.")
    if any(not recipient_allowed(a.source, a.action, a.recipient, document['schema']) for a in assignments):
        raise ValueError('A native-only action was assigned to an incompatible hero.')
    if mode == 'separate':
        for a in assignments:
            native = (HERO_BY_KEY[a.recipient].defenses + HERO_BY_KEY[a.recipient].abilities)[a.slot]
            if action_kind(a.source, a.action) != action_kind(a.recipient, native.key):
                raise ValueError('Separate shuffle placed an action in the wrong slot category.')
    return assignments


def action_has_recipient(assignment, has_item):
    return has_item(HERO_BY_KEY[assignment.recipient].name)


def install_recipient_order_rule(location, assignments_by_player):
    """Prototype equivalent of existing crossworld hero-before-action wrapper.

    Recipient AP slot, NOT the location's owner, determines the loadout. Supply
    every participating chaos slot's mapping before fill. Normal-world rules
    remain on their original wrapper; do not layer this over the donor rule.
    """
    if getattr(location, "_chaos_order_installed", False):
        return
    owners = {player: {a.item: HERO_BY_KEY[a.recipient].name for a in assignments}
              for player, assignments in assignments_by_player.items()}
    original_access, original_fill = location.access_rule, location.can_fill

    def allowed(state, item):
        if item is None or item.game != "Dungeon Defenders":
            return True
        hero = owners.get(item.player, {}).get(item.name)
        return hero is None or state.has(hero, item.player)

    def access(state):
        return original_access(state) and allowed(state, location.item)

    def can_fill(state, item, check_access=True):
        previous = location.item
        try:
            location.item = item
            return ((not check_access or allowed(state, item))
                    and original_fill(state, item, check_access))
        finally:
            location.item = previous

    location.access_rule, location.can_fill = access, can_fill
    location._chaos_order_installed = True


def support_groups(keys, assignments):
    keys = roster(keys)
    owners = {(a.source, a.definition.name): a for a in assignments}
    groups = []
    for group in HIGH_DIFFICULTY_SUPPORT:
        pairs = []
        for source, name in group:
            if source in keys:
                a = owners[source, name]
                pairs.append((HERO_BY_KEY[a.recipient].name, a.item))
        if pairs:
            groups.append(tuple(pairs))
    return tuple(groups)


def has_support(keys, assignments, has_item):
    return all(any(has_item(hero) and has_item(item) for hero, item in group)
               for group in support_groups(keys, assignments))


def usable_count(keys, assignments, has_item):
    return sum(has_item(HERO_BY_KEY[key].name) and
               (not HERO_BY_KEY[key].builder or any(
                   a.recipient == key and a.definition.damaging and has_item(a.item)
                   for a in assignments)) for key in keys)


def starting_pairs(assignments):
    # Generator must choose the opening HERO from these recipients, then grant
    # that assigned defense. Fixed start requests need validation, not rerolls.
    return tuple((HERO_BY_KEY[a.recipient].name, a.item) for a in assignments
                 if is_starting_defense(a.definition)
                 and a.definition.anti_air and a.definition.generic_damage)


def missing_licenses(keys, native_query):
    # True means confirmed ownership; unknown/failed checks must not pass.
    base = {"apprentice", "squire", "huntress", "monk"}
    return tuple(key for key in roster(keys) if key not in base and native_query(key) is not True)


def runtime_preflight(assignments, keys, native_query, tested_pairs):
    missing = missing_licenses(keys, native_query)
    unsupported = tuple(a.key + " -> " + a.recipient for a in assignments
                        if (a.key, a.recipient) not in tested_pairs)
    return {"can_apply": not missing and not unsupported,
            "missing_dlc": missing, "unsupported": unsupported}


def choose_assigned_opening(keys, assignments, rng):
    """Apply the old opening guarantees to the seed's recipients, not donors."""
    all_plans = {}
    for key in keys:
        hero = HERO_BY_KEY[key]
        firsts = [a for a in assignments if a.recipient == key and
                  ((is_starting_defense(a.definition)
                    and (key != 'summoner' or a.definition.generic_damage)) or
                   (not hero.builder and a.definition in HERO_BY_KEY[a.source].abilities))]
        plans = []
        for first in firsts:
            for second in keys:
                if second == key:
                    continue
                candidates = [a for a in assignments if a.recipient in (key, second)
                              and a.item != first.item
                              and a.definition in HERO_BY_KEY[a.source].defenses]
                for left, right in combinations(candidates, 2):
                    if HERO_BY_KEY[second].builder and not any(
                            a.recipient == second and a.definition.damaging for a in (left, right)):
                        continue
                    # Provide affordable damage by wave 3 if the wave-1 reward
                    # was an ability. Both candidate recipients are unlocked.
                    if not is_starting_defense(left.definition) and is_starting_defense(right.definition):
                        left, right = right, left
                    if not is_starting_defense(left.definition) and not is_starting_defense(first.definition):
                        continue
                    tools = [a for a in (first, left, right)
                             if a.definition in HERO_BY_KEY[a.source].defenses]
                    if not any(a.definition.anti_air for a in tools):
                        continue
                    if hero.builder and HERO_BY_KEY[second].builder and not any(
                            a.definition.generic_damage for a in tools):
                        continue
                    plans.append((first, second, left, right,
                                  next(a.item for a in tools if a.definition.anti_air)))
        if not plans:
            raise ValueError(f"Assignment has no safe opening for {hero.name}")
        all_plans[key] = plans
    key = rng.choice(tuple(keys))
    first, second, left, right, anti_air = rng.choice(all_plans[key])
    # Summoner has no ordinary weapon attack to earn its first defense. Use
    # the existing precollected starter slot, but take the defense from this
    # seed's assigned kit rather than forcing a native Summoner minion. Require
    # non-elemental damage: Summoner cannot shoot an immune enemy itself.
    return Opening(key, second, None if key == 'summoner' else first.item,
                   first.item if key == 'summoner' else None,
                   (left.item, right.item), anti_air)


def generate_for_world(keys, player, rng, mode='mixed'):
    """Generation-time constraints only. Client never retries or rerolls.

    Do not exclude a selected starter to disguise an impossible assignment.
    Instead choose a complete mapping in which every selected starter works.
    """
    keys = roster(keys)
    for _ in range(128):
        token = f"{rng.getrandbits(128):032x}"
        assignments = generate(token, player, keys, mode=mode)
        try:
            opening = choose_assigned_opening(keys, assignments, rng)
        except ValueError:
            continue
        return encode(token, player, keys, assignments, mode=mode), assignments, opening
    raise ValueError("Cannot make a safe opening for this Chaos roster. No heroes were removed.")


def validate_slot_mapping(slot_data, player):
    document = slot_data.get('chaos_loadout')
    if (document is not None) != (slot_data.get('dd1_slot_data_version') in (1001, 1002, 1003)):
        raise ValueError('Skill Shuffle requires its matching slot-data version')
    if document is None:
        return ()
    if not isinstance(document, dict):
        raise ValueError('Invalid Chaos loadout document')
    token = document.get('seed')
    if not isinstance(token, str) or len(token) != 32 or any(c not in '0123456789abcdef' for c in token):
        raise ValueError('Invalid Chaos mapping identity')
    assignments = decode(document, token, player)
    if roster(slot_data.get('active_heroes', ())) != roster(document['heroes']):
        raise ValueError('Chaos mapping does not match this slot roster')
    expected = generate(token, player, document['heroes'], mode=document.get('shuffle_mode', 'mixed'), schema=document['schema'])
    if sorted(assignments, key=lambda a: (a.recipient, a.slot)) != sorted(expected, key=lambda a: (a.recipient, a.slot)):
        raise ValueError('Chaos mapping contents do not match their identity')
    return assignments


def config_lines(slot_data, player, seed_identity):
    """Emit only catalog-validated identifiers, never seed-provided asset paths."""
    assignments = validate_slot_mapping(slot_data, player)
    if not assignments:
        return ['bChaosLoadouts=False', 'ChaosMappingToken=', 'ChaosPlayerSlot=0']
    document = slot_data['chaos_loadout']
    separate = document.get('shuffle_mode', 'mixed') == 'separate'
    native_schema = (5 if separate else 4) if document['schema'] == SCHEMA else (3 if separate else 2)
    lines = ['bChaosLoadouts=True', f"ChaosMappingToken={document['seed']}", f'ChaosPlayerSlot={player}', '',
             '[DD1Archipelago.APChaosConfig]', f'Schema={native_schema}', f"MappingToken={document['seed']}",
             f'SeedIdentity={seed_identity}', f'PlayerSlot={player}']
    lines.extend(f'ActiveHeroes={key}' for key in document['heroes'])
    for a in assignments:
        target = ''
        if separate or native_schema >= 4:
            hero = HERO_BY_KEY[a.recipient]
            target = f',RecipientAction="{(hero.defenses + hero.abilities)[a.slot].key}"'
        lines.append(f'Assignments=(SourceHero="{a.source}",SourceAction="{a.action}",RecipientHero="{a.recipient}",ActionSlot={a.slot}{target})')
    return lines
