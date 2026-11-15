#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "MLGWeaponComponent.generated.h"

// Original hitscan rifle with procedural first-person recoil, visible tracer beam, muzzle flash, and audio cues.
UCLASS(ClassGroup = (MLG), meta = (BlueprintSpawnableComponent))
class MARSLASTGREEN_API UMLGWeaponComponent : public UActorComponent
{
	GENERATED_BODY()
public:
	UMLGWeaponComponent() { PrimaryComponentTick.bCanEverTick = true; }

	UPROPERTY(EditAnywhere, BlueprintReadWrite) int32 MagSize = 24;
	UPROPERTY(BlueprintReadWrite) int32 Mag = 24;
	UPROPERTY(BlueprintReadWrite) int32 Reserve = 96;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) float RoundsPerMinute = 540.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) float Damage = 20.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) float Range = 6000.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) float HipSpreadDeg = 0.35f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) float AimSpreadDeg = 0.05f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) float RecoilPitchDeg = 0.55f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) float RecoilYawDeg = 0.16f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) float ReloadSeconds = 2.f;

	UPROPERTY(BlueprintReadOnly) bool bReloading = false;
	UPROPERTY(BlueprintReadOnly) bool bAiming = false;
	float ReloadProgress() const { return bReloading ? 1.f - ReloadLeft / ReloadSeconds : 0.f; }
	float LastHitTime = -100.f, LastShotTime = -100.f, LastCritTime = -100.f, LastKillTime = -100.f;
	float LastHitDamage = 0.f, LastCritDamage = 0.f;

	void StartFire();
	void StopFire() { bTrigger = false; }
	void Reload();
	virtual void TickComponent(float Dt, ELevelTick, FActorComponentTickFunction*) override;

private:
	void FireOnce();
	bool bTrigger = false;
	float Cooldown = 0.f, ReloadLeft = 0.f;
};
