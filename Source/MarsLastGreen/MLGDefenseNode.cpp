#include "MLGDefenseNode.h"
#include "MLGAlien.h"
#include "MLGAssets.h"
#include "MLGCharacter.h"
#include "MLGGameState.h"
#include "Components/PointLightComponent.h"
#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "EngineUtils.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "UObject/ConstructorHelpers.h"

AMLGDefenseNode::AMLGDefenseNode()
{
	PrimaryActorTick.bCanEverTick = true;

	static ConstructorHelpers::FObjectFinder<UStaticMesh> Cube(TEXT("/Engine/BasicShapes/Cube.Cube"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> Cylinder(TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> Sphere(TEXT("/Engine/BasicShapes/Sphere.Sphere"));

	Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	RootComponent = Root;

	BasePad = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("BasePad"));
	BasePad->SetupAttachment(Root);
	if (Cube.Succeeded()) BasePad->SetStaticMesh(Cube.Object);
	BasePad->SetRelativeLocation(FVector(0.f, 0.f, 7.f));
	BasePad->SetRelativeScale3D(FVector(1.4f, 1.4f, 0.14f));
	BasePad->SetCollisionProfileName(TEXT("BlockAll"));

	StructureMesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("StructureMesh"));
	StructureMesh->SetupAttachment(Root);
	if (Cylinder.Succeeded()) StructureMesh->SetStaticMesh(Cylinder.Object);
	StructureMesh->SetRelativeLocation(FVector(0.f, 0.f, 45.f));
	StructureMesh->SetRelativeScale3D(FVector(0.55f, 0.55f, 0.75f));
	StructureMesh->SetCollisionProfileName(TEXT("NoCollision"));
	StructureMesh->SetVisibility(false);

	TurretPivot = CreateDefaultSubobject<USceneComponent>(TEXT("TurretPivot"));
	TurretPivot->SetupAttachment(Root);
	TurretPivot->SetRelativeLocation(FVector(0.f, 0.f, 92.f));

	TurretHead = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("TurretHead"));
	TurretHead->SetupAttachment(TurretPivot);
	if (Cube.Succeeded()) TurretHead->SetStaticMesh(Cube.Object);
	TurretHead->SetRelativeScale3D(FVector(0.55f, 0.36f, 0.28f));
	TurretHead->SetCollisionProfileName(TEXT("NoCollision"));
	TurretHead->SetVisibility(false);

	TurretBarrel = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("TurretBarrel"));
	TurretBarrel->SetupAttachment(TurretPivot);
	if (Cylinder.Succeeded()) TurretBarrel->SetStaticMesh(Cylinder.Object);
	TurretBarrel->SetRelativeLocation(FVector(46.f, 0.f, 0.f));
	TurretBarrel->SetRelativeRotation(FRotator(90.f, 0.f, 0.f));
	TurretBarrel->SetRelativeScale3D(FVector(0.08f, 0.08f, 0.55f));
	TurretBarrel->SetCollisionProfileName(TEXT("NoCollision"));
	TurretBarrel->SetVisibility(false);

	StatusBeacon = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("StatusBeacon"));
	StatusBeacon->SetupAttachment(Root);
	if (Sphere.Succeeded()) StatusBeacon->SetStaticMesh(Sphere.Object);
	StatusBeacon->SetRelativeLocation(FVector(55.f, 55.f, 18.f));
	StatusBeacon->SetRelativeScale3D(FVector(0.16f, 0.16f, 0.16f));
	StatusBeacon->SetCollisionProfileName(TEXT("NoCollision"));

	TracerBeam = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("TracerBeam"));
	TracerBeam->SetupAttachment(Root);
	if (Cylinder.Succeeded()) TracerBeam->SetStaticMesh(Cylinder.Object);
	TracerBeam->SetUsingAbsoluteLocation(true);
	TracerBeam->SetUsingAbsoluteRotation(true);
	TracerBeam->SetUsingAbsoluteScale(true);
	TracerBeam->SetCollisionProfileName(TEXT("NoCollision"));
	TracerBeam->SetCastShadow(false);
	TracerBeam->SetVisibility(false);

	MuzzleLight = CreateDefaultSubobject<UPointLightComponent>(TEXT("MuzzleLight"));
	MuzzleLight->SetupAttachment(TurretPivot);
	MuzzleLight->SetRelativeLocation(FVector(70.f, 0.f, 0.f));
	MuzzleLight->SetIntensity(7000.f);
	MuzzleLight->SetAttenuationRadius(650.f);
	MuzzleLight->SetLightColor(FColor(120, 220, 255));
	MuzzleLight->SetCastShadows(false);
	MuzzleLight->SetVisibility(false);

	DisplayName = FText::FromString(TEXT("Defense pad"));
}

