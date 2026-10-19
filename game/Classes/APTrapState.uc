// Per-seed cumulative consumption survives travel, restart and reconnect.
class APTrapState extends Object config(DD1ArchipelagoTraps);
struct TrapLedger
{
    var string SeedIdentity;
    var int Used[7];
};
var config array<TrapLedger> Seeds;

function int FindSeed(string Identity)
{
    local int I;
    for(I=0; I<Seeds.Length; I++)
        if(Seeds[I].SeedIdentity == Identity) return I;
    I=Seeds.Length;
    Seeds.Length=I+1;
    Seeds[I].SeedIdentity=Identity;
    return I;
}
