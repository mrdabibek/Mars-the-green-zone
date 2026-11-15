#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "MLGCharacter.generated.h"

class UAnimSequence;
class UAudioComponent;
class UCameraComponent;
class UMaterialInstanceDynamic;
class UPointLightComponent;
class USceneComponent;
class USkeletalMeshComponent;
class UStaticMeshComponent;
class UMLGWeaponComponent;

DECLARE_DELEGATE_OneParam(FMLGKitDelegate, int32);

UCLASS()
class MARSLASTGREEN_API AMLGCharacter : public ACharacter
{
	GENERATED_BODY()
public:
	AMLGCharacter();

	UPROPERTY(VisibleAnywhere) UCameraComponent* Cam;
	UPROPERTY(VisibleAnywhere) UMLGWeaponComponent* Weapon;

	// First-person weapon rig & VFX (visible in all builds)
	UPROPERTY(VisibleAnywhere) USceneComponent* WeaponPivot;
	UPROPERTY(VisibleAnywhere) USkeletalMeshComponent* FPArmsMesh;
	UPROPERTY(VisibleAnywhere) USkeletalMeshComponent* FPGunMesh;
	UPROPERTY(VisibleAnywhere) USceneComponent* RifleRoot;
	UPROPERTY(VisibleAnywhere) USceneComponent* MuzzlePoint;
	UPROPERTY(VisibleAnywhere) UStaticMeshComponent* MuzzleFlashMesh;
	UPROPERTY(VisibleAnywhere) UPointLightComponent* MuzzleFlashLight;
	UPROPERTY(VisibleAnywhere) UStaticMeshComponent* TracerBeam;
	UPROPERTY(VisibleAnywhere) UStaticMeshComponent* ImpactFlash;

	UPROPERTY(EditAnywhere, BlueprintReadWrite) float WalkSpeed = 350.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) float SprintSpeed = 560.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) float CrouchSpeed = 200.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) float LookSensitivity = 1.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) bool bToggleCrouch = true;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) float InteractRange = 350.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) float SuitDrainPerSec = 0.16f;      // ~10 min outside from full; untuned
	UPROPERTY(EditAnywhere, BlueprintReadWrite) float SuitRefillPerSec = 5.f;

	UPROPERTY(BlueprintReadOnly) float Health = 100.f;
	UPROPERTY(BlueprintReadOnly) float SuitOxygen = 100.f;
	UPROPERTY(BlueprintReadOnly) bool bDead = false;

	// Interaction & combat HUD feedback
	UPROPERTY(BlueprintReadOnly) FText FocusPrompt;
	UPROPERTY(BlueprintReadOnly) float HoldFraction = 0.f;
	UPROPERTY(BlueprintReadOnly) bool bFocusCanAct = false;
	UPROPERTY(BlueprintReadOnly) float LastDamageTime = -100.f;
	UPROPERTY(BlueprintReadOnly) FVector LastDamageOrigin = FVector::ZeroVector;
	UPROPERTY(BlueprintReadOnly) bool bHasDamageOrigin = false;
	UPROPERTY(BlueprintReadOnly) FString LastHitSourceTag;
	UPROPERTY(BlueprintReadOnly) float HitPunchPitch = 0.f;
	UPROPERTY(BlueprintReadOnly) float HitPunchRoll = 0.f;
	UPROPERTY(BlueprintReadOnly) bool bDyingSequence = false;
	UPROPERTY(BlueprintReadOnly) float DeathSeqTime = 0.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) float DeathSeqDuration = 1.55f;

	bool IsInPressurizedZone() const;
	void ApplySaved(FVector Loc, FRotator Rot, float InHealth, float InSuit, int32 Mag, int32 Reserve);
	void NotifyWeaponFired(const FVector& TargetPoint, bool bHitTarget, bool bCritHit = false, bool bKilledTarget = false);
	void TriggerCameraShake(float Intensity, float Duration);
	FVector GetMuzzleWorldLocation() const;
	virtual float TakeDamage(float Damage, FDamageEvent const& Event, AController* By, AActor* Causer) override;
	virtual void OnJumped_Implementation() override;
	virtual void Landed(const FHitResult& Hit) override;

protected:
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
	virtual void Tick(float Dt) override;
	virtual void SetupPlayerInputComponent(UInputComponent* In) override;

	void BuildFirstPersonRifle();
	void UpdateViewmodel(float Dt, bool bMoving, bool bSprinting);

	bool Frozen() const;
	void MoveForward(float V) { if (!Frozen()) AddMovementInput(GetActorForwardVector(), V); }
	void MoveRight(float V) { if (!Frozen()) AddMovementInput(GetActorRightVector(), V); }
	void Turn(float V);
	void LookUp(float V);
	void KitKey(int32 I);
	void QuickSave();
	void QuickLoad();
	void SprintOn() { bSprint = true; }
	void SprintOff() { bSprint = false; }
	void CrouchPressed();
	void CrouchReleased();
	void InteractPressed();
	void InteractReleased();
	void FirePressed();
	void FireReleased();
	void AimOn();
	void AimOff();
	void ReloadPressed();
	void StartDyingSequence(AActor* Attacker);
	void Die();

	bool bSprint = false, bAim = false, bHolding = false;
	float HoldTime = 0.f, RepairTickSoundTimer = 0.f, MaulPulseTimer = 0.f;
	TWeakObjectPtr<AActor> FatalAttacker;
	float FootstepTimer = 0.f, LowO2HeartbeatTimer = 0.f;
	float AdsAlpha = 0.f, SprintAlpha = 0.f, ReloadAlpha = 0.f, BobTime = 0.f;
	float RecoilKickOffset = 0.f, RecoilKickPitch = 0.f, RecoilKickRoll = 0.f, RecoilRecoverPending = 0.f;
	float FireFovKick = 0.f, CamShakeLeft = 0.f, CamShakeDuration = 0.1f, CamShakeIntensity = 0.f;
	float MuzzleFlashTimer = 0.f, TracerTimer = 0.f, WindVolCurrent = 0.25f;
	FVector2D LookSway = FVector2D::ZeroVector;
	TWeakObjectPtr<AActor> Focus;

	UPROPERTY(Transient) UAudioComponent* WindAudio = nullptr;
	UPROPERTY(Transient) UMaterialInstanceDynamic* RifleCoreMID = nullptr;
	UPROPERTY(Transient) UMaterialInstanceDynamic* TracerMID = nullptr;
	UPROPERTY(Transient) UMaterialInstanceDynamic* MuzzleFlashMID = nullptr;
	UPROPERTY(Transient) UMaterialInstanceDynamic* ImpactMID = nullptr;

	UPROPERTY(Transient) UAnimSequence* FPAnimIdle = nullptr;
	UPROPERTY(Transient) UAnimSequence* FPAnimRun = nullptr;
	UPROPERTY(Transient) UAnimSequence* FPAnimFire = nullptr;
	bool bUsingFPTemplate = false;
	uint8 LastFPAnimState = 255; // 0=idle, 1=run, 2=fire
	float FPFireAnimLeft = 0.f;
};
