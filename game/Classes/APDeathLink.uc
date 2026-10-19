// DD1's own Died/PawnDied path retains respawn, Hardcore and mana-drop rules.
class APDeathLink extends Info;
var APGameRuntime Runtime;
var APDeathLinkInput InputState;
var APDeathLinkState LinkState;
var bool bApplying;
var int LastPulse;
var float LastPulseTime;
var array<Pawn> ReportedPawns;
var bool bReportedCrystalLoss;
var bool bLiveInput;
var array<Pawn> PendingLocalVictims;

function ApplyLiveInput(string Line)
{
    local array<string> Fields;
    ParseStringIntoArray(Line, Fields, "|", false);
    if(Fields.Length != 7 || Runtime == none || Runtime.UnlockState == none ||
        Fields[1] != Runtime.UnlockState.SeedIdentity || Fields[2] == "") return;
    if(InputState == none) InputState = new(self) class'APDeathLinkInput';
    InputState.SeedIdentity = Fields[1];
    InputState.Session = Fields[2];
    InputState.bEnabled = Fields[3] == "1";
    InputState.bCrystalDestruction = Fields[4] == "1";
    InputState.Sequence = int(Fields[5]);
    if(!bLiveInput)
    {
        if(LinkState.Session != InputState.Session || LinkState.SeedIdentity != InputState.SeedIdentity)
        {
            LinkState.Session = InputState.Session;
            LinkState.SeedIdentity = InputState.SeedIdentity;
            LinkState.SeenSequence = InputState.Sequence;
            LinkState.LocalDeaths = int(Fields[6]);
        }
        else LinkState.LocalDeaths = Max(LinkState.LocalDeaths, int(Fields[6]));
    }
    bLiveInput = true;
    LastPulseTime = WorldInfo.RealTimeSeconds;
    Poll();
    SendLiveStatus();
}

function string BlockReason()
{
    local DunDefGameReplicationInfo GRI;
    local DunDefMapInfo MapInfo;
    local DunDefPlayerController PC;
    local string Targets;
    if(Runtime == none || Runtime.UnlockState == none || InputState == none) return "missing_state";
    if(!InputState.bEnabled) return "disabled";
    if(InputState.SeedIdentity != Runtime.UnlockState.SeedIdentity) return "seed_mismatch";
    if(WorldInfo.Pauser != none) return "paused";
    if(WorldInfo.RealTimeSeconds - LastPulseTime > 5) return "heartbeat_expired";
    if(!Runtime.IsStableAPWorld())
    {
        MapInfo = DunDefMapInfo(WorldInfo.GetMapInfo());
        return "world_not_stable map=" $ WorldInfo.GetMapName() $ " next=" $ WorldInfo.NextURL $
            " current=" $ (WorldInfo == class'Engine'.static.GetCurrentWorldInfo()) $
            " travel=" $ WorldInfo.IsInSeamlessTravel() $ " preparing=" $ WorldInfo.IsPreparingMapChange() $
            " returning=" $ Runtime.bAPReturningToMenu $ " mapinfo=" $ MapInfo $
            " loading=" $ (MapInfo != none && MapInfo.IsLoadingLevel);
    }
    GRI = DunDefGameReplicationInfo(WorldInfo.GRI);
    if(GRI == none) return "no_gri";
    if(!GRI.IsGameplayLevel || GRI.IsLobbyLevel) return "menu_or_tavern";
    if(GRI.bDoLevelVictory || GRI.bIsGameOver) return "victory_or_defeat";
    if(!HasTarget())
    {
        foreach WorldInfo.AllControllers(class'DunDefPlayerController', PC)
            Targets $= " pc=" $ PC.Class $ " stable=" $ Runtime.IsStableLocalController(PC) $
                " pawn=" $ PC.Pawn $ " swapping=" $ PC.bCurrentlySwappingHero $
                " initializing=" $ PC.bWaitingForHeroInitialization;
        return "no_living_target crystal_mode=" $ InputState.bCrystalDestruction $ Targets;
    }
    return "ready";
}

function SendLiveStatus()
{
    local string Reason;
    if(!bLiveInput || Runtime.InboundLink == none || !Runtime.InboundLink.IsConnected()) return;
    Reason = BlockReason();
    Runtime.InboundLink.SendPacket("DD1DEATH1|" $ LinkState.SeedIdentity $ "|" $ LinkState.Session $
        "|" $ int(Reason == "ready") $ "|" $ LinkState.LocalDeaths $ "|" $ LinkState.SeenSequence $ "|" $ Reason);
}

