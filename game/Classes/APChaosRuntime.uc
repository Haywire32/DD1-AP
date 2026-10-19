// Seed-assigned Skill Shuffle loadouts. Gameplay remains gated on validated
// assignments, native DLC ownership and the seed's current item permissions.
class APChaosRuntime extends Info;

struct APChaosInstance
{
    var DunDefPlayerAbility Ability;
    var DunDefPlayerController PC;
    var DunDefPlayer Pawn;
    var DunDefHero Hero;
    var string Recipient;
    var string SourceKey;
    var int ActionSlot;
};
struct APChaosPlayer
{
    var DunDefPlayerController PC;
    var DunDefPlayer Pawn;
    var DunDefHero Hero;
    var string Recipient;
    var bool bReady;
};
var APChaosConfig Mapping;
var APUnlockState Permissions;
var array<APChaosInstance> Instances;
var array<APChaosPlayer> Players;
var bool bApplying;

function bool Initialize(APUnlockState InPermissions, out string Reason)
{
    if(WorldInfo.NetMode != NM_Standalone) return false;
    Mapping = new(self) class'APChaosConfig';
    if(!Mapping.Validate(InPermissions,Reason)) { Mapping=none; return false; }
    Permissions=InPermissions;
    return true;
}

function bool IsPreserved(DunDefPlayerController PC, DunDefPlayerAbility A)
{
    local DunDefHero H;
    local string Key;
    if(PC == none || A == none || A.bDeleteMe || Permissions == none || PC.GetHero() == none) return false;
    H=PC.GetHero().GetCurrentHeroTemplate();
    Key=Permissions.GetHeroKey(PC.GetHero());
    // Weapon controls remain native and are never shuffled or copied from a
    // donor. Common utilities retain their actual existing instances/bindings.
    return (H != none && H.WeaponAbilityTemplate != none &&
        (A == H.WeaponAbilityTemplate || A.ObjectArchetype == H.WeaponAbilityTemplate)) ||
        Permissions.IsBasicAbility(A,Key);
}

function int FindInstance(DunDefPlayerAbility A)
{
    local int I;
    if(A == none || A.bDeleteMe) return INDEX_NONE;
    for(I=0; I<Instances.Length; I++)
        if(Instances[I].Ability == A) return I;
    return INDEX_NONE;
}

function bool IsCurrent(DunDefPlayerController PC)
{
    local int I,J,Count;
    local DunDefPlayerAbility A;
    if(PC == none || PC.bDeleteMe || PC.Pawn == none || PC.Pawn.bDeleteMe || PC.Pawn.Health <= 0 ||
        Mapping == none || Permissions == none || !Permissions.bChaosLoadouts ||
        Mapping.MappingToken != Permissions.ChaosMappingToken || Mapping.SeedIdentity != Permissions.SeedIdentity ||
        Mapping.PlayerSlot != Permissions.ChaosPlayerSlot)
        return false;
    for(I=0; I<Players.Length; I++)
        if(Players[I].PC == PC)
        {
            if(!Players[I].bReady || Players[I].Pawn != PC.Pawn || Players[I].Hero != PC.GetHero() ||
                Players[I].Recipient != Permissions.GetHeroKey(PC.GetHero())) return false;
            for(J=0; J<Instances.Length; J++)
                if(Instances[J].PC == PC)
                {
                    A=Instances[J].Ability;
                    if(A == none || A.bDeleteMe || A.Instigator != PC.Pawn || A.GetPC() != PC ||
                        PC.PlayerAbilities.Find(A) == INDEX_NONE || Players[I].Pawn.PlayerAbilities.Find(A) == INDEX_NONE)
                        return false;
                    Count++;
                }
            if(Count != Mapping.ActionCount(Players[I].Recipient) + (Players[I].Recipient == "summoner" ? 1 : 0)) return false;
            foreach PC.PlayerAbilities(A)
                if(A != none && !A.bDeleteMe && !IsPreserved(PC,A) && FindInstance(A) == INDEX_NONE)
                    return false;
            return true;
        }
    return false;
}

