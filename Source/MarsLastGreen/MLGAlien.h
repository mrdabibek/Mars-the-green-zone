#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "MLGAlien.generated.h"

class UAnimSequence;
class UPointLightComponent;
class UStaticMeshComponent;
class UMaterialInstanceDynamic;

UENUM()
enum class EMLGAlienState : uint8 { Approach, Telegraph, Cooldown, Stagger, Cover, Dead };

// Raider: fast, fragile pipe-raider. Breaker: slow, tough infrastructure-breaker with a long wind-up; only its wind-up exposes it.
// Gunner: armed flanker; telegraphs an aimed shot (line-of-sight breaks it), retreats to cover between volleys.
UENUM()
enum class EMLGAlienKind : uint8 { Raider, Breaker, Gunner };

UENUM()
enum class EMLGAlienAnimSlot : uint8 { None, Idle, Walk, Run, Telegraph, Stagger, Cover, Dead };

// All fictional, non-gory: they collapse and fade. Loads imported SkeletalMesh + AnimSequences from /Game/Creatures/{Kind}/
// with graceful fallback to primitive sphere Body when assets are absent (e.g. headless/partial builds).
UCLASS()
class MARSLASTGREEN_API AMLGAlien : public ACharacter
{
	GENERATED_BODY()
public:
	AMLGAlien();

	UPROPERTY(EditAnywhere, BlueprintReadWrite) EMLGAlienKind Kind = EMLGAlienKind::Raider;   // set before BeginPlay (deferred spawn)
	UPROPERTY(EditAnywhere, BlueprintReadWrite) float MaxHealth = 60.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) float MoveSpeed = 520.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) float StructureDamage = 15.f;   // per strike / shot
	UPROPERTY(EditAnywhere, BlueprintReadWrite) float PlayerDamage = 12.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) float Reach = 260.f;            // melee: distance to a structure's centre to start a strike
	UPROPERTY(EditAnywhere, BlueprintReadWrite) float Range = 1300.f;           // gunner: shooting distance
	UPROPERTY(EditAnywhere, BlueprintReadWrite) float TelegraphSeconds = 0.7f;  // warning before damage; staggering during it cancels the strike
	UPROPERTY(EditAnywhere, BlueprintReadWrite) float CooldownSeconds = 0.8f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) float StaggerSeconds = 0.45f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) float AggroSeconds = 8.f;       // raider turns on the player this long after being shot
	UPROPERTY(EditAnywhere, BlueprintReadWrite) float MeshYawOffset = 0.f;      // adjust if imported skeletal mesh faces +Y instead of +X
	UPROPERTY(EditAnywhere, BlueprintReadWrite) float DeathHoldDuration = 1.25f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) float DeathSinkDuration = 0.65f;

	UPROPERTY(BlueprintReadOnly) float Health = 60.f;
	UPROPERTY(BlueprintReadOnly) EMLGAlienState State = EMLGAlienState::Approach;
	UPROPERTY(BlueprintReadOnly) bool bUsingSkeletalMesh = false;
	UPROPERTY(VisibleAnywhere) UStaticMeshComponent* Body;
	UPROPERTY(VisibleAnywhere) UStaticMeshComponent* AimBeam;
	UPROPERTY(VisibleAnywhere) UStaticMeshComponent* PlasmaBolt;
	UPROPERTY(VisibleAnywhere) UStaticMeshComponent* ShockwaveRing;
	UPROPERTY(VisibleAnywhere) UStaticMeshComponent* WeakspotGlow;
	UPROPERTY(VisibleAnywhere) UPointLightComponent* MuzzleLight;
	UPROPERTY(VisibleAnywhere) UPointLightComponent* FillLight;   // faint always-on glow so attackers stay readable at dusk (see Docs/PROGRESS.md)

	void AlertToPlayer(float Seconds);
	void SwarmDownedPlayer(class AMLGCharacter* DownedPlayer);
	bool IsAlive() const { return State != EMLGAlienState::Dead; }
	bool IsTelegraphing() const { return State == EMLGAlienState::Telegraph; }
	bool IsAimingAtPlayer() const { return Kind == EMLGAlienKind::Gunner && IsTelegraphing() && Target.IsValid() && Target->IsA<ACharacter>(); }
	bool IsThreateningPlayer(const AActor* PlayerActor) const;
	FString GetTelegraphWarningText() const;
	static const TCHAR* GetAttackSourceTag(EMLGAlienKind InKind);
	static float ComputePlayerTargetPriority(EMLGAlienKind InKind, float Dist2D, bool bHasLOS, bool bAggroActive);
	bool ShouldShockwaveHitPlayer(const class AMLGCharacter* Player) const;
	bool IsLunging() const { return bLunging && LungeTimer > 0.f; }
	bool HasSkeletalVisual() const { return bUsingSkeletalMesh; }
	bool WasLastHitCrit() const { return bLastHitWasCrit; }
	bool WouldPointHitCrit(const FHitResult& HitInfo) const;
	static float ComputeDamageMultiplier(EMLGAlienKind InKind, EMLGAlienState InState, const FVector& ActorLoc, float CapsuleHalfHeight, const FHitResult* HitInfo, bool& bOutCrit);
	EMLGAlienAnimSlot GetCurrentAnimSlot() const { return CurrentAnimSlot; }
	FString TargetName() const;
	AActor* GetCurrentTarget() const { return Target.Get(); }
	bool HasLOS(const AActor* T) const;          // clear line from this alien to the target
	void DebugSetTarget(AActor* T) { Target = T; }   // tests only
	void ForcePickTarget() { PickTarget(); }
	void ForceEnterState(EMLGAlienState S) { Enter(S); }
	void ForceStrike() { Strike(); }
	bool FindCover(FVector& Out);                // nearest navigable spot (within ~4.5 m) hidden from the current target
	virtual float TakeDamage(float Damage, FDamageEvent const& Event, AController* By, AActor* Causer) override;

