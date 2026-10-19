"""Cosmetic tavern rewards. Order is permanent (item IDs and wire-mask bits)."""
THEME_NAMES = ('Jester Tavern Theme', 'Valentine Tavern Theme', 'Tropical Tavern Theme',
               'Christmas Tavern Theme', 'Outdoors Tavern Theme', 'Tinkers Tavern Theme',
               'Moonbase Tavern Theme', 'Aquanos Tavern Theme', 'Defense Tavern Theme',
               'Halloween Tavern Theme', 'Lava Tavern Theme')

# Retain retired IDs/mask bits so existing seeds cannot shift other rewards.
EXCLUDED_THEME_NAMES = ('Jester Tavern Theme', 'Halloween Tavern Theme')
AVAILABLE_THEME_NAMES = tuple(name for name in THEME_NAMES if name not in EXCLUDED_THEME_NAMES)


def add_theme_rewards(names, enabled, rng, eligible):
    result = list(names)
    if not enabled:
        return result
    indices = [i for i, name in enumerate(result) if name in eligible]
    if len(indices) < len(AVAILABLE_THEME_NAMES):
        raise ValueError('Tavern themes need 9 ordinary filler slots. Enable more checks or disable tavern_themes.')
    rng.shuffle(indices)
    for index, name in zip(indices, AVAILABLE_THEME_NAMES):
        result[index] = name
    return result


def theme_mask(enabled, received, item_ids):
    if not enabled:
        return 0
    received_ids = {item['item_id'] for item in received}
    return sum(1 << i for i, name in enumerate(THEME_NAMES)
               if name in AVAILABLE_THEME_NAMES and item_ids[name] in received_ids)


def theme_snapshot(seed, enabled, received, item_ids):
    if not seed.startswith('dd1-') or len(seed) != 68 or any(c not in '0123456789abcdef' for c in seed[4:]):
        raise ValueError('Invalid theme seed identity.')
    return f'APTHEMES1|{seed}|{int(bool(enabled))}|{theme_mask(enabled, received, item_ids)}\r\n'.encode('ascii')
