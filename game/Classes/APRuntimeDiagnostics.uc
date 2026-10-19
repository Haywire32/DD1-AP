// Bounded crash breadcrumbs, plus readable records in the connected AP client.
class APRuntimeDiagnostics extends Object config(DD1ArchipelagoRuntimeDiagnostics);
var config string LastCheckpoint;
var config array<string> RecentCheckpoints;

static function Record(WorldInfo World, string Message)
{
    local APGameRuntime Runtime;
    if(World == none) return;
    Message = World.GetMapName() $ " " $ Message;
    `log("AP:DIAGNOSTIC " $ Message);
    default.LastCheckpoint = Message;
    default.RecentCheckpoints.AddItem(Message);
    if(default.RecentCheckpoints.Length > 24) default.RecentCheckpoints.Remove(0, 1);
    StaticSaveConfig();
    Runtime = class'APGameRuntime'.static.GetForWorld(World);
    if(Runtime != none && Runtime.InboundLink != none && Runtime.InboundLink.IsConnected())
        Runtime.InboundLink.SendPacket("DD1DIAG1|" $ Message);
}
