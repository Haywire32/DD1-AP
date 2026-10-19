"""Generation-only combat tiers. No map IDs, runtime locks or roster edits.

Source: Gato's DD1 AP Map Order Plan.xlsx, Sheet1 A4:J26, plus Oct 2
clarifications: CD 6/7/9/10, pre-boss Palantir/Akatiti one tier earlier,
Oct 3 feedback: later Survival waves +1 only at campaign tiers 1-6;
tier 7+ and Embermount +0. Survival never increases farming gear tiers.
"""

# Easy/Medium/Hard, Insane, Nightmare, Ruthless (victory tiers).
CAMPAIGN_TIERS = {
    'CAMPDW': (1, 2, 5, 9), 'CAMPFF': (1, 2, 5, 9),
    'CAMPMQ': (1, 2, 5, 9), 'CAMPAL': (1, 2, 5, 9),
    'CAMPSQ': (2, 3, 5, 9), 'CAMPCA': (2, 3, 5, 9),
    'CAMPHC': (2, 3, 5, 9), 'CAMPTR': (2, 3, 6, 10),
    'CAMPRG': (3, 4, 6, 9), 'CAMPRP': (3, 4, 6, 9),
    'CAMPES': (3, 4, 6, 9), 'CAMPTS': (3, 4, 6, 10),
    'CDTCDD': (3, 4, 6, 9),
    'CAMPGC': (4, 5, 7, 10), 'CDTARC': (4, 5, 7, 9),
    'CAMPMF': (4, 5, 7, 10), 'CAMPAR': (4, 5, 7, 10),
    'CAMPAQ': (5, 6, 8, 10), 'CAMPSC': (5, 6, 8, 10),
    'CDTCBB': (5, 6, 8, 10), 'CAMPMB': (5, 6, 8, 10),
    'CAMPPA': (6, 7, 9, 10), 'CAMPJ2': (6, 7, 9, 10),
    'CDTEMV': (6, 7, 9, 10), 'CDTCTP': (6, 7, 9, 10),
    'CAMPCL': (6, 7, 9, 10),
}
CHALLENGE_TIERS = {
    'SPECDW': (3, 4, 6, 10), 'SPECFF': (1, 2, 5, 9),
    'SPECMQ': (1, 2, 5, 9), 'SPECAL': (1, 2, 5, 9),
    'SPECSQ': (3, 4, 6, 10), 'SPECCA': (2, 3, 6, 10),
    'SPECHC': (4, 5, 7, 10), 'SPECTR': (2, 3, 5, 9),
    'SPECRG': (3, 4, 6, 9), 'SPECRP': (4, 5, 7, 10),
    'SPECES': (3, 4, 6, 10), 'SPECTS': (3, 4, 6, 9),
}
PRE_BOSS_MAPS = frozenset(('CAMPPA', 'CAMPJ2'))
# Keep base-map placement areas (0/1/2), use the revised baseline for extras.
MAP_STAGE = {tag: tiers[0] - 1 for tag, tiers in CAMPAIGN_TIERS.items()}
LATE_BASE = ('CAMPRG', 'CAMPRP', 'CAMPES')
INSANE_FARM_MAPS = ('CAMPAQ', 'CAMPSC', 'CDTCBB', 'CAMPMB')

# Logical access edges only. The four victories still unlock CD in map mode,
# but never prevent entering another Shards map on a lower farming difficulty.
PREDECESSORS = {
    'CAMPGC': 'CAMPTS', 'CAMPMF': 'CAMPGC', 'CDTARC': 'CAMPGC',
    'CAMPAR': 'CAMPMF', 'CAMPAQ': 'CAMPAR', 'CAMPSC': 'CAMPAQ',
    'CDTCBB': 'CAMPAQ', 'CAMPMB': 'CAMPAQ', 'CAMPPA': 'CAMPAQ',
    'CAMPJ2': 'CAMPAQ', 'CDTEMV': 'CAMPSC', 'CDTCTP': 'CAMPSC',
}


def difficulty_column(difficulty):
    if not 0 <= difficulty <= 5:
        raise ValueError('Invalid difficulty')
    return max(0, difficulty - 2)


def combat_tier(tag, difficulty, mode='campaign', wave=0, victory=True):
    column = difficulty_column(difficulty)
    if mode == 'challenge':
        return CHALLENGE_TIERS[tag][column]
    tier = CAMPAIGN_TIERS[tag][column]
    if mode == 'survival':
        return tier + int(tag != 'CDTEMV' and tier <= 6 and wave > 10)
    if tag in PRE_BOSS_MAPS and not victory:
        tier -= 1
    return tier


def gear_event(tier):
    return f'Can Farm Tier {tier} Campaign Gear'


def difficulty_deadline(tier):
    return 5 if tier >= 9 else 4 if tier >= 6 else 3 if tier >= 4 else 2 if tier >= 2 else 0
