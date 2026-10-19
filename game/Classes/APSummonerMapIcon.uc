// Rendering-only replacement for the native Summoner Overlord minimap icon.
// Never replace the pawn/archetype, alter hero ownership, or change camera input.
class APSummonerMapIcon extends Info implements(DunDefMiniMapIconInterface);
var DunDefPlayer_Summoner Summoner;
var bool bReplacedIcon;
var bool bLoggedDraw;
var bool bWasOverlord, bWasMapHeld;

simulated event Tick(float DeltaTime)
{
    local DunDefPlayerController PC;
    local bool Overlord, MapHeld;
    super.Tick(DeltaTime);
    if(Summoner == none || Summoner.bDeleteMe) { Destroy(); return; }
    PC = DunDefPlayerController(Summoner.GetTrueController());
    if(PC == none || PC.bDeleteMe || PC.Pawn != Summoner) { Destroy(); return; }
    if(!bReplacedIcon) Initialize(Summoner);
    Overlord = PC.IsInState('OverlordMode');
    MapHeld = DunDefInput(PC.PlayerInput) != none && DunDefInput(PC.PlayerInput).WantsMiniMap();
    if(Overlord != bWasOverlord || (Overlord && MapHeld != bWasMapHeld))
    {
        bLoggedDraw = false;
        class'APRuntimeDiagnostics'.static.Record(WorldInfo,
            "SUMMONER overlord=" $ Overlord $ " map_held=" $ MapHeld $
            " camera=" $ PC.PlayerCamera $ " controlling=" $ PC.CurrentControllingAbility $
            " casting=" $ PC.CurrentCastingAbility $ " hud=" $ PC.myHUD);
    }
    bWasOverlord = Overlord;
    bWasMapHeld = MapHeld;
}

function Initialize(DunDefPlayer_Summoner PlayerPawn)
{
    local int Index;
    Summoner = PlayerPawn;
    if(Summoner == none) return;
    Index = WorldInfo.SpecialActorsLists[AL_MINIMAPICONS_SECONDPASS].Actors.Find(Summoner);
    if(Index != INDEX_NONE)
    {
        WorldInfo.SpecialActorsLists[AL_MINIMAPICONS_SECONDPASS].Actors[Index] = self;
        bReplacedIcon = true;
    }
}

function RestoreIcon()
{
    local int Index;
    Index = WorldInfo.SpecialActorsLists[AL_MINIMAPICONS_SECONDPASS].Actors.Find(self);
    if(Index != INDEX_NONE)
    {
        if(bReplacedIcon && Summoner != none && !Summoner.bDeleteMe &&
            WorldInfo.SpecialActorsLists[AL_MINIMAPICONS_SECONDPASS].Actors.Find(Summoner) == INDEX_NONE)
            WorldInfo.SpecialActorsLists[AL_MINIMAPICONS_SECONDPASS].Actors[Index] = Summoner;
        else
            WorldInfo.SpecialActorsLists[AL_MINIMAPICONS_SECONDPASS].Actors.Remove(Index, 1);
    }
    bReplacedIcon = false;
}

simulated function DrawMiniMapIcon(Canvas C, DunDefMiniMap MiniMap)
{
    local DunDefPlayerController PC;
    local DunDefHero Hero;
    local Vector MapPos;
    local float Size;
    local Color SavedColor, MarkerColor;
    local Font SavedFont;
    if(C == none || MiniMap == none || Summoner == none || Summoner.bDeleteMe ||
        MiniMap.Opacity <= 0 || MiniMap.CurrentDrawMapScale <= 0) return;
    PC = DunDefPlayerController(Summoner.GetTrueController());
    if(PC == none || PC.bDeleteMe || PC.WorldInfo != WorldInfo) return;
    if(!PC.IsInState('OverlordMode'))
    {
        Summoner.DrawMiniMapIcon(C, MiniMap);
        return;
    }
    if(!bLoggedDraw)
        class'APRuntimeDiagnostics'.static.Record(WorldInfo, "OVERLORD minimap_draw_before pawn=" $ Summoner);
    Hero = Summoner.GetHero();
    SavedColor = C.DrawColor;
    SavedFont = C.Font;
    Size = FClamp(MiniMap.CurrentDrawMapScale * Summoner.CharacterMiniMapIconSize, 4, 256);
    MapPos = MiniMap.ConvertCenterMapCoordToCanvasCoord(
        MiniMap.ConvertWorldCoordToCenterMapCoord(Summoner.GetInterpolatedLocation()));
    C.SetPos(MapPos.X - Size/2, MapPos.Y - Size/2);
    C.DrawColor = ColorScaleAlpha(Summoner.MiniMapIconFriendlyPlayerColor, MiniMap.Opacity);
    if(Hero != none && Hero.ColorableMiniMapIconMatInst != none)
    {
        Hero.ColorableMiniMapIconMatInst.SetScalarParameterValue('UI_Opacity', MiniMap.Opacity);
        Hero.ColorableMiniMapIconMatInst.SetVectorParameterValue('UI_Color',
            Summoner.Dead ? Summoner.MiniMapIconDeadColor : Summoner.MiniMapIconLiveColor);
        C.DrawMaterialTile(Hero.ColorableMiniMapIconMatInst, Size, Size, 0, 0, 1, 1);
    }
    if(!MiniMap.DrawTiny && Summoner.MiniMapNameFont != none &&
        DunDefPlayerReplicationInfo(Summoner.PlayerReplicationInfo) != none)
    {
        C.Font = Summoner.MiniMapNameFont;
        C.SetPos(MapPos.X, MapPos.Y - Size/2);
        C.DrawTextCenteredShadowed(DunDefPlayerReplicationInfo(Summoner.PlayerReplicationInfo).GetHeroicName(),,
            FClamp(Size/34, 0.2, 2), FClamp(Size/34, 0.2, 2));
    }
    // Avoid the native Overlord icon branch suspected in the reported Shift
    // crash, without its extra texture. Camera navigation is untouched.
    if(PC.IsInState('OverlordMode') && PC.PlayerCamera != none && !PC.PlayerCamera.bDeleteMe)
    {
        MapPos = MiniMap.ConvertCenterMapCoordToCanvasCoord(
            MiniMap.ConvertWorldCoordToCenterMapCoord(PC.PlayerCamera.Location));
        Size = FClamp(MiniMap.CurrentDrawMapScale * Summoner.cameraIconSize / 2, 4, 64);
        MarkerColor = C.DrawColor;
        C.Draw2DLine(MapPos.X, MapPos.Y-Size, MapPos.X+Size, MapPos.Y, MarkerColor);
        C.Draw2DLine(MapPos.X+Size, MapPos.Y, MapPos.X, MapPos.Y+Size, MarkerColor);
        C.Draw2DLine(MapPos.X, MapPos.Y+Size, MapPos.X-Size, MapPos.Y, MarkerColor);
        C.Draw2DLine(MapPos.X-Size, MapPos.Y, MapPos.X, MapPos.Y-Size, MarkerColor);
    }
    if(Summoner.CallOutOpacity > 0) Summoner.DrawCallOutIcon(none, MiniMap, C);
    C.DrawColor = SavedColor;
    C.Font = SavedFont;
    if(!bLoggedDraw)
    {
        bLoggedDraw = true;
        class'APRuntimeDiagnostics'.static.Record(WorldInfo, "OVERLORD minimap_draw_after");
    }
}

event Destroyed()
{
    RestoreIcon();
    super.Destroyed();
}

defaultproperties
{
    RemoteRole=ROLE_None
    bHidden=true
}
