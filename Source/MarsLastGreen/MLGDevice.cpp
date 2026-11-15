#include "MLGDevice.h"
#include "MLGAssets.h"
#include "MLGCharacter.h"
#include "MLGGameState.h"
#include "MLGPlantPlot.h"
#include "MLGWeaponComponent.h"
#include "EngineUtils.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "UObject/ConstructorHelpers.h"

AMLGDevice::AMLGDevice()
{
	PrimaryActorTick.bCanEverTick = true;
	Mesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Mesh"));
	RootComponent = Mesh;
	static ConstructorHelpers::FObjectFinder<UStaticMesh> Cube(TEXT("/Engine/BasicShapes/Cube.Cube"));
	if (Cube.Succeeded()) Mesh->SetStaticMesh(Cube.Object);
	Mesh->SetCollisionProfileName(TEXT("BlockAll"));
	SetActorScale3D(FVector(0.8f, 0.8f, 1.2f));

	StatusBeacon = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("StatusBeacon"));
	StatusBeacon->SetupAttachment(Mesh);
	static ConstructorHelpers::FObjectFinder<UStaticMesh> Sphere(TEXT("/Engine/BasicShapes/Sphere.Sphere"));
	if (Sphere.Succeeded()) StatusBeacon->SetStaticMesh(Sphere.Object);
	StatusBeacon->SetRelativeLocation(FVector(0.f, 0.f, 58.f));
	StatusBeacon->SetRelativeScale3D(FVector(0.24f, 0.24f, 0.16f));
	StatusBeacon->SetCollisionProfileName(TEXT("NoCollision"));

	DisplayName = FText::FromString(TEXT("Device"));
}

const TCHAR* AMLGDevice::GetMeshPathFor(EMLGDeviceType InType, bool bPipe)
{
	switch (InType)
	{
	case EMLGDeviceType::Power:          return TEXT("/Game/Environment/SM_Dev_PowerUnit");
	case EMLGDeviceType::Oxygen:         return TEXT("/Game/Environment/SM_Dev_OxygenGen");
	case EMLGDeviceType::WaterPurifier:  return TEXT("/Game/Environment/SM_Dev_Purifier");
	case EMLGDeviceType::GreenhouseSeal: return TEXT("/Game/Environment/SM_Dev_GreenhouseSeal");
	case EMLGDeviceType::WaterTank:      return bPipe ? TEXT("/Game/Environment/SM_Dev_WaterPipe") : TEXT("/Game/Environment/SM_Dev_WaterTank");
	case EMLGDeviceType::Comms:          return TEXT("/Game/Environment/SM_Dev_CommsRelay");
	case EMLGDeviceType::Transmitter:    return TEXT("/Game/Environment/SM_Dev_Transmitter");
	case EMLGDeviceType::GeneLab:        return TEXT("/Game/Environment/SM_Dev_OxygenGen");
	case EMLGDeviceType::Sabatier:       return TEXT("/Game/Environment/SM_Dev_Purifier");
	case EMLGDeviceType::CryoRig:        return TEXT("/Game/Environment/SM_Dev_Purifier");
	case EMLGDeviceType::DropLocker:     return TEXT("/Game/Environment/SM_Dev_Transmitter");
	case EMLGDeviceType::SolarSub:       return TEXT("/Game/Environment/SM_Dev_PowerUnit");
	case EMLGDeviceType::CommsSub:       return TEXT("/Game/Environment/SM_Dev_CommsRelay");
	}
	return nullptr;
}

