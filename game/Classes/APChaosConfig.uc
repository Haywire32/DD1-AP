// Skill Shuffle seed projection. Never accept asset paths or reroll in the game.
class APChaosConfig extends Object config(DD1ArchipelagoUnlocks);

struct APChaosAssignment
{
    var string SourceHero;
    var string SourceAction;
    var string RecipientHero;
    var int ActionSlot;
    var string RecipientAction;
};
var config int Schema;
var config string MappingToken;
var config string SeedIdentity;
var config int PlayerSlot;
var config array<string> ActiveHeroes;
var config array<APChaosAssignment> Assignments;
var APUnlockState Keys;
var DunDefHeroManager Templates;

function Initialize()
{
    Keys = new(self) class'APUnlockState';
    Templates = DunDefHeroManager(DynamicLoadObject("DunDefPlayers.HeroManager", class'DunDefHeroManager'));
}

function DunDefHero FindHero(string Key)
{
    local DunDefHero H;
    if(Templates == none || Keys == none) return none;
    foreach Templates.HeroTemplates(H)
        if(Keys.GetTemplateHeroKey(H) == Key) return H;
    return none;
}

function string ActionKey(DunDefPlayerAbility Template, string SourceHero)
{
    if(Template == none || Keys == none) return "";
    if(DunDefPlayerAbility_BuildTower(Template) != none)
        return Keys.GetDefenseKey(DunDefPlayerAbility_BuildTower(Template).TowerArchetype, SourceHero);
    return Keys.GetAbilityKeyForPath(PathName(Template), SourceHero);
}

function DunDefPlayerAbility Resolve(string SourceHero, string SourceAction)
{
    local DunDefHero H;
    local DunDefPlayerAbility A;
    local string Key;
    H = FindHero(SourceHero);
    if(H == none) return none;
    Key = SourceHero $ "." $ SourceAction;
    foreach H.PlayerAbilityTemplates(A)
        if(ActionKey(A,SourceHero) == Key) return A;
    foreach H.AdditionalAbilityTemplates(A)
        if(ActionKey(A,SourceHero) == Key) return A;
    return none;
}

function int ActionCount(string SourceHero)
{
    local DunDefHero H;
    local DunDefPlayerAbility A;
    local array<string> Found;
    local string Key;
    H = FindHero(SourceHero);
    if(H == none) return 0;
    foreach H.PlayerAbilityTemplates(A)
    {
        Key = ActionKey(A,SourceHero);
        if(Key != "" && Found.Find(Key) == INDEX_NONE) Found.AddItem(Key);
    }
    foreach H.AdditionalAbilityTemplates(A)
    {
        Key = ActionKey(A,SourceHero);
        if(Key != "" && Found.Find(Key) == INDEX_NONE) Found.AddItem(Key);
    }
    return Found.Length;
}

function string KeyForAbilityName(string HeroKey, name AbilityName)
{
    local DunDefHero H;
    local DunDefPlayerAbility A;
    if(AbilityName == '') return "";
    H=FindHero(HeroKey);
    if(H == none) return "";
    foreach H.PlayerAbilityTemplates(A)
        if(A.UniqueAbilityName == AbilityName) return ActionKey(A,HeroKey);
    foreach H.AdditionalAbilityTemplates(A)
        if(A.UniqueAbilityName == AbilityName) return ActionKey(A,HeroKey);
    return "";
}

function ActionWheelEntry FindWheelTemplate(string HeroKey, name AbilityName)
{
    local DunDefHero H;
    local ActionWheelEntry E;
    H=FindHero(HeroKey);
    if(H == none || H.ActionWheelTemplate == none) return none;
    foreach H.ActionWheelTemplate.EditorWheelEntries(E)
        if(E.PlayerAbilityName == AbilityName) return E;
    foreach H.AdditionalActionWheelEntries(E)
        if(E.PlayerAbilityName == AbilityName) return E;
    return none;
}

function bool IsNativeOnly(string SourceHero, string SourceAction)
{
    local string Key;
    Key=SourceHero $ "." $ SourceAction;
    return Key == "apprentice.overcharge" ||
        Key == "squire.circular_slice" ||
        Key == "countess.joust" ||
        Key == "series_ev.proton_charge_blast" ||
        Key == "barbarian.battle_leap" ||
        Key == "barbarian.battle_pound" ||
        Key == "barbarian.tornado_stance" ||
        Key == "barbarian.lightning_stance" ||
        Key == "barbarian.siphon_stance" ||
        Key == "summoner.phase_shift_overlord" ||
        (Schema < 4 && Key == "barbarian.turtle_stance") ||
        Key == "barbarian.hawk_stance";
}

function name AssignedAbilityName(string SourceHero, string SourceAction, string RecipientHero)
{
    local DunDefPlayerAbility Template;
    Template=Resolve(SourceHero,SourceAction);
    // Preserve native names for same-hero actions and their native callbacks.
    if(Template != none && SourceHero == RecipientHero) return Template.UniqueAbilityName;
    return name("APChaos_" $ SourceHero $ "_" $ SourceAction);
}

