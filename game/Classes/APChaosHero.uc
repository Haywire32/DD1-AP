// Skill Shuffle stat policy. Retail templates, equipment and save format stay native.
class APChaosHero extends DunDefHero;
var DunDefHero GenericStatTemplate;
var transient APShopLogo AbilityIconArtwork;

static function APChaosHero FromHero(DunDefHero H)
{
    local APChaosHero R;
    local DunDefHero T;
    local int I;
    if(H == none) return none;
    if(APChaosHero(H) != none) return APChaosHero(H);
    T=H.GetCurrentHeroTemplate();
    if(T == none || H.Class != class'DunDefHero') return none;
    // Template directly from the retail archetype, NOT the live hero. Native
    // code compares ObjectArchetype for rewards, class identity and save paths.
    R=new(H.Outer) class'APChaosHero'(T);
    if(R == none) return none;
    R.GenericStatTemplate=DunDefHero(DynamicLoadObject("DunDefPlayers.HeroTemplateRecruit",class'DunDefHero'));
    R.HeroName=H.HeroName;
    R.HeroLevel=H.HeroLevel;
    R.HeroExperience=H.HeroExperience;
    R.HeroHealthModifier=H.HeroHealthModifier;
    R.HeroSpeedModifier=H.HeroSpeedModifier;
    R.HeroDamageModifier=H.HeroDamageModifier;
    R.HeroCastingModifier=H.HeroCastingModifier;
    // Do not migrate or duplicate saved points. Read both legacy fields as
    // one pool; new point spending uses the first field only.
    R.HeroAbilityOneModifier=H.HeroAbilityOneModifier;
    R.HeroAbilityTwoModifier=H.HeroAbilityTwoModifier;
    R.HeroDefenseHealthModifier=H.HeroDefenseHealthModifier;
    R.HeroDefenseAttackRateModifier=H.HeroDefenseAttackRateModifier;
    R.HeroDefenseDamageModifier=H.HeroDefenseDamageModifier;
    R.HeroDefenseAreaOfEffectModifier=H.HeroDefenseAreaOfEffectModifier;
    R.ManaPower=H.ManaPower;
    R.LastPawnHealth=H.LastPawnHealth;
    R.GUID1=H.GUID1; R.GUID2=H.GUID2; R.GUID3=H.GUID3; R.GUID4=H.GUID4;
    R.GameplayInstanceID=H.GameplayInstanceID;
    R.UserID=H.UserID;
    R.CurrentCostumeIndex=H.CurrentCostumeIndex;
    R.color1=H.color1; R.color2=H.color2; R.color3=H.color3;
    R.bDidRespec=H.bDidRespec; R.bGaveExpBonus=H.bGaveExpBonus; R.bAllowRename=H.bAllowRename;
    R.SubstituteNameIndex=H.SubstituteNameIndex;
    R.bIsLocalLoadedHero=H.bIsLocalLoadedHero;
    R.bIsNameOnlineVerified=H.bIsNameOnlineVerified;
    R.bIsNameOnlineRejected=H.bIsNameOnlineRejected;
    R.ActivePlayer=H.ActivePlayer;
    R.OwnerPRI=H.OwnerPRI;
    R.HeroEquipments=H.HeroEquipments;
    R.HeroWeaponEquipment=H.HeroWeaponEquipment;
    R.HeroTowers=H.HeroTowers;
    R.HotKeys=H.HotKeys;
    R.bHasCompleteArmorSet=H.bHasCompleteArmorSet;
    R.activeCosmeticSet=H.activeCosmeticSet;
    R.MyHeroIconMatInst=H.MyHeroIconMatInst;
    R.MyTalkingHeroIconMatInst=H.MyTalkingHeroIconMatInst;
    R.MyTalkingIconMatInst=H.MyTalkingIconMatInst;
    R.ColorableMiniMapIconMatInst=H.ColorableMiniMapIconMatInst;
    for(I=0; I<ArrayCount(H.CachedBuffStatModifiers); I++) R.CachedBuffStatModifiers[I]=H.CachedBuffStatModifiers[I];
    return R;
}

function int GetStatValue(LevelUpValueType Stat, optional bool BaseOnly, optional out int EquipmentChange, optional bool EquipmentOnly)
{
    local int Value;
    if(Stat != LU_HEROABILITYONE && Stat != LU_HEROABILITYTWO)
        return super.GetStatValue(Stat,BaseOnly,EquipmentChange,EquipmentOnly);
    if(EquipmentOnly) return GetTotalEquipmentStatValue(Stat,EquipmentChange);
    Value=HeroAbilityOneModifier+HeroAbilityTwoModifier;
    if(BaseOnly) return Value;
    return Max(0,Value+GetTotalEquipmentStatValue(Stat,EquipmentChange));
}