function bool NativeUtilitiesReady(DunDefPlayerController PC)
{
    local DunDefPlayerAbility A,Template;
    local DunDefHero H;
    local bool Found;
    local array<DunDefPlayerAbility> Expected;
    if(PC == none || PC.GetHero() == none || PC.Pawn == none) return false;
    H=PC.GetHero().GetCurrentHeroTemplate();
    if(H == none) return false;
    Expected=H.PlayerAbilityTemplates;
    foreach H.AdditionalAbilityTemplates(Template) Expected.AddItem(Template);
    if(H.WeaponAbilityTemplate != none) Expected.AddItem(H.WeaponAbilityTemplate);
    foreach Expected(Template)
        if(Template != none && (Template == H.WeaponAbilityTemplate ||
            Permissions.IsBasicAbilityPath(PathName(Template),Permissions.GetHeroKey(PC.GetHero()))))
        {
            Found=false;
            foreach PC.PlayerAbilities(A)
                if(A != none && !A.bDeleteMe && A.ObjectArchetype == Template &&
                    A.Instigator == PC.Pawn && A.GetPC() == PC)
                { Found=true; break; }
            if(!Found) return false;
        }
    return PC.PlayerAbilities.Length > 0;
}

function Discard(DunDefPlayerAbility A)
{
    if(A == none || A.bDeleteMe) return;
    if(A.InitializedForOwner) A.ServerCancel();
    // A failed allocation batch has not registered an instigator. Stock
    // Destroyed assumes a pawn for this flag; do not touch shared templates.
    if(A.Instigator == none) A.bSimulateLocally=false;
    A.Destroy();
}

function ClearFor(DunDefPlayerController PC)
{
    local int I;
    for(I=Players.Length-1; I>=0; I--)
        if(Players[I].PC == PC) Players.Remove(I,1);
    for(I=Instances.Length-1; I>=0; I--)
        if(Instances[I].PC == PC)
        {
            Discard(Instances[I].Ability);
            Instances.Remove(I,1);
        }
}

function DunDefPlayerAbility Allocate(DunDefPlayerController PC, DunDefPlayerAbility Template)
{
    local APChaosTurtleStance Turtle;
    if(Template == Mapping.Resolve("barbarian","turtle_stance") &&
        Permissions.GetHeroKey(PC.GetHero()) != "barbarian")
    {
        Turtle=Spawn(class'APChaosTurtleStance',PC,,,,,true);
        if(Turtle != none) Turtle.CopyNativeSettings(DunDefPlayerAbility_StanceBase(Template));
        return Turtle;
    }
    return Spawn(Template.Class,PC,,, ,Template,true);
}

function ConfigureCrossHero(DunDefPlayerAbility A, string SourceHero, string RecipientHero)
{
    local DunDefPlayerAbility_GenericActorSpawner Spell;
    local DunDefPlayerAbility_BuildTower Builder;
    if(SourceHero == RecipientHero) return;
    Builder=DunDefPlayerAbility_BuildTower(A);
    if(Builder != none)
    {
        Builder.bUseSpellCompleteOverrideAnim=false;
        Builder.bUseCastingOverrideAnim=false;
        Builder.CancelAbilityAnim='';
        Builder.ChoosingBuildWeaponEmitter=none;
    }
    Spell=DunDefPlayerAbility_GenericActorSpawner(A);
    if(Spell == none) return;
    // Use the native timer/projectile/effect, not a donor's skeleton or muzzle.
    // Multi-actor spells derive from this class and use these same fields.
    // These are per-instance visual/attachment changes only: costs, cooldowns,
    // cast time, damage, targeting, spread and effect templates stay native.
    Spell.CastingCharacterAnimation='';
    Spell.CompletedCharacterAnimation='';
    Spell.bPlayFullBodyAnimation=false;
    Spell.bForceFullBodyCompletionAnimation=false;
    Spell.PlayShootAnimation=false;
    Spell.PlayBigShootAnimation=false;
    Spell.CharacterEmitterSocketName='';
    Spell.CastingWeaponEmitter=none;
    Spell.CompletedWeaponEmitter=none;
    if(Spell.TakeTransformationFromWeapon)
    {
        Spell.TakeTransformationFromWeapon=false;
        Spell.TakeTransformationFromInstigator=true;
    }
    if(Spell.SpawnedBaseOnWeapon)
    {
        Spell.SpawnedBaseOnWeapon=false;
        Spell.SpawnedBaseOnInstigator=true;
    }
}

