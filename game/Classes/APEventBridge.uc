class APEventBridge extends Info;

var private int EventSequence;
var private bool bBridgeReady;

function bool Initialize()
{
    if(Role != ROLE_Authority || WorldInfo.NetMode != NM_Standalone)
    {
        return false;
    }

    bBridgeReady = true;
    EmitEvent("session_start", string(WorldInfo.GetPackageName()), -1, "local_standalone");
    `log("AP:BRIDGE_READY mode=ONE_CLOSED_FILE_PER_EVENT");
    return true;
}

function EmitEvent(string EventType, string MapName, int WaveNumber, string Detail)
{
    local FileWriter EventWriter;

    if(!bBridgeReady)
    {
        return;
    }

    EventSequence++;
    EventWriter = Spawn(class'FileWriter');
    if(EventWriter == none)
    {
        `warn("AP:BRIDGE_EVENT_FAILED reason=SPAWN_FILE_WRITER sequence=" $ EventSequence);
        return;
    }

    // FWFT_User confines output to the engine-managed User directory. DD1's
    // old FileWriter does not expose its new length to another process until
    // CloseFile(), so every event gets a unique file that is closed at once.
    if(!EventWriter.OpenFile("DD1ArchipelagoEvent-" $ EventSequence, FWFT_User, "json", true, true))
    {
        `warn("AP:BRIDGE_EVENT_FAILED reason=OPEN_FILE sequence=" $ EventSequence);
        EventWriter.Destroy();
        return;
    }

    EventWriter.Logf("{\"protocol\":1,\"sequence\":" $ EventSequence $
        ",\"event\":\"" $ EventType $ "\",\"map\":\"" $ MapName $
        "\",\"wave\":" $ WaveNumber $ ",\"detail\":\"" $ Detail $ "\"}");
    EventWriter.CloseFile();
    `log("AP:BRIDGE_EVENT_WRITTEN sequence=" $ EventSequence $ " file=" $ EventWriter.Filename);
    EventWriter.Destroy();
}

defaultproperties
{
    bAlwaysRelevant=false
    RemoteRole=ROLE_None
}
