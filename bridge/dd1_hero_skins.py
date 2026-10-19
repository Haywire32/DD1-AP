"""Alternate costumes from the current DD1 hero templates; IDs are append-only.

The runtime additionally checks each live template's DLC requirement. Receiving
an AP costume is not evidence of a Steam license. Default costumes are excluded.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class HeroSkin:
    hero: str
    hero_name: str
    costume_id: int
    name: str
    app_id: int

    @property
    def item_name(self):
        return f'{self.name} Hero Skin ({self.hero_name})'

    @property
    def key(self):
        return f'{self.hero}.{self.costume_id}'


_DATA = (
    ('apprentice', 'Apprentice', (
        (100, 'Mummy', 202520), (101, 'Vampire', 202521), (102, 'Pilgrim', 203700),
        (103, 'Santa', 204380), (104, 'GW', 204388), (105, 'Leprechaun', 208540),
        (106, 'Jim Darkmagic', 202524), (107, 'Legendary Mage', 204384), (108, 'Super Legendary Mage', 204384))),
    ('squire', 'Squire', (
        (200, 'Pirate', 202520), (201, 'Death Knight', 202521), (202, 'Turkey', 203700),
        (203, 'Mrs. Santa', 204380), (204, 'Pants', 204387), (205, 'Mitt', 204388),
        (206, 'Bunny', 0), (207, 'Tycho', 202524), (208, 'Legendary Knight', 204384),
        (209, 'Super Legendary Knight', 204384), (210, 'Donald', 3228700))),
    ('huntress', 'Huntress', (
        (300, 'Witch', 202520), (301, 'Angel', 202521), (302, 'Native Princess', 203700),
        (303, "Santa's Little Helper", 204380), (304, 'Michelle', 204388), (305, 'TrapGirl', 208540),
        (306, 'Annarchy', 202524), (307, 'Legendary Huntress', 204384), (308, 'Super Legendary Huntress', 204384))),
    ('monk', 'Monk', (
        (400, 'Ninja', 202521), (401, 'Devil', 202520), (402, 'Conquistador', 203700),
        (403, 'Rudolph', 204380), (404, 'Cupid', 204387), (405, 'The Prez', 204388),
        (406, 'Cardboard Tube Samurai', 202524), (407, 'Legendary Monk', 204384),
        (408, 'Super Legendary Monk', 204384), (409, 'Elon', 3228700), (410, 'Devil Ninja', 0))),
    ('adept', 'Adept', ((801, 'Desert Princess', 204382), (802, 'Steampunk', 208540), (803, 'Magical Academy', 4849720))),
    ('countess', 'Countess', ((501, 'Queen of Hearts', 204387), (502, 'Mermaid', 204383), (503, 'Skeletal Warrior', 0))),
    ('ranger', 'Ranger', ((601, 'Assassin', 204381), (602, 'Outlander', 204381), (603, 'Tuxedo', 204387), (604, 'Abraham', 3228700))),
    ('initiate', 'Initiate', ((701, 'Cupidette', 204387), (702, 'Sky Captain', 204384), (703, 'Kamala', 3228700), (704, 'Ninja', 0))),
    ('barbarian', 'Barbarian', ((1001, 'Scottish Warrior', 208540), (1002, 'Amazon', 208542),
        (1003, 'Tavernkeep Imposter', 0), (1004, 'Santa Imposter', 204380), (1005, 'Pirate Tavernkeeper', 0))),
    ('series_ev', 'Series EV', ((1101, 'Bounty Hunter', 208543), (1102, 'Jetpacking Bounty Hunter', 208543),
        (1103, 'EV 1.5', 0), (1104, 'EV 1.75', 0), (1106, 'EV 1.80', 0), (1105, 'EV 1.85', 0))),
    ('summoner', 'Summoner', ((1801, 'Demoness', 208545),)),
    ('jester', 'Jester', ((145, 'Fool', 0), (146, 'Punk', 0), (147, 'Lover', 3462540))),
    ('hermit', 'Hermit', ((1901, 'Wooden Hermit', 3462540),)),
    ('gunwitch', 'Gunwitch', ((2001, 'Hatless Gunwitch', 0),)),
    ('warden', 'Warden', ((2101, 'Egyptian', 4259510),)),
    ('guardian', 'Guardian', ()),
)
HERO_SKINS = tuple(HeroSkin(hero, display, uid, name, app)
    for hero, display, rows in _DATA for uid, name, app in rows)
HERO_SKIN_ITEMS = {skin.item_name: skin.key for skin in HERO_SKINS}


def selected_skin_items(active_heroes):
    return tuple(s.item_name for s in HERO_SKINS if s.hero in active_heroes)


def unlocked_skin_keys(active_heroes, settings, received_ids, item_ids):
    return {s.key for s in HERO_SKINS if s.hero in active_heroes and (
        settings.hero_skins_unlocked or
        (settings.hero_skin_items and item_ids[s.item_name] in received_ids))}