function Initialize(APGameRuntime OwnerRuntime)
{
    Runtime = OwnerRuntime;
    LinkState = new(self) class'APDeathLinkState';
    LinkState.bReady = false;
    LinkState.Persist();
    SetTimer(0.25, true, 'Poll');
}

function array<DunDefPlayerController> ActiveControllers()
{
    local DunDefPlayerController PC;
    local array<DunDefPlayerController> Players;
    foreach WorldInfo.AllControllers(class'DunDefPlayerController', PC)
        if(Runtime.IsStableLocalController(PC)) Players.AddItem(PC);
    return Players;
}

function DunDefCrystalCore LivingCrystal()
{
    local DunDefCrystalCore Core;
    foreach WorldInfo.AllActors(class'DunDefCrystalCore', Core)
        if(!Core.bDeleteMe && !Core.bHidden && Core.Health > 0 &&
            !Core.IsDead)
            return Core;
    return none;
}

function bool HasTarget()
{
    local array<DunDefPlayerController> Players;
    local DunDefPlayerController PC;
    if(InputState.bCrystalDestruction) return LivingCrystal() != none;
    Players = ActiveControllers();
    foreach Players(PC)
        if(PC.Pawn != none && PC.Pawn.Health > 0) return true;
    return false;
}

function ApplyLinkedDeath()
{
    local array<DunDefPlayerController> Players;
    local DunDefPlayerController PC;
    local Pawn Target;
    local array<Pawn> Targets;
    local DunDefCrystalCore Core;
    local int PreviousHealth;
    bApplying = true;
    if(InputState.bCrystalDestruction)
    {
        Core = LivingCrystal();
        if(Core != none)
        {
            // Crystal Died triggers the map's ordinary CoreDeath Kismet event.
            // Mark first: its GameOver callback may run now or on a later tick.
            bReportedCrystalLoss = true;
            Core.Health = 0;
            Core.Died(none, Core.Location, class'DunDefDamageType_ForceKill', self);
            Core.NotifyHealthChange();
            // Some maps defer/bypass CoreDeath cinematics during build phase.
            // Always finish with the normal defeat state, never a victory/check.
            if(main(WorldInfo.Game) != none)
                main(WorldInfo.Game).ShowGameOver(0);
        }
    }
    else
    {
        // Snapshot PAWNS before any death changes possession/controller state.
        Players = ActiveControllers();
        foreach Players(PC)
            if(PC.Pawn != none && PC.Pawn.Health > 0) Targets.AddItem(PC.Pawn);
        foreach Targets(Target)
        {
            if(Target == none || Target.bDeleteMe || Target.Health <= 0) continue;
            PreviousHealth = Target.Health;
            ReportedPawns.AddItem(Target);
            Target.Health = 0;
            if(!Target.Died(Target.Controller, class'DunDefDamageType_ForceKill', Target.Location))
            {
                Target.Health = PreviousHealth;
                ReportedPawns.RemoveItem(Target);
            }
        }
    }
    bApplying = false;
}

function ApplyLocalSplitDeath()
{
    local Pawn Target;
    local int PreviousHealth;
    // Run after the original death callback has finished. Never kill a newly
    // respawned/swapped hero or carry a local death across a map/pause boundary.
    if(CanLink() && !InputState.bCrystalDestruction)
    {
        bApplying=true;
        foreach PendingLocalVictims(Target)
        {
            if(Target==none || Target.bDeleteMe || Target.Health<=0 ||
                Target.Controller==none || Target.Controller.Pawn!=Target ||
                !Runtime.IsStableLocalController(DunDefPlayerController(Target.Controller))) continue;
            PreviousHealth=Target.Health;
            ReportedPawns.AddItem(Target);
            Target.Health=0;
            if(!Target.Died(Target.Controller,class'DunDefDamageType_ForceKill',Target.Location))
            {
                Target.Health=PreviousHealth;
                ReportedPawns.RemoveItem(Target);
            }
        }
        bApplying=false;
    }
    PendingLocalVictims.Length=0;
}

