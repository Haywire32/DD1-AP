class APTavernShards extends Object;

static function int ShardIndex(StaticMesh Mesh)
{
    // Exact native fireplace assets; do not touch trophies, portals or crystals
    // elsewhere in the world. The names also work in the streamed tavern themes.
    switch(PathName(Mesh))
    {
        case "DunDef_LobbyItems.Mesh.SpiderCrystalOffset": return 0;
        case "DunDef_LobbyItems.Mesh.GenieCrystalOffset": return 1;
        case "DunDef_LobbyItems.Mesh.KrakenCrystalOffsetShape": return 2;
        case "DunDef_LobbyItems.Mesh.SkyCrystalOffset": return 3;
    }
    return -1;
}

static function int ShardEffectIndex(ParticleSystem Effect)
{
    // The retail fireplace uses mesh particles, not the trophy mesh actors.
    // Individual shards follow their own item bits.
    switch(PathName(Effect))
    {
        case "DunDef_LobbyItems.FX.crystal1_vFX": return 0;
        case "DunDef_LobbyItems.FX.crystal2_vFX": return 1;
        case "DunDef_LobbyItems.FX.crystal3_vFX": return 2;
        case "DunDef_LobbyItems.FX.crystal4_vFX": return 3;
    }
    return -1;
}

static function bool IsShardPortalPath(string EffectPath)
{
    // Native tavern portal includes all four coloured beam/trail emitters.
    // This is visual only: do not fire Kismet grants or bypass AP travel gates.
    return EffectPath == "DunDef_CrystalLevel_2.FX.Crystal_Portal_TavernExpansion";
}

static function bool PortalVisible(int ShardMask)
{
    return ShardMask == 15;
}

static function Apply(WorldInfo W, APUnlockState State)
{
    local Actor A;
    local StaticMeshComponent Mesh;
    local ParticleSystemComponent Effect;
    local DunDefGameReplicationInfo GRI;
    local int Index;
    local bool bHide;
    if(W == none || W.NetMode != NM_Standalone || State == none ||
        State.SeedIdentity == "" || State.EterniaShardMask < 0 || State.EterniaShardMask > 15) return;
    GRI = DunDefGameReplicationInfo(W.GRI);
    if((GRI == none || !GRI.IsLobbyLevel) &&
        InStr(Caps(string(W.GetPackageName())), "LOBBYLEVEL") != 0) return;
    foreach W.AllActors(class'Actor', A)
    {
        foreach A.ComponentList(class'StaticMeshComponent', Mesh)
        {
            Index = ShardIndex(Mesh.StaticMesh);
            if(Index < 0) continue;
            bHide = (State.EterniaShardMask & (1 << Index)) == 0;
            // Cooking merges unrelated static meshes into one collection actor.
            // Hiding that actor hides every shard (and other tavern geometry).
            // Only the individual component should follow this item's bit.
            if(!bHide && A.bHidden && StaticMeshCollectionActor(A) == none)
                A.SetHidden(false);
            if(Mesh.HiddenGame != bHide) Mesh.SetHidden(bHide);
        }
        foreach A.ComponentList(class'ParticleSystemComponent', Effect)
        {
            Index = ShardEffectIndex(Effect.Template);
            if(IsShardPortalPath(PathName(Effect.Template)))
                bHide = !PortalVisible(State.EterniaShardMask);
            else
            {
                if(Index < 0) continue;
                bHide = (State.EterniaShardMask & (1 << Index)) == 0;
            }
            if(!bHide && A.bHidden) A.SetHidden(false);
            if(Effect.HiddenGame != bHide) Effect.SetHidden(bHide);
            // SetActive is idempotent; ActivateSystem would restart the effect
            // on every poll. Polling also handles later-loaded tavern themes.
            Effect.SetActive(!bHide);
        }
    }
}