void AMLGDefenseNode::GetMeshPathsFor(EMLGDefenseKind InKind, const TCHAR*& OutStructurePath, const TCHAR*& OutHeadPath)
{
	if (InKind == EMLGDefenseKind::ShockBarrier)
	{
		OutStructurePath = TEXT("/Game/Environment/SM_Defense_Barrier");
		OutHeadPath = nullptr;
	}
	else
	{
		OutStructurePath = TEXT("/Game/Environment/SM_Defense_TurretBase");
		OutHeadPath = TEXT("/Game/Environment/SM_Defense_TurretHead");
	}
}

void AMLGDefenseNode::BeginPlay()
{
	Super::BeginPlay();
	if (Kind == EMLGDefenseKind::ShockBarrier)
	{
		MaxIntegrity = 180.f;
		BuildPartsCost = 1;
		Range = 450.f;
		DamagePerShot = 10.f;
		FireInterval = 2.0f;
	}
	else
	{
		MaxIntegrity = 100.f;
		BuildPartsCost = 2;
		Range = 1600.f;
		DamagePerShot = 14.f;
		FireInterval = 1.2f;
	}

	const TCHAR* StructPath = nullptr;
	const TCHAR* HeadPath = nullptr;
	GetMeshPathsFor(Kind, StructPath, HeadPath);

	if (UStaticMesh* CustomStruct = MLGAssets::LoadOptional<UStaticMesh>(StructPath))
	{
		bCustomStructure = true;
		StructureMesh->SetStaticMesh(CustomStruct);
		const FBoxSphereBounds B = CustomStruct->GetBounds();
		const FVector TargetBox = Kind == EMLGDefenseKind::ShockBarrier ? FVector(165.f, 165.f, 120.f) : FVector(95.f, 95.f, 76.f);
		const float S = MLGAssets::FitUniformScale(B.BoxExtent * 2.f, TargetBox);
		const float BottomZ = B.Origin.Z - B.BoxExtent.Z;
		StructureMesh->SetRelativeScale3D(FVector(S));
		StructureMesh->SetRelativeRotation(Kind == EMLGDefenseKind::ShockBarrier ? FRotator(0.f, 90.f, 0.f) : FRotator::ZeroRotator);
		StructureMesh->SetRelativeLocation(FVector(0.f, 0.f, 14.f - BottomZ * S));

		if (Kind == EMLGDefenseKind::SentryTurret)
		{
			const float TopZ = 14.f + (B.BoxExtent.Z * 2.f) * S;
			TurretPivot->SetRelativeLocation(FVector(0.f, 0.f, TopZ));
		}
		MLGAssets::EnsureEmissiveMIDs(StructureMesh, StructureSlotMIDs, StructureIsAccent);
	}
	else
	{
		StructureMID = MLGAssets::EnsureColorMID(StructureMesh, 0);
	}

	if (HeadPath)
	{
		if (UStaticMesh* CustomHead = MLGAssets::LoadOptional<UStaticMesh>(HeadPath))
		{
			bCustomTurretHead = true;
			TurretHead->SetStaticMesh(CustomHead);
			const FBoxSphereBounds HB = CustomHead->GetBounds();
			const float HS = MLGAssets::FitUniformScale(HB.BoxExtent * 2.f, FVector(80.f, 48.f, 44.f));
			const float HeadBottomZ = HB.Origin.Z - HB.BoxExtent.Z;
			TurretHead->SetRelativeScale3D(FVector(HS));
			HeadBaseRelLoc = FVector(0.f, 0.f, -HeadBottomZ * HS);
			TurretHead->SetRelativeLocation(HeadBaseRelLoc);
			TurretMuzzleForward = (HB.Origin.X + HB.BoxExtent.X) * HS + 6.f;
			TurretMuzzleZOffset = HB.Origin.Z * HS;
			MuzzleLight->SetRelativeLocation(FVector(TurretMuzzleForward + 8.f, 0.f, TurretMuzzleZOffset));
			MLGAssets::EnsureEmissiveMIDs(TurretHead, HeadSlotMIDs, HeadIsAccent);
		}
		else if (UMaterialInstanceDynamic* HeadMID = MLGAssets::EnsureColorMID(TurretHead, 0))
		{
			HeadBaseRelLoc = FVector::ZeroVector;
			HeadMID->SetVectorParameterValue(TEXT("Color"), FLinearColor(0.32f, 0.36f, 0.42f));
		}
	}
	IdleSweepPhase = FMath::FRandRange(0.f, 6.283185f);

	if (UMaterialInstanceDynamic* PadMID = MLGAssets::EnsureColorMID(BasePad, 0))
	{
		PadMID->SetVectorParameterValue(TEXT("Color"), FLinearColor(0.20f, 0.22f, 0.26f));
	}
	BeaconMID = MLGAssets::EnsureColorMID(StatusBeacon, 0);
	TracerMID = MLGAssets::EnsureColorMID(TracerBeam, 0);
	if (UMaterialInstanceDynamic* BarrelMID = MLGAssets::EnsureColorMID(TurretBarrel, 0))
	{
		BarrelMID->SetVectorParameterValue(TEXT("Color"), FLinearColor(0.15f, 0.16f, 0.2f));
	}
	RefreshVisuals();
}