function bool Apply(DunDefPlayerController PC, out string Reason)
{
    local array<DunDefPlayerAbility> Staged, Old;
    local array<int> Rows;
    local DunDefPlayerAbility A,Template,ExtraTemplate;
    local DunDefPlayer P;
    local string Recipient;
    local APChaosInstance Entry;
    local APChaosPlayer PlayerEntry;
    local int I,J,Count;
    if(bApplying || WorldInfo.NetMode != NM_Standalone || WorldInfo.Pauser != none ||
        PC == none || PC.GetHero() == none || Mapping == none || Permissions == none)
    { Reason="Randomized loadout is waiting for a stable local hero."; return false; }
    P=DunDefPlayer(PC.Pawn);
    if(P == none || P.bDeleteMe || P.Health <= 0) return false;
    if(IsCurrent(PC)) return true;
    // Native creation/destruction can happen over more than one frame. Never
    // declare a loadout ready during the gap and leave heal/repair/etc missing.
    if(!NativeUtilitiesReady(PC))
    { Reason="Waiting for the game's original hero controls."; return false; }
    if(!Mapping.Validate(Permissions,Reason)) return false;
    Recipient=Permissions.GetHeroKey(PC.GetHero());
    if(!Permissions.IsHeroUnlocked(Recipient) || Mapping.ActiveHeroes.Find(Recipient) == INDEX_NONE)
    { Reason="The randomized recipient hero is locked."; return false; }
    bApplying=true;
    Count=Mapping.ActionCount(Recipient);
    // Allocate the ENTIRE replacement before cancelling/destroying anything.
    // Templates, hero saves, costumes and the other split-screen slots stay
    // unchanged. Failure leaves the old lists intact (and AP gates closed).
    for(I=0; I<Count; I++)
        for(J=0; J<Mapping.Assignments.Length; J++)
            if(Mapping.Assignments[J].RecipientHero == Recipient && Mapping.Assignments[J].ActionSlot == I)
            {
                Template=Mapping.Resolve(Mapping.Assignments[J].SourceHero,Mapping.Assignments[J].SourceAction);
                A=Allocate(PC,Template);
                if(A == none)
                {
                    foreach Staged(A) Discard(A);
                    bApplying=false;
                    Reason="Could not allocate the complete randomized loadout.";
                    return false;
                }
                Staged.AddItem(A);
                Rows.AddItem(J);
                // Phase Shift and Overlord are two linked native controls for
                // ONE AP unlock. Keep both on Summoner, not one dead shortcut.
                if(Recipient == "summoner" && Mapping.Assignments[J].SourceAction == "phase_shift_overlord")
                {
                    foreach Mapping.FindHero(Recipient).PlayerAbilityTemplates(ExtraTemplate)
                        if(ExtraTemplate != Template && Mapping.ActionKey(ExtraTemplate,Recipient) == "summoner.phase_shift_overlord")
                        {
                            A=Allocate(PC,ExtraTemplate);
                            if(A != none) { Staged.AddItem(A); Rows.AddItem(J); }
                        }
                    foreach Mapping.FindHero(Recipient).AdditionalAbilityTemplates(ExtraTemplate)
                        if(ExtraTemplate != Template && Mapping.ActionKey(ExtraTemplate,Recipient) == "summoner.phase_shift_overlord")
                        {
                            A=Allocate(PC,ExtraTemplate);
                            if(A != none) { Staged.AddItem(A); Rows.AddItem(J); }
                        }
                }
                break;
            }
    if(Staged.Length != Count + (Recipient == "summoner" ? 1 : 0))
    {
        foreach Staged(A) Discard(A);
        bApplying=false;
        Reason="Incomplete randomized loadout.";
        return false;
    }
    Old=PC.PlayerAbilities;
    ClearFor(PC);
    foreach Old(A)
        if(!IsPreserved(PC,A)) Discard(A);
    PlayerEntry.PC=PC;
    PlayerEntry.Pawn=P;
    PlayerEntry.Hero=PC.GetHero();
    PlayerEntry.Recipient=Recipient;
    PlayerEntry.bReady=false;
    Players.AddItem(PlayerEntry);
    for(I=0; I<Staged.Length; I++)
    {
        J=Rows[I];
        A=Staged[I];
        Entry.Ability=A;
        Entry.PC=PC;
        Entry.Pawn=P;
        Entry.Hero=PC.GetHero();
        Entry.Recipient=Recipient;
        Entry.SourceKey=Mapping.Assignments[J].SourceHero $ "." $ Mapping.Assignments[J].SourceAction;
        Entry.ActionSlot=I;
        Instances.AddItem(Entry);
        A.UniqueAbilityName=Mapping.AssignedAbilityName(Mapping.Assignments[J].SourceHero,
            Mapping.Assignments[J].SourceAction,Recipient);
        if(Mapping.Assignments[J].SourceAction == "phase_shift_overlord")
            A.UniqueAbilityName=DunDefPlayerAbility(A.ObjectArchetype).UniqueAbilityName;
        A.RequiredHeroLevel=0;
        A.bWasUnderRequiredLevel=false;
        ConfigureCrossHero(A,Mapping.Assignments[J].SourceHero,Recipient);
        A.InitializeForController(PC);
        A.InitializeForPlayer(P);
        A.ClearTimer('LocalNotifyUnlock');
    }
    Players[Players.Length-1].bReady=true;
    bApplying=false;
    Reason="";
    return IsCurrent(PC);
}

