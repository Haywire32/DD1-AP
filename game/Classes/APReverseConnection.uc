// Reuses the existing state/event validation and reward deduplication.
// Explicit framing avoids relying on TcpLink's automatic line handling.
class APReverseConnection extends APInboundLink;
var string InputBuffer;
var bool bAuthenticated;

event Accepted()
{
    local IpAddr Loopback;
    local APReverseListener Listener;
    Listener = APReverseListener(Owner);
    StringToIpAddr("127.0.0.1",Loopback);
    if(RemoteAddr.Addr != Loopback.Addr || Listener == none ||
        Listener.Runtime == none || WorldInfo.NetMode != NM_Standalone)
    {
        Close();
        return;
    }
    OwnerGame = Listener.Runtime;
    LastResponseTime = WorldInfo.RealTimeSeconds;
    SetTimer(1.0,true,'MaintainLocalConnection');
}

function SendPacket(string Packet)
{
    SendText(Packet $ Chr(13) $ Chr(10));
}

event ReceivedText(string Text)
{
    local int End;
    local string Line;
    local APInboundLink Previous;
    if(OwnerGame == none || OwnerGame.bDeleteMe || OwnerGame.UnlockState == none)
    { Close(); return; }
    if(Len(InputBuffer) + Len(Text) > 65536) { Close(); return; }
    InputBuffer $= Text;
    End = InStr(InputBuffer,Chr(10));
    while(End != INDEX_NONE)
    {
        Line = Left(InputBuffer,End);
        InputBuffer = Mid(InputBuffer,End+1);
        if(Right(Line,1) == Chr(13)) Line = Left(Line,Len(Line)-1);
        if(!bAuthenticated)
        {
            if(OwnerGame.UnlockState.SeedIdentity == "" ||
                Line != ("APREVERSE1|" $ OwnerGame.UnlockState.SeedIdentity))
            { Close(); return; }
            Previous = OwnerGame.InboundLink;
            // Do not displace a working connection, including another client.
            if(Previous != none && Previous != self && Previous.IsConnected() && Previous.bSnapshotAccepted)
            { Close(); return; }
            bAuthenticated = true;
            OwnerGame.InboundLink = self;
            if(Previous != none && Previous != self) { Previous.Close(); Previous.Destroy(); }
            LastResponseTime = WorldInfo.RealTimeSeconds;
            SendPacket("DD1HELLO10");
            `log("AP:REVERSE_LINK authenticated=1");
        }
        else DispatchPacket(Line);
        End = InStr(InputBuffer,Chr(10));
    }
}

function DispatchPacket(string Line)
{
    super.ReceivedLine(Line);
}

function MaintainLocalConnection()
{
    if(OwnerGame == none || OwnerGame.bDeleteMe || WorldInfo.NetMode != NM_Standalone ||
        WorldInfo.RealTimeSeconds - LastResponseTime > (bAuthenticated ? 15.0 : 5.0))
    { Close(); return; }
    if(bAuthenticated && IsConnected())
    {
        SendPacket("DD1PING1");
        SendPendingEvent();
    }
}

event Closed()
{
    bSnapshotAccepted = false;
    if(OwnerGame != none && OwnerGame.InboundLink == self) OwnerGame.InboundLink = none;
    Destroy();
}

defaultproperties
{
    LinkMode=MODE_Text
    ReceiveMode=RMODE_Event
}
