# Client behavior

The client uses the game folder selected by the player.
It connects to the selected Archipelago server and exchanges game state locally
through loopback connections and files in the TotalConversion folder.

The client writes seed settings and keeps separate character saves per seed.
Keep backups of your conversion folder. Local bridge traffic is not authenticated;
other programs running as your user can modify it.

Startup checks read packaged files and settings. They do not repair generated
engine settings automatically. Steam DLC ownership checks remain required.
