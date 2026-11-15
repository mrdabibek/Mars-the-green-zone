#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "MLGInteractable.h"
#include "MLGModels.h"
#include "MLGPlantPlot.generated.h"

class UStaticMesh;
class UStaticMeshComponent;
class UMaterialInstanceDynamic;

// Greenhouse planter. Supports imported PolyHaven/environment plant meshes with clean primitive cone fallback and status indicator.
UCLASS()
class MARSLASTGREEN_API AMLGPlantPlot : public AActor, public IMLGInteractable
{
	GENERATED_BODY()
public:
	AMLGPlantPlot();

	UPROPERTY(EditAnywhere, BlueprintReadWrite) FMLGPlantModel Plant;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) int32 HarvestSeeds = 2;
	UPROPERTY(VisibleAnywhere) UStaticMeshComponent* Tray;
	UPROPERTY(VisibleAnywhere) UStaticMeshComponent* PlantMesh;
	UPROPERTY(VisibleAnywhere) UStaticMeshComponent* StatusLight;

	bool IsConsuming() const { return Plant.IsLiving() && !Plant.bStalled; }
	bool UsesImportedTray() const { return bUsingCustomTray; }
	static const TCHAR* GetTrayMeshPath() { return TEXT("/Game/Environment/SM_PlantPlot"); }
	static const TCHAR* GetEarlyPlantMeshPath(EMLGPlantStage InStage);

	virtual float TakeDamage(float Damage, FDamageEvent const& Event, AController* By, AActor* Causer) override;
	virtual FText GetPrompt(const AMLGCharacter* Who) const override;
	virtual float GetHoldSeconds() const override;
	virtual bool CanInteract(const AMLGCharacter* Who) const override;
	virtual void Interact(AMLGCharacter* Who) override;

protected:
	virtual void BeginPlay() override;
	virtual void Tick(float Dt) override;
	void RefreshVisual();
	UPROPERTY(Transient) UMaterialInstanceDynamic* PlantMID = nullptr;
	UPROPERTY(Transient) UMaterialInstanceDynamic* StatusMID = nullptr;
	UPROPERTY(Transient) UStaticMesh* FallbackConeMesh = nullptr;
	UPROPERTY(Transient) UStaticMesh* SeedPlantMesh = nullptr;
	UPROPERTY(Transient) UStaticMesh* SeedlingPlantMesh = nullptr;
	UPROPERTY(Transient) UStaticMesh* MaturePlantMesh = nullptr;
	UPROPERTY(Transient) UStaticMesh* ActiveCustomPlantMesh = nullptr;
	UPROPERTY(Transient) TArray<UMaterialInstanceDynamic*> TraySlotMIDs;
	TArray<bool> TraySlotIsAccent;
	bool bUsingCustomTray = false;
	float CustomTrayScale = 1.f;
	float PlantBedLocalZ = 50.f;
	FText StallReason;
	bool bWarnedCritical = false;
};