void AMLGDevice::BeginPlay()
{
	Super::BeginPlay();
	// Maps placed before bPipeSegment existed name the pipe "Water pipe".
	const bool bPipe = bPipeSegment || (Type == EMLGDeviceType::WaterTank && DisplayName.ToString().Contains(TEXT("pipe")));
	if (const TCHAR* EnvMeshPath = GetMeshPathFor(Type, bPipe))
	{
		if (UStaticMesh* CustomMesh = MLGAssets::LoadOptional<UStaticMesh>(EnvMeshPath)) ApplyImportedMesh(CustomMesh);
	}

	if (UMaterialInterface* MetalMat = MLGAssets::LoadOptional<UMaterialInterface>(TEXT("/Game/Environment/Materials/M_Habitat_Trim")))
	{
		if (!bUsingCustomMesh && Mesh && Mesh->GetMaterial(0) && Mesh->GetMaterial(0)->GetName() == TEXT("WorldGridMaterial"))
			Mesh->SetMaterial(0, MetalMat);
		if (StatusBeacon && StatusBeacon->GetMaterial(0) &&
			(StatusBeacon->GetMaterial(0)->GetName() == TEXT("WorldGridMaterial") || StatusBeacon->GetMaterial(0)->GetName() == TEXT("BasicShapeMaterial")))
			StatusBeacon->SetMaterial(0, MetalMat);
	}
	MID = MLGAssets::EnsureColorMID(Mesh, 0);
	if (bUsingCustomMesh) MLGAssets::EnsureEmissiveMIDs(Mesh, SlotMIDs, SlotIsAccent);
	BeaconMID = MLGAssets::EnsureColorMID(StatusBeacon, 0);
}

// The primitive cube (100 cm, centred pivot) scaled by the actor scale defines the device footprint the AI, nav and
// collision were tuned against. The imported prop (bottom pivot) is uniformly fitted inside that box and rests on its floor.
void AMLGDevice::ApplyImportedMesh(UStaticMesh* CustomMesh)
{
	const FVector TargetSize = GetActorScale3D().GetAbs() * 100.f;
	const FVector Floor = GetActorLocation() - GetActorUpVector() * (TargetSize.Z * 0.5f);
	const FBoxSphereBounds B = CustomMesh->GetBounds();
	const float S = MLGAssets::FitUniformScale(B.BoxExtent * 2.f, TargetSize);
	const FVector LocalBottom(B.Origin.X, B.Origin.Y, B.Origin.Z - B.BoxExtent.Z);

	Mesh->SetStaticMesh(CustomMesh);
	SetActorScale3D(FVector(S));
	SetActorLocation(Floor - GetActorRotation().RotateVector(LocalBottom * S));
	bUsingCustomMesh = true;

	// Beacon: ~19 cm sphere floating 10 cm above the prop's top, independent of the fitted scale.
	StatusBeacon->SetRelativeLocation(FVector(B.Origin.X, B.Origin.Y, B.Origin.Z + B.BoxExtent.Z + 10.f / S));
	StatusBeacon->SetRelativeScale3D(FVector(0.19f / S));
}

void AMLGDevice::Tick(float Dt)
{
	Super::Tick(Dt);
	ActionCooldown = FMath::Max(0.f, ActionCooldown - Dt);
	// Colour band: 0 broken (red), 1 degraded (amber), 2 healthy (green/cyan).
	const int32 Band = !IsOperational() ? 0 : (Integrity < MaxIntegrity ? 1 : 2);
	static const FLinearColor Cols[3] = { {0.85f, 0.06f, 0.04f}, {0.92f, 0.55f, 0.05f}, {0.1f, 0.72f, 0.22f} };
	const float Pulse = 0.45f + 0.55f * FMath::Abs(FMath::Sin(GetWorld()->GetTimeSeconds() * 3.5f));

	if (BeaconMID)
	{
		if (Band == 0)
		{
			BeaconMID->SetVectorParameterValue(TEXT("Color"), Cols[0] * Pulse);
		}
		else if (Band != LastShownBand)
		{
			BeaconMID->SetVectorParameterValue(TEXT("Color"), Type == EMLGDeviceType::Transmitter ? FLinearColor(0.15f, 0.75f, 1.f) : Cols[Band]);
		}
	}
	// Imported props keep their baked albedo; state shows as an emissive accent (pulsing while broken).
	if (bUsingCustomMesh && Band == 0)
	{
		MLGAssets::ApplyEmissiveTint(SlotMIDs, SlotIsAccent, Cols[0] * (0.25f * Pulse), Cols[0] * (1.8f * Pulse));
	}

	if (Band == LastShownBand) return;
	LastShownBand = Band;
	const FLinearColor StateCol = Type == EMLGDeviceType::Transmitter ? FLinearColor(0.15f, 0.55f, 0.85f) : Cols[Band];
	if (bUsingCustomMesh)
	{
		MLGAssets::ApplyEmissiveTint(SlotMIDs, SlotIsAccent, StateCol * (Band == 2 ? 0.08f : 0.22f), StateCol * (Band == 2 ? 1.2f : 1.5f));
	}
	else if (MID)
	{
		MID->SetVectorParameterValue(TEXT("Color"), StateCol);
	}
}

