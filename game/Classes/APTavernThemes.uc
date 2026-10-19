// Use the retail tavern's own room, collision gates, selector and theme travel.
// No achievement grants, copied maps, new menu or entitlement overrides.
class APTavernThemes extends Info;

var APGameRuntime Runtime;
var bool Licensed;
var array<SequenceOp> AppliedGates;
var array<int> AppliedValues;

function Initialize(APGameRuntime Host)
{
    Runtime=Host;
    Licensed=HasShardsLicense();
    SetTimer(0.5,true,'Poll');
}

static function bool HasShardsLicense()
{
    return class'APHeroEntitlements'.static.IsDLCAppLicensed(204381) &&
        class'APHeroEntitlements'.static.IsDLCAppLicensed(204382) &&
        class'APHeroEntitlements'.static.IsDLCAppLicensed(204383) &&
        class'APHeroEntitlements'.static.IsDLCAppLicensed(204384);
}

static function bool IsSeedLicensed(APUnlockState Permissions)
{
    return Permissions!=none && (!Permissions.bTavernThemes || HasShardsLicense());
}

static function bool ValidFields(array<string> Fields)
{
    return Fields.Length==4 && Fields[0]=="APTHEMES1" && Fields[1]!="" &&
        (Fields[2]=="0" || Fields[2]=="1") && string(int(Fields[3]))==Fields[3] &&
        int(Fields[3])>=0 && int(Fields[3])<=2047;
}

function bool ApplySnapshot(string Line)
{
    local array<string> Fields;
    ParseStringIntoArray(Line,Fields,"|",false);
    if(!ValidFields(Fields) || Runtime==none || Runtime.UnlockState==none ||
        Fields[1]!=Runtime.UnlockState.SeedIdentity ||
        (Fields[2]=="1")!=Runtime.UnlockState.bTavernThemes) return false;
    // Complete cumulative inventory. Duplicate or delayed packets cannot relock.
    Runtime.UnlockState.TavernThemeMask=Runtime.UnlockState.TavernThemeMask | int(Fields[3]);
    Runtime.RememberSessionUnlocks();
    Poll();
    return true;
}

static function int ThemeIndex(string MapName)
{
    switch(Caps(MapName))
    {
        case "LOBBYLEVEL_NORMAL.UDK": return -1;
        case "LOBBYLEVEL_JESTER.UDK": return 0;
        case "LOBBYLEVEL_VALENTINE.UDK": return 1;
        case "LOBBYLEVEL_ISLAND.UDK": return 2;
        case "LOBBYLEVEL_WINTER.UDK": return 3;
        case "LOBBYLEVEL_OUTDOORS.UDK": return 4;
        case "LOBBYLEVEL_TINKERS.UDK": return 5;
        case "LOBBYLEVEL_MOONBASE.UDK": return 6;
        case "LOBBYLEVEL_AQUANOS.UDK": return 7;
        case "LOBBYLEVEL_DEFENSE.UDK": return 8;
        case "LOBBYLEVEL_SPOOKY.UDK": return 9;
        case "LOBBYLEVEL_LAVA.UDK": return 10;
    }
    return -3; // Unknown future themes are never implicitly granted.
}

function bool Allowed(int Index)
{
    if(Index==-1) return true; // Always allow the original tavern.
    // Retired paid-map rewards stay blocked even in old seeds/manual receipts.
    return Licensed && Index>0 && Index<11 && Index!=9 && Runtime!=none && Runtime.UnlockState!=none &&
        (Runtime.UnlockState.TavernThemeMask & (1<<Index))!=0;
}

static function bool InThemeRoom(SequenceObject Obj)
{
    return Obj!=none && Sequence(Obj.Outer)!=none && Obj.Outer.Name=='Tavern_Themes' &&
        Sequence(Obj.Outer.Outer)!=none && Obj.Outer.Outer.Name=='Main_Sequence' &&
        Obj.Outer.Outer.Outer!=none && Obj.Outer.Outer.Outer.Name=='PersistentLevel';
}

static function int GateIndex(SequenceOp Op)
{
    // Exact nodes inventoried in retail LobbyLevel_Kismet. Only this cosmetic
    // sub-sequence is changed; all DLC purchase nodes remain untouched.
    switch(Op.Name)
    {
        case 'DunDef_SeqCond_IsAchievementUnlocked_0': return -2; // Room door
        case 'DunDef_SeqCond_IsMissionUnlocked_29': return 0;
        case 'DunDef_SeqCond_IsAchievementUnlocked_6': return 1;
        case 'DunDef_SeqCond_IsAchievementUnlocked_8': return 2;
        case 'DunDef_SeqCond_IsAchievementUnlocked_4': return 3;
        case 'DunDef_SeqCond_IsAchievementUnlocked_1': return 4;
        case 'DunDef_SeqCond_IsAchievementUnlocked_7': return 5;
        case 'DunDef_SeqCond_CustomMetaFlag_2': return 6;
        case 'DunDef_SeqCond_IsAchievementUnlocked_2': return 7;
        case 'DunDef_SeqCond_IsAchievementUnlocked_3': return 8;
        case 'DunDef_SeqCond_IsAchievementUnlocked_9': return 9;
        case 'DunDef_SeqCond_IsAchievementUnlocked_5': return 10;
    }
    return -3;
}