function bool ValidateStructure(APUnlockState Permissions, out string Reason)
{
    local int I,J,ExpectedCount;
    local DunDefPlayerAbility SourceTemplate,TargetTemplate;
    if(Permissions == none || !Permissions.bChaosLoadouts || (Schema < 2 || Schema > 5) || PlayerSlot <= 0 ||
        PlayerSlot != Permissions.ChaosPlayerSlot || SeedIdentity == "" ||
        SeedIdentity != Permissions.SeedIdentity || Len(MappingToken) != 32 ||
        MappingToken != Permissions.ChaosMappingToken)
    { Reason="Randomized loadout does not match this seed/player. Restart through the matching client."; return false; }
    if(ActiveHeroes.Length < 2 || ActiveHeroes.Length != Permissions.ActiveHeroes.Length)
    { Reason="Randomized hero roster does not match seed permissions."; return false; }
    Initialize();
    for(I=0; I<ActiveHeroes.Length; I++)
    {
        if(FindHero(ActiveHeroes[I]) == none || Permissions.ActiveHeroes.Find(ActiveHeroes[I]) == INDEX_NONE ||
            (Schema < 4 && ActiveHeroes[I] == "summoner"))
        { Reason="Unsupported randomized hero: " $ ActiveHeroes[I]; return false; }
        for(J=0; J<I; J++)
            if(ActiveHeroes[I] == ActiveHeroes[J])
            { Reason="Duplicate hero in randomized roster."; return false; }
        ExpectedCount += ActionCount(ActiveHeroes[I]);
    }
    if(Assignments.Length == 0 || Assignments.Length != ExpectedCount)
    { Reason="Incomplete randomized actions or mismatched game content. Use the matching 0.8.0 conversion."; return false; }
    for(I=0; I<Assignments.Length; I++)
    {
        if(ActiveHeroes.Find(Assignments[I].SourceHero) == INDEX_NONE ||
            ActiveHeroes.Find(Assignments[I].RecipientHero) == INDEX_NONE ||
            Assignments[I].ActionSlot < 0 || Assignments[I].ActionSlot >= ActionCount(Assignments[I].RecipientHero) ||
            Resolve(Assignments[I].SourceHero,Assignments[I].SourceAction) == none)
        { Reason="Invalid randomized action assignment."; return false; }
        if(IsNativeOnly(Assignments[I].SourceHero,Assignments[I].SourceAction) &&
            Assignments[I].SourceHero != Assignments[I].RecipientHero)
        { Reason="A weapon-dependent action was assigned to an incompatible hero."; return false; }
        if(Schema >= 3)
        {
            SourceTemplate=Resolve(Assignments[I].SourceHero,Assignments[I].SourceAction);
            TargetTemplate=Resolve(Assignments[I].RecipientHero,Assignments[I].RecipientAction);
            if(TargetTemplate == none ||
                ((Schema == 3 || Schema == 5) && (DunDefPlayerAbility_BuildTower(SourceTemplate) != none) !=
                 (DunDefPlayerAbility_BuildTower(TargetTemplate) != none)))
            { Reason="Separate shuffle has an invalid ability/defense slot."; return false; }
        }
        for(J=0; J<I; J++)
            if((Assignments[J].SourceHero == Assignments[I].SourceHero && Assignments[J].SourceAction == Assignments[I].SourceAction) ||
                (Schema >= 3 && Assignments[J].RecipientHero == Assignments[I].RecipientHero && Assignments[J].RecipientAction == Assignments[I].RecipientAction) ||
                (Assignments[J].RecipientHero == Assignments[I].RecipientHero && Assignments[J].ActionSlot == Assignments[I].ActionSlot))
            { Reason="Duplicate randomized action or recipient slot."; return false; }
    }
    Reason="";
    return true;
}

function bool ValidateOwnership(out string Reason)
{
    local string HeroKey, MissingHeroes, DisplayName;
    // Check the ENTIRE roster, not just the character the player selected.
    foreach ActiveHeroes(HeroKey)
        if(!class'APHeroEntitlements'.static.IsHeroLicensed(HeroKey))
        {
            DisplayName=HeroKey;
            if(Keys != none) DisplayName=Keys.GetHeroDisplayName(HeroKey);
            if(MissingHeroes != "") MissingHeroes $= ", ";
            MissingHeroes $= DisplayName;
        }
    if(MissingHeroes != "")
    {
        Reason="Required hero DLC is missing or could not be verified: " $ MissingHeroes $
            ". This randomized seed uses their abilities. Select only heroes you own when generating a new seed.";
        return false;
    }
    Reason="";
    return true;
}

function bool Validate(APUnlockState Permissions, out string Reason)
{
    return ValidateStructure(Permissions,Reason) && ValidateOwnership(Reason);
}
