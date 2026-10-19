// Local-only traps. No paid-DLC assets, console cheats, popup UI or saved-hero edits.
class APTrapRuntime extends Info;

var APGameRuntime Runtime;
var APTrapState Ledger;
var int LedgerIndex, NextKind, LastReadyWave;
var int Received[7];
var string SeedIdentity;
var float ChickenUntil, RushUntil, JamUntil, NextCombatTrap;
var bool SawCombat;
var array<DunDefEnemy> Rushed, Golded;
var DunDefOgre TrapOgre;

struct ChickenRestore
{
    var DunDefPlayer PlayerPawn;
    var int ForcedHealth, Health;
    var bool DisableJump;
    var float Desirability;
};
var array<ChickenRestore> Chickens;

function Initialize(APGameRuntime NewRuntime)
{
    Runtime=NewRuntime;
    Ledger=new(self) class'APTrapState';
    LastReadyWave=-1;
    SetTimer(0.1,true,'Poll');
}

static function bool ParseCounts(string Text, out array<int> Counts)
{
    local array<string> Parts;
    local int I,N;
    Counts.Length=0;
    ParseStringIntoArray(Text,Parts,",",false);
    if(Parts.Length != 7) return false;
    for(I=0;I<7;I++)
    {
        N=int(Parts[I]);
        if(N<0 || N>1000000 || string(N) != Parts[I]) return false;
        Counts.AddItem(N);
    }
    return true;
}

function bool ApplySnapshot(string Line)
{
    local array<string> Fields;
    local array<int> Counts;
    local int I;
    if(Runtime == none || Runtime.UnlockState == none || Ledger == none ||
        WorldInfo.NetMode != NM_Standalone || Len(Line)>200) return false;
    ParseStringIntoArray(Line,Fields,"|",false);
    if(Fields.Length != 3 || Fields[0] != "APTRAPS1" || Fields[1] == "" ||
        Fields[1] != Runtime.UnlockState.SeedIdentity || !ParseCounts(Fields[2],Counts)) return false;
    if(SeedIdentity != Fields[1])
    {
        ClearTemporaryEffects();
        SeedIdentity=Fields[1];
        LedgerIndex=Ledger.FindSeed(SeedIdentity);
        SawCombat=false; LastReadyWave=-1; NextKind=0; NextCombatTrap=0;
        for(I=0;I<7;I++) Received[I]=0;
    }
    // Old socket/file snapshots must not lower totals or replay consumed traps.
    for(I=0;I<7;I++) Received[I]=Max(Received[I],Counts[I]);
    return true;
}

function Persist()
{
    Ledger.SaveConfig();
}

function bool Pending(int Kind)
{
    return Ledger != none && LedgerIndex>=0 && LedgerIndex<Ledger.Seeds.Length &&
        Kind>=0 && Kind<7 && Received[Kind]>Ledger.Seeds[LedgerIndex].Used[Kind];
}