void AMLGDefenseNode::ApplySavedState(EMLGDefenseState InState, float InIntegrity)
{
	DefenseState = InState;
	Integrity = FMath::Clamp(InIntegrity, 0.f, MaxIntegrity);
	if (DefenseState != EMLGDefenseState::Empty && Integrity <= 0.f) DefenseState = EMLGDefenseState::Broken;
	LastVisualState = (EMLGDefenseState)255;
	RefreshVisuals();
}

void AMLGDefenseNode::RefreshVisuals()
{
	const AMLGGameState* GS = GetWorld() ? GetWorld()->GetGameState<AMLGGameState>() : nullptr;
	const bool bPowered = !GS || GS->Sim.HasPower();
	const bool bBuilt = DefenseState != EMLGDefenseState::Empty;
	const bool bIsSentry = Kind == EMLGDefenseKind::SentryTurret;

	StructureMesh->SetVisibility(bBuilt);
	StructureMesh->SetCollisionProfileName(bBuilt ? TEXT("BlockAll") : TEXT("NoCollision"));
	TurretHead->SetVisibility(bBuilt && bIsSentry);
	TurretBarrel->SetVisibility(bBuilt && bIsSentry && !bCustomTurretHead);
	if (!bCustomStructure)
	{
		StructureMesh->SetRelativeScale3D(bIsSentry ? FVector(0.55f, 0.55f, 0.75f) : FVector(0.95f, 0.95f, 1.15f));
		StructureMesh->SetRelativeLocation(bIsSentry ? FVector(0.f, 0.f, 45.f) : FVector(0.f, 0.f, 65.f));
	}

	const FLinearColor AccentCol = DefenseState == EMLGDefenseState::Broken ? FLinearColor(0.95f, 0.1f, 0.08f)
		: DefenseState == EMLGDefenseState::Standby ? FLinearColor(0.2f, 0.5f, 0.95f)
		: (bIsSentry && !bPowered) ? FLinearColor(0.9f, 0.5f, 0.05f)
		: FLinearColor(0.1f, 0.85f, 0.35f);

	if (bCustomStructure)
	{
		const FLinearColor BodyEmissive = DefenseState == EMLGDefenseState::Broken ? FLinearColor(0.22f, 0.03f, 0.02f) : AccentCol * 0.07f;
		MLGAssets::ApplyEmissiveTint(StructureSlotMIDs, StructureIsAccent, BodyEmissive, AccentCol * 1.4f);
	}
	else if (StructureMID)
	{
		const FLinearColor StructCol = DefenseState == EMLGDefenseState::Broken
			? FLinearColor(0.25f, 0.12f, 0.1f)
			: (bIsSentry ? FLinearColor(0.26f, 0.32f, 0.38f) : FLinearColor(0.22f, 0.38f, 0.55f));
		StructureMID->SetVectorParameterValue(TEXT("Color"), StructCol);
	}
	if (bCustomTurretHead)
	{
		MLGAssets::ApplyEmissiveTint(HeadSlotMIDs, HeadIsAccent, AccentCol * 0.06f, AccentCol * 1.5f);
	}

	if (BeaconMID)
	{
		FLinearColor Col(0.15f, 0.55f, 0.85f); // Empty buildable pad
		if (DefenseState == EMLGDefenseState::Broken) Col = FLinearColor(0.95f, 0.1f, 0.08f);
		else if (DefenseState == EMLGDefenseState::Standby) Col = FLinearColor(0.2f, 0.5f, 0.95f);
		else if (DefenseState == EMLGDefenseState::Active)
		{
			Col = (bIsSentry && !bPowered) ? FLinearColor(0.9f, 0.5f, 0.05f)
				: (Integrity < MaxIntegrity * 0.6f ? FLinearColor(0.9f, 0.65f, 0.1f) : FLinearColor(0.1f, 0.85f, 0.35f));
		}
		BeaconMID->SetVectorParameterValue(TEXT("Color"), Col);
	}
	LastVisualState = DefenseState;
	bLastPowered = bPowered;
}