function bool CanUse(DunDefPlayerAbility A)
{
    local int I;
    I=FindInstance(A);
    if(I == INDEX_NONE || bApplying || !IsCurrent(Instances[I].PC) ||
        Instances[I].Hero != Instances[I].PC.GetHero() || Instances[I].Pawn != Instances[I].PC.Pawn ||
        !Permissions.IsHeroUnlocked(Instances[I].Recipient)) return false;
    if(DunDefPlayerAbility_BuildTower(A) != none)
        return Permissions.IsDefenseUnlocked(Instances[I].SourceKey);
    return Permissions.IsAbilityUnlocked(Instances[I].SourceKey);
}

function bool CanBuild(DunDefPlayerController PC, DunDefTower Tower)
{
    local int I;
    local DunDefPlayerAbility_BuildTower B;
    if(Tower == none || !IsCurrent(PC)) return false;
    for(I=0; I<Instances.Length; I++)
        if(Instances[I].PC == PC)
        {
            B=DunDefPlayerAbility_BuildTower(Instances[I].Ability);
            if(B != none && B.TowerArchetype == Tower && CanUse(B)) return true;
        }
    return false;
}

function bool RemapWheel(ActionWheel Wheel, out array<ActionWheelEntry> Entries, out string Reason)
{
    local array<ActionWheelEntry> Replaced;
    local array<string> OriginalKeys;
    local ActionWheelEntry E,Donor,Replacement;
    local DunDefPlayerAbility Template;
    local string Recipient,Key;
    local int I,J,Slot;
    if(Wheel == none || Wheel.PCOwner == none || Mapping == none || Permissions == none ||
        !Mapping.Validate(Permissions,Reason)) return false;
    Recipient=Permissions.GetHeroKey(Wheel.PCOwner.GetHero());
    foreach Entries(E)
    {
        Key=Mapping.KeyForAbilityName(Recipient,E.PlayerAbilityName);
        if(Key != "" && OriginalKeys.Find(Key) == INDEX_NONE) OriginalKeys.AddItem(Key);
    }
    if(OriginalKeys.Length != Mapping.ActionCount(Recipient))
    { Reason="The action menu does not contain the full hero action set."; return false; }
    Replaced=Entries;
    for(I=0; I<Entries.Length; I++)
    {
        E=Entries[I];
        Key=Mapping.KeyForAbilityName(Recipient,E.PlayerAbilityName);
        if(Key == "") continue;
        if(Key == "summoner.phase_shift_overlord") continue;
        Slot=OriginalKeys.Find(Key);
        for(J=0; J<Mapping.Assignments.Length; J++)
            if(Mapping.Assignments[J].RecipientHero == Recipient &&
                ((Mapping.Schema == 2 && Mapping.Assignments[J].ActionSlot == Slot) ||
                 (Mapping.Schema >= 3 && Key == (Recipient $ "." $ Mapping.Assignments[J].RecipientAction))))
            {
                Template=Mapping.Resolve(Mapping.Assignments[J].SourceHero,Mapping.Assignments[J].SourceAction);
                Donor=Mapping.FindWheelTemplate(Mapping.Assignments[J].SourceHero,Template.UniqueAbilityName);
                if(Donor == none || Donor.DoConsoleCommand != "")
                { Reason="Randomized action has no supported menu entry."; return false; }
                Replacement=new(Wheel) Donor.Class(Donor);
                Replacement.WheelEntryName=E.WheelEntryName;
                Replacement.WheelParentName=E.WheelParentName;
                Replacement.ForceHotKeyIndex=E.ForceHotKeyIndex;
                Replacement.PlayerAbilityName=Mapping.AssignedAbilityName(Mapping.Assignments[J].SourceHero,
                    Mapping.Assignments[J].SourceAction,Recipient);
                Replacement.EntryPlayerAbility=none;
                Replacement.EntryParent=none;
                Replacement.EntryChildren.Length=0;
                Replacement.FlashOnLevelUp=false;
                Replaced[I]=Replacement;
                break;
            }
    }
    // Only per-wheel instances change. Existing entry names/hotkey names and
    // all utility entries remain intact; donor icons/descriptions follow the
    // assigned action. Native initialization builds parents and hotkey links.
    Entries=Replaced;
    Reason="";
    return true;
}

event Destroyed()
{
    while(Players.Length > 0) ClearFor(Players[0].PC);
    while(Instances.Length > 0) ClearFor(Instances[0].PC);
    super.Destroyed();
}
