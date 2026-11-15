#include "MLGPickup.h"
#include "MLGGameState.h"
#include "MLGCharacter.h"
#include "MLGAssets.h"
#include "MLGWeaponComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Engine/StaticMesh.h"
#include "UObject/ConstructorHelpers.h"

AMLGPickup::AMLGPickup()
{
	PrimaryActorTick.bCanEverTick = true;
	Mesh = CreateDefaultSubobject<UStaticMeshComponent>("Mesh");
	RootComponent = Mesh;
	static ConstructorHelpers::FObjectFinder<UStaticMesh> Sphere(TEXT("/Engine/BasicShapes/Sphere.Sphere"));
	if (Sphere.Succeeded()) Mesh->SetStaticMesh(Sphere.Object);
	Mesh->SetCollisionProfileName("BlockAll");
	SetActorScale3D(FVector(0.3f));
}

const TCHAR* AMLGPickup::GetMeshPathFor(EMLGPickupKind InKind)
{
	switch (InKind)
	{
	case EMLGPickupKind::RepairParts: return TEXT("/Game/Environment/SM_Pickup_Parts");
	case EMLGPickupKind::Ammo:        return TEXT("/Game/Environment/SM_Pickup_Ammo");
	case EMLGPickupKind::Ice:         return TEXT("/Game/Environment/SM_Pickup_Ice");
	case EMLGPickupKind::Seeds:
	case EMLGPickupKind::SeedBank:
	case EMLGPickupKind::Oxygen:      return TEXT("/Game/Environment/SM_Pickup_Seeds");
	}
	return nullptr;
}

void AMLGPickup::TriggerDropPop()
{
	DropPopTimer = 0.45f;
}

void AMLGPickup::BeginPlay()
{
	Super::BeginPlay();
	BaseLocation = GetActorLocation();
	HoverPhase = FMath::FRandRange(0.f, 6.283185f);

	static const FLinearColor Cols[6] = {
		{0.9f, 0.9f, 0.1f},   // RepairParts
		{0.8f, 0.3f, 0.1f},   // Ammo
		{0.2f, 0.9f, 0.3f},   // Seeds
		{0.5f, 0.8f, 1.f},    // Ice
		{0.9f, 0.2f, 0.9f},   // SeedBank
		{0.12f, 0.88f, 1.f}   // Oxygen
	};
	const int32 Idx = FMath::Clamp((int32)Kind, 0, 5);
	const FLinearColor KindCol = Cols[Idx];

	if (UStaticMesh* CustomMesh = MLGAssets::LoadOptional<UStaticMesh>(GetMeshPathFor(Kind)))
	{
		const FBoxSphereBounds B = CustomMesh->GetBounds();
		const float S = MLGAssets::FitUniformScale(B.BoxExtent * 2.f, FVector(46.f));
		Mesh->SetStaticMesh(CustomMesh);
		SetActorScale3D(FVector(S));
		bUsingCustomMesh = true;
		MLGAssets::EnsureEmissiveMIDs(Mesh, SlotMIDs, SlotIsAccent);
		MLGAssets::ApplyEmissiveTint(SlotMIDs, SlotIsAccent, KindCol * 0.08f, KindCol * (Kind == EMLGPickupKind::SeedBank ? 2.2f : 1.5f));
	}
	else if (UMaterialInstanceDynamic* M = MLGAssets::EnsureColorMID(Mesh, 0))
	{
		M->SetVectorParameterValue("Color", KindCol);
	}
}

void AMLGPickup::Tick(float Dt)
{
	Super::Tick(Dt);
	HoverPhase += Dt * 2.6f;
	FVector HoverLoc = BaseLocation;
	if (DropPopTimer > 0.f)
	{
		DropPopTimer = FMath::Max(0.f, DropPopTimer - Dt);
		const float T = 1.f - DropPopTimer / 0.45f;
		HoverLoc.Z += FMath::Sin(T * PI) * 34.f; // crisp 0.38G Martian hop arc on drop
	}
	else
	{
		HoverLoc.Z += FMath::Sin(HoverPhase) * 5.f;
	}
	SetActorLocation(HoverLoc);
	AddActorLocalRotation(FRotator(0.f, 55.f * Dt, 0.f));
}

static const TCHAR* KindName(EMLGPickupKind K)
{
	switch (K)
	{
	case EMLGPickupKind::RepairParts: return TEXT("repair part(s)");
	case EMLGPickupKind::Ammo:        return TEXT("rounds");
	case EMLGPickupKind::Seeds:       return TEXT("seed(s)");
	case EMLGPickupKind::SeedBank:    return TEXT("seeds from the seed-bank backup");
	case EMLGPickupKind::Oxygen:      return TEXT("% suit O2");
	default:                          return TEXT("ice unit(s)");
	}
}

FText AMLGPickup::GetPrompt(const AMLGCharacter*) const
{
	return FText::FromString(FString::Printf(TEXT("[E] take %d %s"), Amount, KindName(Kind)));
}

void AMLGPickup::Interact(AMLGCharacter* Who)
{
	AMLGGameState* GS = GetWorld()->GetGameState<AMLGGameState>();
	if (!GS) return;
	switch (Kind)
	{
	case EMLGPickupKind::RepairParts: GS->Parts += Amount; break;
	case EMLGPickupKind::Seeds: GS->Seeds += Amount; break;
	case EMLGPickupKind::Ice: GS->Sim.Ice += Amount; GS->IceCollected += Amount; break; // simplified: goes straight to the purifier hopper
	case EMLGPickupKind::SeedBank: GS->Seeds += Amount; GS->bBackupRecovered = true; break;
	case EMLGPickupKind::Ammo: if (Who && Who->Weapon) Who->Weapon->Reserve += Amount; break;
	case EMLGPickupKind::Oxygen: if (Who) Who->SuitOxygen = FMath::Min(100.f, Who->SuitOxygen + (float)Amount); break;
	}
	GS->PushMessage(FString::Printf(TEXT("Picked up %d %s"), Amount, KindName(Kind)));
	MLGAssets::PlaySound2D(this, MLGAssets::Audio::Pickup, 0.8f);
	Destroy();
}