protected:
	virtual void BeginPlay() override;
	virtual void Tick(float Dt) override;
	void InitVisualsAndAnims();
	void PickTarget();
	void Enter(EMLGAlienState S);
	void PlayAnimSlot(EMLGAlienAnimSlot Slot, bool bLoop, float TargetDuration = 0.f);
	void UpdateBeam(const FVector& Start, const FVector& End, float RadiusScale, const FLinearColor& Color);
	FVector GetMuzzleLocation() const;
	FVector GetWeakspotLocation() const;
	void UpdateTelegraphVisuals(float Alpha);
	void ApplyDeathPowerDown(float Alpha);
	void SpawnBurstParticles(const FVector& Origin, const FLinearColor& StartCol, const FLinearColor& EndCol, int32 Count, float Speed, float Scale, float MaxLife, float Gravity);
	void UpdateBurstParticles(float Dt);
	void Strike();
	void Die();
	void Tint(const FLinearColor& C);
	bool Blocked(const AActor* A) const;

	struct FBurstParticle
	{
		UStaticMeshComponent* Comp = nullptr;
		UMaterialInstanceDynamic* MID = nullptr;
		FVector Vel = FVector::ZeroVector;
		FLinearColor StartCol = FLinearColor::White;
		FLinearColor EndCol = FLinearColor::Black;
		float BaseScale = 0.08f;
		float Age = 0.f;
		float MaxLife = 0.f;
		float Gravity = 700.f;
	};
	TArray<FBurstParticle> BurstParticles;

	TWeakObjectPtr<AActor> Target;
	FVector Goal = FVector::ZeroVector, CoverSpot = FVector::ZeroVector;
	FVector BaseScale = FVector(0.8f, 0.5f, 0.5f);
	FLinearColor BaseColor = FLinearColor(0.35f, 0.1f, 0.5f);
	float StateTime = 0.f, RetargetLeft = 0.f, AggroUntil = -1.f, LastStagger = -10.f, NoLosTime = 0.f, ShotFlashTimer = 0.f, SlamRingTimer = 0.f, LungeTimer = 0.f;
	float FollowThroughTimer = 0.f, DeathAnimLength = 1.5f, FillLightBaseIntensity = 300.f;
	FVector ShotStartLoc = FVector::ZeroVector, ShotEndLoc = FVector::ZeroVector, SlamRingOrigin = FVector::ZeroVector, LungeDir = FVector::ZeroVector;
	bool bLastHitWasCrit = false, bLunging = false, bLungeHitDealt = false, bDeathPoseLocked = false;
	int32 Volleys = 0;
	EMLGAlienAnimSlot CurrentAnimSlot = EMLGAlienAnimSlot::None;
	TMap<TWeakObjectPtr<AActor>, float> BlockedUntil;   // targets this gunner could not get a line to; ignored for 8 s

	UPROPERTY(Transient) UMaterialInstanceDynamic* MID = nullptr;
	UPROPERTY(Transient) UMaterialInstanceDynamic* BeamMID = nullptr;
	UPROPERTY(Transient) UMaterialInstanceDynamic* BoltMID = nullptr;
	UPROPERTY(Transient) UMaterialInstanceDynamic* SlamRingMID = nullptr;
	UPROPERTY(Transient) UMaterialInstanceDynamic* WeakspotMID = nullptr;
	UPROPERTY(Transient) TArray<UMaterialInstanceDynamic*> SkelMIDs;
	UPROPERTY(Transient) TArray<UStaticMeshComponent*> ParticleComps;

	UPROPERTY(Transient) UAnimSequence* AnimIdle = nullptr;
	UPROPERTY(Transient) UAnimSequence* AnimWalk = nullptr;
	UPROPERTY(Transient) UAnimSequence* AnimRun = nullptr;
	UPROPERTY(Transient) UAnimSequence* AnimTelegraph = nullptr;
	UPROPERTY(Transient) UAnimSequence* AnimHit = nullptr;
	UPROPERTY(Transient) UAnimSequence* AnimDeath = nullptr;
	UPROPERTY(Transient) UAnimSequence* AnimCover = nullptr;
};
