#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "MLGInteractable.h"
#include "MLGPickup.generated.h"

class UMaterialInstanceDynamic;

UENUM(BlueprintType)
enum class EMLGPickupKind : uint8 { RepairParts, Ammo, Seeds, Ice, SeedBank, Oxygen };

// Instant pickup. Supports optional /Game/Environment/SM_Pickup_* meshes with primitive sphere fallback and hover/spin animation.
UCLASS()
class MARSLASTGREEN_API AMLGPickup : public AActor, public IMLGInteractable
{
	GENERATED_BODY()
public:
	AMLGPickup();
	UPROPERTY(EditAnywhere, BlueprintReadWrite) EMLGPickupKind Kind = EMLGPickupKind::RepairParts;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) int32 Amount = 1;
	UPROPERTY(VisibleAnywhere) UStaticMeshComponent* Mesh;
	UPROPERTY(BlueprintReadWrite) bool bIsEmergencyDrop = false;

	bool UsesImportedMesh() const { return bUsingCustomMesh; }
	void TriggerDropPop();
	static const TCHAR* GetMeshPathFor(EMLGPickupKind InKind);

	virtual FText GetPrompt(const AMLGCharacter* Who) const override;
	virtual void Interact(AMLGCharacter* Who) override;
protected:
	virtual void BeginPlay() override;
	virtual void Tick(float Dt) override;

	UPROPERTY(Transient) TArray<UMaterialInstanceDynamic*> SlotMIDs;
	TArray<bool> SlotIsAccent;
	bool bUsingCustomMesh = false;
	FVector BaseLocation = FVector::ZeroVector;
	float HoverPhase = 0.f;
	float DropPopTimer = 0.f;
};
