#include "MLGLogTerminal.h"
#include "MLGAssets.h"
#include "MLGGameState.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "UObject/ConstructorHelpers.h"

AMLGLogTerminal::AMLGLogTerminal()
{
	Mesh = CreateDefaultSubobject<UStaticMeshComponent>("Mesh");
	RootComponent = Mesh;
	static ConstructorHelpers::FObjectFinder<UStaticMesh> Cube(TEXT("/Engine/BasicShapes/Cube.Cube"));
	if (Cube.Succeeded()) Mesh->SetStaticMesh(Cube.Object);
	Mesh->SetCollisionProfileName("BlockAll");
	SetActorScale3D(FVector(0.4f, 0.4f, 0.9f));
}

void AMLGLogTerminal::BeginPlay()
{
	Super::BeginPlay();
	if (UStaticMesh* CustomMesh = MLGAssets::LoadOptional<UStaticMesh>(GetMeshPath()))
	{
		const FVector CurrentScale = GetActorScale3D().GetAbs();
		const FBoxSphereBounds B = CustomMesh->GetBounds();
		const bool bLegacyCubeScale = FMath::IsNearlyEqual(CurrentScale.X, 0.4f, 0.05f) && FMath::IsNearlyEqual(CurrentScale.Z, 0.9f, 0.05f);
		const FVector TargetSize = bLegacyCubeScale ? FVector(75.f, 65.f, 135.f) : (CurrentScale * 100.f);
		const FVector Floor = bLegacyCubeScale
			? (GetActorLocation() - GetActorUpVector() * 45.f)
			: (GetActorLocation() - GetActorUpVector() * (TargetSize.Z * 0.5f));
		const float S = bLegacyCubeScale ? MLGAssets::FitUniformScale(B.BoxExtent * 2.f, TargetSize) : CurrentScale.GetMax();
		const FVector LocalBottom(B.Origin.X, B.Origin.Y, B.Origin.Z - B.BoxExtent.Z);

		Mesh->SetStaticMesh(CustomMesh);
		SetActorScale3D(FVector(S));
		if (bLegacyCubeScale)
		{
			SetActorLocation(Floor - GetActorRotation().RotateVector(LocalBottom * S));
		}
		bUsingCustomMesh = true;

		TArray<UMaterialInstanceDynamic*> SlotMIDs;
		TArray<bool> SlotIsAccent;
		MLGAssets::EnsureEmissiveMIDs(Mesh, SlotMIDs, SlotIsAccent);
		MLGAssets::ApplyEmissiveTint(SlotMIDs, SlotIsAccent, FLinearColor(0.04f, 0.12f, 0.18f), FLinearColor(0.18f, 0.85f, 1.0f));
	}
	else if (UMaterialInstanceDynamic* MID = MLGAssets::EnsureColorMID(Mesh, 0))
	{
		MID->SetVectorParameterValue(TEXT("Color"), FLinearColor(0.14f, 0.38f, 0.52f));
	}
}

void AMLGLogTerminal::Interact(AMLGCharacter*)
{
	if (AMLGGameState* GS = GetWorld()->GetGameState<AMLGGameState>()) { GS->Say(LogText); ++GS->LogsRead; }
}