void AMLGDefenseNode::Tick(float Dt)
{
	Super::Tick(Dt);

	if (FlashTimer > 0.f)
	{
		FlashTimer -= Dt;
		if (FlashTimer <= 0.f)
		{
			TracerBeam->SetVisibility(false);
			MuzzleLight->SetVisibility(false);
		}
	}

	const AMLGGameState* GS = GetWorld()->GetGameState<AMLGGameState>();
	const bool bPowered = !GS || GS->Sim.HasPower();
	if (DefenseState != LastVisualState || bPowered != bLastPowered)
	{
		RefreshVisuals();
	}

	if (DefenseState != EMLGDefenseState::Active || Integrity <= 0.f) return;
	if (GS && (GS->Phase == EMLGPhase::Planning || GS->Phase == EMLGPhase::Won || GS->Phase == EMLGPhase::Lost)) return;

	if (Kind == EMLGDefenseKind::SentryTurret) TickSentry(Dt);
	else TickShockBarrier(Dt);
}

bool AMLGDefenseNode::HasLineOfSight(const AMLGAlien* Alien) const
{
	if (!Alien) return false;
	FHitResult Hit;
	FCollisionQueryParams Params(SCENE_QUERY_STAT(MLGTurretLOS), false, this);
	const FVector Start = TurretPivot->GetComponentLocation();
	const FVector End = Alien->GetActorLocation() + FVector(0.f, 0.f, 35.f);
	return !GetWorld()->LineTraceSingleByChannel(Hit, Start, End, ECC_Visibility, Params) || Hit.GetActor() == Alien;
}