function bool CanLink()
{
    local DunDefGameReplicationInfo GRI;
    if(Runtime == none || Runtime.UnlockState == none || InputState == none ||
        !InputState.bEnabled || InputState.SeedIdentity != Runtime.UnlockState.SeedIdentity ||
        WorldInfo.Pauser != none || !Runtime.IsStableAPWorld() ||
        WorldInfo.RealTimeSeconds - LastPulseTime > 5.0) return false;
    GRI = DunDefGameReplicationInfo(WorldInfo.GRI);
    // Tavern, menus, map travel and the victory/game-over screen are excluded.
    return GRI != none && GRI.IsGameplayLevel && !GRI.IsLobbyLevel &&
        !GRI.bDoLevelVictory && !GRI.bIsGameOver;
}

function Poll()
{
    local bool Ready, Changed;
    local int I;
    if(Runtime == none || Runtime.UnlockState == none || WorldInfo.Pauser != none) return;
    if(!bLiveInput)
    {
        ConsoleCommand("ReloadCfg DD1Archipelago.APDeathLinkInput");
        InputState = new(self) class'APDeathLinkInput';
    }
    if(InputState.SeedIdentity != Runtime.UnlockState.SeedIdentity || InputState.Session == "") return;
    if(LinkState.Session != InputState.Session || LinkState.SeedIdentity != InputState.SeedIdentity)
    {
        LinkState.Session = InputState.Session;
        LinkState.SeedIdentity = InputState.SeedIdentity;
        LinkState.SeenSequence = InputState.Sequence;
        LinkState.LocalDeaths = 0;
        Changed = true;
    }
    if(LastPulse != InputState.Pulse)
    {
        LastPulse = InputState.Pulse;
        LastPulseTime = WorldInfo.RealTimeSeconds;
    }
    // Do not retain destroyed pawns forever; a revived pawn can die again.
    for(I = ReportedPawns.Length - 1; I >= 0; I--)
        if(ReportedPawns[I] == none || ReportedPawns[I].bDeleteMe || ReportedPawns[I].Health > 0)
            ReportedPawns.Remove(I, 1);
    Ready = CanLink() && HasTarget();
    if(LinkState.bReady != Ready) { LinkState.bReady = Ready; Changed = true; }
    if(InputState.Sequence > LinkState.SeenSequence)
    {
        // Consume once even if already dead, in the Tavern, or travelling.
        LinkState.SeenSequence = InputState.Sequence;
        Changed = true;
        if(Ready)
        {
            ApplyLinkedDeath();
            LinkState.bReady = false;
        }
    }
    if(Changed) LinkState.Persist();
}

function NotifyDeath(DunDefPlayerController PC, Pawn DeadPawn)
{
    local array<DunDefPlayerController> Players;
    local DunDefPlayerController Other;
    if(DeadPawn == none || Runtime == none || !Runtime.IsStableLocalController(PC) ||
        ReportedPawns.Find(DeadPawn) != INDEX_NONE) return;
    ReportedPawns.AddItem(DeadPawn);
    if(bApplying || !CanLink() || InputState.bCrystalDestruction) return;
    LinkState.LocalDeaths++;
    LinkState.bReady = false;
    LinkState.Persist();
    SendLiveStatus();
    // The server does not echo our own DeathLink back to this client. Apply
    // that same death to the remaining local players explicitly, once.
    Players=ActiveControllers();
    foreach Players(Other)
        if(Other.Pawn!=none && Other.Pawn!=DeadPawn && Other.Pawn.Health>0 &&
            PendingLocalVictims.Find(Other.Pawn)==INDEX_NONE)
            PendingLocalVictims.AddItem(Other.Pawn);
    if(PendingLocalVictims.Length>0) SetTimer(0.01,false,'ApplyLocalSplitDeath');
}

function NotifyGameOver(int Reason)
{
    // Crystal loss sends in either mode. The mode only selects the incoming
    // effect and whether ordinary hero deaths also send. Native reason 0 is
    // crystal loss; hero/lives/timer failures must not count as another loss.
    if(Reason != 0 || bReportedCrystalLoss || bApplying || !CanLink()) return;
    bReportedCrystalLoss = true;
    LinkState.LocalDeaths++;
    LinkState.bReady = false;
    LinkState.Persist();
    SendLiveStatus();
}

event Destroyed()
{
    if(LinkState != none) { LinkState.bReady = false; LinkState.Persist(); }
    super.Destroyed();
}

defaultproperties
{
    RemoteRole=ROLE_None
}