function int GetTotalEquipmentStatValue(LevelUpValueType Stat, optional out int EquipmentChange)
{
    if(Stat != LU_HEROABILITYONE && Stat != LU_HEROABILITYTWO)
        return super.GetTotalEquipmentStatValue(Stat,EquipmentChange);
    EquipmentChange=super.GetTotalEquipmentStatValue(LU_HEROABILITYONE)+super.GetTotalEquipmentStatValue(LU_HEROABILITYTWO);
    return EquipmentChange;
}

function string GetStatName(LevelUpValueType Stat)
{
    if(Stat == LU_HEROABILITYONE || Stat == LU_HEROABILITYTWO) return "Ability Power";
    if(Stat >= LU_DEFENSEHEALTH && Stat <= LU_DEFENSEAOE) return class'DunDefHero'.default.StatNames[Stat];
    return super.GetStatName(Stat);
}

function Surface GetStatIcon(LevelUpValueType Stat, optional bool EquipmentIcon)
{
    // Equipment keeps its native icons so both bonuses remain inspectable.
    if(!EquipmentIcon && (Stat == LU_HEROABILITYONE || Stat == LU_HEROABILITYTWO))
    {
        if(AbilityIconArtwork == none) AbilityIconArtwork=new(self) class'APShopLogo';
        return AbilityIconArtwork.GetIcon();
    }
    if(Stat >= LU_DEFENSEHEALTH && Stat <= LU_DEFENSEAOE && GenericStatTemplate != none)
        return GenericStatTemplate.GetStatIcon(Stat,EquipmentIcon);
    return super.GetStatIcon(Stat,EquipmentIcon);
}

function bool MeetsHeroLevelRequirement(LevelUpValueType Stat)
{
    if(Stat >= LU_HEROABILITYONE && Stat <= LU_DEFENSEAOE) return true;
    return super.MeetsHeroLevelRequirement(Stat);
}

function bool CanLevelUpStat(LevelUpValueType Stat, optional int AdditionalPoints)
{
    if(Stat == LU_HEROABILITYTWO) return false;
    return super.CanLevelUpStat(Stat,AdditionalPoints);
}

function float GetStatModifier(Object ForActor, LevelUpValueType Stat)
{
    local float Value;
    // Stances normally borrow four defense stats. Under Chaos they use the
    // same Ability Power as spells; actual towers keep native defense scaling.
    if(DunDefPlayerAbility_StanceBase(ForActor) != none && Stat == DunDefPlayerAbility(ForActor).AssociatedHeroStat)
    {
        Value=FMax(1.0,GetStatValue(LU_HEROABILITYONE));
        // Preserve each stance's curve, especially Turtle's INVERSE rate
        // curve. Replacing it with a damage curve reverses its progression.
        switch(Stat)
        {
            case LU_DEFENSEHEALTH:
                return 1.0 + StatMultInitial_DefenseHealth*(FMin(Value+1,4)**StatExpInitial_DefenseHealth-1.0) + StatMultFull_DefenseHealth*((Value+1)**StatExptFull_DefenseHealth-1.0);
            case LU_DEFENSEBASEDAMAGE:
                return 1.0 + StatMultInitial_DefenseDamage*(FMin(Value+1,4)**StatExpInitial_DefenseDamage-1.0) + StatMultFull_DefenseDamage*((Value+1)**StatExptFull_DefenseDamage-1.0);
            case LU_DEFENSEATTACKRATE:
                return 1.0 / (1.0 + StatMultInitial_DefenseAttackRate*(FMin(Value+1,4)**StatExpInitial_DefenseAttackRate-1.0) + HeroDefenseAttackRateLinearFactor*((Value+1)**HeroDefenseAttackRateExponentialFactor-1.0));
            case LU_DEFENSEAOE:
                return 1.0 + StatMultInitial_DefenseAOE*(FMin(Value+1,4)**StatExpInitial_DefenseAOE-1.0) + StatMultFull_DefenseAOE*((Value+1)**StatExptFull_DefenseAOE-1.0);
        }
    }
    if(Stat == LU_HEROABILITYONE || Stat == LU_HEROABILITYTWO)
    {
        Value=FMax(1.0,GetStatValue(Stat));
        if(GetPlayerPawn() != none)
        {
            GetPlayerPawn().GetBuffedStatvalue(Stat,Value,true);
            GetPlayerPawn().GetBuffedStatvalue(Stat,Value,false);
        }
        // Native curves, but no single-channel 11,500 guard: combining TWO
        // legitimate equipment channels can exceed that vanilla threshold.
        if(Stat == LU_HEROABILITYONE)
            return 1.0 + StatMultInitial_HeroAbilityOne*(FMin(Value+1,4)**StatExpInitial_HeroAbilityOne-1.0) +
                StatMultFull_HeroAbilityOne*((Value+1)**StatExptFull_HeroAbilityOne-1.0);
        return 1.0 + StatMultInitial_HeroAbilityTwo*(FMin(Value+1,4)**StatExpInitial_HeroAbilityTwo-1.0) +
            StatMultFull_HeroAbilityTwo*((Value+1)**StatExptFull_HeroAbilityTwo-1.0);
    }
    return super.GetStatModifier(ForActor,Stat);
}