float AMLGDevice::TakeDamage(float Damage, FDamageEvent const& Event, AController* By, AActor* Causer)
{
	if (Type == EMLGDeviceType::Transmitter || Type == EMLGDeviceType::DropLocker) return 0.f;
	const bool bWas = IsOperational(), bWasFull = Integrity >= MaxIntegrity;
	Integrity = FMath::Max(0.f, Integrity - Damage);
	if (bWasFull)
		if (AMLGGameState* GS = GetWorld()->GetGameState<AMLGGameState>())
			GS->PushMessage(FString::Printf(TEXT("%s is under attack!"), *DisplayName.ToString()));
	if (bWas && !IsOperational())
	{
		if (AMLGGameState* GS = GetWorld()->GetGameState<AMLGGameState>())
			GS->PushMessage(FString::Printf(TEXT("WARNING: %s is down"), *DisplayName.ToString()));
		MLGAssets::PlaySoundAtLocation(this, MLGAssets::Audio::AlertLow, GetActorLocation(), 0.9f);
	}
	return Damage;
}

float AMLGDevice::GetHoldSeconds() const
{
	if (Type == EMLGDeviceType::Transmitter) return 6.f;
	if (Integrity < MaxIntegrity) return RepairSeconds;
	switch (Type)
	{
	case EMLGDeviceType::GeneLab:
	case EMLGDeviceType::Sabatier:
	case EMLGDeviceType::WaterPurifier:
		return 0.35f;
	case EMLGDeviceType::CryoRig:
		return 1.2f;
	case EMLGDeviceType::DropLocker:
		return 0.6f;
	default:
		return 0.45f;
	}
}

bool AMLGDevice::CanInteract(const AMLGCharacter*) const
{
	const AMLGGameState* GS = GetWorld()->GetGameState<AMLGGameState>();
	if (!GS) return false;
	if (Type == EMLGDeviceType::Transmitter) return GS->Phase == EMLGPhase::Transmit;
	if (Integrity < MaxIntegrity) return GS->Parts >= PartsCost;
	if (Type == EMLGDeviceType::DropLocker) return !bLockerOpened;
	if (Type == EMLGDeviceType::GeneLab || Type == EMLGDeviceType::Sabatier || Type == EMLGDeviceType::WaterPurifier) return true;
	return ActionCooldown <= 0.f;
}

