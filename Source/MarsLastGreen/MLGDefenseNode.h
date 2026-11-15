#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "MLGInteractable.h"
#include "MLGDefenseNode.generated.h"

class UStaticMeshComponent;
class USceneComponent;
class UPointLightComponent;
class UMaterialInstanceDynamic;
class AMLGAlien;

UENUM(BlueprintType)
enum class EMLGDefenseKind : uint8
{
	SentryTurret,   // Costs 2 parts, draws 0.5 battery/s while active, auto-fires at aliens within 16m
	ShockBarrier    // Costs 1 part, zero idle power draw, 180 HP decoy/barrier that pulses shock at nearby melee aliens
};

UENUM(BlueprintType)
enum class EMLGDefenseState : uint8
{
	Empty,
	Active,
	Standby,
	Broken
};

// Predefined exterior defensive pad (no freeform building). Supports deployment, standby power toggling, repair, and AI targeting.
UCLASS()
class MARSLASTGREEN_API AMLGDefenseNode : public AActor, public IMLGInteractable
{
	GENERATED_BODY()
public:
	AMLGDefenseNode();

	UPROPERTY(EditAnywhere, BlueprintReadWrite) EMLGDefenseKind Kind = EMLGDefenseKind::SentryTurret;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) FText DisplayName;
	UPROPERTY(BlueprintReadOnly) EMLGDefenseState DefenseState = EMLGDefenseState::Empty;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) float Integrity = 0.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) float MaxIntegrity = 100.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) int32 BuildPartsCost = 2;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) int32 RepairPartsCost = 1;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) float Range = 1600.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) float DamagePerShot = 14.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) float FireInterval = 1.2f;

	UPROPERTY(VisibleAnywhere) USceneComponent* Root;
	UPROPERTY(VisibleAnywhere) UStaticMeshComponent* BasePad;
	UPROPERTY(VisibleAnywhere) UStaticMeshComponent* StructureMesh;
	UPROPERTY(VisibleAnywhere) USceneComponent* TurretPivot;
	UPROPERTY(VisibleAnywhere) UStaticMeshComponent* TurretHead;
	UPROPERTY(VisibleAnywhere) UStaticMeshComponent* TurretBarrel;
	UPROPERTY(VisibleAnywhere) UStaticMeshComponent* StatusBeacon;
	UPROPERTY(VisibleAnywhere) UStaticMeshComponent* TracerBeam;
	UPROPERTY(VisibleAnywhere) UPointLightComponent* MuzzleLight;

	UFUNCTION(BlueprintPure) bool IsOperational() const { return (DefenseState == EMLGDefenseState::Active || DefenseState == EMLGDefenseState::Standby) && Integrity > 0.f; }
	UFUNCTION(BlueprintPure) bool IsActive() const { return DefenseState == EMLGDefenseState::Active && Integrity > 0.f; }
	UFUNCTION(BlueprintPure) bool DrawsPower() const { return Kind == EMLGDefenseKind::SentryTurret && IsActive(); }
	bool UsesImportedMeshes() const { return bCustomStructure || bCustomTurretHead; }
	static void GetMeshPathsFor(EMLGDefenseKind InKind, const TCHAR*& OutStructurePath, const TCHAR*& OutHeadPath);

	void ApplySavedState(EMLGDefenseState InState, float InIntegrity);

	virtual float TakeDamage(float Damage, FDamageEvent const& Event, AController* By, AActor* Causer) override;
	virtual FText GetPrompt(const AMLGCharacter* Who) const override;
	virtual float GetHoldSeconds() const override;
	virtual bool CanInteract(const AMLGCharacter* Who) const override;
	virtual void Interact(AMLGCharacter* Who) override;

protected:
	virtual void BeginPlay() override;
	virtual void Tick(float Dt) override;

private:
	void RefreshVisuals();
	void TickSentry(float Dt);
	void TickShockBarrier(float Dt);
	bool HasLineOfSight(const AMLGAlien* Alien) const;

	float FireCooldown = 0.f;
	float FlashTimer = 0.f;
	float LockSoundCooldown = 0.f;
	float IdleSweepPhase = 0.f;
	float RecoilOffset = 0.f;
	FVector HeadBaseRelLoc = FVector::ZeroVector;
	TWeakObjectPtr<AMLGAlien> CurrentTarget;
	float TurretMuzzleForward = 55.f;
	float TurretMuzzleZOffset = 0.f;
	EMLGDefenseState LastVisualState = EMLGDefenseState::Broken;
	bool bLastPowered = true;
	bool bCustomStructure = false;
	bool bCustomTurretHead = false;

	UPROPERTY(Transient) UMaterialInstanceDynamic* BeaconMID = nullptr;
	UPROPERTY(Transient) UMaterialInstanceDynamic* StructureMID = nullptr;
	UPROPERTY(Transient) UMaterialInstanceDynamic* TracerMID = nullptr;
	UPROPERTY(Transient) TArray<UMaterialInstanceDynamic*> StructureSlotMIDs;
	UPROPERTY(Transient) TArray<UMaterialInstanceDynamic*> HeadSlotMIDs;
	TArray<bool> StructureIsAccent;
	TArray<bool> HeadIsAccent;
};
