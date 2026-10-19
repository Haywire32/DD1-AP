class APGearReward extends Object;

static function HeroEquipment CloneSavedShopGear(DunDefHeroManager Manager, DunDefHero Hero, optional bool bAllowPets)
{
    local array<HeroEquipment> Candidates;
    local HeroEquipment Template, Eq;
    local EquipmentNetInfo EquipmentInfo;
    local int SetIndex, ItemIndex;

    if(Manager == none || Hero == none)
        return none;
    // Include native familiar stock only when the seed opts into pet rewards.
    // Saved stock remains available regardless of the delivery map.
    for(SetIndex = bAllowPets ? 0 : 1; SetIndex <= 2; SetIndex++)
    {
        for(ItemIndex = 0; ItemIndex < Manager.ShopEquipments[SetIndex].Equipments.Length; ItemIndex++)
        {
            Template = Manager.ShopEquipments[SetIndex].Equipments[ItemIndex];
            if(Template == none)
                continue;
            if(Template.EquipmentType == EQT_WEAPON && !Hero.AllowPickupWeaponType(Template.WeaponType))
                continue;
            if(!(bAllowPets && Template.EquipmentType == EQT_FAMILIAR) && Template.EquipmentType != EQT_WEAPON &&
                (Template.EquipmentType < EQT_ARMOR_TORSO || Template.EquipmentType > EQT_ARMOR_GLOVES))
                continue;
            Candidates.AddItem(Template);
        }
    }
    if(Candidates.Length == 0)
        return none;
    Template = Candidates[Rand(Candidates.Length)];
    EquipmentInfo = Template.GetNetInfo(true);
    Eq = class'HeroEquipment'.static.CreateEquipmentFromNetInfo(EquipmentInfo,,Manager);
    if(Eq != none)
    {
        Eq.bIsShopEquipment = false;
        Eq.bIsLocked = false;
    }
    return Eq;
}

static function HeroEquipment RollEquipment(DunDefHeroManager Manager, DunDefHero Hero, APRewardState RewardState, optional bool bAllowPets)
{
    local array<EquipmentDropEntry> NoAdditionalEntries;
    local HeroEquipment Template, Eq;
    local EquipmentNetInfo EquipmentInfo;
    local EEquipmentType TypeFilter;
    local int Attempt;
    local float Quality, ExtraRarity, RandomizerMultiplier;

    if(Manager == none || Hero == none)
        return none;

    // Existing profiles already have native shop stock saved from their latest
    // completion. Use that immediately after upgrading instead of requiring an
    // additional clear before rewards stop looking like level-one starter gear.
    if(RewardState == none || RewardState.BestGearScaleScore <= 0.0)
    {
        Eq = CloneSavedShopGear(Manager, Hero, bAllowPets);
        if(Eq != none)
            return Eq;
    }

    // Match DD1's initial Tavern stock defaults until this seed records a new
    // completed-map scale and no suitable saved shop item exists.
    Quality = 0.3 * Manager.ShopItemQualityMutliplier + Manager.ShopItemQualityAddition;
    ExtraRarity = -0.1 * Manager.ShopRarityMultiplier + Manager.ShopRarityAddition;
    RandomizerMultiplier = 1.0;
    if(RewardState != none && RewardState.BestGearScaleScore > 0.0)
    {
        Quality = RewardState.BestGearQuality;
        ExtraRarity = RewardState.BestGearExtraRarity;
        RandomizerMultiplier = FMax(1.0, RewardState.BestGearRandomizerMultiplier);
    }

    // Equal category chances when enabled: pets, weapons, armour. With pets
    // disabled, preserve the existing weapon/armour split and saved scaling.
    for(Attempt = 0; Attempt < 20; Attempt++)
    {
        if(bAllowPets && Rand(3) == 0)
            TypeFilter = EQT_FAMILIAR;
        else
            TypeFilter = FRand() < 0.5 ? EQT_WEAPON : EQT_ARMOR_TORSO;
        if(TypeFilter == EQT_FAMILIAR)
            Template = Manager.GetGlobalEquipmentDrop(0, 0, ExtraRarity, Quality,
                TypeFilter, true, Manager.AdditionalEquipmentEntries, true, false);
        else
            Template = Manager.GetGlobalEquipmentDrop(0, 0, ExtraRarity, Quality,
                TypeFilter, true, NoAdditionalEntries, true, false);
        if(Template == none)
            continue;
        if(Template.EquipmentType == EQT_WEAPON && !Hero.AllowPickupWeaponType(Template.WeaponType))
            continue;
        if(!(bAllowPets && Template.EquipmentType == EQT_FAMILIAR) && Template.EquipmentType != EQT_WEAPON &&
            (Template.EquipmentType < EQT_ARMOR_TORSO || Template.EquipmentType > EQT_ARMOR_GLOVES))
            continue;

        // Use the same clone and shop-randomization path as DD1's
        // SetRandomShopEquipments(), with the completed-map multiplier saved
        // above instead of whichever map happens to be open at delivery time.
        EquipmentInfo = Template.GetNetInfo(true);
        Eq = class'HeroEquipment'.static.CreateEquipmentFromNetInfo(EquipmentInfo,,Manager);
        if(Eq == none)
            continue;
        Eq.AddRandomizeValues(Quality, false, true, RandomizerMultiplier, true, true);
        Eq.bIsShopEquipment = false;
        return Eq;
    }
    return none;
}