void AMLGDefenseNode::TickSentry(float Dt)
{
	const AMLGGameState* GS = GetWorld()->GetGameState<AMLGGameState>();
	if (GS && !GS->Sim.HasPower())
	{
		CurrentTarget.Reset();
		return;
	}

	FireCooldown = FMath::Max(0.f, FireCooldown - Dt);
	LockSoundCooldown = FMath::Max(0.f, LockSoundCooldown - Dt);
	RecoilOffset = FMath::FInterpTo(RecoilOffset, 0.f, Dt, 22.f);
	TurretHead->SetRelativeLocation(HeadBaseRelLoc + FVector(RecoilOffset, 0.f, 0.f));
	if (!bCustomTurretHead)
	{
		TurretBarrel->SetRelativeLocation(FVector(46.f + RecoilOffset, 0.f, 0.f));
	}

	AMLGAlien* BestTarget = nullptr;
	float BestDist = Range;
	for (TActorIterator<AMLGAlien> It(GetWorld()); It; ++It)
	{
		if (!It->IsAlive()) continue;
		const float D = FVector::Dist(GetActorLocation(), It->GetActorLocation());
		if (D <= BestDist && HasLineOfSight(*It))
		{
			BestDist = D;
			BestTarget = *It;
		}
	}
	const FVector MuzzleOrigin = TurretPivot->GetComponentLocation();
	if (!BestTarget)
	{
		CurrentTarget.Reset();
		IdleSweepPhase += Dt * 1.15f;
		const FRotator IdleRot(0.f, GetActorRotation().Yaw + FMath::Sin(IdleSweepPhase) * 38.f, 0.f);
		TurretPivot->SetWorldRotation(FMath::RInterpTo(TurretPivot->GetComponentRotation(), IdleRot, Dt, 4.f));
		return;
	}

	if (CurrentTarget.Get() != BestTarget)
	{
		CurrentTarget = BestTarget;
		if (LockSoundCooldown <= 0.f)
		{
			LockSoundCooldown = 1.1f;
			MLGAssets::PlaySoundAtLocation(this, MLGAssets::Audio::HitMarker, MuzzleOrigin, 0.55f, 1.55f);
		}
	}

	const FVector AimAt = BestTarget->GetActorLocation() + FVector(0.f, 0.f, 35.f);
	const FVector AimDir = (AimAt - MuzzleOrigin).GetSafeNormal();
	const FRotator DesiredRot = AimDir.Rotation();
	TurretPivot->SetWorldRotation(FMath::RInterpTo(TurretPivot->GetComponentRotation(), DesiredRot, Dt, 18.f));

	const bool bOverclocked = GS && GS->IsTurretOverclocked();
	const float AlignDot = FVector::DotProduct(TurretPivot->GetForwardVector(), AimDir);
	if (FireCooldown > 0.f || AlignDot < 0.965f) return;
	FireCooldown = FireInterval * (bOverclocked ? 0.6f : 1.f);
	RecoilOffset = -7.f;

	FHitResult ShotHit;
	ShotHit.ImpactPoint = AimAt;
	ShotHit.Location = AimAt;
	ShotHit.ImpactNormal = -AimDir;
	UGameplayStatics::ApplyPointDamage(BestTarget, DamagePerShot, AimDir, ShotHit, nullptr, this, nullptr);
	if (BestTarget->IsAlive())
	{
		const float KnockHoriz = BestTarget->Kind == EMLGAlienKind::Breaker ? 95.f : 280.f;
		const float KnockUp = BestTarget->Kind == EMLGAlienKind::Breaker ? 0.f : 70.f;
		const FVector KnockVel = AimDir.GetSafeNormal2D() * KnockHoriz + FVector(0.f, 0.f, KnockUp);
		BestTarget->LaunchCharacter(KnockVel, false, false);
	}

	const FVector Start = MuzzleOrigin + TurretPivot->GetForwardVector() * TurretMuzzleForward + FVector(0.f, 0.f, TurretMuzzleZOffset);
	const FVector Delta = AimAt - Start;
	const float Len = Delta.Size();
	if (Len > 1.f)
	{
		TracerBeam->SetWorldLocation((Start + AimAt) * 0.5f);
		TracerBeam->SetWorldRotation(FRotationMatrix::MakeFromZ(Delta / Len).Rotator());
		TracerBeam->SetWorldScale3D(FVector(0.045f, 0.045f, Len / 100.f));
		if (TracerMID) TracerMID->SetVectorParameterValue(TEXT("Color"), FLinearColor(0.25f, 0.9f, 1.f));
		TracerBeam->SetVisibility(true);
	}
	MuzzleLight->SetIntensity(bOverclocked ? 16000.f : 12000.f);
	MuzzleLight->SetLightColor(bOverclocked ? FColor(160, 245, 255) : FColor(100, 220, 255));
	MuzzleLight->SetVisibility(true);
	FlashTimer = 0.09f;

	MLGAssets::PlaySoundAtLocation(this, MLGAssets::Audio::TurretFire, MuzzleOrigin, 0.85f, FMath::FRandRange(0.95f, 1.05f));
}

