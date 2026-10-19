class APDeathLinkState extends Object config(DD1ArchipelagoDeathLinkOutput);
var config string SeedIdentity;
var config string Session;
var config int SeenSequence;
var config int LocalDeaths;
var config bool bReady;

function Persist()
{
    default.SeedIdentity = SeedIdentity;
    default.Session = Session;
    default.SeenSequence = SeenSequence;
    default.LocalDeaths = LocalDeaths;
    default.bReady = bReady;
    SaveConfig();
}
