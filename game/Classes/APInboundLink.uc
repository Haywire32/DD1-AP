class APInboundLink extends TcpLink;

var APGameRuntime OwnerGame;
var int BridgePort;
var bool bHasBoundPort;
var float LastResponseTime;
var bool bSnapshotAccepted;
var string LastSentEvent;

function SendPacket(string Packet)
{
    SendText(Packet);
}

function Initialize(APGameRuntime NewOwner)
{
    OwnerGame = NewOwner;
    if(class'APBuildProfile'.static.IsPrivateChaosBuild()) BridgePort=38283;
    LinkMode = MODE_Line;
    ReceiveMode = RMODE_Event;
    InLineMode = LMODE_auto;
    OutLineMode = LMODE_UNIX;
    ConnectToLocalClient();
    SetTimer(1.0, true, 'MaintainLocalConnection');
}

function MaintainLocalConnection()
{
    if(OwnerGame == none || WorldInfo.NetMode != NM_Standalone)
        return;

    if(IsConnected())
    {
        if(WorldInfo.RealTimeSeconds - LastResponseTime > 15.0)
        {
            Close();
            return;
        }
        SendPacket("DD1PING1");
        SendPendingEvent();
    }
    else
    {
        ConnectToLocalClient();
    }
}

function ConnectToLocalClient()
{
    local IpAddr Address;

    if(OwnerGame == none || WorldInfo.NetMode != NM_Standalone || IsConnected())
        return;

    if(!StringToIpAddr("127.0.0.1", Address))
        return;

    Address.Port = BridgePort;
    if(!bHasBoundPort && BindPort() == 0)
    {
        `warn("AP:LIVE_LINK_BIND_FAILED");
        SetTimer(1.0, false, 'ConnectToLocalClient');
        return;
    }
    bHasBoundPort = true;
    if(!Open(Address))
    {
        `warn("AP:LIVE_LINK_OPEN_FAILED address=127.0.0.1 port=" $ BridgePort);
        SetTimer(1.0, false, 'ConnectToLocalClient');
    }
}

event Opened()
{
    bSnapshotAccepted = false;
    LastSentEvent = "";
    LastResponseTime = WorldInfo.RealTimeSeconds;
    `log("AP:LIVE_LINK_CONNECTED address=127.0.0.1 port=" $ BridgePort);
    SendPacket("DD1HELLO10");
}

function SendPendingEvent()
{
    if(!bSnapshotAccepted || OwnerGame == none || OwnerGame.EventBridge == none ||
        OwnerGame.UnlockState == none || WorldInfo.NetMode != NM_Standalone)
        return;
    LastSentEvent = OwnerGame.EventBridge.NextPendingEvent(OwnerGame.UnlockState.SeedIdentity);
    if(LastSentEvent != "")
        SendPacket("DD1EVENT2|" $ LastSentEvent);
}

event ReceivedLine(string Line)
{
    LastResponseTime = WorldInfo.RealTimeSeconds;
    if(Line == "DD1PONG1")
        return;
    if(Left(Line,10) == "APTHEMES1|")
    {
        if(bSnapshotAccepted && OwnerGame != none && OwnerGame.Themes != none)
            OwnerGame.Themes.ApplySnapshot(Line);
        return;
    }
    if(Left(Line,9) == "APTRAPS1|")
    {
        if(bSnapshotAccepted && OwnerGame != none && OwnerGame.Traps != none)
            OwnerGame.Traps.ApplySnapshot(Line);
        return;
    }
    if(Left(Line, 9) == "APDEATH1|")
    {
        if(bSnapshotAccepted && OwnerGame != none && OwnerGame.DeathLink != none)
            OwnerGame.DeathLink.ApplyLiveInput(Line);
        return;
    }
    if(Left(Line, 8) == "APGEAR1|")
    {
        if(bSnapshotAccepted && OwnerGame != none)
            OwnerGame.ApplyGearSettingsSnapshot(Line);
        return;
    }
    if(Left(Line, 10) == "APSHARDS1|")
    {
        if(bSnapshotAccepted && OwnerGame != none)
            OwnerGame.ApplyShardDisplaySnapshot(Line);
        return;
    }
    if(Left(Line, 8) == "APSHOP1|" || Left(Line, 8) == "APSHOP2|" || Left(Line, 12) == "APSHOPITEM1|")
    {
        if(OwnerGame != none && OwnerGame.UnlockState != none)
            APViewportClient(class'DunDefViewportClient'.static.GetViewportClient()).GetShopState().ApplyLine(Line, OwnerGame.UnlockState.SeedIdentity);
        return;
    }
    if(Left(Line, 8) == "DD1ACK2|")
    {
        if(bSnapshotAccepted && LastSentEvent != "" && Mid(Line, 8) == LastSentEvent &&
            OwnerGame != none && OwnerGame.EventBridge != none && WorldInfo.NetMode == NM_Standalone)
        {
            OwnerGame.EventBridge.AcknowledgeEvent(LastSentEvent);
            LastSentEvent = "";
            SendPendingEvent();
        }
        return;
    }
    if(Left(Line,8) == "DD1MSG1|")
    {
        if(OwnerGame != none)
            OwnerGame.QueueAPMessage(Mid(Line,8));
        return;
    }

    if((Left(Line, 10) == "APSTATE11|" || Left(Line, 10) == "APSTATE12|") && OwnerGame != none && WorldInfo.NetMode == NM_Standalone)
    {
        bSnapshotAccepted = OwnerGame.ApplyLiveUnlockSnapshot(Line);
        if(bSnapshotAccepted)
        {
            SendPacket("DD1STATEACK1|" $ OwnerGame.UnlockState.Revision);
            SendPendingEvent();
        }
    }
}

event Closed()
{
    bSnapshotAccepted = false;
    LastSentEvent = "";
    // Close releases the bound socket. Force a fresh ephemeral bind before
    // reconnecting; reusing it leaves TcpLink stuck in STATE_Initialized.
    bHasBoundPort = false;
    `log("AP:LIVE_LINK_DISCONNECTED retrying=true");
}

event Destroyed()
{
    ClearTimer('MaintainLocalConnection');
    super.Destroyed();
}

defaultproperties
{
    BridgePort=38282
    bAlwaysTick=True
}
