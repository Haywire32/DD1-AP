// Turtle's native multipliers/costs, without Barbarian skeleton/stance pointers.
class APChaosTurtleStance extends DunDefPlayerAbility_StanceBase;

function CopyNativeSettings(DunDefPlayerAbility_StanceBase T)
{
    UniqueAbilityName=T.UniqueAbilityName;
    DescriptiveName=T.DescriptiveName;
    CastingStateNamePC=T.CastingStateNamePC;
    CastingStateNameAbility=T.CastingStateNameAbility;
    AssociatedHeroStat=T.AssociatedHeroStat;
    ActivationInterval=T.ActivationInterval;
    LobbyActivationInterval=T.LobbyActivationInterval;
    MinimumReactivationInterval=T.MinimumReactivationInterval;
    MinimumRefireTime=T.MinimumRefireTime;
    bInitialCooldownOnCreation=T.bInitialCooldownOnCreation;
    bDisableAbilityInCombatPhase=T.bDisableAbilityInCombatPhase;
    bDisableAbilityInBuildPhase=T.bDisableAbilityInBuildPhase;
    bForceAllowInBuildPhase=T.bForceAllowInBuildPhase;
    bDisableInPureStrategy=T.bDisableInPureStrategy;
    bIgnorePureStratDisabling=T.bIgnorePureStratDisabling;
    bRequiresWalking=T.bRequiresWalking;
    bRequiresInvisibility=T.bRequiresInvisibility;
    bAllowNegativeStatusAffects=T.bAllowNegativeStatusAffects;
    bInvincibleAbility=T.bInvincibleAbility;
    bInvincibleWhileCasting=T.bInvincibleWhileCasting;
    bMultiplyReceivedDamageWhileCasting=T.bMultiplyReceivedDamageWhileCasting;
    ReceivedDamageWhileCastingPercent=T.ReceivedDamageWhileCastingPercent;
    bIgnoreMomentumWhileCasting=T.bIgnoreMomentumWhileCasting;
    bSetAsOverlordCastingAbility=T.bSetAsOverlordCastingAbility;
    bForceDisableAbilitiesInOverlord=T.bForceDisableAbilitiesInOverlord;
    bSimulateLocally=T.bSimulateLocally;
    bPressAndHoldAbility=T.bPressAndHoldAbility;
    bHideActionWheelUponActivation=T.bHideActionWheelUponActivation;
    SoundActivationConfirmation=T.SoundActivationConfirmation;
    SoundActivationFailure=T.SoundActivationFailure;
    SoundCancel=T.SoundCancel; CoolDownFinished=T.CoolDownFinished;
    SoundCancelDueToMana=T.SoundCancelDueToMana;
    TurnOnSound=T.TurnOnSound; TurnOffSound=T.TurnOffSound;
    if(LoopingActiveSoundComponent != none && T.LoopingActiveSoundComponent != none)
        LoopingActiveSoundComponent.SoundCue=T.LoopingActiveSoundComponent.SoundCue;
    LoopingSoundFadeInTime=T.LoopingSoundFadeInTime;
    LoopingSoundFadeOutTime=T.LoopingSoundFadeOutTime;
    InitialManaCostToActivate=T.InitialManaCostToActivate;
    ManaCostPerSecond=T.ManaCostPerSecond;
    ManaCostIncreaseTimeInterval=T.ManaCostIncreaseTimeInterval;
    ManaCostIncreaseLinearFactor=T.ManaCostIncreaseLinearFactor;
    ManaCostIncreaseExponentialFactor=T.ManaCostIncreaseExponentialFactor;
    HeroStatManaCostExponentScale=T.HeroStatManaCostExponentScale;
    bConsumeManaOverTime=T.bConsumeManaOverTime;
    bRequiresInitialManaCost=T.bRequiresInitialManaCost;
    GroundSpeed=T.GroundSpeed; AttackDamage=T.AttackDamage;
    AttackSpeed=T.AttackSpeed; AttackKnockBack=T.AttackKnockBack;
    MomentumMultiplier=T.MomentumMultiplier; DamageResistance=T.DamageResistance;
    JumpZMultiplier=T.JumpZMultiplier; bNullifyJumpModifier=T.bNullifyJumpModifier;
    bIsTurtleStance=true;
    bAllowActivateWhileCasting=T.bAllowActivateWhileCasting;
    AbilityStatModifierTemplate=T.AbilityStatModifierTemplate;
    BuffToApplyToInstigatorOnActivate=T.BuffToApplyToInstigatorOnActivate;
    BuffToApplyToInstigatorOnDeactivate=T.BuffToApplyToInstigatorOnDeactivate;
    bRemoveBuffsOnDeactivate=T.bRemoveBuffsOnDeactivate;
    bRemoveBuffsOnCompletion=T.bRemoveBuffsOnCompletion;
}

simulated function OnActivate()
{
    super(DunDefPlayerAbility_CharacterToggle).OnActivate();
}

state AbilityToggleActive
{
    simulated event BeginState(name PreviousStateName)
    {
        bStatusActive=true;
        // Qualified super state calls resolve the global event in UE3, not
        // CharacterToggle's state event. Keep its mana/toggle lifecycle here
        // without invoking StanceBase's DualMelee-only animation/socket code.
        bToggleEnabled=true;
        bForceNetUpdate=true;
        if(TurnOnSound != none) Instigator.PlaySound(TurnOnSound,true);
        if(LoopingActiveSoundComponent != none && LoopingActiveSoundComponent.SoundCue != none)
            LoopingActiveSoundComponent.FadeIn(LoopingSoundFadeInTime,1);
        if(Role == ROLE_Authority)
        {
            if(bConsumeManaOverTime) SetTimer(1.0,true,'DecreaseMana');
            if(bRequiresInitialManaCost && GetPC().AddManaPower(-InitialManaCostToActivate,true) == 0)
                CancelAbility();
        }
    }

    simulated event EndState(name NextStateName)
    {
        bStatusActive=false;
        if(TurnOnSound != none) Instigator.StopSound(TurnOnSound,0.2);
        if(TurnOffSound != none) Instigator.PlaySound(TurnOffSound,true);
        if(LoopingActiveSoundComponent != none && LoopingActiveSoundComponent.SoundCue != none)
            LoopingActiveSoundComponent.FadeOut(LoopingSoundFadeOutTime,0);
        bToggleEnabled=false;
        bForceNetUpdate=true;
        ClearTimer('DecreaseMana');
    }
}

function AdjustDamage(out int Damage, out Vector Momentum, Controller InstigatedBy,
    Vector HitLocation, class<DamageType> DamageType, optional TraceHitInfo HitInfo, optional Object WhatHitMe)
{
    super.AdjustDamage(Damage,Momentum,InstigatedBy,HitLocation,DamageType,HitInfo,WhatHitMe);
    // The generic ability damage hook replaces DualMelee's stance-only hook.
    if(IsActive() && (!ClassIsChildOf(DamageType,class'DunDefDamageType') ||
        !class<DunDefDamageType>(DamageType).default.bIgnoreMomentumResistance))
        Momentum *= GetPlayerMomentumMultiplier();
}
