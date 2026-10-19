"""Append-only trap order shared by APTRAPS1 and the native runtime."""
TRAP_NAMES = ('Chicken!', 'Gold Rush', 'Rush Hour', 'Skill Jam',
              'Ready or Not', 'Ogre Surprise', 'Sudden Death')
TRAP_KEYS = ('chicken', 'gold_rush', 'rush_hour', 'skill_jam',
             'ready_or_not', 'ogre_surprise', 'sudden_death')


def replace_filler_with_traps(names, percentage, enabled, rng, eligible):
    """Replace only ordinary filler, preserving progression and cosmetic items."""
    if not 0 <= percentage <= 100:
        raise ValueError('Trap percentage must be between 0 and 100.')
    unknown = set(enabled) - set(TRAP_KEYS)
    if unknown:
        raise ValueError('Unknown traps: ' + ', '.join(sorted(unknown)))
    choices = [name for key, name in zip(TRAP_KEYS, TRAP_NAMES) if key in enabled]
    if percentage and not choices:
        raise ValueError('Select at least one enabled_traps entry when trap_percentage is above zero.')
    result = list(names)
    if not percentage:
        return result
    indices = [i for i, name in enumerate(result) if name in eligible]
    rng.shuffle(indices)
    bag = []
    for i in indices[:len(indices) * percentage // 100]:
        if not bag:
            bag = choices.copy()
            rng.shuffle(bag)
        result[i] = bag.pop()
    return result


def trap_snapshot(seed, received, item_ids):
    if not seed.startswith('dd1-') or any(c not in '0123456789abcdef' for c in seed[4:]) or len(seed) != 68:
        raise ValueError('Invalid trap seed identity.')
    counts = [0] * len(TRAP_NAMES)
    lookup = {item_ids[name]: i for i, name in enumerate(TRAP_NAMES)}
    for item in received:
        index = lookup.get(item['item_id'])
        if index is not None:
            counts[index] += 1
    if max(counts) > 1000000:
        raise ValueError('Trap count exceeds the supported limit.')
    return ('APTRAPS1|' + seed + '|' + ','.join(map(str, counts)) + '\r\n').encode('ascii')