function ApplyGate(SequenceOp Op, bool Unlocked)
{
    local int Index, Value, I;
    if(Op.OutputLinks.Length<2) return;
    // Stop later native LevelLoaded/achievement checks overriding AP inventory.
    for(I=0;I<Op.InputLinks.Length;I++) Op.InputLinks[I].bDisabled=true;
    Index=AppliedGates.Find(Op);
    Value=int(Unlocked);
    if(Index!=INDEX_NONE && AppliedValues[Index]==Value) return;
    if(Index==INDEX_NONE)
    {
        AppliedGates.AddItem(Op); AppliedValues.AddItem(Value);
    }
    else AppliedValues[Index]=Value;
    // Let Kismet populate Targets and execute its existing collision/door actions.
    FireGateOutput(Op,1-Value);
}

function FireGateOutput(SequenceOp Op,int OutputIndex)
{
    local int I;
    local SequenceOp Target;
    // ActivateOutputLink alone only sets an impulse on an already-active op.
    // These conditions have finished by the time an AP reward arrives. Queue
    // their existing targets explicitly so native variable binding still runs.
    for(I=0;I<Op.OutputLinks[OutputIndex].Links.Length;I++)
    {
        Target=Op.OutputLinks[OutputIndex].Links[I].LinkedOp;
        // The Moonbase false branch also links another vanilla condition. Do
        // not execute it: it could reopen a theme from old achievement flags.
        if(Target!=none && InThemeRoom(Target) &&
            (SeqAct_ChangeCollision(Target)!=none || SeqAct_Interp(Target)!=none || SeqAct_Toggle(Target)!=none))
            Target.ForceActivateInput(Op.OutputLinks[OutputIndex].Links[I].InputLinkIdx);
    }
}

function ApplyObjects(array<SequenceObject> Objects)
{
    local SequenceObject Obj;
    local SequenceOp Op;
    local SeqEvent_Used Used;
    local DunDef_SeqAct_SetDefaultGameplayLevel SelectTheme;
    local int I, J, Index;
    foreach Objects(Obj)
    {
        if(!InThemeRoom(Obj)) continue;
        Op=SequenceOp(Obj);
        if(Op==none) continue;
        // Moonbase has two alternative vanilla conditions. Disable the second
        // so its true branch cannot override a locked AP Moonbase theme.
        if(Op.Name=='DunDef_SeqCond_CustomMetaFlag_1')
        {
            for(I=0;I<Op.InputLinks.Length;I++) Op.InputLinks[I].bDisabled=true;
        }
        Index=GateIndex(Op);
        if(Index==-2) ApplyGate(Op,Licensed);
        else if(Index>=0) ApplyGate(Op,Allowed(Index));
        Used=SeqEvent_Used(Obj);
        if(Used==none) continue;
        for(I=0;I<Used.OutputLinks.Length;I++)
        {
            for(J=0;J<Used.OutputLinks[I].Links.Length;J++)
            {
                SelectTheme=DunDef_SeqAct_SetDefaultGameplayLevel(Used.OutputLinks[I].Links[J].LinkedOp);
                if(SelectTheme==none || !InThemeRoom(SelectTheme)) continue;
                Used.bEnabled=Allowed(ThemeIndex(SelectTheme.NewDefaultGameplayLevel));
            }
        }
    }
}

function Poll()
{
    local array<Sequence> Roots;
    local Sequence Root;
    local array<SequenceObject> Objects;
    local DunDefGameReplicationInfo GRI;
    if(WorldInfo.NetMode!=NM_Standalone || Runtime==none || Runtime.UnlockState==none ||
        !Runtime.UnlockState.bTavernThemes || Runtime.UnlockState.SeedIdentity=="") return;
    GRI=DunDefGameReplicationInfo(WorldInfo.GRI);
    if(GRI==none || !GRI.IsLobbyLevel) return;
    if(!Licensed) Licensed=HasShardsLicense();
    Roots=WorldInfo.GetAllRootSequences();
    foreach Roots(Root)
    {
        if(Root==none) continue;
        Objects.Length=0;
        Root.FindSeqObjectsByClass(class'SequenceOp',true,Objects);
        ApplyObjects(Objects);
    }
}

defaultproperties
{
    RemoteRole=ROLE_None
}
