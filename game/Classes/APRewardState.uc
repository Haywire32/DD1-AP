class APRewardState extends Object
    config(DD1ArchipelagoRewards);

var config int AppliedXPRewards;
var config int AppliedManaRewards;
var config int AppliedGearRewards;
var config string AppliedSeedIdentity;
// Strongest native tavern-shop roll reached by completing a map in this seed.
// These values let a later AP gear reward use the same scale in the Tavern or
// on a different map instead of falling back to level-one equipment.
var config float BestGearQuality;
var config float BestGearExtraRarity;
var config float BestGearRandomizerMultiplier;
var config float BestGearScaleScore;

defaultproperties
{
    AppliedXPRewards=0
    AppliedManaRewards=0
    AppliedSeedIdentity=""
    BestGearQuality=0.0
    BestGearExtraRarity=-0.1
    BestGearRandomizerMultiplier=1.0
    BestGearScaleScore=0.0
}
