"""Stable shop locations and seed-bound purchase bookkeeping."""
try:
    from .dd1_content import MAPS
except ImportError:
    from dd1_content import MAPS

SHOP_BASE = 9_140_000_000
SHOP_COUNT = 36
LEGACY_SHOP_COUNT = 27
PRICES = ((20_000, 30_000, 50_000), (75_000, 100_000, 150_000),
          (250_000, 350_000, 500_000), (5_000_000, 10_000_000, 20_000_000))
MAP_REQUIREMENTS = (3, 5, 7, 12)


def shop_count(settings):
    get = settings.get if isinstance(settings, dict) else lambda key, default: getattr(settings, key, default)
    if not get('shopsanity', False):
        return 0
    platinum = get('platinum_shop', False) and get('completion_goal', '') == 'crystalline_dimension'
    return SHOP_COUNT if platinum else LEGACY_SHOP_COUNT


def shop_parts(index):
    if type(index) is not int or not 0 <= index < SHOP_COUNT:
        raise ValueError('Invalid tavern shop purchase.')
    return index // 9, index // 3 % 3, index % 3


def shop_price(index):
    category, slot, _ = shop_parts(index)
    return PRICES[category][slot]


def completed_maps(victories):
    return sum(any(key.startswith(f'dd1.campaign.{m.tag}.victory.') for key in victories)
               for m in MAPS)


def remaining_maps(index, cleared):
    return max(0, MAP_REQUIREMENTS[shop_parts(index)[0]] - cleared)


def purchase_available(index, cleared, bought):
    _, _, stage = shop_parts(index)
    return (index not in bought and remaining_maps(index, cleared) == 0
            and all(previous in bought for previous in range(index - stage, index)))
