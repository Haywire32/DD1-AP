class APChaosStats extends APShopPresentation;

struct HeroReplacement { var DunDefHero OldHero; var APChaosHero NewHero; };
var array<HeroReplacement> Replacements;

static function ApplyAbilityIconSize(UIScriptWidget_HeroStat Button)
{
    local UIScriptWidget_HeroStat Template;
    if(Button == none || Button.StatType != LU_HEROABILITYONE) return;
    Template=UIScriptWidget_HeroStat(Button.ObjectArchetype);
    if(Template == none) return;
    // Use the original widget artwork size, never the already-scaled instance.
    // The native renderer keeps it centered without changing the frame/hitbox.
    Button.IconSizeX=Template.IconSizeX*0.85;
    Button.IconSizeY=Template.IconSizeY*0.85;
}

function DunDefHero ResolveHero(DunDefHero H)
{
    local int I;
    for(I=0; I<Replacements.Length; I++) if(Replacements[I].OldHero == H) return Replacements[I].NewHero;
    return H;
}

function Apply(APViewportClient V, APUnlockState State)
{
    local DunDefHeroManager M;
    local DunDefHero H;
    local APChaosHero R;
    local HeroReplacement Pair;
    local DunDefPlayerController PC;
    local DunDefPlayer P;
    local HeroEquipment E;
    local DunDefTower T;
    local int I,J;
    local bool Changed;
    local array<DunDefUIScene> Scenes;
    local DunDefUIScene Scene;
    local UI_HeroInfoNew Info;
    local UI_EquipmentInfo EquipmentInfo;
    local UIScriptWidget_HeroStat Button;
    local DataListEntryInterface HeroEntry;
    if(State == none || !State.bChaosLoadouts) return;
    M=class'DunDefHeroManager'.static.GetHeroManager();
    if(M == none) return;
    for(I=0; I<M.LocalLoadedHeroes.Length; I++)
    {
        HeroEntry=M.LocalLoadedHeroes[I];
        H=DunDefHero(HeroEntry);
        if(H == none || APChaosHero(H) != none) continue;
        R=class'APChaosHero'.static.FromHero(H);
        if(R == none) continue;
        Pair.OldHero=H; Pair.NewHero=R;
        Replacements.AddItem(Pair);
        M.LocalLoadedHeroes[I]=DataListEntryInterface(R);
        for(J=0; J<M.ActiveHeroes.Length; J++) if(M.ActiveHeroes[J] == H) M.ActiveHeroes[J]=R;
        if(H.ActivePlayer != none)
        {
            PC=DunDefPlayerController(H.ActivePlayer.Actor);
            if(PC != none && PC.MyHero == H)
            {
                PC.PrivateSetHero(R);
                P=DunDefPlayer(PC.Pawn);
                if(P != none && P.MyPlayerHero == H) P.MyPlayerHero=R;
            }
        }
        foreach R.HeroEquipments(E) if(E != none && E.EquipmentHero == H) E.EquipmentHero=R;
        foreach R.HeroTowers(T) if(T != none && T.CreatorHero == H) T.CreatorHero=R;
        H.ActivePlayer=none;
        Changed=true;
    }
    if(Changed && V.theSceneClient != none) DunDefSceneClient(V.theSceneClient).RefreshHeroLists();
    if(V.theSceneClient == none) return;
    Scenes=V.GetActiveUIScenesFromClass(class'DunDefUIScene');
    foreach Scenes(Scene)
    {
        EquipmentInfo=UI_EquipmentInfo(Scene);
        if(EquipmentInfo != none) EquipmentInfo.MyHero=ResolveHero(EquipmentInfo.MyHero);
        Info=UI_HeroInfoNew(Scene);
        if(Info == none) continue;
        Info.MyHero=ResolveHero(Info.MyHero);
        if(APChaosHero(Info.MyHero) == none) continue;
        foreach Info.HeroStatButtons(Button)
        {
            Button.MyHero=Info.MyHero;
            if(Button.StatType == LU_HEROABILITYONE)
            {
                Button.bDoesStatHaveLevelRequirement=false;
                ApplyAbilityIconSize(Button);
            }
            if(Button.StatType == LU_HEROABILITYTWO)
            {
                // Return any pending points if this screen was opened before
                // the private stat wrapper was attached. Never discard points.
                Info.PointsToSpend+=Button.LevelUpPoints;
                Button.LevelUpPoints=0;
                Button.SetVisibility(false);
                Button.SetEnabled(false);
                Button.AcceptGamepadNavigation=false;
                Button.bIsClickable=false;
            }
        }
    }
}