void AMLGDefenseNode::TickShockBarrier(float Dt)
{
	FireCooldown = FMath::Max(0.f, FireCooldown - Dt);
	if (FireCooldown > 0.f) return;

	TArray<AMLGAlien*> InRange;
	for (TActorIterator<AMLGAlien> It(GetWorld()); It; ++It)
	{
		if (It->IsAlive() && FVector::Dist2D(GetActorLocation(), It->GetActorLocation()) <= Range)
		{
			InRange.Add(*It);
		}
	}
	if (InRange.IsEmpty()) return;

	const AMLGGameState* GS = GetWorld()->GetGameState<AMLGGameState>();
	const bool bOverclocked = GS && GS->IsTurretOverclocked();
	FireCooldown = FireInterval * (bOverclocked ? 0.65f : 1.f);
	AMLGAlien* First = InRange[0];
	for (AMLGAlien* A : InRange)
	{
		UGameplayStatics::ApplyDamage(A, DamagePerShot, nullptr, this, UDamageType::StaticClass());
		if (A->IsAlive())
		{
			FVector PushDir = (A->GetActorLocation() - GetActorLocation()).GetSafeNormal2D();
			if (PushDir.IsNearlyZero()) PushDir = GetActorForwardVector();
			const float PushForce = A->Kind == EMLGAlienKind::Breaker ? 180.f : 380.f;
			A->LaunchCharacter(PushDir * PushForce + FVector(0.f, 0.f, 95.f), false, false);
		}
	}

	// Visual arc pulse toward nearest shocked target
	const FVector Start = GetActorLocation() + FVector(0.f, 0.f, 80.f);
	const FVector End = First->GetActorLocation() + FVector(0.f, 0.f, 35.f);
	const FVector Delta = End - Start;
	const float Len = Delta.Size();
	if (Len > 1.f)
	{
		TracerBeam->SetWorldLocation((Start + End) * 0.5f);
		TracerBeam->SetWorldRotation(FRotationMatrix::MakeFromZ(Delta / Len).Rotator());
		TracerBeam->SetWorldScale3D(FVector(0.065f, 0.065f, Len / 100.f));
		if (TracerMID) TracerMID->SetVectorParameterValue(TEXT("Color"), FLinearColor(0.35f, 0.78f, 1.f));
		TracerBeam->SetVisibility(true);
	}
	MuzzleLight->SetIntensity(13000.f);
	MuzzleLight->SetLightColor(FColor(90, 190, 255));
	MuzzleLight->SetVisibility(true);
	FlashTimer = 0.16f;

	MLGAssets::PlaySoundAtLocation(this, MLGAssets::Audio::AlienHit, Start, 0.72f, 1.45f);
}

float AMLGDefenseNode::TakeDamage(float Damage, FDamageEvent const& Event, AController* By, AActor* Causer)
{
	if (DefenseState == EMLGDefenseState::Empty || DefenseState == EMLGDefenseState::Broken) return 0.f;
	const bool bWasFull = Integrity >= MaxIntegrity;
	Integrity = FMath::Max(0.f, Integrity - Damage);
	if (bWasFull && Integrity > 0.f)
	{
		if (AMLGGameState* GS = GetWorld()->GetGameState<AMLGGameState>())
			GS->PushMessage(FString::Printf(TEXT("%s is taking damage!"), *DisplayName.ToString()));
	}
	if (Integrity <= 0.f)
	{
		DefenseState = EMLGDefenseState::Broken;
		if (AMLGGameState* GS = GetWorld()->GetGameState<AMLGGameState>())
			GS->PushMessage(FString::Printf(TEXT("WARNING: %s is destroyed!"), *DisplayName.ToString()));
		MLGAssets::PlaySoundAtLocation(this, MLGAssets::Audio::AlertLow, GetActorLocation(), 0.8f);
		RefreshVisuals();
	}
	return Damage;
}

float AMLGDefenseNode::GetHoldSeconds() const
{
	if (DefenseState == EMLGDefenseState::Empty) return 2.5f;
	if (DefenseState == EMLGDefenseState::Broken) return 3.0f;
	if (Integrity < MaxIntegrity) return 2.0f;
	return 0.8f; // toggle standby/active
}

bool AMLGDefenseNode::CanInteract(const AMLGCharacter*) const
{
	const AMLGGameState* GS = GetWorld()->GetGameState<AMLGGameState>();
	if (!GS) return false;
	if (DefenseState == EMLGDefenseState::Empty) return GS->Parts >= BuildPartsCost;
	if (DefenseState == EMLGDefenseState::Broken || Integrity < MaxIntegrity) return GS->Parts >= RepairPartsCost;
	return Kind == EMLGDefenseKind::SentryTurret; // toggle standby to save battery
}

