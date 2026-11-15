#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "MLGInteractable.h"
#include "MLGDevice.generated.h"

class UStaticMesh;
class UStaticMeshComponent;
class UMaterialInstanceDynamic;

UENUM(BlueprintType)
enum class EMLGDeviceType : uint8
{
	Power,
	Oxygen,
	WaterPurifier,
	GreenhouseSeal,
	WaterTank,
	Comms,
	Transmitter,
	GeneLab,
	Sabatier,
	CryoRig,
	DropLocker,
	SolarSub,
	CommsSub
};

// Repairable base system. Supports optional imported meshes from /Game/Environment/ with clean primitive fallback and status beacon.
UCLASS()
class MARSLASTGREEN_API AMLGDevice : public AActor, public IMLGInteractable
{
	GENERATED_BODY()
public:
	AMLGDevice();

	UPROPERTY(EditAnywhere, BlueprintReadWrite) EMLGDeviceType Type = EMLGDeviceType::Power;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) FText DisplayName;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) float Integrity = 0.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) float MaxIntegrity = 100.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) float OperationalThreshold = 25.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) float RepairSeconds = 4.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) int32 PartsCost = 1;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) bool bPipeSegment = false;   // WaterTank-type pipe run: uses SM_Dev_WaterPipe
	UPROPERTY(VisibleAnywhere) UStaticMeshComponent* Mesh;
	UPROPERTY(VisibleAnywhere) UStaticMeshComponent* StatusBeacon;

	UFUNCTION(BlueprintPure) bool IsOperational() const { return Integrity >= OperationalThreshold; }
	bool UsesImportedMesh() const { return bUsingCustomMesh; }
	// /Game/Environment/SM_Dev_* mesh for a device type (pipe segments get their own conduit mesh).
	static const TCHAR* GetMeshPathFor(EMLGDeviceType InType, bool bPipe);

	virtual float TakeDamage(float Damage, FDamageEvent const& Event, AController* By, AActor* Causer) override;
	virtual FText GetPrompt(const AMLGCharacter* Who) const override;
	virtual float GetHoldSeconds() const override;
	virtual bool CanInteract(const AMLGCharacter* Who) const override;
	virtual void Interact(AMLGCharacter* Who) override;

protected:
	virtual void BeginPlay() override;
	virtual void Tick(float Dt) override;
	UPROPERTY(Transient) UMaterialInstanceDynamic* MID = nullptr;
	UPROPERTY(Transient) UMaterialInstanceDynamic* BeaconMID = nullptr;
	UPROPERTY(Transient) TArray<UMaterialInstanceDynamic*> SlotMIDs;
	TArray<bool> SlotIsAccent;
	int32 LastShownBand = -1;
	bool bUsingCustomMesh = false;
	float ActionCooldown = 0.f;
	bool bLockerOpened = false;
	void ApplyImportedMesh(UStaticMesh* CustomMesh);
};
