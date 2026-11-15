#include <limits>
#include "MLGLogicValidator.h"
#include "Misc/AutomationTest.h"
#include "Engine/Engine.h"
#include "Engine/DamageEvents.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "MLGAlien.h"
#include "MLGAssets.h"
#include "MLGCharacter.h"
#include "MLGDefenseNode.h"
#include "MLGDevice.h"
#include "MLGGameMode.h"
#include "MLGGameState.h"
#include "MLGHUD.h"
#include "MLGLogTerminal.h"
#include "MLGModels.h"
#include "MLGPickup.h"
#include "MLGPlantPlot.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Kismet/GameplayStatics.h"

#if WITH_DEV_AUTOMATION_TESTS

static void RunPlant(FMLGPlantModel& P, float Seconds, bool W, bool Pw, bool S)
{
	for (float t = 0; t < Seconds; t += 0.1f) P.Tick(0.1f, W, Pw, S);
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMLGPlantTest, "MarsLastGreen.Plant.GrowthStarvationRecovery",
	EAutomationTestFlags::ApplicationContextMask | EAutomationTestFlags::ProductFilter)
bool FMLGPlantTest::RunTest(const FString&)
{
	FMLGPlantModel P; P.Plant();
	RunPlant(P, 31.f, true, true, true);
	TestEqual("seed -> seedling", P.Stage, EMLGPlantStage::Seedling);
	RunPlant(P, 46.f, true, true, true);
	TestEqual("seedling -> mature", P.Stage, EMLGPlantStage::Mature);

	FMLGPlantModel Q; Q.Plant(); RunPlant(Q, 10.f, true, true, true);
	const float Prog = Q.Progress;
	RunPlant(Q, 20.f, false, true, true);
	TestTrue("stalled flag set", Q.bStalled);
	TestEqual("growth frozen while starved", Q.Progress, Prog, 0.001f);
	TestTrue("health dropped", Q.Health < 0.9f);
	const float Low = Q.Health;
	RunPlant(Q, 10.f, true, true, true);
	TestTrue("health recovers once repaired", Q.Health > Low);
	TestTrue("growth resumes", Q.Progress > Prog);

	FMLGPlantModel D; D.Plant(); RunPlant(D, 200.f, false, true, true);
	TestEqual("starved plant dies", D.Stage, EMLGPlantStage::Dead);
	RunPlant(D, 50.f, true, true, true);
	TestEqual("death is permanent", D.Stage, EMLGPlantStage::Dead);

	FMLGPlantModel A, B; A.Plant(); B.Plant();
	RunPlant(A, 20.f, false, true, true); RunPlant(B, 20.f, true, true, false);
	TestTrue("pressure loss hurts faster than water loss", B.Health < A.Health);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMLGResourceTest, "MarsLastGreen.Resources.PowerWaterOxygen",
	EAutomationTestFlags::ApplicationContextMask | EAutomationTestFlags::ProductFilter)
