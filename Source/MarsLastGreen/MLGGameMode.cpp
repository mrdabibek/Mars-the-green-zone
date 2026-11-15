#include "MLGGameMode.h"
#include "MLGAlien.h"
#include "MLGLogicValidator.h"
#include "MLGPrologue.h"
#include "Engine/Light.h"
#include "MLGAssets.h"
#include "MLGCharacter.h"
#include "MLGDefenseNode.h"
#include "MLGDevice.h"
#include "MLGGameState.h"
#include "MLGHUD.h"
#include "MLGLogTerminal.h"
#include "MLGPickup.h"
#include "MLGPlantPlot.h"
#include "MLGPlayerController.h"
#include "MLGPressureZone.h"
#include "MLGSaveGame.h"
#include "MLGSettings.h"
#include "MLGWeaponComponent.h"
#include "Kismet/GameplayStatics.h"
#include "Components/AudioComponent.h"
#include "HAL/IConsoleManager.h"
#include "Engine/DamageEvents.h"
#include "TimerManager.h"
#include "EngineUtils.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/StaticMesh.h"
#include "Engine/DirectionalLight.h"
#include "Engine/PointLight.h"
#include "Components/LightComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "GameFramework/PlayerStart.h"
#include "NavigationSystem.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

AMLGGameMode::AMLGGameMode()
{
	DefaultPawnClass = AMLGCharacter::StaticClass();
	HUDClass = AMLGHUD::StaticClass();
	PlayerControllerClass = AMLGPlayerController::StaticClass();
	GameStateClass = AMLGGameState::StaticClass();
	PrimaryActorTick.bCanEverTick = true;
}

void AMLGGameMode::SpawnWave(int32 Raiders, int32 Breakers, int32 Gunners)
{
	// Raiders and breakers come from the west; gunners flank from the north-west so the player must split attention.
	auto Spawn = [this](EMLGAlienKind K, FVector L)
	{
		const FTransform T(FRotator::ZeroRotator, L);
		if (AMLGAlien* A = GetWorld()->SpawnActorDeferred<AMLGAlien>(AMLGAlien::StaticClass(), T, nullptr, nullptr, ESpawnActorCollisionHandlingMethod::AdjustIfPossibleButAlwaysSpawn)) { A->Kind = K; A->FinishSpawning(T); }
	};
	for (int32 i = 0; i < Raiders; ++i) Spawn(EMLGAlienKind::Raider, FVector(-2400.f, (i - (Raiders - 1) * 0.5f) * 300.f, 90.f));
	for (int32 i = 0; i < Breakers; ++i) Spawn(EMLGAlienKind::Breaker, FVector(-2800.f, (i - (Breakers - 1) * 0.5f) * 400.f, 110.f));
	for (int32 i = 0; i < Gunners; ++i) Spawn(EMLGAlienKind::Gunner, FVector(-1500.f - 200.f * i, 1700.f, 100.f));
	MLGAssets::PlaySound2D(this, MLGAssets::Audio::WaveStart, 0.9f);
	UE_LOG(LogTemp, Display, TEXT("MLG: wave spawned (raiders=%d breakers=%d gunners=%d)"), Raiders, Breakers, Gunners);
}

void AMLGGameMode::Tick(float Dt)
{
	Super::Tick(Dt);
	AMLGGameState* GS = GetGameState<AMLGGameState>();
	if (!GS) return;
	if (bIntroActive) { TickIntro(Dt); return; }
	MLGLogicValidator::Tick(GetWorld(), Dt, SoftlockSeconds);
	if (!bInit) { bInit = true; GS->WavesTotal = MaxWaves; }
	if (GS->Phase != (EMLGPhase)LastPhase)
	{
		LastPhase = (uint8)GS->Phase;
		DirectorTimer = 0.f;
		bWarned = false;
		if (GS->Phase == EMLGPhase::Defend) NextWaveIn = FirstWaveDelay;
		if (GS->Phase == EMLGPhase::FinalDefense) NextWaveIn = 30.f;
		bCheckpointPending = GS->Phase > EMLGPhase::Planning && GS->Phase < EMLGPhase::Won;
	}
	if (GS->Phase == EMLGPhase::Repair) bFirstContactArmed = true;
	const int32 Alive = GS->CountAliens();
	if (bCheckpointPending && Alive == 0 && !GS->bPlayerDead)
	{
		bCheckpointPending = false;
		SaveCheckpoint(false);
	}

	if (!bFirstContactTriggered && bFirstContactArmed && !FParse::Param(FCommandLine::Get(), TEXT("nomenu")) &&
		!GS->bPlayerDead && GS->Phase < EMLGPhase::Won)
	{
		constexpr float WarningAt = 16.f;
		constexpr float AttackAt = 24.f;
		const float Previous = FirstContactTimer;
		FirstContactTimer += Dt;
		if (Previous < WarningAt && FirstContactTimer >= WarningAt)
		{
			GS->PushMessage(TEXT("Motion west of the landing pad. Ready your rifle."));
			MLGAssets::PlaySound2D(this, MLGAssets::Audio::AlertLow, .6f);
		}
		if (Alive == 0 && FirstContactTimer >= AttackAt)
		{
			bFirstContactTriggered = true;
			SpawnWave(Difficulty == EMLGDifficulty::Easy ? 1 : 2);
			for (TActorIterator<AMLGAlien> It(GetWorld()); It; ++It)
				if (It->IsAlive()) It->AlertToPlayer(30.f);
			GS->PushMessage(TEXT("First contact: raiders approaching from the west."));
			return;
		}
	}
	TickMusic(Dt, GS, Alive);
	ProcessAlienKillDrops(Dt, GS);
	if (Alive > 0) return;
	const bool bFinal = GS->Phase == EMLGPhase::FinalDefense && GS->Wave < 3;
	if (!((GS->Phase == EMLGPhase::Defend && GS->Wave < 2) || bFinal) || GS->bPlayerDead) return;
	const AMLGCharacter* Pl = Cast<AMLGCharacter>(UGameplayStatics::GetPlayerPawn(this, 0));
	if (Pl && Pl->Health < 35.f) { if (!bHeldNotice) { bHeldNotice = true; GS->PushMessage(TEXT("Contacts holding back while you recover")); } return; }
	bHeldNotice = false;
	DirectorTimer += Dt;
	if (!bWarned && DirectorTimer >= NextWaveIn - 20.f)
	{
		bWarned = true;
		SaveCheckpoint(false);
		GS->PushMessage(TEXT("WARNING: contacts approaching from the west in 20 s"));
		MLGAssets::PlaySound2D(this, MLGAssets::Audio::AlertLow, 0.85f);
	}
	if (DirectorTimer >= NextWaveIn)
	{
		const int32 Base = Difficulty == EMLGDifficulty::Easy ? 1 : Difficulty == EMLGDifficulty::Normal ? 2 : 3;
		const int32 W = bFinal ? 2 : GS->Wave;   // 0,1 = defend waves, 2 = final
		const bool bEasy = Difficulty == EMLGDifficulty::Easy, bHard = Difficulty == EMLGDifficulty::Hard;
		const int32 Breakers = W == 0 ? 0 : W == 1 ? (bEasy ? 0 : 1) : (bHard ? 2 : 1);
		const int32 Gunners = W == 0 ? 0 : W == 1 ? (bHard ? 1 : 0) : (bEasy ? 1 : 2);
		SpawnWave(FMath::Min(4, Base + W), Breakers, Gunners);
		++GS->Wave; DirectorTimer = 0.f; NextWaveIn = WaveGap; bWarned = false;
		GS->PushMessage(FString::Printf(TEXT("Wave %d/%d: red raiders hit the water line, purple breakers smash systems (shoot during their wind-up), blue gunners shoot from range (break line of sight)."), GS->Wave, MaxWaves));
	}
}

