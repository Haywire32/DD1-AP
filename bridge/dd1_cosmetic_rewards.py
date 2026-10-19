"""Base-game crystal indices; append-only to match the audited retail catalog."""

CRYSTAL_NAMES = (
    'Classic', 'Crystalline', 'Geode', 'Mystical', 'Cell', 'Molecular', 'Runic',
    'Landscaped', 'Waterfall', 'Eastern', 'Western', 'Fantasy', 'Goblet', 'Horned',
    "Pandora's Box", 'Book of Souls', 'Majestic Urn', 'Skulltacular!', 'Money',
    'Obelisk', 'Sky City', 'Bio Container', 'Fusion Core', 'Organic Goblet',
    "King's Crown", 'You Are Trendy',
)
CRYSTAL_ITEMS = tuple(f'{name} Crystal Skin' for name in CRYSTAL_NAMES)
GEAR_ITEM = 'Random Gear Drop'


def cosmetic_totals(received, item_ids):
    ids = [entry['item_id'] for entry in received]
    owned = set(ids)
    return (ids.count(item_ids[GEAR_ITEM]),
            sum(1 << index for index, name in enumerate(CRYSTAL_ITEMS)
                if item_ids[name] in owned))