function Consume(int Kind)
{
    Ledger.Seeds[LedgerIndex].Used[Kind]++;
    Persist();
    `log("AP:TRAP activated=" $ Kind $ " consumed=" $ Ledger.Seeds[LedgerIndex].Used[Kind]);
}

function bool SafeWorld()
{
    local DunDefGameReplicationInfo GRI;
    if(Runtime == none || Runtime.UnlockState == none || WorldInfo.NetMode != NM_Standalone ||
        WorldInfo.Pauser != none || !Runtime.IsStableAPWorld() ||
        SeedIdentity == "" || SeedIdentity != Runtime.UnlockState.SeedIdentity) return false;
    GRI=DunDefGameReplicationInfo(WorldInfo.GRI);
    return GRI != none && GRI.IsGameplayLevel && !GRI.IsLobbyLevel &&
        GRI.bIsGameActive && !GRI.bDoLevelVictory && !GRI.bIsGameOver;
}

function bool LivingLocalPlayer(DunDefPlayerController PC)
{
    return Runtime.IsStableLocalController(PC) && DunDefPlayer(PC.Pawn) != none &&
        !PC.Pawn.bDeleteMe && PC.Pawn.Health>0 && !DunDefPlayer(PC.Pawn).IsDead();
}

function bool HasPlayer()
{
    local DunDefPlayerController PC;
    foreach WorldInfo.AllControllers(class'DunDefPlayerController',PC)
        if(LivingLocalPlayer(PC)) return true;
    return false;
}

function bool SkillJammed()
{
    return JamUntil>WorldInfo.TimeSeconds && SafeWorld() &&
        DunDefGameReplicationInfo(WorldInfo.GRI).IsInCombatPhase;
}

function bool DeniesAbility(DunDefPlayerAbility Ability)
{
    local DunDefPlayerController PC;
    local string HeroKey;
    if(!SkillJammed() || Ability == none) return false;
    PC=Ability.GetPC();
    if(PC == none || PC.GetHero() == none) return false;
    HeroKey=Runtime.UnlockState.GetHeroKey(PC.GetHero());
    // Leave healing/repair/upgrade/sell and native weapon controls untouched.
    if(Runtime.UnlockState.bChaosLoadouts && Runtime.ChaosRuntime != none)
        return !Runtime.ChaosRuntime.IsPreserved(PC,Ability);
    return Ability.IsATowerBuildingAbility || Runtime.UnlockState.GetAbilityKey(Ability,HeroKey) != "";
}

function bool StartChicken()
{
    local DunDefPlayerController PC;
    local DunDefPlayer P;
    local ChickenRestore Entry;
    local DunDefGRI_Chicken NativeChicken;
    NativeChicken=DunDefGRI_Chicken(WorldInfo.GRI);
    foreach WorldInfo.AllControllers(class'DunDefPlayerController',PC)
    {
        if(!LivingLocalPlayer(PC)) continue;
        P=DunDefPlayer(PC.Pawn);
        if(NativeChicken != none && NativeChicken.ChickenPlayer == P) continue;
        Entry.PlayerPawn=P; Entry.ForcedHealth=P.ForcedMaxHealth;
        Entry.Health=P.Health; Entry.DisableJump=P.bDisableJump;
        Entry.Desirability=P.EnemyTargetingDesirability;
        Chickens.AddItem(Entry);
        P.ForcedMaxHealth=1; P.bDisableJump=true; P.EnemyTargetingDesirability=28.0;
        P.SetMaxHealth(1,true);
    }
    if(Chickens.Length == 0) return false;
    ChickenUntil=WorldInfo.TimeSeconds+20.0;
    return true;
}

function bool ShowChickenIcon(DunDefPlayer P)
{
    local DunDefGRI_Chicken NativeChicken;
    if(ChickenUntil<=WorldInfo.TimeSeconds || P==none || P.bDeleteMe || P.Health<=0 || P.IsDead()) return false;
    NativeChicken=DunDefGRI_Chicken(WorldInfo.GRI);
    // The original challenge already draws its own target's icon.
    return NativeChicken==none || NativeChicken.ChickenPlayer!=P;
}

function DrawChickenHUD(DunDefHUD H)
{
    local ChickenRestore Entry;
    local Texture2D Icon;
    local Vector WorldPosition, ScreenPosition, Offset;
    local float DistanceScale, Size, OldX, OldY;
    local Color OldColor;
    if(ChickenUntil<=WorldInfo.TimeSeconds || H==none || H.Canvas==none ||
        H.PlayerOwner==none || H.PlayerOwner.PlayerCamera==none) return;
    Icon=class'DunDefGRI_Chicken'.default.ChickenIcon;
    if(Icon==none) return;
    OldColor=H.Canvas.DrawColor; OldX=H.Canvas.CurX; OldY=H.Canvas.CurY;
    foreach Chickens(Entry)
    {
        if(!ShowChickenIcon(Entry.PlayerPawn)) continue;
        Offset=class'DunDefGRI_Chicken'.default.ChickenIconPositionOffset;
        Offset.Z+=Entry.PlayerPawn.GetCollisionHeight()*class'DunDefGRI_Chicken'.default.ChickenIconPositionHeightScale;
        WorldPosition=Entry.PlayerPawn.Location+(Offset >> Entry.PlayerPawn.Rotation);
        ScreenPosition=H.Canvas.Project(WorldPosition);
        DistanceScale=FClamp(1.0-VSize(WorldPosition-H.PlayerOwner.PlayerCamera.ViewTarget.POV.Location)/3000,0.2,1.0)*(H.Canvas.ClipY/768.0);
        Size=class'DunDefGRI_Chicken'.default.ChickenIconSize*DistanceScale*(1.0+0.4*Abs(Sin(WorldInfo.TimeSeconds*4)));
        if(!H.IsOnCanvas(ScreenPosition,Size,Size)) continue;
        H.Canvas.SetDrawColor(255,255,255,255);
        H.Canvas.SetPos(ScreenPosition.X-Size/2,ScreenPosition.Y-Size/2);
        H.Canvas.DrawTile(Icon,Size,Size,0,0,Icon.SizeX,Icon.SizeY);
    }
    H.Canvas.DrawColor=OldColor; H.Canvas.SetPos(OldX,OldY);
}

function EndChicken()
{
    local ChickenRestore Entry;
    local DunDefPlayer P;
    local DunDefPlayerController PC;
    local DunDefGRI_Chicken NativeChicken;
    NativeChicken=DunDefGRI_Chicken(WorldInfo.GRI);
    foreach Chickens(Entry)
    {
        P=Entry.PlayerPawn;
        if(P == none || P.bDeleteMe) continue;
        // The actual Chicken challenge retains authority over its current target.
        if(NativeChicken != none && NativeChicken.ChickenPlayer == P) continue;
        P.ForcedMaxHealth=Entry.ForcedHealth; P.bDisableJump=Entry.DisableJump;
        P.EnemyTargetingDesirability=Entry.Desirability;
        PC=DunDefPlayerController(P.Controller);
        if(PC != none && !P.IsDead() && P.Health>0)
        {
            P.SetMaxHealth(PC.GetHeroMaxHealth(P),false);
            P.Health=Min(Entry.Health,P.HealthMax);
        }
    }
    Chickens.Length=0; ChickenUntil=0;
}

function bool EnemyEligible(DunDefEnemy Enemy)
{
    return Enemy != none && !Enemy.bDeleteMe && !Enemy.IsDead() && Enemy.Health>0 &&
        !Enemy.IsPlayerAlly && DunDefBoss(Enemy) == none;
}

function ApplyRush()
{
    local DunDefEnemy Enemy;
    local int I;
    for(I=Rushed.Length-1;I>=0;I--)
        if(Rushed[I] == none || Rushed[I].bDeleteMe) Rushed.Remove(I,1);
    foreach WorldInfo.AllActors(class'DunDefEnemy',Enemy)
        if(EnemyEligible(Enemy) && Rushed.Find(Enemy) == INDEX_NONE)
        {
            Enemy.MyMovementSpeedMultiplier*=1.5;
            Rushed.AddItem(Enemy);
        }
}

function EndRush()
{
    local DunDefEnemy Enemy;
    foreach Rushed(Enemy)
        if(Enemy != none && !Enemy.bDeleteMe) Enemy.MyMovementSpeedMultiplier/=1.5;
    Rushed.Length=0; RushUntil=0;
}

function bool ApplyGold()
{
    local array<DunDefEnemy> Targets;
    local DunDefEnemy Enemy;
    local DunDefGRI_GoldenTokens Treasure;
    local int J;
    Treasure=DunDefGRI_GoldenTokens(WorldInfo.GRI);
    foreach WorldInfo.AllActors(class'DunDefEnemy',Enemy)
        if(EnemyEligible(Enemy) && !Enemy.bGolded && Enemy.Mesh != none &&
            Golded.Find(Enemy) == INDEX_NONE &&
            (Treasure == none || Treasure.GoldenEnemy != Enemy)) Targets.AddItem(Enemy);
    if(Targets.Length==0) return false;
    foreach Targets(Enemy)
    {
        // Native base-game Treasure Hunt strength and visuals. Do not add its
        // special token drops or invoke the DLC Djinn's conversion ability.
        Enemy.DifficultySetOffset+=class'DunDefGRI_GoldenTokens'.default.TokenEnemyDifficultyOffset;
        Enemy.UpdateDifficultyValues(false);
        Enemy.bGolded=true;
        Enemy.SpawnAttachParticleEffect(class'DunDefGRI_GoldenTokens'.default.GoldParticleEffect);
        for(J=0;J<Enemy.Mesh.GetNumElements();J++)
            Enemy.Mesh.SetMaterial(J,class'DunDefGRI_GoldenTokens'.default.GoldMaterialTemplate);
        Golded.AddItem(Enemy);
    }
    return true;
}

function bool ApplySuddenDeath()
{
    local array<DunDefCrystalCore> Targets;
    local DunDefCrystalCore Core;
    foreach WorldInfo.AllActors(class'DunDefCrystalCore',Core)
        if(!Core.bDeleteMe && !Core.bHidden && !Core.IsDead && Core.Health>1) Targets.AddItem(Core);
    if(Targets.Length == 0) return false;
    Core=Targets[Rand(Targets.Length)];
    Core.Health=1; Core.NotifyHealthChange();
    return true;
}

function bool SpawnOgre()
{
    local DunDefEnemy GroundEnemy, Template;
    local DunDef_SeqAct_EnemyWaveSpawner Spawner;
    local DunDefEnemyController EC;
    local Actor Entrance;
    local main Game;
    local int I;
    if(TrapOgre != none && !TrapOgre.bDeleteMe && !TrapOgre.IsDead()) return false;
    Game=main(WorldInfo.Game);
    if(Game == none || Game.CurrentNumberOfEnemies>=Game.GetMaximumNumberOfEnemies()) return false;
    Template=DunDefEnemy(DynamicLoadObject("DunDefArchetypes.EnemyOgre",class'DunDefOgre'));
    if(Template == none) return false;
    foreach WorldInfo.AllActors(class'DunDefEnemy',GroundEnemy)
    {
        if(!EnemyEligible(GroundEnemy) || GroundEnemy.Physics != PHYS_Walking ||
            GroundEnemy.WaveSpawner == none) continue;
        Spawner=GroundEnemy.WaveSpawner;
        // Only an unfinished native ground-wave spawner. Never a fly lane,
        // summoned minion, boss script, or already completed wave's counter.
        if(Spawner.AllKilled || Spawner.TotalNumEnemies<=Spawner.NumEnemiesKilled ||
            Spawner.bSpawnForever || Spawner.OverrideEnemyTargetingTeam != -1) continue;
        for(I=0;I<Spawner.SpawnPoints.Length;I++)
        {
            Entrance=Spawner.SpawnPoints[I];
            if(Entrance == none || Entrance.bDeleteMe) continue;
            // Collision-checked spawn: do not force a large ogre inside walls.
            TrapOgre=Spawn(class'DunDefOgre',,,Entrance.Location,Entrance.Rotation,Template);
            if(TrapOgre == none) continue;
            TrapOgre.WaveSpawner=Spawner;
            TrapOgre.DifficultySetWaveOffset=GroundEnemy.DifficultySetWaveOffset;
            TrapOgre.UpdateDifficultyValues();
            EC=DunDefEnemyController(TrapOgre.Controller);
            if(EC != none)
            {
                EC.bReachedInitialTarget=EC.default.bReachedInitialTarget || !Spawner.bNavigateToInitialCustomNode;
                EC.InitialTargetNodeID=Spawner.NavigateToInitialCustomNodeID;
            }
            Spawner.SpawnedEnemies.AddItem(TrapOgre);
            Spawner.TotalNumEnemies++; Spawner.NumEnemiesSpawned++;
            if(Spawner.DeathsDecrementKillCount && Game.CurrentKillCountUI != none)
            {
                Game.CurrentKillCountUI.TotalKillCount++;
                Game.CurrentKillCountUI.KillCountRemaining++;
            }
            Game.SpawnedEnemy(TrapOgre);
            return true;
        }
    }
    return false;
}

function UI_BuildTimer ActiveBuildTimer()
{
    local DunDefViewportClient Viewport;
    Viewport=class'DunDefViewportClient'.static.GetViewportClient();
    if(Viewport == none) return none;
    return UI_BuildTimer(Viewport.GetActiveUISceneFromClass(class'UI_BuildTimer'));
}

function bool StartNextWave()
{
    local DunDefGameReplicationInfo GRI;
    local UI_BuildTimer TimerUI;
    GRI=DunDefGameReplicationInfo(WorldInfo.GRI);
    if(GRI == none || !SawCombat || GRI.IsInCombatPhase || GRI.WaveNumber == LastReadyWave ||
        GRI.bDoLevelVictory || GRI.bIsGameOver) return false;
    TimerUI=ActiveBuildTimer();
    if(TimerUI == none || TimerUI.bFinishedBuildPhase || TimerUI.BuildTimerUIAction == none) return false;
    // Use the native Kismet completion, including infinite build time. Do not
    // just flip IsInCombatPhase or bypass map-specific wave/spawner setup.
    LastReadyWave=GRI.WaveNumber;
    TimerUI.FinishBuildPhase();
    return true;
}

function ClearTemporaryEffects()
{
    EndChicken(); EndRush(); JamUntil=0;
}

function Poll()
{
    local DunDefGameReplicationInfo GRI;
    local int I,Kind;
    local bool Applied;
    if(WorldInfo.Pauser != none) return;
    if(!SafeWorld()) { ClearTemporaryEffects(); return; }
    GRI=DunDefGameReplicationInfo(WorldInfo.GRI);
    if(!GRI.IsInCombatPhase)
    {
        ClearTemporaryEffects();
        if(Pending(4) && HasPlayer() && StartNextWave())
        { Consume(4); }
        return;
    }
    SawCombat=true;
    if(ChickenUntil>0 && ChickenUntil<=WorldInfo.TimeSeconds) EndChicken();
    if(RushUntil>0)
    {
        if(RushUntil<=WorldInfo.TimeSeconds) EndRush();
        else ApplyRush();
    }
    if(!HasPlayer() || WorldInfo.TimeSeconds<NextCombatTrap ||
        ChickenUntil>0 || RushUntil>0 || JamUntil>WorldInfo.TimeSeconds) return;
    for(I=0;I<7;I++)
    {
        Kind=(NextKind+I)%7;
        if(Kind == 4 || !Pending(Kind)) continue;
        Applied=false;
        switch(Kind)
        {
            case 0: Applied=StartChicken(); break;
            case 1: Applied=ApplyGold(); break;
            case 2: RushUntil=WorldInfo.TimeSeconds+30; ApplyRush(); Applied=true; break;
            case 3: JamUntil=WorldInfo.TimeSeconds+30; Applied=true; break;
            case 5: Applied=SpawnOgre(); break;
            case 6: Applied=ApplySuddenDeath(); break;
        }
        if(Applied)
        {
            Consume(Kind); NextKind=(Kind+1)%7;
            NextCombatTrap=WorldInfo.TimeSeconds+5;
            return;
        }
    }
}

event Destroyed()
{
    ClearTemporaryEffects();
    super.Destroyed();
}

defaultproperties
{
    RemoteRole=ROLE_None
    LedgerIndex=-1
    LastReadyWave=-1
}
