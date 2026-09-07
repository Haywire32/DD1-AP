class APEventBridge extends Info config(DD1ArchipelagoBridgeDiagnostics);

// FileWriter.OpenFile fails in retail. Keep checks in config until the client has
// durably recorded them; pending entries survive disconnects and map travel.
var config array<string> PendingEvents;
var private bool bBridgeReady;
var config string LastEventWriteStatus;

function bool Initialize()
{
    if(Role != ROLE_Authority || WorldInfo.NetMode != NM_Standalone)
    {
        return false;
    }

    bBridgeReady = true;
    LastEventWriteStatus = "ready_local_journal";
    PersistJournal();
    return true;
}

function EmitEvent(string EventType, string MapName, int WaveNumber, string Detail)
{
    local APGameInfo APGame;
    local string Payload;

    if(!bBridgeReady)
    {
        return;
    }

    APGame = APGameInfo(WorldInfo.Game);
    if(APGame == none || !APGame.CanEmitAPGameplayEvents())
    {
        `warn("AP:BRIDGE_EVENT_BLOCKED reason=hero_permissions_unavailable event=" $ EventType);
        return;
    }

    if(EventType != "wave_complete" && EventType != "level_victory")
        return;
    if(APGame.UnlockState == none || APGame.UnlockState.SeedIdentity == "")
        return;
    if(InStr(MapName, "|") != -1 || InStr(Detail, "|") != -1)
        return;
    Payload = APGame.UnlockState.SeedIdentity $ "|" $ EventType $ "|" $
        MapName $ "|" $ WaveNumber $ "|" $ Detail;
    if(PendingEvents.Find(Payload) != INDEX_NONE)
        return;
    PendingEvents.AddItem(Payload);
    LastEventWriteStatus = "queued:" $ Payload;
    PersistJournal();
    if(APGame.InboundLink != none && APGame.InboundLink.IsConnected())
        APGame.InboundLink.SendPendingEvent();
}

function string NextPendingEvent(string SeedIdentity)
{
    local string Payload;
    if(SeedIdentity == "")
        return "";
    foreach PendingEvents(Payload)
        if(Left(Payload, Len(SeedIdentity) + 1) == (SeedIdentity $ "|"))
            return Payload;
    return "";
}

function AcknowledgeEvent(string Payload)
{
    if(PendingEvents.Find(Payload) == INDEX_NONE)
        return;
    PendingEvents.RemoveItem(Payload);
    LastEventWriteStatus = "acknowledged:" $ Payload;
    PersistJournal();
}

function PersistJournal()
{
    // A later map spawns a new actor from the class defaults. Keep those in
    // sync too; do not depend on native SaveConfig refreshing live defaults.
    default.PendingEvents = PendingEvents;
    default.LastEventWriteStatus = LastEventWriteStatus;
    SaveConfig();
}

defaultproperties
{
    bAlwaysRelevant=false
    RemoteRole=ROLE_None
}
