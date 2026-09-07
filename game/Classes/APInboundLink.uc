class APInboundLink extends TcpLink;

var APGameInfo OwnerGame;
var int BridgePort;
var bool bHasBoundPort;
var float LastResponseTime;
var bool bSnapshotAccepted;
var string LastSentEvent;

function Initialize(APGameInfo NewOwner)
{
    OwnerGame = NewOwner;
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
        if(WorldInfo.RealTimeSeconds - LastResponseTime > 3.0)
        {
            Close();
            return;
        }
        SendText("DD1PING1");
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
    SendText("DD1HELLO3");
}

function SendPendingEvent()
{
    if(!bSnapshotAccepted || OwnerGame == none || OwnerGame.EventBridge == none ||
        OwnerGame.UnlockState == none || WorldInfo.NetMode != NM_Standalone)
        return;
    LastSentEvent = OwnerGame.EventBridge.NextPendingEvent(OwnerGame.UnlockState.SeedIdentity);
    if(LastSentEvent != "")
        SendText("DD1EVENT1|" $ LastSentEvent);
}

event ReceivedLine(string Line)
{
    LastResponseTime = WorldInfo.RealTimeSeconds;
    if(Line == "DD1PONG1")
        return;
    if(Left(Line, 8) == "DD1ACK1|")
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

    if(OwnerGame != none && WorldInfo.NetMode == NM_Standalone)
    {
        bSnapshotAccepted = OwnerGame.ApplyLiveUnlockSnapshot(Line);
        if(bSnapshotAccepted)
            SendPendingEvent();
    }
}

event Closed()
{
    bSnapshotAccepted = false;
    LastSentEvent = "";
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
