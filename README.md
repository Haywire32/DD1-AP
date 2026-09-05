# Dungeon Defenders Archipelago
An Archipelago randomizer for Dungeon Defenders 1 on Steam.
The mod randomizes available heroes, levels, defenses and abilities.
The goal is to beat a set number of levels to unlock the "The Summit" and beat the boss.
This mod is for Local play only.

### Current location checks
- Complete a wave
- Complete a level. One check for each difficulty: easy, medium, hard. Harder difficulties grants checks for the lower ones.

### Current items/rewards
- Level access
- The four basic heroes: Apprentice, Squire, Huntress and Monk
- Defenses
- Hero abilities
- Experience points
- Bank mana

### Download
[Download can be found here.](https://github.com/Haywire32/DD1-AP/releases/tag/v0.3.1)

# Installation guide
### Requirements
- Dungeon Defenders from Steam
- Dungeon Defenders Development Kit from Steam
- Archipelago 0.6.7 or newer

### Game install
1. Install/update both Dungeon Defenders and Dungeon Defenders Development Kit
   in Steam.
2. Open the install folder of both Dungeon Defenders and Dungeon Defenders Development Kit
3. Copy all files from \Steam\steamapps\common\Dungeon Defenders into Steam\steamapps\common\DungeonDefendersDevelopmentKit. 
   Select yes when asked to overwrite existing files.

### Mod install
1. Double-click dungeon_defenders.apworld to install it.
   Alternatively put the file into your \Archipelago\custom_worlds folder.
2. Copy the DD1ArchipelagoCurrent folder
   to: \Steam\steamapps\common\DungeonDefendersDevelopmentKit\TotalConversions

   The final path is ...\TotalConversions\DD1ArchipelagoCurrent.
4. Copy Dungeon Defenders.yaml to C:\Archipelago\Players. Edit its slot name
   and documented options, then generate normally.

### Play
Open Archipelago Launcher, select Dungeon Defenders Client, and enter the
server and slot. The game should launch automatically. 
Choose Play Local; online play is intentionally disabled.

# Feedback or questions
I'd love feedback on design choices and bugs in the [Dungeon Defenders channel](https://discord.com/channels/731205301247803413/1328369703810240593) in the [Archipelago discord](https://discord.gg/8Z65BR2)

The current version is still unstable and most likely has bugs.

### Future plans and ideas
- Game balance adjustments
- DLC heroes
- More checks and rewards

### Disclaimer
AI assistance was used for reverse engineering and hook implementation. Item and logic mapping, in-game testing, verification, and design decisions were done manually by me.
