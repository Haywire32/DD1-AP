"""Build identity, independent of the seed's Skill Shuffle setting.

The regular conversion supports normal and shuffled seeds. The private flag
only isolates historical prototype folders, bridge ports and save profiles.
"""

PRIVATE_CHAOS_BUILD = False
TC_DIRECTORY = "DD1ArchipelagoChaos" if PRIVATE_CHAOS_BUILD else "DD1ArchipelagoCurrent"
STATE_DIRECTORY = "dd1_archipelago_chaos" if PRIVATE_CHAOS_BUILD else "dd1_archipelago"
LIVE_BRIDGE_PORT = 38283 if PRIVATE_CHAOS_BUILD else 38282
CLIENT_TITLE = "Dungeon Defenders Chaos Test" if PRIVATE_CHAOS_BUILD else "Dungeon Defenders Client"