FText AMLGDevice::GetPrompt(const AMLGCharacter* Who) const
{
	const AMLGGameState* GS = GetWorld()->GetGameState<AMLGGameState>();
	if (Type == EMLGDeviceType::Transmitter)
		return FText::FromString(GS && GS->Phase == EMLGPhase::Transmit ? TEXT("[E] TRANSMIT DATA")
			: GS && GS->Phase == EMLGPhase::Won ? TEXT("TX:SENT") : TEXT("TX:LOCKED"));

	const int32 Pct = FMath::RoundToInt(100.f * Integrity / MaxIntegrity);
	if (Integrity < MaxIntegrity)
	{
		if (GS && GS->Parts < PartsCost)
			return FText::FromString(FString::Printf(TEXT("%s %d%% (NEED %d PART)"), *DisplayName.ToString(), Pct, PartsCost));
		return FText::FromString(FString::Printf(TEXT("[E] REPAIR %s %d%% (-%dP)"), *DisplayName.ToString(), Pct, PartsCost));
	}

	const int32 Cd = FMath::CeilToInt(ActionCooldown);
	switch (Type)
	{
	case EMLGDeviceType::GeneLab:
		return FText::FromString(FString::Printf(TEXT("[E] GENE:%s"), GS ? *GS->GetCropGeneCode() : TEXT("WT")));
	case EMLGDeviceType::Sabatier:
		return FText::FromString(GS && GS->IsSabatierActive() ? TEXT("[E] SABATIER:ON (2.2x H2O)") : TEXT("[E] SABATIER:OFF"));
	case EMLGDeviceType::WaterPurifier:
		return FText::FromString(GS && GS->IsSabatierActive() ? TEXT("[E] PUR:SABATIER ON") : TEXT("[E] PUR:SABATIER OFF"));
	case EMLGDeviceType::Power:
		if (ActionCooldown > 0.f)
			return FText::FromString(FString::Printf(TEXT("PWR:%d%% SOLAR %d%% (%ds)"), Pct, GS ? FMath::RoundToInt(GS->SolarEfficiency * 100.f) : 100, Cd));
		return FText::FromString(FString::Printf(TEXT("[E] PWR:BOOST (SOLAR %d%%)"), GS ? FMath::RoundToInt(GS->SolarEfficiency * 100.f) : 100));
	case EMLGDeviceType::SolarSub:
		return FText::FromString(ActionCooldown > 0.f
			? FString::Printf(TEXT("SOLAR:+15%% (%ds)"), Cd)
			: TEXT("[E] SOLAR:+35% GRID"));
	case EMLGDeviceType::Oxygen:
		return FText::FromString(ActionCooldown > 0.f ? FString::Printf(TEXT("O2:VENT (%ds)"), Cd) : TEXT("[E] O2:VENT +30"));
	case EMLGDeviceType::GreenhouseSeal:
		return FText::FromString(ActionCooldown > 0.f ? FString::Printf(TEXT("SEAL:OK (%ds)"), Cd) : TEXT("[E] SEAL:FLUSH +O2/HP"));
	case EMLGDeviceType::WaterTank:
		return FText::FromString(ActionCooldown > 0.f ? FString::Printf(TEXT("H2O:OK (%ds)"), Cd) : TEXT("[E] H2O:PURGE +6L"));
	case EMLGDeviceType::CryoRig:
		return FText::FromString(ActionCooldown > 0.f ? FString::Printf(TEXT("CRYO:DRILL (%ds)"), Cd) : TEXT("[E] CRYO:+1 ICE +4L"));
	case EMLGDeviceType::DropLocker:
		return FText::FromString(bLockerOpened ? TEXT("LOCKER:EMPTY") : TEXT("[E] LOCKER:KIT+LOG"));
	case EMLGDeviceType::Comms:
	case EMLGDeviceType::CommsSub:
		return FText::FromString(ActionCooldown > 0.f ? FString::Printf(TEXT("COMMS:OC (%ds)"), Cd) : TEXT("[E] COMMS:TURRET OC"));
	default:
		return FText::FromString(FString::Printf(TEXT("%s OK (%d%%)"), *DisplayName.ToString(), Pct));
	}
}