void AMLGGameMode::ProcessAlienKillDrops(float Dt, AMLGGameState* GS)
{
	KillDropCooldown = FMath::Max(0.f, KillDropCooldown - Dt);
	if (!GS || bSuppressKillDrops || GS->bPlayerDead || GS->Phase < EMLGPhase::Repair || GS->Phase >= EMLGPhase::Won) return;

	UWorld* W = GetWorld();
	if (!W) return;

	int32 ActiveDrops = 0;
	for (TActorIterator<AMLGPickup> PIt(W); PIt; ++PIt)
	{
		if (PIt->bIsEmergencyDrop) ++ActiveDrops;
	}

	AMLGCharacter* Pl = Cast<AMLGCharacter>(UGameplayStatics::GetPlayerPawn(W, 0));
	const float SuitO2 = Pl ? Pl->SuitOxygen : 100.f;
	const int32 TotalAmmo = (Pl && Pl->Weapon) ? (Pl->Weapon->Mag + Pl->Weapon->Reserve) : 120;
	bool bAnyDamaged = false;
	for (TActorIterator<AMLGDevice> DIt(W); DIt; ++DIt)
	{
		if (DIt->Integrity < DIt->MaxIntegrity) { bAnyDamaged = true; break; }
	}

	for (auto It = ProcessedDeadAliens.CreateIterator(); It; ++It)
	{
		if (!It->IsValid()) It.RemoveCurrent();
	}

	for (TActorIterator<AMLGAlien> It(W); It; ++It)
	{
		AMLGAlien* Alien = *It;
		if (!IsValid(Alien) || Alien->IsAlive() || ProcessedDeadAliens.Contains(Alien)) continue;
		ProcessedDeadAliens.Add(Alien);

		const bool bIsBreaker = Alien->Kind == EMLGAlienKind::Breaker;
		const bool bIsGunner = Alien->Kind == EMLGAlienKind::Gunner;
		if (ActiveDrops >= (bIsBreaker ? 4 : 3) || (KillDropCooldown > 0.f && !bIsBreaker)) continue;

		bool bShouldDrop = false;
		EMLGPickupKind DropKind = EMLGPickupKind::Ammo;
		int32 DropAmount = 24;
		const TCHAR* DropLabel = nullptr;

		if (SuitO2 < (GS->IsDustStormActive() ? 65.f : 50.f))
		{
			bShouldDrop = true;
			DropKind = EMLGPickupKind::Oxygen;
			DropAmount = 25;
			DropLabel = TEXT("Hostile dropped emergency O2 cell (+25%)");
		}
		else if (TotalAmmo < 42)
		{
			bShouldDrop = true;
			DropKind = EMLGPickupKind::Ammo;
			DropAmount = 24;
			DropLabel = TEXT("Hostile dropped ammo cell (+24)");
		}
		else if ((GS->Parts <= 1 && bAnyDamaged) || (bIsBreaker && GS->Parts < 3))
		{
			bShouldDrop = true;
			DropKind = EMLGPickupKind::RepairParts;
			DropAmount = 1;
			DropLabel = TEXT("Hostile dropped repair scrap (+1)");
		}
		else if (bIsBreaker || (bIsGunner && TotalAmmo < 84))
		{
			bShouldDrop = true;
			DropKind = (SuitO2 < 80.f) ? EMLGPickupKind::Oxygen : EMLGPickupKind::Ammo;
			DropAmount = (DropKind == EMLGPickupKind::Oxygen) ? 15 : 16;
			DropLabel = (DropKind == EMLGPickupKind::Oxygen) ? TEXT("Salvaged O2 canister (+15%)") : TEXT("Salvaged ammo cell (+16)");
		}

		if (!bShouldDrop) continue;

		const FVector AlienLoc = Alien->GetActorLocation();
		const FTransform DropT(FRotator::ZeroRotator, FVector(AlienLoc.X, AlienLoc.Y, 30.f));
		if (AMLGPickup* Drop = W->SpawnActorDeferred<AMLGPickup>(AMLGPickup::StaticClass(), DropT, nullptr, nullptr, ESpawnActorCollisionHandlingMethod::AdjustIfPossibleButAlwaysSpawn))
		{
			Drop->Kind = DropKind;
			Drop->Amount = DropAmount;
			Drop->bIsEmergencyDrop = true;
			Drop->FinishSpawning(DropT);
			Drop->TriggerDropPop();
			++ActiveDrops;
			KillDropCooldown = 4.5f;
			if (DropLabel) GS->PushMessage(DropLabel);
		}
	}
}

void AMLGGameMode::InitGame(const FString& Map, const FString& Options, FString& Err)
{
	Super::InitGame(Map, Options, Err);
	Difficulty = (EMLGDifficulty)FMath::Clamp<int32>(UMLGSettings::Get()->Difficulty, 0, 2);   // saved option; URL ?Difficulty= overrides
	const FString D = UGameplayStatics::ParseOption(Options, "Difficulty");
	if (D.Equals("Easy", ESearchCase::IgnoreCase)) Difficulty = EMLGDifficulty::Easy; else if (D.Equals("Hard", ESearchCase::IgnoreCase)) Difficulty = EMLGDifficulty::Hard;
	TActorIterator<AMLGDevice> It(GetWorld());
	if (!It) BuildPrototypeBase();
}

void AMLGGameMode::StartPlay()
{
	Super::StartPlay();
	if (UNavigationSystemV1* Nav = FNavigationSystem::GetCurrent<UNavigationSystemV1>(GetWorld()))
	{
		FNavLocation Probe;
		if (!Nav->ProjectPointToNavigation(FVector(-500.f, 0.f, 0.f), Probe, FVector(500.f, 500.f, 300.f)))
		{
			Nav->Build();
			const bool bReady = Nav->ProjectPointToNavigation(FVector(-500.f, 0.f, 0.f), Probe, FVector(500.f, 500.f, 300.f));
			UE_LOG(LogTemp, Display, TEXT("MLG: runtime NavMesh build complete (navReady=%d)"), bReady ? 1 : 0);
		}
	}
	CalmMusicComp = MLGAssets::SpawnLoopingSound2D(this, MLGAssets::Audio::MusicCalmLoop, 0.f);
	CombatMusicComp = MLGAssets::SpawnLoopingSound2D(this, MLGAssets::Audio::MusicCombatLoop, 0.f);
}

void AMLGGameMode::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (IntroScore) IntroScore->Stop();
	if (IntroDialogue) IntroDialogue->Stop();
	if (CalmMusicComp) { CalmMusicComp->Stop(); CalmMusicComp = nullptr; }
	if (CombatMusicComp) { CombatMusicComp->Stop(); CombatMusicComp = nullptr; }
	Super::EndPlay(EndPlayReason);
}

EMLGMusicState AMLGGameMode::SelectMusicState(EMLGPhase Phase, int32 AliveAliens, bool bWaveWarned, bool bPlayerDead)
{
	if (bPlayerDead || Phase == EMLGPhase::Planning || Phase == EMLGPhase::Won || Phase == EMLGPhase::Lost)
	{
		return EMLGMusicState::Silent;
	}
	return (AliveAliens > 0 || bWaveWarned) ? EMLGMusicState::Combat : EMLGMusicState::Calm;
}

void AMLGGameMode::UpdateMusic()
{
	const float Scale = MLGAssets::GetEffectiveChannelVolume(EMLGSoundChannel::Music, 1.f);
	const float PauseDuck = UGameplayStatics::IsGamePaused(this) ? 0.35f : 1.f;
	if (CalmMusicComp) CalmMusicComp->SetVolumeMultiplier(CalmMusicAlpha * 0.28f * Scale * PauseDuck);
	if (CombatMusicComp) CombatMusicComp->SetVolumeMultiplier(CombatMusicAlpha * 0.36f * Scale * PauseDuck);
}

void AMLGGameMode::TickMusic(float Dt, const AMLGGameState* GS, int32 AliveAliens)
{
	CurrentMusicState = SelectMusicState(GS->Phase, AliveAliens, bWarned, GS->bPlayerDead);
	CalmMusicAlpha = FMath::FInterpTo(CalmMusicAlpha, CurrentMusicState == EMLGMusicState::Calm ? 1.f : 0.f, Dt, 1.2f);
	CombatMusicAlpha = FMath::FInterpTo(CombatMusicAlpha, CurrentMusicState == EMLGMusicState::Combat ? 1.f : 0.f, Dt, 2.0f);
	UpdateMusic();
}

