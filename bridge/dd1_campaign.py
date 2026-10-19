"""0.7.0 campaign route. Map identities and wave ranges are asset-audited."""
try:
    from .dd1_protocol import CAMPAIGN_MAPS
except ImportError:
    from dd1_protocol import CAMPAIGN_MAPS

BASE_MAPS = CAMPAIGN_MAPS[:12]
SHARD_TAGS = ('CAMPMF', 'CAMPAR', 'CAMPAQ', 'CAMPSC')
CD_TAG = 'CAMPCL'
# Separate IDs shared by client/event handling without importing AP's world.
ETERNIA_SHARD_ITEMS = {f'Eternia Shard from {name}': 9_200_010_000 + i
              for i, name in enumerate(('Mistymire Forest', 'Moraggo Desert Town', 'Aquanos', 'Sky City'))}
EXTRA_MAPS = CAMPAIGN_MAPS[12:]
FREE_MAPS = CAMPAIGN_MAPS[18:]
EXTRA_MAP_ITEMS = {m.name + ' Map': m.tag for m in EXTRA_MAPS if m.tag != CD_TAG}
# These are access/gear stages, not a forced item-receipt order.
MAP_STAGE = {m.tag: min(i // 4, 2) for i, m in enumerate(BASE_MAPS)}
MAP_STAGE.update(dict(zip(
    ('CAMPGC', 'CAMPMF', 'CAMPAR', 'CAMPAQ', 'CAMPSC', 'CAMPCL',
     'CDTCDD', 'CDTARC', 'CAMPPA', 'CAMPJ2', 'CDTCBB', 'CDTEMV', 'CDTCTP', 'CAMPMB'),
    (3, 4, 5, 6, 8, 10, 0, 4, 4, 7, 7, 9, 9, 9), strict=True)))
ACCESS_PREDECESSOR = {
    'CAMPGC': 'CAMPTS', 'CAMPMF': 'CAMPGC',
    'CDTARC': 'CAMPGC', 'CAMPPA': 'CAMPGC',
    'CAMPJ2': 'CAMPAQ', 'CDTCBB': 'CAMPJ2',
}
SHARD_PREDECESSOR = {'CAMPAR': 'CAMPMF', 'CAMPAQ': 'CAMPAR', 'CAMPSC': 'CAMPAQ'}
ENDGAME_BRANCHES = frozenset(('CDTEMV', 'CDTCTP', 'CAMPMB'))
LATE_GEAR_MAPS = frozenset(('CAMPJ2', 'CDTCBB', *ENDGAME_BRANCHES))


def enabled_maps(settings):
    if settings.completion_goal != 'crystalline_dimension':
        return BASE_MAPS
    return CAMPAIGN_MAPS if settings.extra_campaign_maps else CAMPAIGN_MAPS[:18]


def campaign_cleared(history, tag, difficulty):
    names = ('easy', 'medium', 'hard', 'insane', 'nightmare', 'ruthless')
    return any(history.get(f'dd1.campaign.{tag}.victory.{d}') for d in names[difficulty:])


def shards_cleared(history, difficulty):
    return all(campaign_cleared(history, tag, difficulty) for tag in SHARD_TAGS)


def eternia_shard_display_mask(settings, received_items):
    """-1 leaves vanilla cosmetics alone outside the randomized-shard goal."""
    if (settings.completion_goal != 'crystalline_dimension'
            or settings.crystalline_dimension_unlock != 'eternia_shards'):
        return -1
    received = {item['item_id'] for item in received_items}
    return sum(1 << index for index, item in enumerate(ETERNIA_SHARD_ITEMS.values())
               if item in received)


def cd_unlocked(history, difficulty, unlock_mode='shard_maps', received_items=()):
    if unlock_mode == 'shard_maps':
        return shards_cleared(history, difficulty)
    if unlock_mode == 'eternia_shards':
        received = {item['item_id'] for item in received_items}
        return set(ETERNIA_SHARD_ITEMS.values()) <= received
    raise ValueError('Unknown Crystalline Dimension unlock mode.')


def cd_goal_complete(history, difficulty, unlock_mode='shard_maps', received_items=()):
    return (cd_unlocked(history, difficulty, unlock_mode, received_items)
            and campaign_cleared(history, CD_TAG, difficulty))