void AMLGDevice::Interact(AMLGCharacter* Who)
{
	AMLGGameState* GS = GetWorld()->GetGameState<AMLGGameState>();
	if (!GS) return;
	if (Type == EMLGDeviceType::Transmitter)
	{
		if (GS->Phase == EMLGPhase::Transmit)
		{
			MLGAssets::PlaySound2D(this, MLGAssets::Audio::Transmit);
			GS->Win();
		}
		return;
	}
	if (Integrity < MaxIntegrity)
	{
		if (GS->Parts < PartsCost) return;
		GS->Parts -= PartsCost;
		Integrity = MaxIntegrity;
		++GS->Repairs;
		GS->PushMessage(FString::Printf(TEXT("%s repaired (-%d part)"), *DisplayName.ToString(), PartsCost));
		MLGAssets::PlaySoundAtLocation(this, MLGAssets::Audio::RepairDone, GetActorLocation());
		return;
	}

	switch (Type)
	{
	case EMLGDeviceType::GeneLab:
		GS->CycleOrToggleGeneTrait();
		MLGAssets::PlaySoundAtLocation(this, MLGAssets::Audio::RepairDone, GetActorLocation(), 0.85f, 1.35f);
		break;
	case EMLGDeviceType::Sabatier:
	case EMLGDeviceType::WaterPurifier:
		GS->ToggleSabatier();
		MLGAssets::PlaySoundAtLocation(this, MLGAssets::Audio::RepairDone, GetActorLocation(), 0.85f, 1.18f);
		break;
	case EMLGDeviceType::Power:
		if (ActionCooldown <= 0.f)
		{
			ActionCooldown = 25.f;
			GS->Sim.Power = FMath::Min(100.f, GS->Sim.Power + 12.f);
			GS->TriggerGridOverclock(20.f);
			MLGAssets::PlaySoundAtLocation(this, MLGAssets::Audio::RepairDone, GetActorLocation(), 0.9f, 1.25f);
		}
		break;
	case EMLGDeviceType::SolarSub:
		if (ActionCooldown <= 0.f)
		{
			ActionCooldown = 30.f;
			GS->Sim.Power = FMath::Min(100.f, GS->Sim.Power + 15.f);
			GS->TriggerGridOverclock(35.f);
			MLGAssets::PlaySoundAtLocation(this, MLGAssets::Audio::RepairDone, GetActorLocation(), 0.9f, 1.3f);
		}
		break;
	case EMLGDeviceType::Oxygen:
		if (ActionCooldown <= 0.f)
		{
			ActionCooldown = 20.f;
			if (Who) Who->SuitOxygen = FMath::Min(100.f, Who->SuitOxygen + 30.f);
			GS->Sim.BaseOxygen = FMath::Min(100.f, GS->Sim.BaseOxygen + 15.f);
			GS->PushMessage(TEXT("Emergency O2 vent: +30% suit / +15% base O2"));
			MLGAssets::PlaySoundAtLocation(this, MLGAssets::Audio::Pickup, GetActorLocation(), 0.9f, 1.15f);
		}
		break;
	case EMLGDeviceType::GreenhouseSeal:
		if (ActionCooldown <= 0.f)
		{
			ActionCooldown = 25.f;
			GS->Sim.BaseOxygen = FMath::Min(100.f, GS->Sim.BaseOxygen + 10.f);
			for (TActorIterator<AMLGPlantPlot> It(GetWorld()); It; ++It)
			{
				if (It->Plant.IsLiving()) It->Plant.Health = FMath::Min(1.f, It->Plant.Health + 0.1f);
			}
			GS->PushMessage(TEXT("Greenhouse seal pressurized (+10% crop HP)"));
			MLGAssets::PlaySoundAtLocation(this, MLGAssets::Audio::RepairDone, GetActorLocation(), 0.85f, 1.1f);
		}
		break;
	case EMLGDeviceType::WaterTank:
		if (ActionCooldown <= 0.f)
		{
			ActionCooldown = 30.f;
			GS->Sim.Water = FMath::Min(FMLGResourceModel::MaxWater, GS->Sim.Water + 6.f);
			GS->PushMessage(TEXT("Condensate purge: +6L water"));
			MLGAssets::PlaySoundAtLocation(this, MLGAssets::Audio::Pickup, GetActorLocation(), 0.85f, 1.05f);
		}
		break;
	case EMLGDeviceType::CryoRig:
		if (ActionCooldown <= 0.f)
		{
			ActionCooldown = 28.f;
			GS->Sim.Ice += 1.f;
			++GS->IceCollected;
			GS->Sim.Water = FMath::Min(FMLGResourceModel::MaxWater, GS->Sim.Water + 4.f);
			GS->PushMessage(TEXT("Cryo rig drilled: +1 ice, +4L H2O"));
			MLGAssets::PlaySoundAtLocation(this, MLGAssets::Audio::RepairDone, GetActorLocation(), 0.95f, 0.92f);
		}
		break;
	case EMLGDeviceType::DropLocker:
		if (!bLockerOpened)
		{
			bLockerOpened = true;
			++GS->Parts;
			++GS->LogsRead;
			if (Who)
			{
				Who->SuitOxygen = FMath::Min(100.f, Who->SuitOxygen + 20.f);
				if (Who->Weapon) Who->Weapon->Reserve += 24;
			}
			GS->PushMessage(TEXT("DropShip BlackBox: +1 part, +24 ammo, +15 sci"));
			MLGAssets::PlaySoundAtLocation(this, MLGAssets::Audio::Pickup, GetActorLocation(), 0.95f, 1.15f);
		}
		break;
	case EMLGDeviceType::Comms:
	case EMLGDeviceType::CommsSub:
		if (ActionCooldown <= 0.f)
		{
			ActionCooldown = 35.f;
			GS->TriggerTurretOverclock(35.f);
			MLGAssets::PlaySoundAtLocation(this, MLGAssets::Audio::Transmit, GetActorLocation(), 0.7f, 1.25f);
		}
		break;
	default:
		break;
	}
}
