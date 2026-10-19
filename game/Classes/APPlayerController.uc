class APPlayerController extends DunDefPlayerController;
var APSummonerMapIcon APSummonerIcon;
var bool bAPMapHeld;

function SetAPOverlordIcon(bool Enabled)
{
    if(APSummonerIcon != none && (!Enabled || APSummonerIcon.Summoner != Pawn))
    {
        APSummonerIcon.Destroy();
        APSummonerIcon = none;
    }
    if(Enabled && APSummonerIcon == none && WorldInfo.NetMode == NM_Standalone &&
        DunDefPlayer_Summoner(Pawn) != none)
    {
        APSummonerIcon = Spawn(class'APSummonerMapIcon', self);
        if(APSummonerIcon != none) APSummonerIcon.Initialize(DunDefPlayer_Summoner(Pawn));
    }
}

state OverlordMode
{
    event PlayerTick(float DeltaTime)
    {
        super.PlayerTick(DeltaTime);
        if(DunDefInput(PlayerInput) != none &&
            bAPMapHeld != DunDefInput(PlayerInput).WantsMiniMap())
        {
            bAPMapHeld = DunDefInput(PlayerInput).WantsMiniMap();
            class'APRuntimeDiagnostics'.static.Record(WorldInfo,
                "OVERLORD map_input=" $ bAPMapHeld $ " pawn=" $ Pawn $
                " camera=" $ PlayerCamera $ " controlling=" $ CurrentControllingAbility $
                " casting=" $ CurrentCastingAbility $ " hud=" $ myHUD);
        }
    }
    simulated event PushedState()
    {
        class'APRuntimeDiagnostics'.static.Record(WorldInfo, "OVERLORD push_before pawn=" $ Pawn $ " camera=" $ PlayerCamera);
        super.PushedState();
        SetAPOverlordIcon(true);
        class'APRuntimeDiagnostics'.static.Record(WorldInfo, "OVERLORD push_after icon=" $ APSummonerIcon);
    }
    simulated event BeginState(name PreviousStateName)
    {
        class'APRuntimeDiagnostics'.static.Record(WorldInfo, "OVERLORD begin_before");
        super.BeginState(PreviousStateName);
        SetAPOverlordIcon(true);
    }
    simulated event PoppedState()
    {
        class'APRuntimeDiagnostics'.static.Record(WorldInfo, "OVERLORD pop_before");
        SetAPOverlordIcon(false);
        super.PoppedState();
    }
    simulated event EndState(name NextStateName)
    {
        class'APRuntimeDiagnostics'.static.Record(WorldInfo, "OVERLORD end_before");
        SetAPOverlordIcon(false);
        super.EndState(NextStateName);
    }
}

event Destroyed()
{
    SetAPOverlordIcon(false);
    super.Destroyed();
}

// DD1 ignores GameInfo.HUDType and spawns the hero's HUD archetype directly.
// Retain that archetype's layout/settings while using our message filter.
function CreateHUD()
{
    if(!IsLocalPlayerController() || !class'DunDefGameReplicationInfo'.static.IsInGameplayLevel() ||
        myHUD != none || GetHero() == none)
        return;
    if(GetHero().GetPlayerTemplate().HudTemplate != none)
        myHUD = Spawn(class'APHUD', self);
}

function PawnDied(Pawn inPawn)
{
    local APGameRuntime Runtime;
    Runtime = class'APGameRuntime'.static.GetForWorld(WorldInfo);
    if(Runtime != none && Runtime.DeathLink != none)
        Runtime.DeathLink.NotifyDeath(self, inPawn);
    super.PawnDied(inPawn);
}

// Native DLC/costume checks can announce many outfits while AP reapplies its
// seed-specific permissions. Keep the actual unlock/save behavior, but suppress
// costume popups, HUD text and their sound in both menus and gameplay. Hero
// unlocks use this same native function and must retain their notifications.
reliable client function UnlockCostume(DunDefHero forHeroArchetype, int CostumeIndex,
    optional SoundCue GivenCostumeSound, optional bool bNotifyUser=true, optional bool bIsHeroUnlock)
{
    super.UnlockCostume(forHeroArchetype, CostumeIndex, GivenCostumeSound,
        bNotifyUser && bIsHeroUnlock, bIsHeroUnlock);
}

// Record native menu returns as well as AP's explicit hero rejection. This is
// diagnostic only: keep stock travel/cleanup behavior unchanged.
function QuitToMainMenu(optional bool forceImmediateReturn = false)
{
    local APGameRuntime Runtime;
    Runtime = class'APGameRuntime'.static.GetForWorld(WorldInfo);
    if(Runtime != none && Runtime.UnlockState != none)
        `log("AP:MENU_RETURN map=" $ WorldInfo.GetMapName() $
            " revision=" $ Runtime.UnlockState.Revision $
            " ap_rejected=" $ Runtime.bAPReturningToMenu $
            " immediate=" $ forceImmediateReturn);
    super.QuitToMainMenu(forceImmediateReturn);
}

// Stock QuickAddSplits is not safe to repeat: it attempts to add all three
// secondary controller IDs again even when some or all are already present.
// Make F6 idempotent while preserving its normal one-key four-player setup.
exec function QuickAddSplits()
{
    local DunDefViewportClient Viewport;
    local int ControllerID;

    Viewport = class'DunDefViewportClient'.static.GetViewportClient();
    if(Viewport == none)
        return;

    for(ControllerID = 1; ControllerID < 4; ControllerID++)
    {
        if(Viewport.FindPlayerByControllerId(ControllerID) == none)
            Viewport.DebugCreateLocalPlayer(ControllerID);
    }
}

// Remove every secondary local player from highest ID to lowest. Doing this
// through RemovePlayer retains DD1's NotifyPlayerLeft/SetActiveHero cleanup,
// so F7 also works reliably from the four-player title-screen hero view.
exec function KickAllSplits()
{
    local DunDefViewportClient Viewport;
    local LocalPlayer SplitPlayer;
    local int ControllerID;

    Viewport = class'DunDefViewportClient'.static.GetViewportClient();
    if(Viewport == none)
        return;

    for(ControllerID = 3; ControllerID > 0; ControllerID--)
    {
        SplitPlayer = Viewport.FindPlayerByControllerId(ControllerID);
        if(SplitPlayer != none)
            Viewport.RemovePlayer(SplitPlayer);
    }
}

// Steam remains available for native DLC ownership queries, not invitations.
// This also covers callbacks registered before the viewport's next tick.
function OnGameInviteAccepted(const out OnlineGameSearchResult InviteResult)
{
}
