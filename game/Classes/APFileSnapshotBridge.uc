// Linux fallback using a complete, atomically replaced snapshot. Reuses the
// established state parsers and cumulative reward counters; no new item IDs.
class APFileSnapshotBridge extends Info;
var APGameRuntime Runtime;
var APFileSnapshotReader Reader;
var string LastHeader;
var string LastSession;
var int LastSequence;
var int AcknowledgedRevision;

function Initialize(APGameRuntime OwnerRuntime)
{
    Runtime=OwnerRuntime;
    Reader=new(self) class'APFileSnapshotReader';
    AcknowledgedRevision=-1;
    SetTimer(0.5,true,'Poll');
}

function APShopState GetShopState()
{
    local APViewportClient Viewport;
    Viewport=APViewportClient(class'DunDefViewportClient'.static.GetViewportClient());
    if(Viewport == none) return none;
    return Viewport.GetShopState();
}

function Poll()
{
    local string Filename;
    if(Runtime == none || Runtime.UnlockState == none || WorldInfo.NetMode != NM_Standalone) return;
    if(Runtime.InboundLink != none && Runtime.InboundLink.IsConnected() && Runtime.InboundLink.bSnapshotAccepted) return;
    Filename="DD1ArchipelagoCurrent-live.uhtm";
    if(class'APBuildProfile'.static.IsPrivateChaosBuild()) Filename="DD1ArchipelagoChaos-live.uhtm";
    if(Reader.FileExists(Filename)) ApplySnapshot(Reader.LoadParsedUHTM(Filename));
}

function bool ApplySnapshot(string Text)
{
    local array<string> Lines, Header, Fields;
    local int I, Sequence;
    local array<int> TrapCounts;
    local bool Established;
    local APShopState Shop;
    local APFileSnapshotStatus Status;
    if(Runtime == none || Runtime.UnlockState == none || WorldInfo.NetMode != NM_Standalone ||
        Len(Text) > 65536 || Len(Text) < 20) return false;
    Text=Repl(Text,Chr(13),"");
    ParseStringIntoArray(Text,Lines,Chr(10),true);
    if(Lines.Length < 3 || Lines.Length > 48) return false;
    ParseStringIntoArray(Lines[0],Header,"|",false);
    if(Header.Length != 5 || Header[0] != "APFILE1" || Header[1] != Runtime.UnlockState.SeedIdentity ||
        Len(Header[2]) != 32 || Lines[Lines.Length-1] != ("END|" $ Lines[0]) ||
        string(Lines.Length-2) != Header[4]) return false;
    Sequence=int(Header[3]);
    if(Sequence < 1 || string(Sequence) != Header[3] || Lines[0] == LastHeader ||
        (Header[2] == LastSession && Sequence <= LastSequence)) return false;
    if(Left(Lines[1],10) != "APSTATE11|" && Left(Lines[1],10) != "APSTATE12|") return false;
    // Validate the whole envelope before applying any part. Names are hex,
    // never markup, script, filenames, or console commands.
    for(I=1;I<Lines.Length-1;I++)
    {
        ParseStringIntoArray(Lines[I],Fields,"|",false);
        if(Fields.Length < 2 || Fields[1] != Header[1] || Len(Lines[I]) > 8192) return false;
        if(I>1 && Fields[0] != "APSHARDS1" && Fields[0] != "APGEAR1" &&
            Fields[0] != "APSHOP1" && Fields[0] != "APSHOP2" &&
            Fields[0] != "APSHOPITEM1" && Fields[0] != "APDEATH1" && Fields[0] != "APTRAPS1" && Fields[0] != "APTHEMES1") return false;
        if(Fields[0] == "APTHEMES1" && !class'APTavernThemes'.static.ValidFields(Fields)) return false;
        if(Fields[0] == "APTRAPS1" && (Fields.Length != 3 ||
            !class'APTrapRuntime'.static.ParseCounts(Fields[2],TrapCounts))) return false;
    }
    if(!Runtime.ApplyLiveUnlockSnapshot(Lines[1])) return false;
    Established=LastSession == Header[2] && LastSequence > 0;
    LastHeader=Lines[0]; LastSession=Header[2]; LastSequence=Sequence;
    Shop=GetShopState();
    for(I=2;I<Lines.Length-1;I++)
    {
        if(Left(Lines[I],10) == "APSHARDS1|") Runtime.ApplyShardDisplaySnapshot(Lines[I]);
        else if(Left(Lines[I],8) == "APGEAR1|") Runtime.ApplyGearSettingsSnapshot(Lines[I]);
        else if(Left(Lines[I],10) == "APTHEMES1|")
        {
            if(Runtime.Themes != none) Runtime.Themes.ApplySnapshot(Lines[I]);
        }
        else if(Left(Lines[I],9) == "APTRAPS1|")
        {
            if(Runtime.Traps != none) Runtime.Traps.ApplySnapshot(Lines[I]);
        }
        else if(Left(Lines[I],9) == "APDEATH1|")
        {
            // Require a changing file heartbeat, not a file left from a closed
            // client. The existing DeathLink checks still enforce world safety.
            if(Established && Runtime.DeathLink != none) Runtime.DeathLink.ApplyLiveInput(Lines[I]);
        }
        else if(Shop != none) Shop.ApplyLine(Lines[I],Header[1]);
    }
    if(!Established || AcknowledgedRevision != Runtime.UnlockState.Revision)
    {
        AcknowledgedRevision=Runtime.UnlockState.Revision;
        Status=new(self) class'APFileSnapshotStatus';
        Status.SeedIdentity=Header[1]; Status.Session=Header[2];
        Status.Revision=AcknowledgedRevision; Status.SaveConfig();
        `log("AP:FILE_SNAPSHOT_APPLIED revision=" $ AcknowledgedRevision);
    }
    return true;
}

defaultproperties
{
    RemoteRole=ROLE_None
}
