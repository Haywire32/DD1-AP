// Optional test transport: native AP client connects to the Proton game.
// Never used in online play; accepted peers must be IPv4 loopback.
class APReverseListener extends TcpLink;
var APGameRuntime Runtime;
var int BridgePort;

function Initialize(APGameRuntime NewRuntime)
{
    Runtime = NewRuntime;
    BridgePort = class'APBuildProfile'.static.IsPrivateChaosBuild() ? 38285 : 38284;
    StartListening();
}

function StartListening()
{
    local IpAddr LocalAddress, Loopback;
    if(Runtime == none || Runtime.bDeleteMe || WorldInfo.NetMode != NM_Standalone) return;
    GetLocalIP(LocalAddress);
    StringToIpAddr("127.0.0.1",Loopback);
    // The Linux client supplies -MULTIHOME=127.0.0.1. Fail closed if
    // manually launched without it, rather than listen on a LAN address.
    if(LocalAddress.Addr != Loopback.Addr)
    {
        `log("AP:REVERSE_LISTENER skipped=1 reason=loopback_launch_required");
        return;
    }
    if(BindPort(BridgePort,false) == 0)
    {
        SetTimer(2.0,false,'StartListening');
        return;
    }
    if(!Listen()) { Close(); return; }
    `log("AP:REVERSE_LISTENER ready=1 port=" $ BridgePort);
}

defaultproperties
{
    AcceptClass=class'APReverseConnection'
    LinkMode=MODE_Text
    ReceiveMode=RMODE_Event
    bAlwaysTick=True
}