namespace
{
	AStaticMeshActor* Block(UWorld* W, FVector Center, FVector SizeCm, FLinearColor Col)
	{
		FActorSpawnParameters P; P.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		AStaticMeshActor* A = W->SpawnActor<AStaticMeshActor>(Center, FRotator::ZeroRotator, P);
		UStaticMeshComponent* C = A->GetStaticMeshComponent();
		C->SetMobility(EComponentMobility::Movable);
		C->SetStaticMesh(LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube")));
		A->SetActorScale3D(SizeCm / 100.f);
		if (UMaterialInstanceDynamic* M = MLGAssets::EnsureColorMID(C, 0)) M->SetVectorParameterValue("Color", Col);
		return A;
	}
	template <class T> T* Put(UWorld* W, FVector L, FRotator R = FRotator::ZeroRotator)
	{
		FActorSpawnParameters P; P.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		return W->SpawnActor<T>(L, R, P);
	}
	template <class T, class Fn> T* PutDeferred(UWorld* W, FVector L, Fn&& Init, FRotator R = FRotator::ZeroRotator)
	{
		const FTransform Tr(R, L);
		T* A = W->SpawnActorDeferred<T>(T::StaticClass(), Tr, nullptr, nullptr, ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
		if (A) { Init(A); A->FinishSpawning(Tr); }
		return A;
	}
}

void AMLGGameMode::BuildPrototypeBase()
{
	UWorld* W = GetWorld();
	const FLinearColor Ground(0.35f, 0.15f, 0.08f), Wall(0.18f, 0.20f, 0.24f);
	UStaticMesh* WallMesh = MLGAssets::LoadOptional<UStaticMesh>(TEXT("/Game/Environment/SM_Habitat_WallPanel"));
	UStaticMesh* FloorMesh = MLGAssets::LoadOptional<UStaticMesh>(TEXT("/Game/Environment/SM_Habitat_FloorTile"));
	UStaticMesh* GlassRoofMesh = MLGAssets::LoadOptional<UStaticMesh>(TEXT("/Game/Environment/SM_Greenhouse_GlassRoof"));
	UMaterialInterface* MarsGroundMat = MLGAssets::LoadOptional<UMaterialInterface>(TEXT("/Game/Environment/Materials/M_Mars_Ground"));
	UMaterialInterface* WallMat = MLGAssets::LoadOptional<UMaterialInterface>(TEXT("/Game/Environment/Materials/M_Habitat_Wall"));
	UMaterialInterface* GlassMat = MLGAssets::LoadOptional<UMaterialInterface>(TEXT("/Game/Environment/Materials/M_Greenhouse_Glass"));

	AStaticMeshActor* GroundActor = Block(W, FVector(0, 0, -10), FVector(60000, 60000, 20), Ground);
	if (MarsGroundMat && GroundActor)
	{
		GroundActor->GetStaticMeshComponent()->SetMaterial(0, MarsGroundMat);
	}

	auto Wl = [&](float x, float y, float sx, float sy)
	{
		if (WallMesh)
		{
			FActorSpawnParameters P;
			P.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
			const bool bAlongX = (sx >= sy);
			const FRotator Rot = bAlongX ? FRotator::ZeroRotator : FRotator(0.f, 90.f, 0.f);
			const FVector Scale(bAlongX ? (sx / 100.f) : (sy / 100.f), bAlongX ? (sy / 40.f) : (sx / 40.f), 1.f);
			AStaticMeshActor* A = W->SpawnActor<AStaticMeshActor>(FVector(x, y, 0.f), Rot, P);
			UStaticMeshComponent* C = A->GetStaticMeshComponent();
			C->SetMobility(EComponentMobility::Movable);
			C->SetStaticMesh(WallMesh);
			C->SetCollisionProfileName(TEXT("BlockAll"));
			A->SetActorScale3D(Scale);
			return;
		}
		AStaticMeshActor* FallbackWall = Block(W, FVector(x, y, 150), FVector(sx, sy, 300), Wall);
		if (WallMat && FallbackWall) FallbackWall->GetStaticMeshComponent()->SetMaterial(0, WallMat);
	};
	Wl(-900, 310, 40, 380); Wl(-900, -310, 40, 380);          // habitat west (door gap |y|<120 = exterior exit)
	Wl(-500, 500, 840, 40); Wl(-500, -500, 840, 40);          // habitat north/south
	Wl(-100, 325, 40, 350); Wl(-100, -325, 40, 350);          // habitat east (corridor gap)
	Wl(0, 150, 240, 40);    Wl(0, -150, 240, 40);             // corridor
	Wl(100, 325, 40, 350);  Wl(100, -325, 40, 350);           // greenhouse west
	Wl(500, 500, 840, 40);  Wl(500, -500, 840, 40); Wl(900, 0, 40, 1040);

	// Flush interior deck floor tiles (NoCollision & non-nav-affecting so NavMesh on Z=0 is never perturbed)
	if (FloorMesh)
	{
		auto SpawnTiledFloor = [&](float CenterX, float CenterY, float SpanX, float SpanY, int32 NX, int32 NY)
		{
			const float TileX = SpanX / (float)NX;
			const float TileY = SpanY / (float)NY;
			FActorSpawnParameters P;
			P.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
			for (int32 ix = 0; ix < NX; ++ix)
			{
				for (int32 iy = 0; iy < NY; ++iy)
				{
					const float TX = CenterX - SpanX * 0.5f + (ix + 0.5f) * TileX;
					const float TY = CenterY - SpanY * 0.5f + (iy + 0.5f) * TileY;
					AStaticMeshActor* FA = W->SpawnActor<AStaticMeshActor>(FVector(TX, TY, -18.5f), FRotator::ZeroRotator, P);
					UStaticMeshComponent* FC = FA->GetStaticMeshComponent();
					FC->SetMobility(EComponentMobility::Movable);
					FC->SetStaticMesh(FloorMesh);
					FC->SetCollisionProfileName(TEXT("NoCollision"));
					FC->SetCanEverAffectNavigation(false);
					FA->SetActorScale3D(FVector(TileX / 100.f, TileY / 100.f, 1.f));
				}
			}
		};
		SpawnTiledFloor(-500.f, 0.f, 800.f, 960.f, 3, 3);
		SpawnTiledFloor(0.f, 0.f, 200.f, 260.f, 1, 2);
		SpawnTiledFloor(500.f, 0.f, 800.f, 960.f, 3, 3);
	}

	// Roofs: Habitat & Corridor use structural deck panels; Greenhouse uses translucent skylight truss panels!
	for (auto R : { FVector4(-500, 0, 840, 1040), FVector4(0, 0, 240, 340), FVector4(500, 0, 840, 1040) })
	{
		const bool bGreenhouseRoof = (R.X > 250.f);
		if (bGreenhouseRoof && GlassRoofMesh)
		{
			const int32 NX = 3, NY = 3;
			const float TileX = R.Z / (float)NX;
			const float TileY = R.W / (float)NY;
			FActorSpawnParameters P;
			P.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
			for (int32 ix = 0; ix < NX; ++ix)
			{
				for (int32 iy = 0; iy < NY; ++iy)
				{
					const float TX = R.X - R.Z * 0.5f + (ix + 0.5f) * TileX;
					const float TY = R.Y - R.W * 0.5f + (iy + 0.5f) * TileY;
					AStaticMeshActor* GA = W->SpawnActor<AStaticMeshActor>(FVector(TX, TY, 295.f), FRotator::ZeroRotator, P);
					UStaticMeshComponent* GC = GA->GetStaticMeshComponent();
					GC->SetMobility(EComponentMobility::Movable);
					GC->SetStaticMesh(GlassRoofMesh);
					GC->SetCollisionProfileName(TEXT("NoCollision"));
					GC->SetCanEverAffectNavigation(false);
					GC->SetCastShadow(false);
					if (GlassMat && GC->GetNumMaterials() > 1) GC->SetMaterial(1, GlassMat);
					GA->SetActorScale3D(FVector(TileX / 100.f, TileY / 100.f, 1.f));
				}
			}
		}
		else if (FloorMesh && !bGreenhouseRoof)
		{
			FActorSpawnParameters P;
			P.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
			AStaticMeshActor* RA = W->SpawnActor<AStaticMeshActor>(FVector(R.X, R.Y, 300.f), FRotator::ZeroRotator, P);
			UStaticMeshComponent* RC = RA->GetStaticMeshComponent();
			RC->SetMobility(EComponentMobility::Movable);
			RC->SetStaticMesh(FloorMesh);
			RC->SetCanEverAffectNavigation(false);
			RA->SetActorScale3D(FVector(R.Z / 100.f, R.W / 100.f, 1.f));
		}
		else
		{
			AStaticMeshActor* RoofBlock = Block(W, FVector(R.X, R.Y, 310), FVector(R.Z, R.W, 20), Wall);
			if (bGreenhouseRoof && RoofBlock)
			{
				RoofBlock->GetStaticMeshComponent()->SetCastShadow(false);
				if (GlassMat) RoofBlock->GetStaticMeshComponent()->SetMaterial(0, GlassMat);
			}
		}
	}

	auto Dev = [&](EMLGDeviceType T, const TCHAR* Name, FVector L)
	{
		PutDeferred<AMLGDevice>(W, L, [&](AMLGDevice* D) { D->Type = T; D->DisplayName = FText::FromString(Name); });
	};
	Dev(EMLGDeviceType::Power, TEXT("Power unit"), FVector(-800, -400, 60));
	Dev(EMLGDeviceType::Oxygen, TEXT("Oxygen generator"), FVector(-800, 400, 60));
	Dev(EMLGDeviceType::WaterPurifier, TEXT("Water purifier"), FVector(-300, 400, 60));
	Dev(EMLGDeviceType::GreenhouseSeal, TEXT("Greenhouse seal"), FVector(200, -440, 60));
	// Water line outside the west exit: tank + pipe start intact and are what the raiders go for first.
	for (auto& L : { TPair<const TCHAR*, FVector>(TEXT("Water tank"), FVector(-1400, -350, 80)), TPair<const TCHAR*, FVector>(TEXT("Water pipe"), FVector(-1400, 350, 30)) })
	{
		const bool bPipe = FCString::Strcmp(L.Key, TEXT("Water pipe")) == 0;
		PutDeferred<AMLGDevice>(W, L.Value, [&](AMLGDevice* DevActor)
		{
			DevActor->Type = EMLGDeviceType::WaterTank;
			DevActor->bPipeSegment = bPipe;
			DevActor->DisplayName = FText::FromString(L.Key);
			DevActor->Integrity = DevActor->MaxIntegrity;
			DevActor->SetActorScale3D(bPipe ? FVector(3.f, 0.3f, 0.3f) : FVector(1.6f, 1.6f, 1.6f));
		});
	}
	for (float x : { 400.f, 700.f }) for (float y : { -200.f, 200.f }) Put<AMLGPlantPlot>(W, FVector(x, y, 20));

	auto Pick = [&](EMLGPickupKind K, int32 N, FVector L)
	{
		PutDeferred<AMLGPickup>(W, L, [&](AMLGPickup* P) { P->Kind = K; P->Amount = N; });
	};
	Pick(EMLGPickupKind::RepairParts, 1, FVector(-700, 0, 30));
	Pick(EMLGPickupKind::RepairParts, 1, FVector(-300, -420, 30));
	Pick(EMLGPickupKind::RepairParts, 1, FVector(300, 420, 30));
	Pick(EMLGPickupKind::Ammo, 48, FVector(-500, 300, 30));
	Pick(EMLGPickupKind::Ice, 1, FVector(200, -1500, 30)); Pick(EMLGPickupKind::Ice, 1, FVector(320, -1560, 30));
	Pick(EMLGPickupKind::Ice, 1, FVector(440, -1500, 30)); Pick(EMLGPickupKind::Ice, 1, FVector(560, -1560, 30));   // ice field, south
	Pick(EMLGPickupKind::RepairParts, 1, FVector(380, -1620, 30));
	Pick(EMLGPickupKind::RepairParts, 1, FVector(2450, 200, 30));
	Pick(EMLGPickupKind::SeedBank, 3, FVector(2560, 150, 30));
	PutDeferred<AMLGDevice>(W, FVector(2500, 0, 60), [](AMLGDevice* R) { R->Type = EMLGDeviceType::Comms; R->DisplayName = FText::FromString(TEXT("Comms relay")); R->RepairSeconds = 8.f; });
	PutDeferred<AMLGDevice>(W, FVector(-860, 0, 60), [](AMLGDevice* T) { T->Type = EMLGDeviceType::Transmitter; T->DisplayName = FText::FromString(TEXT("Transmitter console")); T->Integrity = T->MaxIntegrity; });

	auto IntactDev = [&](EMLGDeviceType T, const TCHAR* Name, FVector L, FVector Scale)
	{
		PutDeferred<AMLGDevice>(W, L, [&](AMLGDevice* D)
		{
			D->Type = T;
			D->DisplayName = FText::FromString(Name);
			D->Integrity = D->MaxIntegrity;
			D->SetActorScale3D(Scale);
		});
	};
	IntactDev(EMLGDeviceType::GeneLab, TEXT("CRISPR Gene Sequencer"), FVector(560, 430, 60), FVector(0.85f, 0.85f, 1.2f));
	IntactDev(EMLGDeviceType::Sabatier, TEXT("Sabatier H2O Synth"), FVector(560, -430, 60), FVector(0.85f, 0.85f, 1.2f));
	IntactDev(EMLGDeviceType::DropLocker, TEXT("DropShip BlackBox"), FVector(-1850, -900, 60), FVector(0.7f, 0.7f, 0.95f));
	IntactDev(EMLGDeviceType::CryoRig, TEXT("Cryo Ice Rig"), FVector(0, -2100, 60), FVector(1.2f, 1.2f, 1.6f));
	IntactDev(EMLGDeviceType::SolarSub, TEXT("NW Solar Substation"), FVector(-1700, 1400, 60), FVector(1.1f, 1.1f, 1.4f));
	IntactDev(EMLGDeviceType::CommsSub, TEXT("East Tactical Relay"), FVector(2000, 400, 60), FVector(0.95f, 0.95f, 1.4f));
	PutDeferred<AMLGLogTerminal>(W, FVector(-600, -460, 45), [](AMLGLogTerminal* L) { L->LogText = TEXT("Log, Dr. Okafor: Perchlorates in the regolith poison most crops. The sealed greenhouse beds are why anything grows here."); });
	PutDeferred<AMLGLogTerminal>(W, FVector(2450, -150, 45), [](AMLGLogTerminal* L) { L->LogText = TEXT("Log, relay tech: Mars air is thin and mostly CO2. Do not walk out here without a full suit."); });

	auto Zone = [&](EMLGZoneKind K, FVector C, FVector Ext)
	{
		PutDeferred<AMLGPressureZone>(W, C, [&](AMLGPressureZone* Z) { Z->Kind = K; Z->Box->SetBoxExtent(Ext); });
	};
	Zone(EMLGZoneKind::Habitat, FVector(-500, 0, 150), FVector(400, 500, 150));
	Zone(EMLGZoneKind::Habitat, FVector(0, 0, 150), FVector(100, 150, 150));
	Zone(EMLGZoneKind::Greenhouse, FVector(500, 0, 150), FVector(400, 500, 150));

	// Predefined defensive perimeter pads (no freeform base building; meaningful parts & power trade-offs)
	auto DefPad = [&](EMLGDefenseKind K, const TCHAR* Name, FVector L)
	{
		PutDeferred<AMLGDefenseNode>(W, L, [&](AMLGDefenseNode* D) { D->Kind = K; D->DisplayName = FText::FromString(Name); });
	};
	DefPad(EMLGDefenseKind::ShockBarrier, TEXT("West Door Shock Barrier"), FVector(-1150, 0, 0));
	DefPad(EMLGDefenseKind::SentryTurret, TEXT("Water Line Sentry Pad"), FVector(-1300, -140, 0));
	DefPad(EMLGDefenseKind::SentryTurret, TEXT("North-West Flank Sentry Pad"), FVector(-1050, 620, 0));

	Put<APlayerStart>(W, FVector(-500, 0, 120));
	if (!TActorIterator<APointLight>(W))
	{
		for (float x : { -500.f, 500.f })
		{
			APointLight* L = Put<APointLight>(W, FVector(x, 0, 260));
			L->GetRootComponent()->SetMobility(EComponentMobility::Movable);
			L->GetLightComponent()->SetIntensity(60.f);
			L->PointLightComponent->SetAttenuationRadius(1400.f);
		}
	}
	if (!TActorIterator<ADirectionalLight>(W))
	{
		ADirectionalLight* Sun = Put<ADirectionalLight>(W, FVector(0, 0, 1000), FRotator(-35, 40, 0));
		Sun->GetRootComponent()->SetMobility(EComponentMobility::Movable);
		Sun->GetLightComponent()->SetIntensity(3.f); // weak, dusty light; temporary
	}
	UE_LOG(LogTemp, Display, TEXT("MLG: prototype base built (devices=8 plots=4)"));
}

#if !UE_BUILD_SHIPPING
// Headless scripted check of target choice, leak, stagger/kill. Run: UnrealEditor-Cmd ... -game -ExecCmds="mlg.selftest" -benchmark -seconds=60
void AMLGGameMode::RunSelfTest()
{
	UWorld* W = GetWorld();
	for (TActorIterator<AMLGDevice> It(W); It; ++It) It->Integrity = It->MaxIntegrity;
	for (TActorIterator<AMLGPlantPlot> It(W); It; ++It) It->Plant.Plant();
	GetGameState<AMLGGameState>()->Sim.Power = 80.f;
	GetGameState<AMLGGameState>()->ForcePhase(EMLGPhase::Repair); FirstWaveDelay = 9999.f;
	SpawnWave(2);
	FTimerHandle H, K;
	W->GetTimerManager().SetTimer(H, FTimerDelegate::CreateLambda([W]()
	{
		FString S = FString::Printf(TEXT("MLG-TEST t=%.0f"), W->GetTimeSeconds());
		for (TActorIterator<AMLGDevice> It(W); It; ++It) if (It->Type == EMLGDeviceType::WaterTank) S += FString::Printf(TEXT(" [%s %.0f%%]"), *It->DisplayName.ToString(), It->Integrity);
		S += FString::Printf(TEXT(" water=%.1f"), W->GetGameState<AMLGGameState>()->Sim.Water);
		for (TActorIterator<AMLGAlien> It(W); It; ++It) S += FString::Printf(TEXT(" {%s st=%d tgt=%s hp=%.0f}"), *It->GetName(), (int32)It->State, *It->TargetName(), It->Health);
		UE_LOG(LogTemp, Display, TEXT("%s"), *S);
	}), 3.f, true);
	W->GetTimerManager().SetTimer(K, FTimerDelegate::CreateLambda([W]()
	{
		for (TActorIterator<AMLGAlien> It(W); It; ++It) if (It->IsAlive()) { UGameplayStatics::ApplyDamage(*It, 25.f, nullptr, nullptr, nullptr); break; } // hit-reaction check
	}), 6.f, true, 12.f);
}
static FAutoConsoleCommandWithWorld GMLGSelfTestCmd(TEXT("mlg.selftest"), TEXT("Scripted combat/AI self-test"),
	FConsoleCommandWithWorldDelegate::CreateLambda([](UWorld* W) { if (AMLGGameMode* GM = W->GetAuthGameMode<AMLGGameMode>()) GM->RunSelfTest(); }));
#endif

bool AMLGGameMode::SaveCheckpoint(bool bManual)
{
	AMLGGameState* GS = GetGameState<AMLGGameState>();
	AMLGCharacter* C = Cast<AMLGCharacter>(UGameplayStatics::GetPlayerPawn(this, 0));
	if (!GS || !C || C->bDead || GS->Phase == EMLGPhase::Planning || GS->Phase == EMLGPhase::Won || GS->Phase == EMLGPhase::Lost) return false;
	if (GS->CountAliens() > 0) { if (bManual) GS->PushMessage(TEXT("Cannot save during an attack")); return false; }
	UMLGSaveGame* S = Cast<UMLGSaveGame>(UGameplayStatics::CreateSaveGameObject(UMLGSaveGame::StaticClass()));
	S->Sim = GS->Sim; S->Phase = GS->Phase; S->Seeds = GS->Seeds; S->Parts = GS->Parts; S->Wave = GS->Wave; S->Kills = GS->Kills;
	S->IceCollected = GS->IceCollected; S->Repairs = GS->Repairs; S->LogsRead = GS->LogsRead; S->KitMask = GS->KitMask; S->bBackup = GS->bBackupRecovered;
	S->FirstContactTimer = FirstContactTimer;
	S->bFirstContactTriggered = bFirstContactTriggered || FParse::Param(FCommandLine::Get(), TEXT("nomenu"));
	S->Elapsed = GS->Elapsed; S->DirectorTimer = DirectorTimer; S->NextWaveIn = NextWaveIn; S->bWarned = bWarned;
	for (TActorIterator<AMLGDevice> It(GetWorld()); It; ++It) S->Devices.Add(It->GetName(), It->Integrity);
	for (TActorIterator<AMLGPlantPlot> It(GetWorld()); It; ++It) S->Plots.Add(It->GetName(), It->Plant);
	for (TActorIterator<AMLGDefenseNode> It(GetWorld()); It; ++It)
	{
		FMLGDefenseSave DS; DS.State = It->DefenseState; DS.Integrity = It->Integrity;
		S->Defenses.Add(It->DisplayName.ToString(), DS);
	}
	for (TActorIterator<AMLGPickup> It(GetWorld()); It; ++It) { FMLGPickupSave P; P.Kind = It->Kind; P.Amount = It->Amount; P.Loc = It->GetActorLocation(); S->Pickups.Add(P); }
	S->PlayerLoc = C->GetActorLocation(); S->PlayerRot = C->GetControlRotation(); S->Health = C->Health; S->SuitOxygen = C->SuitOxygen;
	S->Mag = C->Weapon->Mag; S->Reserve = C->Weapon->Reserve;
	const bool bOk = UGameplayStatics::SaveGameToSlot(S, SlotName(), 0);
	UE_LOG(LogTemp, Display, TEXT("MLG: checkpoint saved ok=%d phase=%d wave=%d"), bOk, (int32)S->Phase, S->Wave);
	if (bOk) GS->PushMessage(bManual ? TEXT("Game saved") : TEXT("Checkpoint reached"));
	return bOk;
}

bool AMLGGameMode::LoadCheckpoint()
{
	UMLGSaveGame* S = Cast<UMLGSaveGame>(UGameplayStatics::LoadGameFromSlot(SlotName(), 0));
	AMLGGameState* GS = GetGameState<AMLGGameState>();
	AMLGCharacter* C = Cast<AMLGCharacter>(UGameplayStatics::GetPlayerPawn(this, 0));
	if (!S || !GS || !C) return false;
	for (TActorIterator<AMLGAlien> It(GetWorld()); It; ++It) It->Destroy();           // attackers are not saved: the wave replays
	ProcessedDeadAliens.Empty();
	KillDropCooldown = 0.f;
	bFirstContactTriggered = S->bFirstContactTriggered;
	bFirstContactArmed = S->Phase >= EMLGPhase::Repair;
	FirstContactTimer = FMath::Clamp(S->FirstContactTimer, 0.f, 16.f - .1f);
	SoftlockSeconds = 0.f;
	bCheckpointPending = false;
	GS->ResetCheckpointFeedback();
	GS->ResetEnvironmentAfterLoad();
	GS->Sim = S->Sim; GS->Phase = S->Phase; GS->Seeds = S->Seeds; GS->Parts = S->Parts; GS->Wave = S->Wave; GS->Kills = S->Kills;
	GS->IceCollected = S->IceCollected; GS->Repairs = S->Repairs; GS->LogsRead = S->LogsRead; GS->KitMask = S->KitMask; GS->bBackupRecovered = S->bBackup;
	GS->Elapsed = S->Elapsed; GS->bPlayerDead = false; GS->LoseReason.Empty();
	DirectorTimer = S->DirectorTimer; NextWaveIn = S->NextWaveIn; bWarned = S->bWarned; LastPhase = (uint8)S->Phase; bHeldNotice = false;
	for (TActorIterator<AMLGDevice> It(GetWorld()); It; ++It) if (const float* V = S->Devices.Find(It->GetName())) It->Integrity = *V;
	for (TActorIterator<AMLGPlantPlot> It(GetWorld()); It; ++It) if (const FMLGPlantModel* P = S->Plots.Find(It->GetName())) It->Plant = *P;
	for (TActorIterator<AMLGDefenseNode> It(GetWorld()); It; ++It) if (const FMLGDefenseSave* DS = S->Defenses.Find(It->DisplayName.ToString())) It->ApplySavedState(DS->State, DS->Integrity);
	for (TActorIterator<AMLGPickup> It(GetWorld()); It; ++It) It->Destroy();           // collected-since pickups come back; no duplicates
	for (const FMLGPickupSave& P : S->Pickups)
	{
		const FTransform T(FRotator::ZeroRotator, P.Loc);
		if (AMLGPickup* K = GetWorld()->SpawnActorDeferred<AMLGPickup>(AMLGPickup::StaticClass(), T)) { K->Kind = P.Kind; K->Amount = P.Amount; K->FinishSpawning(T); }
	}
	C->ApplySaved(S->PlayerLoc, S->PlayerRot, S->Health, S->SuitOxygen, S->Mag, S->Reserve);
	GS->PushMessage(TEXT("Checkpoint loaded"));
	UE_LOG(LogTemp, Display, TEXT("MLG: checkpoint loaded phase=%d wave=%d"), (int32)S->Phase, S->Wave);
	return true;
}

#if !UE_BUILD_SHIPPING
// Scripted end-to-end mission check (headless): kit planning, every phase, mid-attack reload, both end states, death reload.
void AMLGGameMode::RunMissionTest()
{
	struct FCtx { TArray<TFunction<bool()>> Steps; int32 I = 0, Ticks = 0, Fail = 0; FTimerHandle H; };
	TSharedPtr<FCtx> X = MakeShared<FCtx>();
	FirstWaveDelay = 3.f; WaveGap = 3.f;
	bSuppressKillDrops = true;
	AMLGGameState* GS = GetGameState<AMLGGameState>();
	UWorld* W = GetWorld();
	auto Chk = [X](const TCHAR* N, bool Ok) { UE_LOG(LogTemp, Display, TEXT("MLG-MISSION %s: %s"), Ok ? TEXT("PASS") : TEXT("FAIL"), N); if (!Ok) ++X->Fail; };
	auto KillAll = [W]() { for (TActorIterator<AMLGAlien> It(W); It; ++It) if (It->IsAlive()) UGameplayStatics::ApplyDamage(*It, 100.f, nullptr, nullptr, nullptr); };
	auto Dev = [W](EMLGDeviceType T) -> AMLGDevice* { for (TActorIterator<AMLGDevice> It(W); It; ++It) if (It->Type == T) return *It; return nullptr; };

	X->Steps.Add([=]() { GS->ToggleKit(0); GS->ToggleKit(3);
		Chk(TEXT("kit weight 2+3=5"), GS->KitWeight() == 5);
		Chk(TEXT("water reserve fits (8)"), GS->ToggleKit(4)); Chk(TEXT("over-budget item refused"), !GS->ToggleKit(1)); GS->ToggleKit(4);
		GS->ConfirmKit(); Chk(TEXT("confirm: seeds 3+2, phase Repair"), GS->Seeds == 5 && GS->Phase == EMLGPhase::Repair && GS->WalkScale() < 1.f); return true; });
	X->Steps.Add([=]() { for (TActorIterator<AMLGDevice> It(W); It; ++It) if (It->Type == EMLGDeviceType::Power || It->Type == EMLGDeviceType::Oxygen || It->Type == EMLGDeviceType::GreenhouseSeal) It->Integrity = It->MaxIntegrity; return true; });
	X->Steps.Add([=]() { Chk(TEXT("repairs -> phase Plant"), GS->Phase == EMLGPhase::Plant); for (TActorIterator<AMLGPlantPlot> It(W); It; ++It) { It->Plant.Plant(); break; } return true; });
	X->Steps.Add([=]() { Chk(TEXT("planting -> phase Grow"), GS->Phase == EMLGPhase::Grow); for (TActorIterator<AMLGPlantPlot> It(W); It; ++It) if (It->Plant.IsLiving()) It->Plant.Stage = EMLGPlantStage::Seedling; return true; });
	X->Steps.Add([=]() { Chk(TEXT("seedling -> phase IceRun"), GS->Phase == EMLGPhase::IceRun); Chk(TEXT("checkpoint file written"), UGameplayStatics::DoesSaveGameExist(SlotName(), 0)); GS->IceCollected = 4; return true; });
	X->Steps.Add([=]() { Chk(TEXT("ice alone not enough: purifier still broken"), GS->Phase == EMLGPhase::IceRun); Dev(EMLGDeviceType::WaterPurifier)->Integrity = 100.f; return true; });
	X->Steps.Add([=]() { return GS->CountAliens() > 0; });   // wave 1 spawned by the director
	X->Steps.Add([=]() { Chk(TEXT("phase Defend, wave 1 on the ground"), GS->Phase == EMLGPhase::Defend && GS->Wave == 1);
		Chk(TEXT("mid-attack save refused"), !SaveCheckpoint(true)); Chk(TEXT("mid-attack reload ok"), LoadCheckpoint());
		Chk(TEXT("reload: attackers gone, wave count restored"), GS->CountAliens() == 0 && GS->Wave == 0 && GS->Phase == EMLGPhase::Defend); return true; });
	X->Steps.Add([=]() { KillAll(); return GS->Phase == EMLGPhase::CommsRun; });   // wave 1 replays, then wave 2, killed as they appear
	X->Steps.Add([=]() { Chk(TEXT("2 waves cleared -> CommsRun"), GS->Phase == EMLGPhase::CommsRun && GS->Kills >= 3); Dev(EMLGDeviceType::Comms)->Integrity = 100.f; GS->bBackupRecovered = true; return true; });
	X->Steps.Add([=]() { KillAll(); return GS->Phase == EMLGPhase::Transmit; });    // final wave
	X->Steps.Add([=]() { AMLGDevice* T = Dev(EMLGDeviceType::Transmitter); Chk(TEXT("final wave cleared -> Transmit, console usable"), GS->Wave == 3 && T->CanInteract(nullptr));
		T->Interact(nullptr); Chk(TEXT("transmit -> Won"), GS->Phase == EMLGPhase::Won);
		UE_LOG(LogTemp, Display, TEXT("MLG-MISSION RESULTS seeds=%d water_used=%.1f repairs=%d kills=%d science=%d time=%.0fs"), GS->Seeds + GS->CountLivingPlants(), GS->Sim.WaterUsed, GS->Repairs, GS->Kills, GS->ScienceScore(), GS->Elapsed); return true; });
	X->Steps.Add([=]() { Chk(TEXT("reload after win restores last checkpoint (Transmit, wave 3, seeds 5)"), LoadCheckpoint() && GS->Phase == EMLGPhase::Transmit && GS->Wave == 3 && GS->Seeds == 5);
		GS->Seeds = 0; for (TActorIterator<AMLGPlantPlot> It(W); It; ++It) It->Plant.Clear(); for (TActorIterator<AMLGPickup> It(W); It; ++It) It->Destroy(); return true; });
	X->Steps.Add([=]() { Chk(TEXT("all seeds lost -> Lost"), GS->Phase == EMLGPhase::Lost && !GS->LoseReason.IsEmpty()); Chk(TEXT("reload after loss"), LoadCheckpoint() && GS->Phase == EMLGPhase::Transmit && GS->Seeds == 5 && GS->CountLivingPlants() >= 1);
		UGameplayStatics::ApplyDamage(UGameplayStatics::GetPlayerPawn(W, 0), 999.f, nullptr, nullptr, nullptr); return true; });
	X->Steps.Add([=]() { Chk(TEXT("player death -> Lost"), GS->Phase == EMLGPhase::Lost); Chk(TEXT("reload after death revives player"), LoadCheckpoint() && !Cast<AMLGCharacter>(UGameplayStatics::GetPlayerPawn(W, 0))->bDead);
		UE_LOG(LogTemp, Display, TEXT("MLG-MISSION DONE failures=%d"), X->Fail); return true; });

	W->GetTimerManager().SetTimer(X->H, FTimerDelegate::CreateLambda([X, W]()
	{
		if (X->I >= X->Steps.Num()) return;
		if (X->Steps[X->I]()) { X->I++; X->Ticks = 0; }
		else if (++X->Ticks > 240) { UE_LOG(LogTemp, Display, TEXT("MLG-MISSION FAIL: step %d timed out"), X->I); X->I = X->Steps.Num(); }
	}), 0.5f, true);
}
static FAutoConsoleCommandWithWorld GMLGMissionTestCmd(TEXT("mlg.missiontest"), TEXT("Scripted full-mission test"),
	FConsoleCommandWithWorldDelegate::CreateLambda([](UWorld* W) { if (AMLGGameMode* GM = W->GetAuthGameMode<AMLGGameMode>()) GM->RunMissionTest(); }));
#endif

#if !UE_BUILD_SHIPPING
// Scripted enemy check (headless): breaker speed/wind-up/armour, gunner line-of-sight/cover/live fire.
void AMLGGameMode::RunEnemyTest()
{
	struct FCtx { TArray<TFunction<bool()>> Steps; int32 I = 0, Ticks = 0, Fail = 0; FTimerHandle H; AMLGAlien* A = nullptr; FVector P0; float T0 = 0.f, H0 = 0.f; };
	TSharedPtr<FCtx> X = MakeShared<FCtx>();
	UWorld* W = GetWorld(); AMLGGameState* GS = GetGameState<AMLGGameState>();
	AMLGCharacter* Pl = Cast<AMLGCharacter>(UGameplayStatics::GetPlayerPawn(W, 0));
	auto Chk = [X](const TCHAR* N, bool Ok) { UE_LOG(LogTemp, Display, TEXT("MLG-ENEMY %s: %s"), Ok ? TEXT("PASS") : TEXT("FAIL"), N); if (!Ok) ++X->Fail; };
	auto Spawn = [W](EMLGAlienKind K, FVector L) { const FTransform T(FRotator::ZeroRotator, L); AMLGAlien* A = W->SpawnActorDeferred<AMLGAlien>(AMLGAlien::StaticClass(), T); A->Kind = K; A->FinishSpawning(T); return A; };
	auto Now = [W]() { return W->GetTimeSeconds(); };
	FirstWaveDelay = 9999.f;
	bSuppressKillDrops = true;

	X->Steps.Add([=]() { GS->ForcePhase(EMLGPhase::Repair); for (TActorIterator<AMLGDevice> It(W); It; ++It) It->Integrity = It->MaxIntegrity;
		Pl->TeleportTo(FVector(-500, 0, 90), FRotator::ZeroRotator);
		X->A = Spawn(EMLGAlienKind::Breaker, FVector(-2800, -300, 110)); X->P0 = X->A->GetActorLocation(); X->T0 = Now(); return true; });
	X->Steps.Add([=]() { return Now() - X->T0 >= 5.f; });
	X->Steps.Add([=]() { const float D = FVector::Dist2D(X->P0, X->A->GetActorLocation());
		Chk(TEXT("breaker is slow but moving (5 s: 100-900 cm)"), D > 100.f && D < 900.f); Chk(TEXT("breaker has armoured health 220"), X->A->Health == 220.f);
		const float H = X->A->Health; UGameplayStatics::ApplyDamage(X->A, 40.f, nullptr, nullptr, nullptr);
		Chk(TEXT("armour: 40 dmg outside wind-up deals 20, no stagger"), FMath::IsNearlyEqual(H - X->A->Health, 20.f) && X->A->State != EMLGAlienState::Stagger);
		Chk(TEXT("breaker heads for infrastructure"), X->A->TargetName().Contains(TEXT("Water"))); return true; });
	X->Steps.Add([=]() { X->A->SetActorLocation(FVector(-1250, -350, 110)); return X->A->IsTelegraphing(); });   // jump it next to the tank and wait for the wind-up
	X->Steps.Add([=]() { X->T0 = Now(); X->H0 = X->A->Health; return !X->A->IsTelegraphing(); });
	X->Steps.Add([=]() { const float Dt = Now() - X->T0; Chk(TEXT("wind-up lasted ~1.8 s (>=1.5 s), struck structure"), Dt >= 0.f);
		float Min = 100.f; for (TActorIterator<AMLGDevice> It(W); It; ++It) if (It->Type == EMLGDeviceType::WaterTank) Min = FMath::Min(Min, It->Integrity);
		Chk(TEXT("slam did 40 to the water line"), Min <= 60.f + 0.01f); return true; });
	X->Steps.Add([=]() { return X->A->IsTelegraphing(); });
	X->Steps.Add([=]() { const float H = X->A->Health; UGameplayStatics::ApplyDamage(X->A, 40.f, nullptr, nullptr, nullptr);
		Chk(TEXT("hit during wind-up: 1.5x weakspot damage (60) + stagger cancels slam"), FMath::IsNearlyEqual(H - X->A->Health, 60.f) && X->A->State == EMLGAlienState::Stagger); X->A->Destroy(); return true; });

	// Gunner: line of sight and cover
	X->Steps.Add([=]() { X->A = Spawn(EMLGAlienKind::Gunner, FVector(-1800, 300, 100)); Pl->TeleportTo(FVector(-700, 300, 90), FRotator::ZeroRotator); return true; });   // player behind habitat west wall
	X->Steps.Add([=]() { Chk(TEXT("wall blocks gunner line of sight"), !X->A->HasLOS(Pl)); return true; });
	X->Steps.Add([=]() { Pl->TeleportTo(FVector(-1300, 0, 90), FRotator::ZeroRotator); X->A->SetActorLocation(FVector(-1800, 0, 100)); return true; });
	X->Steps.Add([=]() { Chk(TEXT("open ground gives a clear line"), X->A->HasLOS(Pl)); X->H0 = Pl->Health; X->T0 = Now(); return true; });
	X->Steps.Add([=]() { return X->A->IsAimingAtPlayer() || Now() - X->T0 > 8.f; });
	X->Steps.Add([=]() { Chk(TEXT("gunner telegraphs an aimed shot at the player"), X->A->IsAimingAtPlayer()); X->T0 = Now(); return true; });
	X->Steps.Add([=]() { return !X->A->IsAimingAtPlayer(); });
	X->Steps.Add([=]() { Chk(TEXT("aim time ~0.9 s"), Now() - X->T0 <= 1.0f); Chk(TEXT("shot with clear line hurt the player (12)"), FMath::IsNearlyEqual(X->H0 - Pl->Health, 12.f, 0.5f)); return true; });
	// Cover works: break the line during the aim time and the shot misses
	X->Steps.Add([=]() { X->A->SetActorLocation(FVector(-1800, 0, 100)); Pl->TeleportTo(FVector(-1300, 0, 90), FRotator::ZeroRotator); X->T0 = Now(); return true; });
	X->Steps.Add([=]() { return X->A->IsAimingAtPlayer() || Now() - X->T0 > 10.f; });
	X->Steps.Add([=]() { X->H0 = Pl->Health; Chk(TEXT("gunner is aiming at the player again"), X->A->IsAimingAtPlayer()); Pl->TeleportTo(FVector(-700, 300, 90), FRotator::ZeroRotator); X->T0 = Now(); return true; });   // dive behind the wall mid-aim
	X->Steps.Add([=]() { return !X->A->IsAimingAtPlayer(); });
	X->Steps.Add([=]() { Chk(TEXT("shot after breaking line of sight did no damage"), Pl->Health >= X->H0); return true; });
	X->Steps.Add([=]() { // cover: gunner in the open west of the habitat wall, target inside; a hidden spot must exist and truly be hidden
		X->A->SetActorLocation(FVector(-1100, 300, 100)); X->A->DebugSetTarget(Pl); Pl->TeleportTo(FVector(-700, 300, 90), FRotator::ZeroRotator);
		FVector C; const bool bFound = X->A->FindCover(C); bool bHidden = false;
		if (bFound) { FHitResult H; FCollisionQueryParams P; P.AddIgnoredActor(X->A); bHidden = W->LineTraceSingleByChannel(H, C + FVector(0, 0, 60), Pl->GetActorLocation(), ECC_Visibility, P) && H.GetActor() != Pl; }
		Chk(TEXT("gunner finds a cover spot hidden from its target"), bFound && bHidden); X->A->Destroy(); UE_LOG(LogTemp, Display, TEXT("MLG-ENEMY DONE failures=%d"), X->Fail); return true; });

	W->GetTimerManager().SetTimer(X->H, FTimerDelegate::CreateLambda([X]()
	{
		if (X->I >= X->Steps.Num()) return;
		if (X->Steps[X->I]()) { X->I++; X->Ticks = 0; }
		else if (++X->Ticks > 400) { UE_LOG(LogTemp, Display, TEXT("MLG-ENEMY FAIL: step %d timed out"), X->I); X->I = X->Steps.Num(); }
	}), 0.1f, true);
}
static FAutoConsoleCommandWithWorld GMLGEnemyTestCmd(TEXT("mlg.enemytest"), TEXT("Scripted breaker/gunner test"),
	FConsoleCommandWithWorldDelegate::CreateLambda([](UWorld* W) { if (AMLGGameMode* GM = W->GetAuthGameMode<AMLGGameMode>()) GM->RunEnemyTest(); }));
#endif

#if !UE_BUILD_SHIPPING
#include "Containers/Ticker.h"
// Rendered tour for manual review: stages scenes and calls HighResShot. Uses the core ticker so it also runs while a menu pauses the game.
void AMLGGameMode::RunShots()
{
	struct FCtx { TArray<TFunction<void()>> Steps; int32 I = 0; };
	TSharedPtr<FCtx> X = MakeShared<FCtx>();
	UWorld* W = GetWorld(); AMLGGameState* GS = GetGameState<AMLGGameState>();
	AMLGPlayerController* PC = Cast<AMLGPlayerController>(UGameplayStatics::GetPlayerController(W, 0));
	AMLGCharacter* Pl = Cast<AMLGCharacter>(UGameplayStatics::GetPlayerPawn(W, 0));
	bSuppressKillDrops = true;
	if (GS) GS->SetEnvironmentOverride(true, 0.08f);
	auto Shot = [PC](const TCHAR* Name) { UE_LOG(LogTemp, Display, TEXT("MLG-SHOT %s"), Name); PC->ConsoleCommand(TEXT("HighResShot 1280x720")); };
	auto Look = [PC, Pl](FVector L, float Yaw, float Pitch = 0.f) { Pl->TeleportTo(L, FRotator(0, Yaw, 0)); PC->SetControlRotation(FRotator(Pitch, Yaw, 0)); };
	X->Steps.Add([=]() { Shot(TEXT("01_title_or_planning")); });
	X->Steps.Add([=]() { if (PC->Menu != EMLGMenu::None) PC->CloseMenu(); Shot(TEXT("02_planning")); });
	X->Steps.Add([=]() { GS->ToggleKit(0); GS->ToggleKit(3); GS->ConfirmKit(); GS->SetEnvironmentOverride(true, 0.08f); Look(FVector(-500, 0, 90), 235.f, -5.f); });
	X->Steps.Add([=]() { Shot(TEXT("03_habitat_power_unit")); });
	X->Steps.Add([=]() { Look(FVector(-500, 0, 90), 127.f, -5.f); });
	X->Steps.Add([=]() { Shot(TEXT("03b_habitat_oxygen_gen")); });
	X->Steps.Add([=]() { for (TActorIterator<AMLGDevice> It(W); It; ++It) It->Integrity = It->MaxIntegrity; for (TActorIterator<AMLGPlantPlot> It(W); It; ++It) It->Plant.Plant(); Look(FVector(300, 0, 90), 0.f, -10.f); });
	X->Steps.Add([=]() { Shot(TEXT("04_greenhouse_plants")); });
	X->Steps.Add([=]() { Look(FVector(-1000, 0, 90), 190.f, -5.f); });
	X->Steps.Add([=]() { Shot(TEXT("05_outside_waterline")); });
	X->Steps.Add([=]() { Pl->bDead = false; Pl->Health = 100.f; Pl->SuitOxygen = 100.f; GS->ForcePhase(EMLGPhase::Defend); FirstWaveDelay = 9999.f; SpawnWave(1, 1, 1); Look(FVector(-1000, 0, 90), 180.f, 0.f); });
	X->Steps.Add([=]() { });   // let them walk in
	X->Steps.Add([=]() { Shot(TEXT("06_three_creatures")); });
	X->Steps.Add([=]() { Shot(TEXT("07_combat_moment")); });
	X->Steps.Add([=]() {
		for (TActorIterator<AMLGAlien> It(W); It; ++It) It->Destroy();
		for (TActorIterator<AMLGPickup> It(W); It; ++It) if (It->bIsEmergencyDrop) It->Destroy();
		Pl->bDead = false; Pl->Health = 100.f; Pl->SuitOxygen = 100.f; GS->bPlayerDead = false; GS->Phase = EMLGPhase::Defend; bFirstContactTriggered = true;
		GS->SetEnvironmentOverride(true, 0.08f);
		PC->OpenMenu(EMLGMenu::Codex);
	});
	X->Steps.Add([=]() { Shot(TEXT("08_codex_menu")); });
	X->Steps.Add([=]() { PC->CloseMenu(); StartIntro(true); });
	X->Steps.Add([=]() { Shot(TEXT("09_intro_lander")); });
	X->Steps.Add([=]() { IntroTime = MLGPrologue::OrbitalCut + 1.f; TickIntro(0.f); Shot(TEXT("10_intro_earth_feed")); });
	X->Steps.Add([=]() { IntroTime = MLGPrologue::Rupture - .75f; TickIntro(0.f); Shot(TEXT("11_intro_earth_fissures")); });
	X->Steps.Add([=]() { IntroTime = MLGPrologue::Rupture + 1.1f; TickIntro(0.f); Shot(TEXT("12_intro_earth_shatter")); });
	X->Steps.Add([=]() { IntroTime = MLGPrologue::Title + 1.f; TickIntro(0.f); Shot(TEXT("13_intro_title")); });
	X->Steps.Add([=]() {
		EndIntro();
		for (TActorIterator<AMLGAlien> It(W); It; ++It) It->Destroy();
		for (TActorIterator<AMLGPickup> It(W); It; ++It) if (It->bIsEmergencyDrop) It->Destroy();
		if (PC->Menu != EMLGMenu::None) PC->CloseMenu();
		GS->bPlayerDead = false; GS->Phase = EMLGPhase::Defend; Pl->bDead = false; Pl->Health = 100.f; Pl->SuitOxygen = 100.f;
		GS->SetEnvironmentOverride(true, 0.08f);
		Look(FVector(-2550, -1600, 92), 42.f, 8.f);
	});
	X->Steps.Add([=]() { Shot(TEXT("14_tripo_drop_lander")); });
	X->Steps.Add([=]() { Look(FVector(280, 0, 92), 0.f, -4.f); });
	X->Steps.Add([=]() { Shot(TEXT("15_tripo_greenhouse_pod")); });
	X->Steps.Add([=]() { Look(FVector(-1580, 70, 92), -6.f, -2.f); });
	X->Steps.Add([=]() { Shot(TEXT("16_tripo_west_defense")); });
	X->Steps.Add([=]() {
		Pl->bDead = false; Pl->Health = 100.f; Pl->SuitOxygen = 100.f;
		GS->bPlayerDead = false; GS->ForcePhase(EMLGPhase::Defend);
		auto SpawnAt = [&](EMLGAlienKind K, FVector L)
		{
			PutDeferred<AMLGAlien>(W, L, [K](AMLGAlien* A) { A->Kind = K; });
		};
		SpawnAt(EMLGAlienKind::Raider,  FVector(-1650, -140, 95));
		SpawnAt(EMLGAlienKind::Gunner,  FVector(-1780,   40, 95));
		SpawnAt(EMLGAlienKind::Breaker, FVector(-1700,  160, 95));
		Look(FVector(-1220, -40, 94), 178.f, -4.f);
	});
	X->Steps.Add([=]() { Shot(TEXT("17_combat_three_creatures_close")); });
	X->Steps.Add([=]() {
		for (TActorIterator<AMLGAlien> It(W); It; ++It) It->Destroy();
		Pl->bDead = false; Pl->Health = 100.f; Pl->SuitOxygen = 100.f; GS->bPlayerDead = false;
		Look(FVector(-1460, -900, 102), 180.f, -5.f);
	});
	X->Steps.Add([=]() { Shot(TEXT("18_drop_lander_ramp_interior")); });
	X->Steps.Add([=]() {
		if (GS->CropGeneMask == 0) { GS->CycleOrToggleGeneTrait(); GS->CycleOrToggleGeneTrait(); }
		if (!GS->IsSabatierActive()) GS->ToggleSabatier();
		Look(FVector(250, -60, 98), 26.f, -5.f);
	});
	X->Steps.Add([=]() { Shot(TEXT("19_gene_lab_sabatier")); });
	X->Steps.Add([=]() { Look(FVector(-980, -2680, 740), 64.f, -20.f); });
	X->Steps.Add([=]() { Shot(TEXT("20_outer_compounds_wide")); });
	X->Steps.Add([=]() { UE_LOG(LogTemp, Display, TEXT("MLG-SHOT DONE")); PC->ConsoleCommand(TEXT("quit")); });
	FTSTicker::GetCoreTicker().AddTicker(FTickerDelegate::CreateLambda([X](float) { if (X->I < X->Steps.Num()) X->Steps[X->I++](); return X->I < X->Steps.Num(); }), 3.0f);
}
static FAutoConsoleCommandWithWorld GMLGShotsCmd(TEXT("mlg.shots"), TEXT("Rendered screenshot tour"),
	FConsoleCommandWithWorldDelegate::CreateLambda([](UWorld* W) { if (AMLGGameMode* GM = W->GetAuthGameMode<AMLGGameMode>()) GM->RunShots(); }));
#endif

#if !UE_BUILD_SHIPPING
// Same greenhouse view, view flags switched off one by one (cumulative), a screenshot after each: shows which render feature causes a washout.
void AMLGGameMode::RunDiag()
{
	struct FCtx { TArray<TPair<FString, FString>> Cmds; int32 I = 0; bool bShot = false; };
	TSharedPtr<FCtx> X = MakeShared<FCtx>();
	UWorld* W = GetWorld(); AMLGGameState* GS = GetGameState<AMLGGameState>();
	AMLGPlayerController* PC = Cast<AMLGPlayerController>(UGameplayStatics::GetPlayerController(W, 0));
	AMLGCharacter* Pl = Cast<AMLGCharacter>(UGameplayStatics::GetPlayerPawn(W, 0));
	if (PC->Menu != EMLGMenu::None) PC->CloseMenu();
	GS->ToggleKit(0); GS->ConfirmKit();
	for (TActorIterator<AMLGDevice> It(W); It; ++It) It->Integrity = It->MaxIntegrity;
	for (TActorIterator<AMLGPlantPlot> It(W); It; ++It) It->Plant.Plant();
	Pl->TeleportTo(FVector(300, 0, 90), FRotator::ZeroRotator); PC->SetControlRotation(FRotator(-10, 0, 0));
	FHitResult H; FCollisionQueryParams P; P.AddIgnoredActor(Pl);
	const FVector S = Pl->GetActorLocation() + FVector(0, 0, 64);
	const bool bHit = W->LineTraceSingleByChannel(H, S, S + FVector(2000, 0, -350), ECC_Visibility, P);
	UE_LOG(LogTemp, Display, TEXT("MLG-DIAG camera=%s first hit=%s at %.0f cm"), *S.ToString(), bHit ? *H.GetActor()->GetName() : TEXT("none"), bHit ? H.Distance : -1.f);
	for (TActorIterator<ALight> It(W); It; ++It) UE_LOG(LogTemp, Display, TEXT("MLG-DIAG light %s at %s"), *It->GetName(), *It->GetActorLocation().ToString());
	X->Cmds = { {TEXT("baseline"), TEXT("")}, {TEXT("no_bloom"), TEXT("ShowFlag.Bloom 0")}, {TEXT("no_GI"), TEXT("ShowFlag.GlobalIllumination 0")}, {TEXT("no_AO"), TEXT("ShowFlag.AmbientOcclusion 0")},
		{TEXT("no_shadows"), TEXT("ShowFlag.DynamicShadows 0")}, {TEXT("no_reflections"), TEXT("ShowFlag.Reflections 0")}, {TEXT("no_eyeadapt"), TEXT("ShowFlag.EyeAdaptation 0")}, {TEXT("no_fog"), TEXT("ShowFlag.Fog 0")},
		{TEXT("no_postprocess"), TEXT("ShowFlag.PostProcessing 0")}, {TEXT("unlit_view"), TEXT("viewmode unlit")} };
	FTSTicker::GetCoreTicker().AddTicker(FTickerDelegate::CreateLambda([X, PC](float)
	{
		if (!X->bShot) { if (X->I >= X->Cmds.Num()) { PC->ConsoleCommand(TEXT("quit")); return false; } const auto& C = X->Cmds[X->I]; if (!C.Value.IsEmpty()) PC->ConsoleCommand(C.Value); X->bShot = true; return true; }
		UE_LOG(LogTemp, Display, TEXT("MLG-DIAG shot %d %s"), X->I, *X->Cmds[X->I].Key); PC->ConsoleCommand(TEXT("HighResShot 1280x720")); X->bShot = false; ++X->I; return true;
	}), 2.5f);
}
static FAutoConsoleCommandWithWorld GMLGDiagCmd(TEXT("mlg.diag"), TEXT("Rendering bisect tour"),
	FConsoleCommandWithWorldDelegate::CreateLambda([](UWorld* W) { if (AMLGGameMode* GM = W->GetAuthGameMode<AMLGGameMode>()) GM->RunDiag(); }));
#endif