bool FMLGResourceTest::RunTest(const FString&)
{
	FMLGResourceInputs In; In.ConsumingPlots = 4; In.bOxygenGenOnline = true;
	FMLGResourceModel NoGen; for (int i = 0; i < 600; ++i) NoGen.Step(0.1f, In);
	TestEqual("battery empties with no generator", NoGen.Power, 0.f, 0.001f);
	const float O2AtBlackout = NoGen.BaseOxygen;
	for (int i = 0; i < 100; ++i) NoGen.Step(0.1f, In);
	TestTrue("oxygen decays after blackout", NoGen.BaseOxygen < O2AtBlackout);

	In.PowerGenerators = 1;
	FMLGResourceModel WithGen; WithGen.Power = 10.f; for (int i = 0; i < 600; ++i) WithGen.Step(0.1f, In);
	TestTrue("one generator sustains the base", WithGen.Power > 10.f);

	FMLGResourceInputs Sealed = In, Open = In; Sealed.bGreenhouseSealed = true;
	FMLGResourceModel S, O; for (int i = 0; i < 600; ++i) { S.Step(0.1f, Sealed); O.Step(0.1f, Open); }
	TestTrue("sealed greenhouse recycles water", S.Water > O.Water);

	FMLGResourceInputs P; P.PowerGenerators = 1; P.bPurifierOnline = true;
	FMLGResourceModel Pur; Pur.Ice = 1.f; Pur.Water = 0.f; for (int i = 0; i < 200; ++i) Pur.Step(0.1f, P);
	TestEqual("purifier turns 1 ice into 8 L", Pur.Water, 8.f, 0.01f);
	TestEqual("ice consumed", Pur.Ice, 0.f, 0.001f);
	FMLGResourceInputs Leak; Leak.TankLeak = 1.f;
	FMLGResourceModel L; for (int i = 0; i < 100; ++i) L.Step(0.1f, Leak);
	TestEqual("leak drains the tank (60 L - 10 s * 1 L/s)", L.Water, 50.f, 0.01f);
	Leak.TankLeak = 0.f; const float Before = L.Water; for (int i = 0; i < 100; ++i) L.Step(0.1f, Leak);
	TestEqual("repair stops the leak", L.Water, Before, 0.001f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMLGTurretResourceTest, "MarsLastGreen.Resources.TurretLoadAndBlackout",
	EAutomationTestFlags::ApplicationContextMask | EAutomationTestFlags::ProductFilter)
bool FMLGTurretResourceTest::RunTest(const FString&)
{
	FMLGResourceInputs In;
	In.PowerGenerators = 1; // +3.0/s
	In.bOxygenGenOnline = true; // -0.5/s
	In.bPurifierOnline = true;  // -0.5/s when Ice > 0
	In.ConsumingPlots = 4;      // -1.6/s
	In.ActiveTurrets = 2;       // -1.0/s -> total -3.6/s (net -0.6/s)

	FMLGResourceModel M;
	M.Power = 10.f;
	M.Ice = 10.f;
	for (int i = 0; i < 600; ++i) M.Step(0.1f, In);
	TestTrue("two active turrets under full base load drain battery to blackout/brownout", M.Power <= 0.05f);

	// Putting turrets on standby restores positive net power
	In.ActiveTurrets = 0;
	for (int i = 0; i < 200; ++i) M.Step(0.1f, In);
	TestTrue("standby turrets allow generator to recharge battery", M.Power > 5.f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMLGSafeAssetLoadTest, "MarsLastGreen.Assets.SafeOptionalLoad",
	EAutomationTestFlags::ApplicationContextMask | EAutomationTestFlags::ProductFilter)
bool FMLGSafeAssetLoadTest::RunTest(const FString&)
{
	UStaticMesh* Missing = MLGAssets::LoadOptional<UStaticMesh>(TEXT("/Game/DoesNotExist/MissingAsset"));
	TestNull("missing /Game asset safely returns nullptr without errors", Missing);

	UStaticMesh* Cube = MLGAssets::LoadOptional<UStaticMesh>(TEXT("/Engine/BasicShapes/Cube.Cube"));
	TestNotNull("existing engine shape loads cleanly", Cube);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMLGDefenseAndAlienTest, "MarsLastGreen.Gameplay.DefenseAndAlienStates",
	EAutomationTestFlags::ApplicationContextMask | EAutomationTestFlags::ProductFilter)
bool FMLGDefenseAndAlienTest::RunTest(const FString&)
{
	UWorld* World = UWorld::CreateWorld(EWorldType::Game, false);
	TestNotNull("transient test world created", World);
	if (!World) return false;

	FWorldContext& Ctx = GEngine->CreateNewWorldContext(EWorldType::Game);
	Ctx.SetCurrentWorld(World);
	World->InitializeActorsForPlay(FURL());

	AMLGGameState* GS = World->SpawnActor<AMLGGameState>();
	World->SetGameState(GS);
	GS->Parts = 1;

	AMLGDefenseNode* Sentry = World->SpawnActor<AMLGDefenseNode>(FVector::ZeroVector, FRotator::ZeroRotator);
	Sentry->Kind = EMLGDefenseKind::SentryTurret;
	Sentry->DispatchBeginPlay();

	TestEqual("defense pad starts empty", Sentry->DefenseState, EMLGDefenseState::Empty);
	TestFalse("cannot deploy sentry with 1 part (needs 2)", Sentry->CanInteract(nullptr));

	GS->Parts = 3;
	TestTrue("can deploy sentry with 3 parts", Sentry->CanInteract(nullptr));
	Sentry->Interact(nullptr);
	TestEqual("sentry deployed to Active", Sentry->DefenseState, EMLGDefenseState::Active);
	TestEqual("deploying sentry deducted 2 parts", GS->Parts, 1);
	TestTrue("active sentry draws power", Sentry->DrawsPower());

	Sentry->Interact(nullptr);
	TestEqual("sentry toggled to Standby", Sentry->DefenseState, EMLGDefenseState::Standby);
	TestFalse("standby sentry draws no power", Sentry->DrawsPower());

	Sentry->TakeDamage(120.f, FDamageEvent(), nullptr, nullptr);
	TestEqual("heavy damage breaks sentry", Sentry->DefenseState, EMLGDefenseState::Broken);
	TestFalse("broken sentry is not operational", Sentry->IsOperational());

	Sentry->Interact(nullptr);
	TestEqual("repairing with 1 part restores Active", Sentry->DefenseState, EMLGDefenseState::Active);
	TestEqual("parts spent on repair", GS->Parts, 0);
	TestEqual("integrity restored to 100", Sentry->Integrity, 100.f, 0.01f);

	// Deferred-spawned ShockBarrier preset stats & zero idle power draw
	const FTransform BarrierT(FRotator::ZeroRotator, FVector(200.f, 0.f, 0.f));
	AMLGDefenseNode* Barrier = World->SpawnActorDeferred<AMLGDefenseNode>(AMLGDefenseNode::StaticClass(), BarrierT);
	Barrier->Kind = EMLGDefenseKind::ShockBarrier;
	Barrier->FinishSpawning(BarrierT);
	Barrier->DispatchBeginPlay();
	TestEqual("shock barrier MaxIntegrity preset 180", Barrier->MaxIntegrity, 180.f, 0.01f);
	TestEqual("shock barrier BuildPartsCost preset 1", Barrier->BuildPartsCost, 1);
	TestEqual("shock barrier Range preset 450", Barrier->Range, 450.f, 0.01f);
	TestEqual("shock barrier DamagePerShot preset 10", Barrier->DamagePerShot, 10.f, 0.01f);
	TestEqual("shock barrier FireInterval preset 2.0", Barrier->FireInterval, 2.0f, 0.01f);
	GS->Parts = 1;
	TestTrue("can deploy shock barrier with 1 part", Barrier->CanInteract(nullptr));
	Barrier->Interact(nullptr);
	TestEqual("shock barrier deployed to Active", Barrier->DefenseState, EMLGDefenseState::Active);
	TestEqual("shock barrier integrity 180", Barrier->Integrity, 180.f, 0.01f);
	TestFalse("active shock barrier draws zero power", Barrier->DrawsPower());

	// Alien presets, armor, and death state transition
	const FTransform T(FRotator::ZeroRotator, FVector(500.f, 0.f, 100.f));
	AMLGAlien* Breaker = World->SpawnActorDeferred<AMLGAlien>(AMLGAlien::StaticClass(), T);
	Breaker->Kind = EMLGAlienKind::Breaker;
	Breaker->FinishSpawning(T);
	Breaker->DispatchBeginPlay();
	TestEqual("breaker health preset 220", Breaker->Health, 220.f, 0.01f);

	Breaker->TakeDamage(40.f, FDamageEvent(), nullptr, nullptr);
	TestEqual("breaker armor halves damage outside windup", Breaker->Health, 200.f, 0.01f);
	TestEqual("breaker stays in Approach on armored hit", Breaker->State, EMLGAlienState::Approach);

	Breaker->TakeDamage(500.f, FDamageEvent(), nullptr, nullptr);
	TestEqual("lethal damage transitions alien to Dead", Breaker->State, EMLGAlienState::Dead);
	TestEqual("death increments GameState Kills", GS->Kills, 1);

	GEngine->DestroyWorldContext(World);
	World->DestroyWorld(false);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMLGWeakspotAndCritTest, "MarsLastGreen.Combat.WeakspotAndCrit",
	EAutomationTestFlags::ApplicationContextMask | EAutomationTestFlags::ProductFilter)
bool FMLGWeakspotAndCritTest::RunTest(const FString&)
{
	bool bCrit = false;
	FHitResult HeadHit;
	HeadHit.BoneName = FName(TEXT("Head"));
	TestEqual("raider head bone deals 1.75x crit", AMLGAlien::ComputeDamageMultiplier(EMLGAlienKind::Raider, EMLGAlienState::Approach, FVector(0, 0, 40), 40.f, &HeadHit, bCrit), 1.75f, 0.001f);
	TestTrue("raider head bone marks crit", bCrit);

	FHitResult UpperHit;
	UpperHit.ImpactPoint = FVector(0.f, 0.f, 105.f);
	TestEqual("gunner upper-Z hit deals 1.75x crit", AMLGAlien::ComputeDamageMultiplier(EMLGAlienKind::Gunner, EMLGAlienState::Approach, FVector(0, 0, 70), 70.f, &UpperHit, bCrit), 1.75f, 0.001f);
	TestTrue("gunner upper-Z marks crit", bCrit);

	FHitResult BodyHit;
	BodyHit.ImpactPoint = FVector(0.f, 0.f, 65.f);
	TestEqual("gunner body hit deals 1.0x", AMLGAlien::ComputeDamageMultiplier(EMLGAlienKind::Gunner, EMLGAlienState::Approach, FVector(0, 0, 70), 70.f, &BodyHit, bCrit), 1.0f, 0.001f);
	TestFalse("gunner body hit is not crit", bCrit);

	TestEqual("breaker armored outside telegraph deals 0.5x", AMLGAlien::ComputeDamageMultiplier(EMLGAlienKind::Breaker, EMLGAlienState::Approach, FVector::ZeroVector, 70.f, nullptr, bCrit), 0.5f, 0.001f);
	TestFalse("breaker armored hit is not crit", bCrit);
	TestEqual("breaker during telegraph deals 1.5x weakspot", AMLGAlien::ComputeDamageMultiplier(EMLGAlienKind::Breaker, EMLGAlienState::Telegraph, FVector::ZeroVector, 70.f, nullptr, bCrit), 1.5f, 0.001f);
	TestTrue("breaker windup hit marks crit", bCrit);

	// Live actor TakeDamage integration
	UWorld* World = UWorld::CreateWorld(EWorldType::Game, false);
	TestNotNull("weakspot test world created", World);
	if (!World) return false;
	FWorldContext& Ctx = GEngine->CreateNewWorldContext(EWorldType::Game);
	Ctx.SetCurrentWorld(World);
	World->InitializeActorsForPlay(FURL());

	const FTransform T(FRotator::ZeroRotator, FVector(0.f, 0.f, 40.f));
	AMLGAlien* Raider = World->SpawnActorDeferred<AMLGAlien>(AMLGAlien::StaticClass(), T);
	Raider->Kind = EMLGAlienKind::Raider;
	Raider->FinishSpawning(T);
	Raider->DispatchBeginPlay();

	FHitResult LiveBody;
	LiveBody.ImpactPoint = FVector(0.f, 0.f, 35.f);
	const float BodyApplied = UGameplayStatics::ApplyPointDamage(Raider, 20.f, FVector::ForwardVector, LiveBody, nullptr, nullptr, nullptr);
	TestEqual("raider body point damage is 20", BodyApplied, 20.f, 0.01f);
	TestFalse("raider body point damage did not crit", Raider->WasLastHitCrit());

	FHitResult LiveHead;
	LiveHead.BoneName = FName(TEXT("neck_01"));
	const float HeadApplied = UGameplayStatics::ApplyPointDamage(Raider, 20.f, FVector::ForwardVector, LiveHead, nullptr, nullptr, nullptr);
	TestEqual("raider neck bone point damage is 35 (1.75x)", HeadApplied, 35.f, 0.01f);
	TestTrue("raider neck bone point damage marked crit", Raider->WasLastHitCrit());

	GEngine->DestroyWorldContext(World);
	World->DestroyWorld(false);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMLGMeshPathAndFallbackTest, "MarsLastGreen.Assets.MeshPathsAndFallbacks",
	EAutomationTestFlags::ApplicationContextMask | EAutomationTestFlags::ProductFilter)
bool FMLGMeshPathAndFallbackTest::RunTest(const FString&)
{
	TestEqual("power unit path", FString(AMLGDevice::GetMeshPathFor(EMLGDeviceType::Power, false)), FString(TEXT("/Game/Environment/SM_Dev_PowerUnit")));
	TestEqual("water tank path", FString(AMLGDevice::GetMeshPathFor(EMLGDeviceType::WaterTank, false)), FString(TEXT("/Game/Environment/SM_Dev_WaterTank")));
	TestEqual("water pipe path", FString(AMLGDevice::GetMeshPathFor(EMLGDeviceType::WaterTank, true)), FString(TEXT("/Game/Environment/SM_Dev_WaterPipe")));
	TestEqual("comms relay path", FString(AMLGDevice::GetMeshPathFor(EMLGDeviceType::Comms, false)), FString(TEXT("/Game/Environment/SM_Dev_CommsRelay")));
	TestEqual("parts pickup path", FString(AMLGPickup::GetMeshPathFor(EMLGPickupKind::RepairParts)), FString(TEXT("/Game/Environment/SM_Pickup_Parts")));
	TestEqual("ice pickup path", FString(AMLGPickup::GetMeshPathFor(EMLGPickupKind::Ice)), FString(TEXT("/Game/Environment/SM_Pickup_Ice")));
	TestEqual("seedbank pickup path", FString(AMLGPickup::GetMeshPathFor(EMLGPickupKind::SeedBank)), FString(TEXT("/Game/Environment/SM_Pickup_Seeds")));

	const TCHAR* StructPath = nullptr;
	const TCHAR* HeadPath = nullptr;
	AMLGDefenseNode::GetMeshPathsFor(EMLGDefenseKind::SentryTurret, StructPath, HeadPath);
	TestEqual("turret base path", FString(StructPath), FString(TEXT("/Game/Environment/SM_Defense_TurretBase")));
	TestEqual("turret head path", FString(HeadPath), FString(TEXT("/Game/Environment/SM_Defense_TurretHead")));
	AMLGDefenseNode::GetMeshPathsFor(EMLGDefenseKind::ShockBarrier, StructPath, HeadPath);
	TestEqual("barrier path", FString(StructPath), FString(TEXT("/Game/Environment/SM_Defense_Barrier")));
	TestNull("barrier has no head mesh", HeadPath);
	TestEqual("log terminal path", FString(AMLGLogTerminal::GetMeshPath()), FString(TEXT("/Game/Environment/SM_Log_Terminal")));

	// Spawn actors in a transient world and confirm clean BeginPlay (custom mesh or primitive fallback)
	UWorld* World = UWorld::CreateWorld(EWorldType::Game, false);
	TestNotNull("fallback test world created", World);
	if (!World) return false;
	FWorldContext& Ctx = GEngine->CreateNewWorldContext(EWorldType::Game);
	Ctx.SetCurrentWorld(World);
	World->InitializeActorsForPlay(FURL());

	const FTransform PipeT(FRotator::ZeroRotator, FVector(-1400.f, 350.f, 30.f));
	AMLGDevice* Pipe = World->SpawnActorDeferred<AMLGDevice>(AMLGDevice::StaticClass(), PipeT);
	Pipe->Type = EMLGDeviceType::WaterTank;
	Pipe->bPipeSegment = true;
	Pipe->SetActorScale3D(FVector(3.f, 0.3f, 0.3f));
	Pipe->FinishSpawning(PipeT);
	Pipe->DispatchBeginPlay();
	TestNotNull("device mesh valid after BeginPlay", Pipe->Mesh->GetStaticMesh().Get());

	const FTransform PickT(FRotator::ZeroRotator, FVector(100.f, 100.f, 30.f));
	AMLGPickup* IcePick = World->SpawnActorDeferred<AMLGPickup>(AMLGPickup::StaticClass(), PickT);
	IcePick->Kind = EMLGPickupKind::Ice;
	IcePick->FinishSpawning(PickT);
	IcePick->DispatchBeginPlay();
	TestNotNull("pickup mesh valid after BeginPlay", IcePick->Mesh->GetStaticMesh().Get());

	AMLGLogTerminal* Term = World->SpawnActor<AMLGLogTerminal>(FVector(0.f, 200.f, 30.f), FRotator::ZeroRotator);
	Term->DispatchBeginPlay();
	TestNotNull("log terminal mesh valid after BeginPlay", Term->Mesh->GetStaticMesh().Get());

	AMLGGameState* GS = World->SpawnActor<AMLGGameState>();
	World->SetGameState(GS);
	GS->Seeds = 1;
	AMLGPlantPlot* Plot = World->SpawnActor<AMLGPlantPlot>(FVector(400.f, 200.f, 20.f), FRotator::ZeroRotator);
	Plot->DispatchBeginPlay();
	Plot->Interact(nullptr);
	TestNotNull("plant tray mesh valid after BeginPlay", Plot->Tray->GetStaticMesh().Get());
	TestNotNull("plant seed mesh valid after Plant", Plot->PlantMesh->GetStaticMesh().Get());

	GEngine->DestroyWorldContext(World);
	World->DestroyWorld(false);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMLGMusicSelectionTest, "MarsLastGreen.Audio.AdaptiveMusicSelection",
	EAutomationTestFlags::ApplicationContextMask | EAutomationTestFlags::ProductFilter)
bool FMLGMusicSelectionTest::RunTest(const FString&)
{
	TestEqual("planning is silent", AMLGGameMode::SelectMusicState(EMLGPhase::Planning, 0, false, false), EMLGMusicState::Silent);
	TestEqual("won is silent", AMLGGameMode::SelectMusicState(EMLGPhase::Won, 0, false, false), EMLGMusicState::Silent);
	TestEqual("lost is silent", AMLGGameMode::SelectMusicState(EMLGPhase::Lost, 2, true, false), EMLGMusicState::Silent);
	TestEqual("dead player is silent", AMLGGameMode::SelectMusicState(EMLGPhase::Defend, 3, false, true), EMLGMusicState::Silent);
	TestEqual("exploration selects calm loop", AMLGGameMode::SelectMusicState(EMLGPhase::IceRun, 0, false, false), EMLGMusicState::Calm);
	TestEqual("wave warning selects combat loop", AMLGGameMode::SelectMusicState(EMLGPhase::Defend, 0, true, false), EMLGMusicState::Combat);
	TestEqual("live aliens select combat loop", AMLGGameMode::SelectMusicState(EMLGPhase::Repair, 1, false, false), EMLGMusicState::Combat);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMLGRaiderLungeAndPlayerAggroTest, "MarsLastGreen.Combat.RaiderLungeAndPlayerAggro",
	EAutomationTestFlags::ApplicationContextMask | EAutomationTestFlags::ProductFilter)
bool FMLGRaiderLungeAndPlayerAggroTest::RunTest(const FString&)
{
	// 1. Pure priority math for Raider player aggro within 900 cm (higher priority beats water tank = 4.0f)
	const float NearClear = AMLGAlien::ComputePlayerTargetPriority(EMLGAlienKind::Raider, 550.f, true, false);
	const float NearBlocked = AMLGAlien::ComputePlayerTargetPriority(EMLGAlienKind::Raider, 550.f, false, false);
	const float FarClear = AMLGAlien::ComputePlayerTargetPriority(EMLGAlienKind::Raider, 1100.f, true, false);
	const float FarProvoked = AMLGAlien::ComputePlayerTargetPriority(EMLGAlienKind::Raider, 1100.f, false, true);
	TestTrue("unobstructed Raider within 900cm out-prioritizes water tank (> 4.0)", NearClear > 4.0f);
	TestTrue("obstructed Raider without aggro has low player priority (< 2.0)", NearBlocked < 2.0f);
	TestTrue("unprovoked Raider beyond 900cm has low player priority (< 2.0)", FarClear < 2.0f);
	TestTrue("shot/provoked Raider aggros player even beyond 900cm (> 4.5)", FarProvoked > 4.5f);

	// 2. Live Raider vs Player target selection, Telegraph stagger cancel, and Lunge Strike
	UWorld* World = UWorld::CreateWorld(EWorldType::Game, false);
	TestNotNull("raider lunge test world created", World);
	if (!World) return false;
	FWorldContext& Ctx = GEngine->CreateNewWorldContext(EWorldType::Game);
	Ctx.SetCurrentWorld(World);
	World->InitializeActorsForPlay(FURL());

	AMLGGameState* GS = World->SpawnActor<AMLGGameState>();
	World->SetGameState(GS);

	AMLGCharacter* Player = World->SpawnActor<AMLGCharacter>(FVector(0.f, 0.f, 90.f), FRotator::ZeroRotator);
	Player->DispatchBeginPlay();
	TestEqual("player starts at 100 HP", Player->Health, 100.f, 0.01f);

	const FTransform RT(FRotator::ZeroRotator, FVector(210.f, 0.f, 40.f));
	AMLGAlien* Raider = World->SpawnActorDeferred<AMLGAlien>(AMLGAlien::StaticClass(), RT);
	Raider->Kind = EMLGAlienKind::Raider;
	Raider->FinishSpawning(RT);
	Raider->DispatchBeginPlay();
	TestEqual("raider PlayerDamage is 12", Raider->PlayerDamage, 12.f, 0.01f);

	Raider->ForcePickTarget();
	TestEqual("raider picks unobstructed player within 900cm", Raider->GetCurrentTarget(), static_cast<AActor*>(Player));

	// Enter Telegraph and verify warning + stagger cancel on shot
	Raider->ForceEnterState(EMLGAlienState::Telegraph);
	TestTrue("raider telegraphing at player reports threat", Raider->IsThreateningPlayer(Player));
	TestTrue("raider telegraph banner text contains RAIDER LUNGE", Raider->GetTelegraphWarningText().Contains(TEXT("RAIDER LUNGE")));

	Raider->TakeDamage(10.f, FDamageEvent(), nullptr, Player);
	TestEqual("shooting Raider during Telegraph staggers and cancels lunge", Raider->State, EMLGAlienState::Stagger);
	TestFalse("staggered Raider is not lunging", Raider->IsLunging());

	// Re-enter Telegraph and execute Lunge Strike on player
	Raider->ForceEnterState(EMLGAlienState::Telegraph);
	Raider->ForceStrike();
	TestTrue("raider Strike activates lunge dash window", Raider->IsLunging());
	TestTrue("raider physically lunges forward toward player", Raider->GetVelocity().Size2D() > 200.f);
	TestEqual("raider lunge deals 12 damage to player", Player->Health, 88.f, 0.01f);
	TestEqual("player records RAIDER LUNGE hit tag", Player->LastHitSourceTag, FString(TEXT("RAIDER LUNGE")));
	TestTrue("player receives knockback velocity from lunge", Player->GetVelocity().Size2D() > 100.f);
	TestTrue("player receives directional camera punch", FMath::Abs(Player->HitPunchPitch) > 0.1f);

	GEngine->DestroyWorldContext(World);
	World->DestroyWorld(false);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMLGBreakerShockwaveCounterplayTest, "MarsLastGreen.Combat.BreakerShockwaveJumpCounterplay",
	EAutomationTestFlags::ApplicationContextMask | EAutomationTestFlags::ProductFilter)
bool FMLGBreakerShockwaveCounterplayTest::RunTest(const FString&)
{
	UWorld* World = UWorld::CreateWorld(EWorldType::Game, false);
	TestNotNull("breaker shockwave test world created", World);
	if (!World) return false;
	FWorldContext& Ctx = GEngine->CreateNewWorldContext(EWorldType::Game);
	Ctx.SetCurrentWorld(World);
	World->InitializeActorsForPlay(FURL());

	AMLGGameState* GS = World->SpawnActor<AMLGGameState>();
	World->SetGameState(GS);

	AMLGCharacter* Player = World->SpawnActor<AMLGCharacter>(FVector(240.f, 0.f, 200.f), FRotator::ZeroRotator);
	Player->DispatchBeginPlay();

	const FTransform BT(FRotator::ZeroRotator, FVector(0.f, 0.f, 70.f));
	AMLGAlien* Breaker = World->SpawnActorDeferred<AMLGAlien>(AMLGAlien::StaticClass(), BT);
	Breaker->Kind = EMLGAlienKind::Breaker;
	Breaker->FinishSpawning(BT);
	Breaker->DispatchBeginPlay();

	Breaker->ForcePickTarget();
	Breaker->ForceEnterState(EMLGAlienState::Telegraph);
	TestTrue("breaker telegraph banner text contains BREAKER SHOCKWAVE", Breaker->GetTelegraphWarningText().Contains(TEXT("BREAKER SHOCKWAVE")));

	// Case A: Player jumps over the shockwave (DeltaZ = 130 >= 110 and upward velocity)
	if (UCharacterMovementComponent* Move = Player->GetCharacterMovement())
	{
		Move->SetMovementMode(MOVE_Falling);
		Move->Velocity = FVector(0.f, 0.f, 320.f);
	}
	TestFalse("jumping player is not hit by shockwave check", Breaker->ShouldShockwaveHitPlayer(Player));
	Breaker->ForceStrike();
	TestEqual("jumping player avoids Breaker shockwave damage", Player->Health, 100.f, 0.01f);

	// Case B: Player outside 350cm avoids shockwave
	Player->SetActorLocation(FVector(420.f, 0.f, 80.f));
	if (UCharacterMovementComponent* Move = Player->GetCharacterMovement())
	{
		Move->Velocity = FVector::ZeroVector;
	}
	TestFalse("player outside 350cm is not hit by shockwave check", Breaker->ShouldShockwaveHitPlayer(Player));

	// Case C: Player is near ground within 350 cm -> takes 25 dmg + radial knockback
	Player->SetActorLocation(FVector(240.f, 0.f, 80.f));
	TestTrue("grounded player within 350cm is hit by shockwave check", Breaker->ShouldShockwaveHitPlayer(Player));
	Breaker->ForceEnterState(EMLGAlienState::Telegraph);
	Breaker->ForceStrike();
	TestEqual("grounded player within 350cm takes 25 shockwave damage", Player->Health, 75.f, 0.01f);
	TestEqual("player records BREAKER SHOCKWAVE hit tag", Player->LastHitSourceTag, FString(TEXT("BREAKER SHOCKWAVE")));
	TestTrue("grounded player receives radial knockback from shockwave", Player->GetVelocity().Size2D() > 200.f);

	GEngine->DestroyWorldContext(World);
	World->DestroyWorld(false);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMLGHUDPlanningAndCompassFormattingTest, "MarsLastGreen.UI.PlanningZeroWeightAndCompassLayout",
	EAutomationTestFlags::ApplicationContextMask | EAutomationTestFlags::ProductFilter)
bool FMLGHUDPlanningAndCompassFormattingTest::RunTest(const FString&)
{
	// 1. Zero-weight planning formatting (never "-0% speed")
	const FString ZeroPenalty = AMLGHUD::FormatKitSpeedPenalty(0);
	const FString ZeroLine = AMLGHUD::FormatPlanningWeightLine(0, 8);
	TestFalse("zero weight penalty never contains -0%", ZeroPenalty.Contains(TEXT("-0%")));
	TestFalse("zero weight line never contains -0%", ZeroLine.Contains(TEXT("-0%")));
	TestTrue("zero weight line mentions 0% speed penalty", ZeroLine.Contains(TEXT("0% speed penalty")));
	TestTrue("zero weight line mentions no speed penalty", ZeroLine.Contains(TEXT("no speed penalty")));

	const FString TwoPenalty = AMLGHUD::FormatKitSpeedPenalty(2);
	const FString ThreePenalty = AMLGHUD::FormatKitSpeedPenalty(3);
	TestEqual("weight 2 formats -3% speed penalty", TwoPenalty, FString(TEXT("heavier kit = slower on foot: -3% speed")));
	TestEqual("weight 3 formats -4.5% speed penalty", ThreePenalty, FString(TEXT("heavier kit = slower on foot: -4.5% speed")));

	// 2. Compass marker clamping inside [CX - StripW*0.44f, CX + StripW*0.44f] and de-overlapping
	const float CX = 640.f;
	const float StripW = 540.f;
	const float MinBound = CX - StripW * 0.44f;
	const float MaxBound = CX + StripW * 0.44f;

	TArray<float> RawX = { 100.f, 642.f, 648.f, 1200.f };
	TArray<float> ClampedX;
	TArray<int32> StaggerRow;
	AMLGHUD::LayoutCompassMarkers(CX, StripW, RawX, ClampedX, StaggerRow, 65.f);

	TestEqual("4 compass markers laid out", ClampedX.Num(), 4);
	for (int32 i = 0; i < ClampedX.Num(); ++i)
	{
		TestTrue("marker clamped >= MinBound", ClampedX[i] >= MinBound - 0.01f);
		TestTrue("marker clamped <= MaxBound", ClampedX[i] <= MaxBound + 0.01f);
	}
	TestTrue("closely spaced middle markers stagger onto different vertical rows",
		StaggerRow[1] != StaggerRow[2]);

	return true;
}

#include "Sound/SoundAttenuation.h"
#include "../MLGSettings.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMLGAudioSpatialAndChannelsTest, "MarsLastGreen.Audio.SpatialAndChannels",
	EAutomationTestFlags::ApplicationContextMask | EAutomationTestFlags::ProductFilter)
bool FMLGAudioSpatialAndChannelsTest::RunTest(const FString&)
{
	// 1. Channel classification
	TestEqual("music calm classifies to Music", (uint8)MLGAssets::ClassifySoundChannel(MLGAssets::Audio::MusicCalmLoop), (uint8)EMLGSoundChannel::Music);
	TestEqual("music combat classifies to Music", (uint8)MLGAssets::ClassifySoundChannel(MLGAssets::Audio::MusicCombatLoop), (uint8)EMLGSoundChannel::Music);
	TestEqual("wind loop classifies to Ambience", (uint8)MLGAssets::ClassifySoundChannel(MLGAssets::Audio::MarsWindLoop), (uint8)EMLGSoundChannel::Ambience);
	TestEqual("ui click classifies to UI", (uint8)MLGAssets::ClassifySoundChannel(MLGAssets::Audio::UIClick), (uint8)EMLGSoundChannel::UI);
	TestEqual("rifle fire classifies to SFX", (uint8)MLGAssets::ClassifySoundChannel(MLGAssets::Audio::RifleFire), (uint8)EMLGSoundChannel::SFX);

	// 2. Channel volume mixing math (with and without master applied on hardware audio device)
	TestEqual("headless SFX scales by Master*SFX", MLGAssets::ComputeChannelVolume(EMLGSoundChannel::SFX, 0.8f, 0.5f, 0.5f, 0.7f, 0.8f, false), 0.2f, 0.001f);
	TestEqual("active audio device does not square Master", MLGAssets::ComputeChannelVolume(EMLGSoundChannel::SFX, 0.8f, 0.5f, 0.5f, 0.7f, 0.8f, true), 0.4f, 0.001f);
	TestEqual("zero master silences Music", MLGAssets::ComputeChannelVolume(EMLGSoundChannel::Music, 1.f, 0.f, 1.f, 0.9f, 1.f, true), 0.f, 0.001f);
	TestEqual("Ambience uses AmbienceVol", MLGAssets::ComputeChannelVolume(EMLGSoundChannel::Ambience, 0.5f, 1.f, 0.2f, 0.2f, 0.6f, false), 0.3f, 0.001f);

	// 3. Anti-spam cooldown throttling
	MLGAssets::ResetSoundCooldowns();
	TestTrue("first AlertLow passes cooldown", MLGAssets::TryPassSoundCooldown(MLGAssets::Audio::AlertLow, 10.0));
	TestFalse("immediate duplicate AlertLow blocked by cooldown", MLGAssets::TryPassSoundCooldown(MLGAssets::Audio::AlertLow, 10.4));
	TestTrue("AlertLow passes again after 1.5s cooldown", MLGAssets::TryPassSoundCooldown(MLGAssets::Audio::AlertLow, 11.6));
	MLGAssets::ResetSoundCooldowns();

	// 4. Spatial 3D attenuation (Standard vs Heavy Combat)
	USoundAttenuation* StdAtt = MLGAssets::GetSpatialAttenuation(false);
	USoundAttenuation* HeavyAtt = MLGAssets::GetSpatialAttenuation(true);
	TestNotNull("standard spatial attenuation created", StdAtt);
	TestNotNull("heavy combat spatial attenuation created", HeavyAtt);
	if (StdAtt && HeavyAtt)
	{
		TestTrue("standard attenuation enables 3D spatialization", StdAtt->Attenuation.bSpatialize);
		TestTrue("standard attenuation enables distance LPF", StdAtt->Attenuation.bAttenuateWithLPF);
		TestTrue("heavy combat carries farther than standard", HeavyAtt->Attenuation.FalloffDistance > StdAtt->Attenuation.FalloffDistance);
	}

	// 5. Settings defaults include all 4 channels
	UMLGSettings* S = NewObject<UMLGSettings>();
	S->ResetDefaults();
	TestEqual("default MasterVolume", S->MasterVolume, 1.f, 0.001f);
	TestEqual("default SFXVolume", S->SFXVolume, 0.9f, 0.001f);
	TestEqual("default MusicVolume", S->MusicVolume, 0.7f, 0.001f);
	TestEqual("default AmbienceVolume", S->AmbienceVolume, 0.8f, 0.001f);

	return true;
}
#endif

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMLGInvariantAudit, "MarsLastGreen.Logic.InvariantAudit", EAutomationTestFlags::ApplicationContextMask | EAutomationTestFlags::ProductFilter)
bool FMLGInvariantAudit::RunTest(const FString& Parameters)
{
	TestTrue(TEXT("UI rectangle fits"), MLGLogicValidator::ValidateUIRect(0, 0, 1280, 720, 1280, 720));
	TestFalse(TEXT("UI rectangle overflows"), MLGLogicValidator::ValidateUIRect(1200, 0, 100, 50, 1280, 720));
	TestFalse(TEXT("UI rectangle negative X"), MLGLogicValidator::ValidateUIRect(-5, 0, 100, 50, 1280, 720));
	TestFalse(TEXT("UI rectangle zero clip"), MLGLogicValidator::ValidateUIRect(0, 0, 100, 50, 0, 720));
	TestTrue(TEXT("stuck alien"), MLGLogicValidator::IsStuckCandidate(0, 600, 0, 3.6f));
	TestFalse(TEXT("moving alien"), MLGLogicValidator::IsStuckCandidate(30, 600, 0, 4.f));
	TestFalse(TEXT("close alien not stuck"), MLGLogicValidator::IsStuckCandidate(0, 200, 0, 5.f));
	TestFalse(TEXT("invalid location"), MLGLogicValidator::ValidLocation(FVector(std::numeric_limits<float>::quiet_NaN(),0,0)));
 TestTrue(TEXT("positive resource"), MLGLogicValidator::ValidResource(1.f));
 TestFalse(TEXT("negative resource"), MLGLogicValidator::ValidResource(-1.f));
 TestFalse(TEXT("nonfinite resource"), MLGLogicValidator::ValidResource(std::numeric_limits<float>::infinity()));
 TestTrue(TEXT("floor penetration"), MLGLogicValidator::NeedsFloorRecovery(FVector(0,0,-61)));
 TestFalse(TEXT("normal floor"), MLGLogicValidator::NeedsFloorRecovery(FVector(0,0,10)));
 TestFalse(TEXT("softlock before timeout"), MLGLogicValidator::IsAmmoSoftlock(0,0,1,10.f));
 TestTrue(TEXT("softlock after timeout"), MLGLogicValidator::IsAmmoSoftlock(0,0,1,11.f));
 TestFalse(TEXT("reserve prevents softlock"), MLGLogicValidator::IsAmmoSoftlock(0,1,1,11.f));
 return true;
}