FText AMLGDefenseNode::GetPrompt(const AMLGCharacter*) const
{
	const AMLGGameState* GS = GetWorld()->GetGameState<AMLGGameState>();
	const int32 HaveParts = GS ? GS->Parts : 0;
	const TCHAR* KindLabel = Kind == EMLGDefenseKind::SentryTurret ? TEXT("Sentry Turret (draws power)") : TEXT("Shock Barrier (decoy, 0 idle power)");
	if (DefenseState == EMLGDefenseState::Empty)
	{
		if (HaveParts < BuildPartsCost)
			return FText::FromString(FString::Printf(TEXT("%s pad: %s - needs %d parts (have %d)"), *DisplayName.ToString(), KindLabel, BuildPartsCost, HaveParts));
		return FText::FromString(FString::Printf(TEXT("Hold [E] deploy %s (%d parts)"), KindLabel, BuildPartsCost));
	}
	const int32 Pct = FMath::RoundToInt(100.f * Integrity / MaxIntegrity);
	if (DefenseState == EMLGDefenseState::Broken || Integrity < MaxIntegrity)
	{
		if (HaveParts < RepairPartsCost)
			return FText::FromString(FString::Printf(TEXT("%s (%d%%) - needs %d part to repair (have %d)"), *DisplayName.ToString(), Pct, RepairPartsCost, HaveParts));
		return FText::FromString(FString::Printf(TEXT("Hold [E] repair %s (%d%% -> 100%%, %d part)"), *DisplayName.ToString(), Pct, RepairPartsCost));
	}
	if (Kind == EMLGDefenseKind::SentryTurret)
	{
		if (DefenseState == EMLGDefenseState::Active)
			return FText::FromString(FString::Printf(TEXT("%s ACTIVE (%d%%) - hold [E] switch to Standby (saves battery)"), *DisplayName.ToString(), Pct));
		return FText::FromString(FString::Printf(TEXT("%s STANDBY (%d%%) - hold [E] activate turret"), *DisplayName.ToString(), Pct));
	}
	return FText::FromString(FString::Printf(TEXT("%s ONLINE (%d%%)"), *DisplayName.ToString(), Pct));
}

void AMLGDefenseNode::Interact(AMLGCharacter*)
{
	AMLGGameState* GS = GetWorld()->GetGameState<AMLGGameState>();
	if (!GS) return;
	if (DefenseState == EMLGDefenseState::Empty)
	{
		if (GS->Parts < BuildPartsCost) return;
		GS->Parts -= BuildPartsCost;
		Integrity = MaxIntegrity;
		DefenseState = EMLGDefenseState::Active;
		++GS->Repairs;
		GS->PushMessage(FString::Printf(TEXT("%s deployed (-%d parts)"), *DisplayName.ToString(), BuildPartsCost));
		MLGAssets::PlaySoundAtLocation(this, MLGAssets::Audio::RepairDone, GetActorLocation());
	}
	else if (DefenseState == EMLGDefenseState::Broken || Integrity < MaxIntegrity)
	{
		if (GS->Parts < RepairPartsCost) return;
		GS->Parts -= RepairPartsCost;
		Integrity = MaxIntegrity;
		DefenseState = EMLGDefenseState::Active;
		++GS->Repairs;
		GS->PushMessage(FString::Printf(TEXT("%s repaired (-%d part)"), *DisplayName.ToString(), RepairPartsCost));
		MLGAssets::PlaySoundAtLocation(this, MLGAssets::Audio::RepairDone, GetActorLocation());
	}
	else if (Kind == EMLGDefenseKind::SentryTurret)
	{
		DefenseState = (DefenseState == EMLGDefenseState::Active) ? EMLGDefenseState::Standby : EMLGDefenseState::Active;
		GS->PushMessage(FString::Printf(TEXT("%s %s"), *DisplayName.ToString(), DefenseState == EMLGDefenseState::Active ? TEXT("activated") : TEXT("set to standby")));
		MLGAssets::PlaySoundAtLocation(this, MLGAssets::Audio::RepairTick, GetActorLocation());
	}
	RefreshVisuals();
}
