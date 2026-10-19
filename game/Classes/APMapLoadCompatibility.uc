// TotalConversions intentionally run official retail maps with custom scripts.
// Native SetGameInfo calls SetGameType BEFORE its official-map warning; InitGame
// runs AFTER it. Only adjust the live world's marker across that narrow window.
class APMapLoadCompatibility extends Object config(DD1ArchipelagoMapLoadDiagnostics);

var private WorldInfo PendingWorld;
var config string LastPreparedMap;
var config string LastRestoredMap;
var config string LastAttempt;
var config array<string> RecentAttempts;

static function string MapPackageName(string MapName)
{
    // Retail travel URLs include .udk; WorldInfo returns the package basename.
    // Only remove known map extensions, never accept partial/prefix matches.
    if(Right(Caps(MapName), 4) == ".UDK" || Right(Caps(MapName), 4) == ".UPK")
        return Left(MapName, Len(MapName) - 4);
    return MapName;
}

static function Prepare(string MapName)
{
    local WorldInfo W;
    W = class'Engine'.static.GetCurrentWorldInfo();
    default.LastAttempt = "requested=" $ MapName $ " world=" $ PathName(W);
    if(W != none)
        default.LastAttempt $= " map=" $ W.GetMapName(true) $ " game=" $ PathName(W.Game) $
            " net=" $ W.NetMode $ " official=" $ W.bOfficialMap;
    default.RecentAttempts.AddItem(default.LastAttempt);
    if(default.RecentAttempts.Length > 12) default.RecentAttempts.Remove(0, 1);
    StaticSaveConfig();
    if(W == none || W.NetMode != NM_Standalone || W.Game != none || !W.bOfficialMap)
        return;
    // Never touch the previous world during game-class preloading, even when
    // restarting the same map. Its Game already exists; the new world's does not.
    if(!(MapPackageName(W.GetMapName(true)) ~= MapPackageName(MapName)))
        return;
    if(default.PendingWorld != none && default.PendingWorld != W)
        Restore(default.PendingWorld);
    default.PendingWorld = W;
    W.bOfficialMap = false;
    default.LastPreparedMap = W.GetMapName(true);
    StaticSaveConfig();
    `log("AP:MAP_LOAD_COMPAT prepared=" $ W.GetMapName(true));
}

static function Restore(WorldInfo W)
{
    if(W == none || default.PendingWorld != W)
        return;
    W.bOfficialMap = true;
    default.PendingWorld = none;
    default.LastRestoredMap = W.GetMapName(true);
    StaticSaveConfig();
    `log("AP:MAP_LOAD_COMPAT restored=" $ W.GetMapName(true));
}
