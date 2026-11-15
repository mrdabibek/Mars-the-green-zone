#include "MLGPlantPlot.h"
#include "MLGAssets.h"
#include "MLGCharacter.h"
#include "MLGGameState.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "UObject/ConstructorHelpers.h"

AMLGPlantPlot::AMLGPlantPlot()
{
	PrimaryActorTick.bCanEverTick = true;
	Tray = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Tray"));
	RootComponent = Tray;
	PlantMesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Plant"));
	PlantMesh->SetupAttachment(Tray);
	StatusLight = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("StatusLight"));
	StatusLight->SetupAttachment(Tray);

	static ConstructorHelpers::FObjectFinder<UStaticMesh> Cube(TEXT("/Engine/BasicShapes/Cube.Cube"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> Cone(TEXT("/Engine/BasicShapes/Cone.Cone"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> Sphere(TEXT("/Engine/BasicShapes/Sphere.Sphere"));
	if (Cube.Succeeded()) Tray->SetStaticMesh(Cube.Object);
	if (Cone.Succeeded()) { PlantMesh->SetStaticMesh(Cone.Object); FallbackConeMesh = Cone.Object; }
	if (Sphere.Succeeded()) StatusLight->SetStaticMesh(Sphere.Object);

	Tray->SetCollisionProfileName(TEXT("BlockAll"));
	PlantMesh->SetCollisionProfileName(TEXT("NoCollision"));
	StatusLight->SetCollisionProfileName(TEXT("NoCollision"));

	SetActorScale3D(FVector(1.5f, 1.5f, 0.4f));
	PlantMesh->SetRelativeLocation(FVector(0, 0, 50.f));
	PlantMesh->SetVisibility(false);

	StatusLight->SetRelativeLocation(FVector(42.f, 42.f, 54.f));
	StatusLight->SetRelativeScale3D(FVector(0.10f, 0.10f, 0.35f));
}

const TCHAR* AMLGPlantPlot::GetEarlyPlantMeshPath(EMLGPlantStage InStage)
{
	if (InStage == EMLGPlantStage::Seed) return TEXT("/Game/Environment/SM_Plant_Seed");
	if (InStage == EMLGPlantStage::Seedling) return TEXT("/Game/Environment/SM_Plant_Seedling");
	return nullptr;
}

void AMLGPlantPlot::BeginPlay()
{
	Super::BeginPlay();
	if (UStaticMesh* TrayCustom = MLGAssets::LoadOptional<UStaticMesh>(GetTrayMeshPath()))
	{
		// Legacy Cube (100 cm, centred) scaled by (1.5, 1.5, 0.4) -> 150x150x40 cm floor-anchored footprint.
		const FVector TargetSize = GetActorScale3D().GetAbs() * 100.f;
		const FVector Floor = GetActorLocation() - GetActorUpVector() * (TargetSize.Z * 0.5f);
		const FBoxSphereBounds B = TrayCustom->GetBounds();
		const float S = MLGAssets::FitUniformScale(B.BoxExtent * 2.f, TargetSize);
		const FVector LocalBottom(B.Origin.X, B.Origin.Y, B.Origin.Z - B.BoxExtent.Z);

		Tray->SetStaticMesh(TrayCustom);
		SetActorScale3D(FVector(S));
		SetActorLocation(Floor - GetActorRotation().RotateVector(LocalBottom * S));
		bUsingCustomTray = true;
		CustomTrayScale = S;
		PlantBedLocalZ = (B.Origin.Z + B.BoxExtent.Z) * 0.72f;

		StatusLight->SetRelativeLocation(FVector(B.Origin.X + B.BoxExtent.X * 0.78f, B.Origin.Y + B.BoxExtent.Y * 0.78f, B.Origin.Z + B.BoxExtent.Z + 4.f / S));
		StatusLight->SetRelativeScale3D(FVector(0.10f / S, 0.10f / S, 0.14f / S));
		MLGAssets::EnsureEmissiveMIDs(Tray, TraySlotMIDs, TraySlotIsAccent);
	}
	else if (UMaterialInstanceDynamic* TrayMID = MLGAssets::EnsureColorMID(Tray, 0))
	{
		TrayMID->SetVectorParameterValue(TEXT("Color"), FLinearColor(0.24f, 0.25f, 0.27f));
	}

	SeedPlantMesh = MLGAssets::LoadOptional<UStaticMesh>(GetEarlyPlantMeshPath(EMLGPlantStage::Seed));
	SeedlingPlantMesh = MLGAssets::LoadOptional<UStaticMesh>(GetEarlyPlantMeshPath(EMLGPlantStage::Seedling));

	// Alternate between the two PolyHaven mature plant variants based on plot X/Y position if imported
	const bool bAltVariant = (FMath::Abs(FMath::RoundToInt(GetActorLocation().X + GetActorLocation().Y)) % 400) > 100;
	MaturePlantMesh = bAltVariant
		? MLGAssets::LoadFirst<UStaticMesh>({ TEXT("/Game/Environment/SM_Plant_Mature_04"), TEXT("/Game/Environment/SM_Plant_Mature_02"), TEXT("/Game/Environment/SM_Plant_Mature") })
		: MLGAssets::LoadFirst<UStaticMesh>({ TEXT("/Game/Environment/SM_Plant_Mature_02"), TEXT("/Game/Environment/SM_Plant_Mature_04"), TEXT("/Game/Environment/SM_Plant_Mature") });

	PlantMID = MLGAssets::EnsureColorMID(PlantMesh, 0);
	StatusMID = MLGAssets::EnsureColorMID(StatusLight, 0);
	RefreshVisual();
}

void AMLGPlantPlot::Tick(float Dt)
{
	Super::Tick(Dt);
	AMLGGameState* GS = GetWorld()->GetGameState<AMLGGameState>();
	if (!GS || !Plant.IsLiving()) { RefreshVisual(); return; }
	const bool bW = GS->Sim.HasWater(), bP = GS->Sim.HasPower(), bS = GS->IsOperational(EMLGDeviceType::GreenhouseSeal);
	Plant.Tick(Dt, bW, bP, bS, GS->CropGeneMask);
	StallReason = !bS ? FText::FromString(TEXT("SEAL DOWN")) : !bP ? FText::FromString(TEXT("NO PWR")) : !bW ? FText::FromString(TEXT("NO H2O")) : FText();
	if (Plant.IsCritical() && !bWarnedCritical) { bWarnedCritical = true; GS->PushMessage(TEXT("CRITICAL: a plant will die permanently unless systems are restored")); }
	if (!Plant.IsCritical()) bWarnedCritical = false;
	if (Plant.Stage == EMLGPlantStage::Dead)
	{
		GS->PushMessage(TEXT("A plant has died - the seed is lost"));
		MLGAssets::PlaySoundAtLocation(this, MLGAssets::Audio::AlertLow, GetActorLocation(), 0.8f);
	}
	RefreshVisual();
}

void AMLGPlantPlot::RefreshVisual()
{
	const bool bShow = Plant.Stage != EMLGPlantStage::Empty;
	PlantMesh->SetVisibility(bShow);

	FLinearColor StatusCol(0.25f, 0.3f, 0.35f);
	if (Plant.Stage == EMLGPlantStage::Dead) StatusCol = FLinearColor(0.55f, 0.08f, 0.06f);
	else if (Plant.IsLiving()) StatusCol = Plant.bStalled ? FLinearColor(0.95f, 0.65f, 0.08f) : FLinearColor(0.12f, 0.88f, 0.3f);

	if (StatusMID) StatusMID->SetVectorParameterValue(TEXT("Color"), StatusCol);
	if (bUsingCustomTray) MLGAssets::ApplyEmissiveTint(TraySlotMIDs, TraySlotIsAccent, FLinearColor::Black, StatusCol * 1.3f);

	if (!bShow) return;

	UStaticMesh* DesiredCustomMesh = nullptr;
	float DesiredWorldHeight = 30.f;
	switch (Plant.Stage)
	{
	case EMLGPlantStage::Seed:
		DesiredCustomMesh = SeedPlantMesh;
		DesiredWorldHeight = 16.f + 10.f * Plant.Progress;
		break;
	case EMLGPlantStage::Seedling:
		DesiredCustomMesh = SeedlingPlantMesh ? SeedlingPlantMesh : MaturePlantMesh;
		DesiredWorldHeight = 45.f + 45.f * Plant.Progress;
		break;
	case EMLGPlantStage::Mature:
		DesiredCustomMesh = MaturePlantMesh;
		DesiredWorldHeight = 130.f;
		break;
	default:
		break;
	}

	if (DesiredCustomMesh)
	{
		if (ActiveCustomPlantMesh != DesiredCustomMesh)
		{
			ActiveCustomPlantMesh = DesiredCustomMesh;
			PlantMesh->SetStaticMesh(DesiredCustomMesh);
			PlantMID = MLGAssets::EnsureColorMID(PlantMesh, 0);
		}
		const FBoxSphereBounds Bounds = DesiredCustomMesh->GetBounds();
		const float RawHeight = FMath::Max(5.f, Bounds.BoxExtent.Z * 2.f);
		const float UniformWorldScale = DesiredWorldHeight / RawHeight;
		if (bUsingCustomTray)
		{
			PlantMesh->SetRelativeScale3D(FVector(UniformWorldScale / CustomTrayScale));
		}
		else
		{
			// Legacy Tray actor scale is (1.5, 1.5, 0.4); divide relative scale so world proportions stay natural
			PlantMesh->SetRelativeScale3D(FVector(UniformWorldScale / 1.5f, UniformWorldScale / 1.5f, UniformWorldScale / 0.4f));
		}
		PlantMesh->SetRelativeLocation(FVector(0.f, 0.f, PlantBedLocalZ));
		if (PlantMID)
		{
			PlantMID->SetVectorParameterValue(TEXT("EmissiveColor"),
				Plant.bStalled ? FLinearColor(0.35f, 0.22f, 0.02f) : FLinearColor(0.02f, 0.08f, 0.02f));
		}
		return;
	}

	if (ActiveCustomPlantMesh != nullptr && FallbackConeMesh)
	{
		ActiveCustomPlantMesh = nullptr;
		PlantMesh->SetStaticMesh(FallbackConeMesh);
		PlantMID = MLGAssets::EnsureColorMID(PlantMesh, 0);
	}

	float S = 0.15f;
	if (Plant.Stage == EMLGPlantStage::Seedling) S = 0.3f + 0.4f * Plant.Progress;
	else if (Plant.Stage == EMLGPlantStage::Mature) S = 1.0f;
	else if (Plant.Stage == EMLGPlantStage::Seed) S = 0.15f + 0.1f * Plant.Progress;
	if (bUsingCustomTray)
	{
		const float Inv = 1.f / CustomTrayScale;
		PlantMesh->SetRelativeScale3D(FVector(S * 0.9f * Inv, S * 0.9f * Inv, S * 0.6f * Inv));
	}
	else
	{
		PlantMesh->SetRelativeScale3D(FVector(S * 0.6f, S * 0.6f, S * 1.5f));
	}
	PlantMesh->SetRelativeLocation(FVector(0.f, 0.f, PlantBedLocalZ));
	if (PlantMID)
		PlantMID->SetVectorParameterValue(TEXT("Color"),
			Plant.Stage == EMLGPlantStage::Dead ? FLinearColor(0.15f, 0.12f, 0.1f)
			: Plant.bStalled ? FLinearColor(0.7f, 0.6f, 0.1f) : FLinearColor(0.05f, 0.6f, 0.12f));
}

float AMLGPlantPlot::GetHoldSeconds() const
{
	return Plant.Stage == EMLGPlantStage::Empty ? 1.5f : Plant.Stage == EMLGPlantStage::Mature ? 2.f : 1.f;
}

bool AMLGPlantPlot::CanInteract(const AMLGCharacter*) const
{
	const AMLGGameState* GS = GetWorld()->GetGameState<AMLGGameState>();
	switch (Plant.Stage)
	{
	case EMLGPlantStage::Empty: return GS && GS->Seeds > 0;
	case EMLGPlantStage::Mature: case EMLGPlantStage::Dead: return true;
	default: return false;
	}
}

FText AMLGPlantPlot::GetPrompt(const AMLGCharacter*) const
{
	const AMLGGameState* GS = GetWorld()->GetGameState<AMLGGameState>();
	const FString GeneTag = (GS && GS->CropGeneMask != MLGGeneTrait::None) ? FString::Printf(TEXT(" [%s]"), *GS->GetCropGeneCode()) : FString();
	const int32 BonusSeeds = (GS && GS->HasGeneTrait(MLGGeneTrait::PHO)) ? 1 : 0;
	switch (Plant.Stage)
	{
	case EMLGPlantStage::Empty:
		return FText::FromString(GS && GS->Seeds > 0 ? FString::Printf(TEXT("[E] PLANT (%d)%s"), GS->Seeds, *GeneTag) : TEXT("EMPTY: 0 SEEDS"));
	case EMLGPlantStage::Mature:
		return FText::FromString(FString::Printf(TEXT("[E] HARVEST +%d%s"), HarvestSeeds + BonusSeeds, *GeneTag));
	case EMLGPlantStage::Dead:
		return FText::FromString(TEXT("[E] CLEAR PLOT"));
	default:
		return FText::FromString(FString::Printf(TEXT("%s %d%% HP:%d%%%s%s"),
			Plant.Stage == EMLGPlantStage::Seed ? TEXT("SEED") : TEXT("SPROUT"),
			FMath::RoundToInt(Plant.Progress * 100.f), FMath::RoundToInt(Plant.Health * 100.f),
			*GeneTag,
			Plant.bStalled ? *(FString(TEXT(" ")) + StallReason.ToString()) : TEXT("")));
	}
}

void AMLGPlantPlot::Interact(AMLGCharacter*)
{
	AMLGGameState* GS = GetWorld()->GetGameState<AMLGGameState>();
	if (!GS) return;
	switch (Plant.Stage)
	{
	case EMLGPlantStage::Empty:
		if (GS->Seeds > 0)
		{
			--GS->Seeds; Plant.Plant(); GS->PushMessage(TEXT("Seed planted"));
			MLGAssets::PlaySoundAtLocation(this, MLGAssets::Audio::RepairDone, GetActorLocation(), 0.75f, 1.25f);
		}
		break;
	case EMLGPlantStage::Mature:
	{
		const int32 Gain = HarvestSeeds + (GS->HasGeneTrait(MLGGeneTrait::PHO) ? 1 : 0);
		GS->Seeds += Gain; Plant.Clear(); GS->PushMessage(FString::Printf(TEXT("Harvested: +%d seeds"), Gain));
		MLGAssets::PlaySoundAtLocation(this, MLGAssets::Audio::RepairDone, GetActorLocation(), 0.85f, 1.35f);
		break;
	}
	case EMLGPlantStage::Dead:
		Plant.Clear(); GS->PushMessage(TEXT("Plot cleared"));
		MLGAssets::PlaySoundAtLocation(this, MLGAssets::Audio::RepairTick, GetActorLocation(), 0.7f);
		break;
	default: break;
	}
	RefreshVisual();
}

float AMLGPlantPlot::TakeDamage(float Damage, FDamageEvent const&, AController*, AActor*)
{
	if (!Plant.IsLiving()) return 0.f;
	Plant.Health = FMath::Max(0.f, Plant.Health - Damage * 0.01f);
	if (Plant.Health <= 0.f) Plant.Stage = EMLGPlantStage::Dead;
	return Damage;
}
