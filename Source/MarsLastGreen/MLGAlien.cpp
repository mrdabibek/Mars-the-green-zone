#include "MLGAlien.h"
#include "MLGAssets.h"
#include "MLGCharacter.h"
#include "MLGDefenseNode.h"
#include "MLGDevice.h"
#include "MLGGameState.h"
#include "MLGPlantPlot.h"
#include "AIController.h"
#include "Animation/AnimSequence.h"
#include "Components/CapsuleComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/DamageEvents.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/StaticMesh.h"
#include "EngineUtils.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "NavigationPath.h"
#include "NavigationSystem.h"
#include "UObject/ConstructorHelpers.h"

AMLGAlien::AMLGAlien()
{
	PrimaryActorTick.bCanEverTick = true;
	AIControllerClass = AAIController::StaticClass();
	AutoPossessAI = EAutoPossessAI::PlacedInWorldOrSpawned;
	GetCapsuleComponent()->InitCapsuleSize(30.f, 40.f);
	GetMesh()->SetVisibility(false);

	Body = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Body"));
	Body->SetupAttachment(GetCapsuleComponent());
	Body->SetCollisionProfileName(TEXT("NoCollision"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> Sphere(TEXT("/Engine/BasicShapes/Sphere.Sphere"));
	if (Sphere.Succeeded()) Body->SetStaticMesh(Sphere.Object);

	AimBeam = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("AimBeam"));
	AimBeam->SetupAttachment(GetCapsuleComponent());
	static ConstructorHelpers::FObjectFinder<UStaticMesh> Cylinder(TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
	if (Cylinder.Succeeded()) AimBeam->SetStaticMesh(Cylinder.Object);
	AimBeam->SetUsingAbsoluteLocation(true);
	AimBeam->SetUsingAbsoluteRotation(true);
	AimBeam->SetUsingAbsoluteScale(true);
	AimBeam->SetCollisionProfileName(TEXT("NoCollision"));
	AimBeam->SetCastShadow(false);
	AimBeam->SetVisibility(false);

	PlasmaBolt = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("PlasmaBolt"));
	PlasmaBolt->SetupAttachment(GetCapsuleComponent());
	if (Sphere.Succeeded()) PlasmaBolt->SetStaticMesh(Sphere.Object);
	PlasmaBolt->SetUsingAbsoluteLocation(true);
	PlasmaBolt->SetUsingAbsoluteRotation(true);
	PlasmaBolt->SetUsingAbsoluteScale(true);
	PlasmaBolt->SetCollisionProfileName(TEXT("NoCollision"));
	PlasmaBolt->SetCastShadow(false);
	PlasmaBolt->SetVisibility(false);

	ShockwaveRing = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("ShockwaveRing"));
	ShockwaveRing->SetupAttachment(GetCapsuleComponent());
	if (Cylinder.Succeeded()) ShockwaveRing->SetStaticMesh(Cylinder.Object);
	ShockwaveRing->SetUsingAbsoluteLocation(true);
	ShockwaveRing->SetUsingAbsoluteRotation(true);
	ShockwaveRing->SetUsingAbsoluteScale(true);
	ShockwaveRing->SetCollisionProfileName(TEXT("NoCollision"));
	ShockwaveRing->SetCastShadow(false);
	ShockwaveRing->SetVisibility(false);

	WeakspotGlow = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("WeakspotGlow"));
	WeakspotGlow->SetupAttachment(GetCapsuleComponent());
	if (Sphere.Succeeded()) WeakspotGlow->SetStaticMesh(Sphere.Object);
	WeakspotGlow->SetUsingAbsoluteLocation(true);
	WeakspotGlow->SetUsingAbsoluteRotation(true);
	WeakspotGlow->SetUsingAbsoluteScale(true);
	WeakspotGlow->SetCollisionProfileName(TEXT("NoCollision"));
	WeakspotGlow->SetCastShadow(false);
	WeakspotGlow->SetVisibility(false);

	ParticleComps.Reserve(12);
	for (int32 PIdx = 0; PIdx < 12; ++PIdx)
	{
		UStaticMeshComponent* P = CreateDefaultSubobject<UStaticMeshComponent>(*FString::Printf(TEXT("BurstP_%d"), PIdx));
		P->SetupAttachment(GetCapsuleComponent());
		if (Sphere.Succeeded()) P->SetStaticMesh(Sphere.Object);
		P->SetUsingAbsoluteLocation(true);
		P->SetUsingAbsoluteRotation(true);
		P->SetUsingAbsoluteScale(true);
		P->SetCollisionProfileName(TEXT("NoCollision"));
		P->SetCastShadow(false);
		P->SetVisibility(false);
		ParticleComps.Add(P);
	}

	FillLight = CreateDefaultSubobject<UPointLightComponent>(TEXT("FillLight"));
	FillLight->SetupAttachment(GetCapsuleComponent());
	FillLight->SetMobility(EComponentMobility::Movable);   // static/stationary lights need baked lighting; this level has none
	FillLight->SetRelativeLocation(FVector(0.f, 0.f, 120.f));
	FillLight->SetCastShadows(false);
	FillLight->SetIntensity(30.f);
	FillLight->SetAttenuationRadius(450.f);

	MuzzleLight = CreateDefaultSubobject<UPointLightComponent>(TEXT("MuzzleLight"));
	MuzzleLight->SetupAttachment(GetCapsuleComponent());
	MuzzleLight->SetRelativeLocation(FVector(50.f, 0.f, 50.f));
	MuzzleLight->SetIntensity(7500.f);
	MuzzleLight->SetAttenuationRadius(600.f);
	MuzzleLight->SetLightColor(FColor(255, 190, 70));
	MuzzleLight->SetCastShadows(false);
	MuzzleLight->SetVisibility(false);

	GetCharacterMovement()->bOrientRotationToMovement = true;
	GetCharacterMovement()->RotationRate = FRotator(0, 540, 0);
	bUseControllerRotationYaw = false;
}

void AMLGAlien::BeginPlay()
{
	Super::BeginPlay();
	switch (Kind)   // tier-scaled body size, toughness & damage presets
	{
	case EMLGAlienKind::Breaker:
		MaxHealth = 220.f; MoveSpeed = 150.f; StructureDamage = 45.f; PlayerDamage = 25.f; Reach = 300.f;
		TelegraphSeconds = 1.8f; CooldownSeconds = 1.5f; StaggerSeconds = 1.2f;
		BaseScale = FVector(1.8f, 1.4f, 1.2f); BaseColor = FLinearColor(0.8f, 0.3f, 0.05f);
		GetCapsuleComponent()->InitCapsuleSize(60.f, 70.f);
		break;
	case EMLGAlienKind::Gunner:
		MaxHealth = 70.f; MoveSpeed = 380.f; StructureDamage = 10.f; PlayerDamage = 12.f;
		TelegraphSeconds = 0.9f; CooldownSeconds = 1.2f; StaggerSeconds = 0.5f;
		BaseScale = FVector(0.5f, 0.5f, 1.f); BaseColor = FLinearColor(0.1f, 0.4f, 0.9f);
		GetCapsuleComponent()->InitCapsuleSize(30.f, 70.f);
		break;
	default:
		MaxHealth = 50.f; MoveSpeed = 480.f; StructureDamage = 14.f; PlayerDamage = 12.f;
		break;
	}
	Health = MaxHealth;
	Body->SetRelativeScale3D(BaseScale);
	GetCharacterMovement()->MaxWalkSpeed = MoveSpeed;
	MID = MLGAssets::EnsureColorMID(Body, 0);
	BeamMID = MLGAssets::EnsureColorMID(AimBeam, 0);
	BoltMID = MLGAssets::EnsureColorMID(PlasmaBolt, 0);
	SlamRingMID = MLGAssets::EnsureColorMID(ShockwaveRing, 0);
	WeakspotMID = MLGAssets::EnsureColorMID(WeakspotGlow, 0);
	BurstParticles.SetNum(ParticleComps.Num());
	for (int32 PIdx = 0; PIdx < ParticleComps.Num(); ++PIdx)
	{
		BurstParticles[PIdx].Comp = ParticleComps[PIdx];
		BurstParticles[PIdx].MID = ParticleComps[PIdx] ? MLGAssets::EnsureColorMID(ParticleComps[PIdx], 0) : nullptr;
		BurstParticles[PIdx].MaxLife = 0.f;
	}
	InitVisualsAndAnims();
	Tint(BaseColor);
	// Readability fill: kind colour washed toward white; bigger bodies get more light. Candela values chosen by rendered comparison.
	FillLightBaseIntensity = Kind == EMLGAlienKind::Breaker ? 900.f : Kind == EMLGAlienKind::Gunner ? 400.f : 300.f;
	FillLight->SetLightColor(FLinearColor::LerpUsingHSV(BaseColor, FLinearColor::White, 0.45f).ToFColor(true));
	FillLight->SetIntensity(FillLightBaseIntensity);
	FillLight->SetAttenuationRadius(Kind == EMLGAlienKind::Breaker ? 750.f : 450.f);
	FillLight->SetRelativeLocation(FVector(0.f, 0.f, Kind == EMLGAlienKind::Breaker ? 220.f : 120.f));
	Enter(EMLGAlienState::Approach);
}

void AMLGAlien::InitVisualsAndAnims()
{
	const TCHAR* KindDir = Kind == EMLGAlienKind::Breaker ? TEXT("Breaker") : Kind == EMLGAlienKind::Gunner ? TEXT("Gunner") : TEXT("Raider");
	auto LoadCreatureAnim = [KindDir](const TCHAR* Action, const TCHAR* AltAction = nullptr) -> UAnimSequence*
	{
		const FString P1 = FString::Printf(TEXT("/Game/Creatures/%s/AS_%s_%s"), KindDir, KindDir, Action);
		if (UAnimSequence* A = MLGAssets::LoadOptional<UAnimSequence>(*P1)) return A;
		if (AltAction)
		{
			const FString P2 = FString::Printf(TEXT("/Game/Creatures/%s/AS_%s_%s"), KindDir, KindDir, AltAction);
			if (UAnimSequence* A = MLGAssets::LoadOptional<UAnimSequence>(*P2)) return A;
		}
		const FString P3 = FString::Printf(TEXT("/Game/Creatures/%s/%s_%s"), KindDir, KindDir, Action);
		return MLGAssets::LoadOptional<UAnimSequence>(*P3);
	};

	const FString MeshPath = FString::Printf(TEXT("/Game/Creatures/%s/SK_Alien_%s"), KindDir, KindDir);
	USkeletalMesh* Skel = MLGAssets::LoadOptional<USkeletalMesh>(*MeshPath);
	if (!Skel)
	{
		const FString AltMeshPath = FString::Printf(TEXT("/Game/Creatures/%s/SK_%s"), KindDir, KindDir);
		Skel = MLGAssets::LoadOptional<USkeletalMesh>(*AltMeshPath);
	}

	if (Skel)
	{
		bUsingSkeletalMesh = true;
		GetMesh()->SetSkeletalMesh(Skel);
		GetMesh()->SetAnimationMode(EAnimationMode::AnimationSingleNode);
		GetMesh()->SetRelativeLocation(FVector(0.f, 0.f, -GetCapsuleComponent()->GetScaledCapsuleHalfHeight()));
		GetMesh()->SetRelativeRotation(FRotator(0.f, MeshYawOffset, 0.f));
		GetMesh()->SetVisibility(true);
		Body->SetVisibility(false);

		if (Skel->GetPhysicsAsset())
		{
			GetMesh()->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
			GetMesh()->SetCollisionResponseToChannel(ECC_Visibility, ECR_Block);
			GetCapsuleComponent()->SetCollisionResponseToChannel(ECC_Visibility, ECR_Ignore);
		}
		else
		{
			GetCapsuleComponent()->SetCollisionResponseToChannel(ECC_Visibility, ECR_Block);
		}

		const int32 NumMats = GetMesh()->GetNumMaterials();
		for (int32 MIdx = 0; MIdx < NumMats; ++MIdx)
		{
			if (UMaterialInstanceDynamic* SkelMID = MLGAssets::EnsureColorMID(GetMesh(), MIdx))
			{
				SkelMIDs.Add(SkelMID);
			}
		}

		AnimIdle = LoadCreatureAnim(TEXT("Idle"));
		AnimWalk = LoadCreatureAnim(TEXT("Walk"));
		AnimRun = LoadCreatureAnim(TEXT("Run"));
		AnimTelegraph = LoadCreatureAnim(TEXT("Telegraph"), TEXT("Attack"));
		AnimHit = LoadCreatureAnim(TEXT("Hit"), TEXT("Stagger"));
		AnimDeath = LoadCreatureAnim(TEXT("Death"), TEXT("Dead"));
		if (Kind == EMLGAlienKind::Gunner) AnimCover = LoadCreatureAnim(TEXT("Cover"));
		DeathAnimLength = AnimDeath ? FMath::Clamp(AnimDeath->GetPlayLength(), 0.6f, 2.5f) : 1.2f;
	}
	else
	{
		bUsingSkeletalMesh = false;
		DeathAnimLength = 1.2f;
		GetMesh()->SetVisibility(false);
		Body->SetVisibility(true);
		GetCapsuleComponent()->SetCollisionResponseToChannel(ECC_Visibility, ECR_Block);
	}
}

void AMLGAlien::PlayAnimSlot(EMLGAlienAnimSlot Slot, bool bLoop, float TargetDuration)
{
	if (State == EMLGAlienState::Dead && Slot != EMLGAlienAnimSlot::Dead)
	{
		return;
	}
	if (!bUsingSkeletalMesh)
	{
		CurrentAnimSlot = Slot;
		return;
	}
	UAnimSequence* Seq = nullptr;
	switch (Slot)
	{
	case EMLGAlienAnimSlot::Idle:      Seq = AnimIdle; break;
	case EMLGAlienAnimSlot::Walk:      Seq = AnimWalk ? AnimWalk : AnimIdle; break;
	case EMLGAlienAnimSlot::Run:       Seq = AnimRun ? AnimRun : (AnimWalk ? AnimWalk : AnimIdle); break;
	case EMLGAlienAnimSlot::Telegraph: Seq = AnimTelegraph ? AnimTelegraph : AnimIdle; break;
	case EMLGAlienAnimSlot::Stagger:   Seq = AnimHit ? AnimHit : AnimIdle; break;
	case EMLGAlienAnimSlot::Cover:     Seq = AnimCover ? AnimCover : AnimIdle; break;
	case EMLGAlienAnimSlot::Dead:      Seq = AnimDeath ? AnimDeath : AnimIdle; break;
	default: break;
	}
	if (Slot == CurrentAnimSlot && bLoop) return;
	CurrentAnimSlot = Slot;
	if (!Seq) return;

	if (Slot == EMLGAlienAnimSlot::Dead)
	{
		bDeathPoseLocked = false;
	}
	GetMesh()->PlayAnimation(Seq, bLoop);
	float Rate = 1.f;
	const float Len = Seq->GetPlayLength();
	if (TargetDuration > 0.05f && Len > 0.05f)
	{
		Rate = FMath::Clamp(Len / TargetDuration, 0.35f, 3.0f);
	}
	GetMesh()->SetPlayRate(Rate);
}

void AMLGAlien::Enter(EMLGAlienState S)
{
	State = S;
	StateTime = 0.f;
	switch (S)
	{
	case EMLGAlienState::Approach:
		bLunging = false;
		LungeTimer = 0.f;
		FollowThroughTimer = 0.f;
		WeakspotGlow->SetVisibility(false);
		if (ShotFlashTimer <= 0.f) MuzzleLight->SetVisibility(false);
		PlayAnimSlot(EMLGAlienAnimSlot::Idle, true);
		break;
	case EMLGAlienState::Telegraph:
	{
		bLunging = false;
		LungeTimer = 0.f;
		FollowThroughTimer = 0.f;
		// Stretch clip so the animation's windup apex aligns with TelegraphSeconds, leaving the strike follow-through right after Strike()
		const float ApexFrac = Kind == EMLGAlienKind::Breaker ? 0.66f : Kind == EMLGAlienKind::Gunner ? 0.78f : 0.55f;
		PlayAnimSlot(EMLGAlienAnimSlot::Telegraph, false, TelegraphSeconds / ApexFrac);
		UpdateTelegraphVisuals(0.f);
		MuzzleLight->SetVisibility(true);
		break;
	}
	case EMLGAlienState::Cooldown:
		WeakspotGlow->SetVisibility(false);
		if (ShotFlashTimer <= 0.f) MuzzleLight->SetVisibility(false);
		if (FollowThroughTimer <= 0.f) PlayAnimSlot(EMLGAlienAnimSlot::Idle, true);
		break;
	case EMLGAlienState::Stagger:
		bLunging = false;
		LungeTimer = 0.f;
		FollowThroughTimer = 0.f;
		AimBeam->SetVisibility(false);
		WeakspotGlow->SetVisibility(false);
		MuzzleLight->SetVisibility(false);
		PlayAnimSlot(EMLGAlienAnimSlot::Stagger, false, StaggerSeconds);
		break;
	case EMLGAlienState::Cover:
		bLunging = false;
		LungeTimer = 0.f;
		FollowThroughTimer = 0.f;
		WeakspotGlow->SetVisibility(false);
		PlayAnimSlot(EMLGAlienAnimSlot::Cover, true);
		break;
	case EMLGAlienState::Dead:
		bLunging = false;
		LungeTimer = 0.f;
		FollowThroughTimer = 0.f;
		AimBeam->SetVisibility(false);
		WeakspotGlow->SetVisibility(false);
		MuzzleLight->SetVisibility(false);
		PlayAnimSlot(EMLGAlienAnimSlot::Dead, false, DeathAnimLength);
		break;
	}
}

void AMLGAlien::Tint(const FLinearColor& C)
{
	if (MID) MID->SetVectorParameterValue(TEXT("Color"), C);
	if (bUsingSkeletalMesh)
	{
		if (State == EMLGAlienState::Dead) return;
		const bool bHighlight = (State == EMLGAlienState::Telegraph || State == EMLGAlienState::Stagger);
		const float EmissiveBoost = State == EMLGAlienState::Telegraph ? 1.25f : 0.65f;
		const FLinearColor Emissive = bHighlight ? C * EmissiveBoost : FLinearColor::Black;
		for (UMaterialInstanceDynamic* SM : SkelMIDs)
		{
			if (SM) SM->SetVectorParameterValue(TEXT("EmissiveColor"), Emissive);
		}
	}
}

const TCHAR* AMLGAlien::GetAttackSourceTag(EMLGAlienKind InKind)
{
	switch (InKind)
	{
	case EMLGAlienKind::Breaker: return TEXT("BREAKER SHOCKWAVE");
	case EMLGAlienKind::Gunner:  return TEXT("GUNNER PLASMA");
	default:                     return TEXT("RAIDER LUNGE");
	}
}

FString AMLGAlien::GetTelegraphWarningText() const
{
	switch (Kind)
	{
	case EMLGAlienKind::Breaker: return TEXT("BREAKER SHOCKWAVE // [SPACE] JUMP OR HIT CORE");
	case EMLGAlienKind::Gunner:  return TEXT("TARGETED // BREAK LOS");
	default:                     return TEXT("RAIDER LUNGE // SHOOT TO STAGGER");
	}
}

bool AMLGAlien::IsThreateningPlayer(const AActor* PlayerActor) const
{
	if (!IsAlive() || !IsTelegraphing() || !PlayerActor) return false;
	if (Target.Get() == PlayerActor) return true;
	const float Dist2D = FVector::Dist2D(PlayerActor->GetActorLocation(), GetActorLocation());
	if (Kind == EMLGAlienKind::Breaker && Dist2D <= 500.f) return true;
	if (Kind == EMLGAlienKind::Raider && Dist2D <= 380.f) return true;
	return false;
}

float AMLGAlien::ComputePlayerTargetPriority(EMLGAlienKind InKind, float Dist2D, bool bHasLOS, bool bAggroActive)
{
	if (InKind == EMLGAlienKind::Gunner)
	{
		return (bAggroActive || (Dist2D < 2500.f && bHasLOS)) ? 5.f : 1.f;
	}
	if (InKind == EMLGAlienKind::Breaker)
	{
		return (Dist2D <= 420.f) ? 4.5f : 0.f;
	}
	// Raider: targets player within 900 cm if unobstructed or when shot (AggroActive)
	if (bAggroActive) return 5.f;
	if (Dist2D <= 900.f && bHasLOS) return 4.5f;
	if (Dist2D < 500.f) return 3.f;
	return 1.f;
}

bool AMLGAlien::ShouldShockwaveHitPlayer(const AMLGCharacter* Player) const
{
	if (!Player || Player->bDead) return false;
	const float Dist2D = FVector::Dist2D(Player->GetActorLocation(), GetActorLocation());
	if (Dist2D > 350.f) return false;
	const float DeltaZ = FMath::Abs(Player->GetActorLocation().Z - GetActorLocation().Z);
	if (DeltaZ >= 110.f) return false;
	if (const UCharacterMovementComponent* MoveComp = Player->GetCharacterMovement())
	{
		// Jumping over the shockwave avoids damage when airborne with upward jump velocity or elevated above ground level
		if (!MoveComp->IsMovingOnGround() && (Player->GetVelocity().Z > 80.f || (Player->GetActorLocation().Z - GetActorLocation().Z) > 55.f))
		{
			return false;
		}
		if (MoveComp->IsMovingOnGround()) return true;
	}
	return DeltaZ < 110.f;
}

FVector AMLGAlien::GetMuzzleLocation() const
{
	if (bUsingSkeletalMesh)
	{
		if (GetMesh()->DoesSocketExist(TEXT("Muzzle"))) return GetMesh()->GetSocketLocation(TEXT("Muzzle"));
		if (GetMesh()->DoesSocketExist(TEXT("muzzle"))) return GetMesh()->GetSocketLocation(TEXT("muzzle"));
		if (GetMesh()->DoesSocketExist(TEXT("head"))) return GetMesh()->GetSocketLocation(TEXT("head"));
	}
	return GetActorLocation() + GetActorForwardVector() * 45.f + FVector(0.f, 0.f, 52.f);
}

FVector AMLGAlien::GetWeakspotLocation() const
{
	if (bUsingSkeletalMesh && GetMesh())
	{
		static const FName RaiderBones[] = { TEXT("Head_1"), TEXT("Head_0"), TEXT("head"), TEXT("Spine_3") };
		static const FName BreakerBones[] = { TEXT("Spine_2"), TEXT("Head_0"), TEXT("Head_1"), TEXT("Spine_1") };
		static const FName GunnerBones[] = { TEXT("head"), TEXT("muzzle"), TEXT("neck_01"), TEXT("spine_03") };
		const FName* List = Kind == EMLGAlienKind::Breaker ? BreakerBones : Kind == EMLGAlienKind::Gunner ? GunnerBones : RaiderBones;
		for (int32 I = 0; I < 4; ++I)
		{
			if (GetMesh()->GetBoneIndex(List[I]) != INDEX_NONE || GetMesh()->DoesSocketExist(List[I]))
			{
				return GetMesh()->GetSocketLocation(List[I]);
			}
		}
	}
	const float HalfH = GetCapsuleComponent()->GetScaledCapsuleHalfHeight();
	const float Fwd = Kind == EMLGAlienKind::Breaker ? 45.f : 26.f;
	return GetActorLocation() + GetActorForwardVector() * Fwd + FVector(0.f, 0.f, HalfH * 0.55f);
}

void AMLGAlien::UpdateTelegraphVisuals(float Alpha)
{
	const float Clamped = FMath::Clamp(Alpha, 0.f, 1.f);
	const float Pulse = 0.65f + 0.35f * FMath::Abs(FMath::Sin(StateTime * (Kind == EMLGAlienKind::Gunner ? 26.f : 18.f)));
	const FVector WeakLoc = GetWeakspotLocation();
	FLinearColor GlowCol;
	float BaseLight = 4500.f;
	float BaseRadius = 0.14f;
	if (Kind == EMLGAlienKind::Breaker)
	{
		GlowCol = FMath::Lerp(FLinearColor(1.f, 0.65f, 0.08f), FLinearColor(1.f, 0.96f, 0.45f), Clamped) * (1.8f + 1.6f * Clamped) * Pulse;
		BaseLight = 6500.f;
		BaseRadius = 0.34f + 0.20f * Clamped;
	}
	else if (Kind == EMLGAlienKind::Gunner)
	{
		GlowCol = FMath::Lerp(FLinearColor(1.f, 0.42f, 0.06f), FLinearColor(1.f, 0.14f, 0.04f), Clamped) * (1.6f + 1.4f * Clamped) * Pulse;
		BaseLight = 5500.f;
		BaseRadius = 0.14f + 0.10f * Clamped;
	}
	else
	{
		GlowCol = FMath::Lerp(FLinearColor(1.f, 0.28f, 0.04f), FLinearColor(1.f, 0.68f, 0.15f), Clamped) * (1.5f + 1.2f * Clamped) * Pulse;
		BaseLight = 4500.f;
		BaseRadius = 0.15f + 0.08f * Clamped;
	}

	if (WeakspotGlow)
	{
		WeakspotGlow->SetWorldLocation(WeakLoc);
		WeakspotGlow->SetWorldScale3D(FVector(BaseRadius * (0.85f + 0.35f * Pulse)));
		if (WeakspotMID) WeakspotMID->SetVectorParameterValue(TEXT("Color"), GlowCol);
		WeakspotGlow->SetVisibility(true);
	}
	MuzzleLight->SetWorldLocation(Kind == EMLGAlienKind::Gunner ? GetMuzzleLocation() : WeakLoc);
	MuzzleLight->SetLightColor(GlowCol.ToFColor(true));
	MuzzleLight->SetIntensity(BaseLight * (0.65f + 0.85f * Clamped) * Pulse);
	MuzzleLight->SetVisibility(true);
}

void AMLGAlien::ApplyDeathPowerDown(float Alpha)
{
	const float A = FMath::Clamp(Alpha, 0.f, 1.f);
	const FLinearColor DeadBody = FMath::Lerp(BaseColor * 0.55f, FLinearColor(0.06f, 0.06f, 0.07f), A);
	if (MID) MID->SetVectorParameterValue(TEXT("Color"), DeadBody);
	if (bUsingSkeletalMesh)
	{
		// Negative offset cancels the additive sheen_plus_floor term in M_Alien_* materials so corpses look powered down
		const FLinearColor Emissive = FMath::Lerp(BaseColor * 0.25f, FLinearColor(-0.15f, -0.15f, -0.15f), A);
		for (UMaterialInstanceDynamic* SM : SkelMIDs)
		{
			if (!SM) continue;
			SM->SetVectorParameterValue(TEXT("Color"), DeadBody);
			SM->SetVectorParameterValue(TEXT("EmissiveColor"), Emissive);
		}
	}
	if (FillLight)
	{
		const float Int = FillLightBaseIntensity * (1.f - A);
		FillLight->SetIntensity(Int);
		if (Int <= 5.f) FillLight->SetVisibility(false);
	}
}

void AMLGAlien::SpawnBurstParticles(const FVector& Origin, const FLinearColor& StartCol, const FLinearColor& EndCol, int32 Count, float Speed, float Scale, float MaxLife, float Gravity)
{
	if (BurstParticles.Num() == 0) return;
	int32 Spawned = 0;
	for (int32 Pass = 0; Pass < 2 && Spawned < Count; ++Pass)
	{
		for (FBurstParticle& P : BurstParticles)
		{
			if (Spawned >= Count) break;
			if (Pass == 0 && P.MaxLife > 0.f) continue; // prefer free slots first
			if (!P.Comp) continue;
			const FVector Dir = FMath::VRand();
			const float Spd = Speed * FMath::FRandRange(0.45f, 1.15f);
			P.Vel = Dir * Spd + FVector(0.f, 0.f, Speed * FMath::FRandRange(0.15f, 0.55f));
			P.StartCol = StartCol;
			P.EndCol = EndCol;
			P.BaseScale = Scale * FMath::FRandRange(0.65f, 1.35f);
			P.Age = 0.f;
			P.MaxLife = FMath::Max(0.08f, MaxLife * FMath::FRandRange(0.75f, 1.2f));
			P.Gravity = Gravity;
			P.Comp->SetWorldLocation(Origin + Dir * FMath::FRandRange(4.f, 18.f));
			P.Comp->SetWorldScale3D(FVector(P.BaseScale));
			if (P.MID) P.MID->SetVectorParameterValue(TEXT("Color"), StartCol);
			P.Comp->SetVisibility(true);
			++Spawned;
		}
	}
}

void AMLGAlien::UpdateBurstParticles(float Dt)
{
	for (FBurstParticle& P : BurstParticles)
	{
		if (P.MaxLife <= 0.f || !P.Comp) continue;
		P.Age += Dt;
		if (P.Age >= P.MaxLife)
		{
			P.MaxLife = 0.f;
			P.Comp->SetVisibility(false);
			continue;
		}
		P.Vel.Z -= P.Gravity * Dt;
		P.Comp->SetWorldLocation(P.Comp->GetComponentLocation() + P.Vel * Dt);
		const float A = P.Age / P.MaxLife;
		P.Comp->SetWorldScale3D(FVector(P.BaseScale * (1.f - 0.78f * A)));
		if (P.MID)
		{
			P.MID->SetVectorParameterValue(TEXT("Color"), FMath::Lerp(P.StartCol, P.EndCol, A));
		}
	}
}

void AMLGAlien::UpdateBeam(const FVector& Start, const FVector& End, float RadiusScale, const FLinearColor& Color)
{
	const FVector Delta = End - Start;
	const float Len = Delta.Size();
	if (Len <= 1.f)
	{
		AimBeam->SetVisibility(false);
		return;
	}
	AimBeam->SetWorldLocation((Start + End) * 0.5f);
	AimBeam->SetWorldRotation(FRotationMatrix::MakeFromZ(Delta / Len).Rotator());
	AimBeam->SetWorldScale3D(FVector(RadiusScale, RadiusScale, Len / 100.f));
	if (BeamMID) BeamMID->SetVectorParameterValue(TEXT("Color"), Color);
	AimBeam->SetVisibility(true);
}

FString AMLGAlien::TargetName() const
{
	AActor* T = Target.Get();
	if (!T) return TEXT("none");
	if (const AMLGDevice* D = Cast<AMLGDevice>(T)) return D->DisplayName.ToString();
	if (const AMLGDefenseNode* Def = Cast<AMLGDefenseNode>(T)) return Def->DisplayName.ToString();
	return T->IsA<ACharacter>() ? TEXT("player") : T->GetName();
}

static bool StillWorthAttacking(const AActor* T)
{
	if (!IsValid(T)) return false;
	if (const AMLGDevice* D = Cast<AMLGDevice>(T)) return D->Integrity > 0.f && D->Type != EMLGDeviceType::Transmitter;   // wrecked devices are not re-attacked
	if (const AMLGDefenseNode* Def = Cast<AMLGDefenseNode>(T)) return Def->IsOperational();
	if (const AMLGPlantPlot* P = Cast<AMLGPlantPlot>(T)) return P->Plant.IsLiving();
	if (const AMLGCharacter* C = Cast<AMLGCharacter>(T)) return !C->bDead;
	return false;
}

static AMLGCharacter* FindPlayerCharacter(UWorld* W, AActor* Candidate = nullptr)
{
	if (AMLGCharacter* C = Cast<AMLGCharacter>(Candidate)) return C;
	if (!W) return nullptr;
	if (AMLGCharacter* C = Cast<AMLGCharacter>(UGameplayStatics::GetPlayerPawn(W, 0))) return C;
	for (TActorIterator<AMLGCharacter> It(W); It; ++It)
	{
		if (IsValid(*It)) return *It;
	}
	return nullptr;
}

bool AMLGAlien::Blocked(const AActor* A) const
{
	const float* U = BlockedUntil.Find(const_cast<AActor*>(A));
	return U && GetWorld()->GetTimeSeconds() < *U;
}

bool AMLGAlien::HasLOS(const AActor* T) const
{
	if (!T) return false;
	FHitResult H;
	FCollisionQueryParams P(SCENE_QUERY_STAT(MLGAlienLOS), false, this);
	const FVector S = GetActorLocation() + FVector(0, 0, 40.f);
	const FVector E = T->GetActorLocation() + FVector(0, 0, T->IsA<ACharacter>() ? 40.f : 30.f);
	return !GetWorld()->LineTraceSingleByChannel(H, S, E, ECC_Visibility, P) || H.GetActor() == T;
}

bool AMLGAlien::FindCover(FVector& Out)
{
	AActor* T = Target.Get();
	UNavigationSystemV1* Nav = FNavigationSystem::GetCurrent<UNavigationSystemV1>(GetWorld());
	if (!T || !Nav) return false;
	float Best = 1e9f;
	bool bFound = false;
	for (int32 I = 0; I < 8; ++I)
	{
		FNavLocation NL;
		FHitResult H;
		FCollisionQueryParams P(SCENE_QUERY_STAT(MLGCover), false, this);
		if (!Nav->ProjectPointToNavigation(GetActorLocation() + FRotator(0, I * 45.f, 0).RotateVector(FVector(450.f, 0, 0)), NL, FVector(100.f, 100.f, 100.f))) continue;
		if (GetWorld()->LineTraceSingleByChannel(H, NL.Location + FVector(0, 0, 60.f), T->GetActorLocation(), ECC_Visibility, P) && H.GetActor() != T)
		{
			const float D = FVector::Dist(NL.Location, GetActorLocation());
			if (D < Best) { Best = D; Out = NL.Location; bFound = true; }
		}
	}
	return bFound;
}

// Raider: player within 900cm unobstructed (or when shot) > water tank/pipe > shock barrier decoy > greenhouse equipment > living plants > power/oxygen.
// Breaker: player within 420cm > infrastructure (water line, greenhouse equipment, active turrets/barriers); ignores plants.
// Gunner: player within 25m unobstructed > greenhouse equipment (the flank) > water line / active turrets.
void AMLGAlien::PickTarget()
{
	UWorld* W = GetWorld();
	UNavigationSystemV1* Nav = FNavigationSystem::GetCurrent<UNavigationSystemV1>(W);
	AActor* Old = Target.Get();
	AActor* Best = nullptr;
	float BestScore = -1e9f;
	auto Consider = [&](AActor* A, float Prio)
	{
		if (Prio <= 0.f || Blocked(A)) return;
		if (!Nav)
		{
			// Fallback for transient unit-test worlds without a navigation system
			const float Dist = FVector::Dist2D(GetActorLocation(), A->GetActorLocation());
			const float Score = Prio * 10000.f - Dist + (A == Old ? 300.f : 0.f);
			if (Score > BestScore) { BestScore = Score; Best = A; Goal = A->GetActorLocation(); }
			return;
		}
		FNavLocation NL;
		// Project from ground level with a small vertical extent: otherwise the goal snaps onto the roof of the device block.
		FVector Ground = A->GetActorLocation(); Ground.Z = 0.f;
		if (!Nav->ProjectPointToNavigation(Ground, NL, FVector(300.f, 300.f, 60.f))) return;
		UNavigationPath* P = UNavigationSystemV1::FindPathToLocationSynchronously(W, GetActorLocation(), NL.Location, this);
		if (!P || !P->IsValid() || P->PathPoints.Num() < 2) return;
		const FVector End = P->PathPoints.Last();
		if (P->IsPartial() && FVector::Dist2D(End, A->GetActorLocation()) > Reach) return;
		const float Score = Prio * 10000.f - P->GetPathLength() + (A == Old ? 300.f : 0.f);
		if (Score > BestScore) { BestScore = Score; Best = A; Goal = End; }
	};
	for (TActorIterator<AMLGDevice> It(W); It; ++It)
	{
		if (!StillWorthAttacking(*It)) continue;
		const bool bTank = It->Type == EMLGDeviceType::WaterTank, bGh = It->Type == EMLGDeviceType::GreenhouseSeal || It->Type == EMLGDeviceType::WaterPurifier;
		float Prio;
		switch (Kind)
		{
		case EMLGAlienKind::Breaker: Prio = bTank ? 4.f : bGh ? 3.f : 2.5f; break;
		case EMLGAlienKind::Gunner:  Prio = bGh ? 4.f : bTank ? 3.f : 2.f; break;
		default:                     Prio = bTank ? 4.f : bGh ? 3.f : 1.5f; break;
		}
		Consider(*It, Prio);
	}
	for (TActorIterator<AMLGDefenseNode> It(W); It; ++It)
	{
		if (!StillWorthAttacking(*It)) continue;
		const float D = FVector::Dist2D(It->GetActorLocation(), GetActorLocation());
		float Prio = 2.0f;
		if (It->Kind == EMLGDefenseKind::ShockBarrier)
		{
			Prio = (Kind != EMLGAlienKind::Gunner && D < 1000.f) ? 3.6f : 2.2f;
		}
		else
		{
			Prio = (Kind == EMLGAlienKind::Breaker || Kind == EMLGAlienKind::Gunner) ? 3.2f : 2.2f;
		}
		Consider(*It, Prio);
	}
	if (Kind != EMLGAlienKind::Breaker)
		for (TActorIterator<AMLGPlantPlot> It(W); It; ++It) if (StillWorthAttacking(*It)) Consider(*It, Kind == EMLGAlienKind::Gunner ? 2.5f : 2.f);
	if (AMLGCharacter* Pl = FindPlayerCharacter(W))
		if (StillWorthAttacking(Pl))
		{
			const float D = FVector::Dist2D(Pl->GetActorLocation(), GetActorLocation());
			const bool bLos = HasLOS(Pl);
			const bool bAggro = W->GetTimeSeconds() < AggroUntil;
			const float Prio = ComputePlayerTargetPriority(Kind, D, bLos, bAggro);
			Consider(Pl, Prio);
		}
	Target = Best;
	if (Best != Old) UE_LOG(LogTemp, Display, TEXT("MLG: %s(%d) retargets -> %s"), *GetName(), (int32)Kind, *TargetName());
}

void AMLGAlien::Tick(float Dt)
{
	Super::Tick(Dt);
	StateTime += Dt;
	UpdateBurstParticles(Dt);
	// Key the fill light from the viewer's side (above/beside the creature, toward the player) so the face the player sees is lit, not just its back.
	if (FillLight->IsVisible())
		if (const APawn* Viewer = UGameplayStatics::GetPlayerPawn(this, 0))
		{
			const FVector ToViewer = (Viewer->GetActorLocation() - GetActorLocation()).GetSafeNormal2D();
			const float Out = Kind == EMLGAlienKind::Breaker ? 380.f : 200.f, Up = Kind == EMLGAlienKind::Breaker ? 180.f : 100.f;
			FillLight->SetWorldLocation(GetActorLocation() + ToViewer * Out + FVector(0.f, 0.f, Up));
		}

	if (bLunging && LungeTimer > 0.f)
	{
		LungeTimer -= Dt;
		if (!bLungeHitDealt && State != EMLGAlienState::Dead && State != EMLGAlienState::Stagger)
		{
			if (AMLGCharacter* Pl = FindPlayerCharacter(GetWorld(), Target.Get()))
			{
				if (StillWorthAttacking(Pl) && FVector::Dist2D(Pl->GetActorLocation(), GetActorLocation()) <= 240.f)
				{
					bLungeHitDealt = true;
					UGameplayStatics::ApplyDamage(Pl, PlayerDamage, GetController(), this, UDamageType::StaticClass());
					const FVector KnockVel = LungeDir * 320.f + FVector(0.f, 0.f, 110.f);
					Pl->LaunchCharacter(KnockVel, false, false);
					if (Pl->GetCharacterMovement()) Pl->GetCharacterMovement()->Velocity = KnockVel;
					MLGAssets::PlaySoundAtLocation(this, MLGAssets::Audio::AlienHit, Pl->GetActorLocation(), 1.f, 0.92f);
				}
			}
		}
		if (LungeTimer <= 0.f) bLunging = false;
	}

	if (ShotFlashTimer > 0.f)
	{
		ShotFlashTimer -= Dt;
		if (ShotFlashTimer <= 0.f)
		{
			if (State != EMLGAlienState::Telegraph) AimBeam->SetVisibility(false);
			PlasmaBolt->SetVisibility(false);
			if (State != EMLGAlienState::Telegraph) MuzzleLight->SetVisibility(false);
		}
		else if (Kind == EMLGAlienKind::Gunner)
		{
			const float T = 1.f - FMath::Clamp(ShotFlashTimer / 0.18f, 0.f, 1.f);
			const FVector Delta = ShotEndLoc - ShotStartLoc;
			const float Len = Delta.Size();
			if (Len > 5.f)
			{
				PlasmaBolt->SetWorldLocation(FMath::Lerp(ShotStartLoc, ShotEndLoc, T));
				PlasmaBolt->SetWorldRotation(Delta.Rotation());
				PlasmaBolt->SetWorldScale3D(FVector(0.42f, 0.14f, 0.14f));
				PlasmaBolt->SetVisibility(true);
			}
		}
	}

	if (SlamRingTimer > 0.f)
	{
		SlamRingTimer -= Dt;
		if (SlamRingTimer <= 0.f)
		{
			ShockwaveRing->SetVisibility(false);
		}
		else
		{
			const float Alpha = 1.f - FMath::Clamp(SlamRingTimer / 0.50f, 0.f, 1.f);
			const float RingScale = FMath::Lerp(0.6f, 7.0f, Alpha);
			ShockwaveRing->SetWorldLocation(SlamRingOrigin);
			ShockwaveRing->SetWorldScale3D(FVector(RingScale, RingScale, 0.05f));
			if (SlamRingMID)
			{
				const FLinearColor Col = FMath::Lerp(FLinearColor(1.f, 0.68f, 0.12f), FLinearColor(0.35f, 0.08f, 0.02f), Alpha);
				SlamRingMID->SetVectorParameterValue(TEXT("Color"), Col);
			}
			ShockwaveRing->SetVisibility(true);
		}
	}

	if (State == EMLGAlienState::Dead)
	{
		const float FadeDur = FMath::Max(0.25f, DeathAnimLength * 0.7f);
		ApplyDeathPowerDown(StateTime / FadeDur);

		const float SinkStart = DeathAnimLength + DeathHoldDuration;
		if (bUsingSkeletalMesh)
		{
			// Freeze skeletal collapse on its final ground pose before sinking so single-node playback never snaps back toward idle
			if (!bDeathPoseLocked && AnimDeath && StateTime >= DeathAnimLength - 0.04f)
			{
				bDeathPoseLocked = true;
				GetMesh()->SetPlayRate(0.f);
				GetMesh()->SetPosition(FMath::Max(0.f, DeathAnimLength - 0.01f), false);
			}
			if (StateTime > SinkStart)
			{
				const float Alpha = FMath::Clamp((StateTime - SinkStart) / FMath::Max(0.1f, DeathSinkDuration), 0.f, 1.f);
				const float HalfH = GetCapsuleComponent()->GetScaledCapsuleHalfHeight();
				GetMesh()->SetRelativeLocation(FVector(0.f, 0.f, -HalfH - Alpha * (Kind == EMLGAlienKind::Breaker ? 85.f : 55.f)));
				GetMesh()->SetRelativeScale3D(FVector(1.f - 0.18f * Alpha));
			}
		}
		else
		{
			const float TotalNoMesh = FMath::Max(0.8f, DeathAnimLength + DeathHoldDuration * 0.4f);
			Body->SetRelativeScale3D(BaseScale * FMath::Max(0.f, 1.f - StateTime / TotalNoMesh)); // collapses, no gore
		}
		if (StateTime > SinkStart + DeathSinkDuration) Destroy();
		return;
	}

	RetargetLeft -= Dt;
	AAIController* AI = Cast<AAIController>(GetController());
	switch (State)
	{
	case EMLGAlienState::Approach:
	{
		if (RetargetLeft <= 0.f || !StillWorthAttacking(Target.Get()) || Blocked(Target.Get()))
		{
			RetargetLeft = 1.f;
			PickTarget();
			if (AI) { if (Target.IsValid()) AI->MoveToLocation(Goal, 20.f); else AI->StopMovement(); }
		}
		if (bUsingSkeletalMesh)
		{
			const float Speed2D = GetVelocity().Size2D();
			if (Speed2D > MoveSpeed * 0.58f) PlayAnimSlot(EMLGAlienAnimSlot::Run, true);
			else if (Speed2D > 15.f) PlayAnimSlot(EMLGAlienAnimSlot::Walk, true);
			else PlayAnimSlot(EMLGAlienAnimSlot::Idle, true);
		}
		AActor* T = Target.Get();
		// Breaker also triggers its shockwave ground slam whenever the player steps within 420 cm
		if (Kind == EMLGAlienKind::Breaker)
		{
			if (AMLGCharacter* Pl = FindPlayerCharacter(GetWorld(), T))
			{
				if (StillWorthAttacking(Pl) && FVector::Dist2D(Pl->GetActorLocation(), GetActorLocation()) <= 420.f)
				{
					if (!T || FVector::Dist2D(T->GetActorLocation(), GetActorLocation()) > Reach)
					{
						Target = Pl;
						T = Pl;
					}
				}
			}
		}
		if (!T) break;
		bool bGo;
		if (Kind == EMLGAlienKind::Gunner)
		{
			const bool bLos = HasLOS(T);
			bGo = bLos && FVector::Dist(T->GetActorLocation(), GetActorLocation()) <= Range;
			NoLosTime = (!bLos && GetVelocity().Size2D() < 20.f) ? NoLosTime + Dt : 0.f;
			if (NoLosTime > 1.5f) { BlockedUntil.Add(T, GetWorld()->GetTimeSeconds() + 8.f); Target = nullptr; NoLosTime = 0.f; RetargetLeft = 0.f; break; }
		}
		else if (Kind == EMLGAlienKind::Breaker)
		{
			const float TriggerDist = T->IsA<ACharacter>() ? 420.f : Reach;
			bGo = FVector::Dist2D(T->GetActorLocation(), GetActorLocation()) <= TriggerDist;
		}
		else
		{
			// Raider pounces from 300 cm against player (or Reach against structures)
			const float TriggerDist = T->IsA<ACharacter>() ? 300.f : Reach;
			bGo = FVector::Dist2D(T->GetActorLocation(), GetActorLocation()) <= TriggerDist;
		}
		if (bGo)
		{
			if (AI) AI->StopMovement();
			Enter(EMLGAlienState::Telegraph);
			const FLinearColor TelegraphCol = Kind == EMLGAlienKind::Raider ? FLinearColor(1.f, 0.28f, 0.05f)
				: Kind == EMLGAlienKind::Breaker ? FLinearColor(1.f, 0.68f, 0.08f)
				: FLinearColor(1.f, 0.45f, 0.08f);
			Tint(TelegraphCol);
			if (Kind == EMLGAlienKind::Gunner) MLGAssets::PlaySoundAtLocation(this, MLGAssets::Audio::GunnerCharge, GetActorLocation());
			else if (Kind == EMLGAlienKind::Breaker) MLGAssets::PlaySoundAtLocation(this, MLGAssets::Audio::RaiderTelegraph, GetActorLocation(), 1.f, 0.55f);
			else MLGAssets::PlaySoundAtLocation(this, MLGAssets::Audio::RaiderTelegraph, GetActorLocation());
		}
		break;
	}
	case EMLGAlienState::Telegraph:
	{
		AActor* T = Target.Get();
		if (T) SetActorRotation(FRotator(0, (T->GetActorLocation() - GetActorLocation()).Rotation().Yaw, 0));
		const float Alpha = FMath::Clamp(StateTime / FMath::Max(0.05f, TelegraphSeconds), 0.f, 1.f);
		UpdateTelegraphVisuals(Alpha);
		if (!bUsingSkeletalMesh)
		{
			Body->SetRelativeScale3D(BaseScale * (1.f + 0.5f * Alpha)); // rears up
		}
		if (Kind == EMLGAlienKind::Gunner && T)
		{
			// Vivid pulsing red-orange laser sight in ALL builds so players can read the 0.9s aimed shot and break LOS
			const FVector Start = GetMuzzleLocation();
			FVector End = T->GetActorLocation() + FVector(0.f, 0.f, T->IsA<ACharacter>() ? 35.f : 25.f);
			FHitResult BeamHit;
			FCollisionQueryParams BeamParams(SCENE_QUERY_STAT(MLGGunnerBeam), false, this);
			if (GetWorld()->LineTraceSingleByChannel(BeamHit, Start, End, ECC_Visibility, BeamParams) && BeamHit.GetActor() != T)
			{
				End = BeamHit.ImpactPoint;
			}
			const float Pulse = 0.75f + 0.25f * FMath::Abs(FMath::Sin(StateTime * 24.f));
			const float Width = FMath::Lerp(0.040f, 0.014f, Alpha);
			const FLinearColor BeamCol(1.f, FMath::Lerp(0.55f, 0.12f, Alpha) * Pulse, 0.05f);
			UpdateBeam(Start, End, Width, BeamCol);
		}
		if (StateTime >= TelegraphSeconds)
		{
			Strike();
			if (!bUsingSkeletalMesh) Body->SetRelativeScale3D(BaseScale);
			Enter(EMLGAlienState::Cooldown);
			Tint(BaseColor);
		}
		break;
	}
	case EMLGAlienState::Cooldown:
		if (FollowThroughTimer > 0.f)
		{
			FollowThroughTimer -= Dt;
			if (FollowThroughTimer <= 0.f)
			{
				PlayAnimSlot(EMLGAlienAnimSlot::Idle, true);
			}
		}
		if (StateTime >= CooldownSeconds)
		{
			RetargetLeft = 0.f;
			// Gunner peek-and-shoot: after every other volley, or once hurt, fall back to cover for 2 s.
			if (Kind == EMLGAlienKind::Gunner && (++Volleys % 2 == 0 || Health < MaxHealth * 0.4f) && FindCover(CoverSpot))
			{
				if (AI) AI->MoveToLocation(CoverSpot, 15.f);
				Enter(EMLGAlienState::Cover);
				Tint(BaseColor * 0.5f);
				UE_LOG(LogTemp, Display, TEXT("MLG: %s takes cover"), *GetName());
			}
			else Enter(EMLGAlienState::Approach);
		}
		break;
	case EMLGAlienState::Cover:
		if (StateTime >= 2.f) { Enter(EMLGAlienState::Approach); Tint(BaseColor); RetargetLeft = 0.f; }
		break;
	case EMLGAlienState::Stagger:
		if (StateTime >= StaggerSeconds) { Enter(EMLGAlienState::Approach); Tint(BaseColor); RetargetLeft = 0.f; }
		break;
	default:
		break;
	}
}

void AMLGAlien::Strike()
{
	AActor* T = Target.Get();
	if (Kind != EMLGAlienKind::Breaker && !StillWorthAttacking(T)) { AimBeam->SetVisibility(false); return; }

	FollowThroughTimer = Kind == EMLGAlienKind::Breaker ? 0.42f : Kind == EMLGAlienKind::Raider ? 0.30f : 0.20f;

	if (Kind == EMLGAlienKind::Gunner)
	{
		const bool bHit = HasLOS(T);   // cover works: breaking the line during the aim time makes the shot miss
		const FVector Start = GetMuzzleLocation();
		FVector End = T->GetActorLocation() + FVector(0.f, 0.f, T->IsA<ACharacter>() ? 35.f : 25.f);
		if (!bHit)
		{
			FHitResult BlockHit;
			FCollisionQueryParams P(SCENE_QUERY_STAT(MLGGunnerShot), false, this);
			if (GetWorld()->LineTraceSingleByChannel(BlockHit, Start, End, ECC_Visibility, P))
			{
				End = BlockHit.ImpactPoint;
			}
		}
		const FLinearColor ShotCol = bHit ? FLinearColor(1.f, 0.22f, 0.06f) : FLinearColor(0.25f, 0.7f, 1.f);
		UpdateBeam(Start, End, 0.068f, ShotCol);
		if (BoltMID) BoltMID->SetVectorParameterValue(TEXT("Color"), ShotCol * 1.6f);
		ShotStartLoc = Start;
		ShotEndLoc = End;
		PlasmaBolt->SetWorldLocation(Start);
		PlasmaBolt->SetWorldScale3D(FVector(0.42f, 0.14f, 0.14f));
		PlasmaBolt->SetVisibility(true);
		MuzzleLight->SetWorldLocation(Start);
		MuzzleLight->SetLightColor(bHit ? FColor(255, 100, 50) : FColor(80, 170, 255));
		MuzzleLight->SetIntensity(8500.f);
		MuzzleLight->SetVisibility(true);
		ShotFlashTimer = 0.18f;
		SpawnBurstParticles(Start, ShotCol * 1.8f, FLinearColor(0.15f, 0.06f, 0.03f), 4, 210.f, 0.08f, 0.26f, 450.f);
		SpawnBurstParticles(End, ShotCol * 1.6f, FLinearColor(0.1f, 0.1f, 0.12f), 5, 260.f, 0.09f, 0.30f, 650.f);
		MLGAssets::PlaySoundAtLocation(this, MLGAssets::Audio::GunnerCharge, Start, 0.65f, 1.45f);

		UE_LOG(LogTemp, Display, TEXT("MLG: %s shot at %s -> %s"), *GetName(), *TargetName(), bHit ? TEXT("hit") : TEXT("blocked"));
		if (bHit)
		{
			UGameplayStatics::ApplyDamage(T, T->IsA<ACharacter>() ? PlayerDamage : StructureDamage, GetController(), this, UDamageType::StaticClass());
			if (AMLGCharacter* Pl = Cast<AMLGCharacter>(T))
			{
				FVector ShotDir = (End - Start).GetSafeNormal2D();
				if (!ShotDir.IsNearlyZero()) Pl->LaunchCharacter(ShotDir * 180.f + FVector(0.f, 0.f, 45.f), false, false);
			}
		}
		return;
	}

	if (Kind == EMLGAlienKind::Breaker)
	{
		if (T && !T->IsA<ACharacter>() && StillWorthAttacking(T) && FVector::Dist2D(T->GetActorLocation(), GetActorLocation()) <= Reach + 80.f)
		{
			UGameplayStatics::ApplyDamage(T, StructureDamage, GetController(), this, UDamageType::StaticClass());
		}

		MLGAssets::PlaySoundAtLocation(this, MLGAssets::Audio::BreakerSlam, GetActorLocation());
		SlamRingOrigin = GetActorLocation() - FVector(0.f, 0.f, GetCapsuleComponent()->GetScaledCapsuleHalfHeight() - 4.f);
		MuzzleLight->SetWorldLocation(SlamRingOrigin + FVector(0.f, 0.f, 35.f));
		MuzzleLight->SetLightColor(FColor(255, 140, 40));
		MuzzleLight->SetIntensity(9500.f);
		MuzzleLight->SetVisibility(true);
		ShotFlashTimer = 0.22f;
		SlamRingTimer = 0.50f;
		ShockwaveRing->SetWorldLocation(SlamRingOrigin);
		ShockwaveRing->SetWorldScale3D(FVector(0.6f, 0.6f, 0.05f));
		if (SlamRingMID) SlamRingMID->SetVectorParameterValue(TEXT("Color"), FLinearColor(1.f, 0.68f, 0.12f));
		ShockwaveRing->SetVisibility(true);
		SpawnBurstParticles(SlamRingOrigin + FVector(0.f, 0.f, 16.f), FLinearColor(1.f, 0.68f, 0.18f) * 1.4f, FLinearColor(0.35f, 0.15f, 0.08f), 10, 420.f, 0.16f, 0.45f, 750.f);

		if (AMLGCharacter* Pl = FindPlayerCharacter(GetWorld(), T))
		{
			const float DistToPlayer = FVector::Dist2D(Pl->GetActorLocation(), GetActorLocation());
			if (DistToPlayer < 750.f) Pl->TriggerCameraShake(5.5f * (1.f - DistToPlayer / 800.f), 0.34f);
			if (ShouldShockwaveHitPlayer(Pl))
			{
				const float SlamDmg = (DistToPlayer < 205.f) ? 42.f : PlayerDamage;
				UGameplayStatics::ApplyDamage(Pl, SlamDmg, GetController(), this, UDamageType::StaticClass());
				FVector KnockDir = (Pl->GetActorLocation() - GetActorLocation());
				KnockDir.Z = 0.f;
				KnockDir = KnockDir.GetSafeNormal(); if (KnockDir.IsNearlyZero()) KnockDir = GetActorForwardVector();
				// Colossal juggernaut fling: sends player arcing backwards & high under 0.38G Martian gravity
				const FVector KnockVel = KnockDir * 1450.f + FVector(0.f, 0.f, 520.f);
				Pl->LaunchCharacter(KnockVel, true, true);
				if (Pl->GetCharacterMovement()) Pl->GetCharacterMovement()->Velocity = KnockVel;
				Pl->HitPunchPitch = -14.f;
				Pl->HitPunchRoll = FMath::RandBool() ? 16.f : -16.f;
				Pl->TriggerCameraShake(11.f, 0.50f);
				SpawnBurstParticles(Pl->GetActorLocation(), FLinearColor(0.85f, 0.42f, 0.18f) * 1.3f, FLinearColor(0.28f, 0.14f, 0.08f), 8, 440.f, 0.16f, 0.55f, 450.f);
			}
		}
		return;
	}

	// Raider: physical pounce/lunge forward when attacking the player
	if (AMLGCharacter* Pl = Cast<AMLGCharacter>(T))
	{
		FVector Dir = (Pl->GetActorLocation() - GetActorLocation());
		Dir.Z = 0.f;
		Dir = Dir.GetSafeNormal(); if (Dir.IsNearlyZero()) Dir = GetActorForwardVector();
		const FVector LungeVel = Dir * 920.f + FVector(0.f, 0.f, 220.f);
		LaunchCharacter(LungeVel, true, true);
		if (GetCharacterMovement()) GetCharacterMovement()->Velocity = LungeVel;
		bLunging = true;
		LungeTimer = 0.24f;
		LungeDir = Dir;
		bLungeHitDealt = false;
		SpawnBurstParticles(GetWeakspotLocation() + Dir * 32.f, FLinearColor(1.f, 0.32f, 0.08f) * 1.5f, FLinearColor(0.25f, 0.06f, 0.02f), 5, 240.f, 0.08f, 0.26f, 520.f);

		if (FVector::Dist2D(Pl->GetActorLocation(), GetActorLocation()) <= 360.f)
		{
			bLungeHitDealt = true;
			UGameplayStatics::ApplyDamage(Pl, PlayerDamage, GetController(), this, UDamageType::StaticClass());
			const FVector KnockVel = Dir * 320.f + FVector(0.f, 0.f, 110.f);
			Pl->LaunchCharacter(KnockVel, false, false);
			if (Pl->GetCharacterMovement()) Pl->GetCharacterMovement()->Velocity = KnockVel;
			MLGAssets::PlaySoundAtLocation(this, MLGAssets::Audio::AlienHit, Pl->GetActorLocation(), 1.f, 0.92f);
		}
		return;
	}

	SpawnBurstParticles(GetWeakspotLocation() + GetActorForwardVector() * 35.f, FLinearColor(1.f, 0.35f, 0.1f) * 1.4f, FLinearColor(0.2f, 0.08f, 0.04f), 4, 210.f, 0.08f, 0.25f, 500.f);
	MLGAssets::PlaySoundAtLocation(this, MLGAssets::Audio::AlienHit, GetActorLocation(), 0.8f, 0.88f);
	UGameplayStatics::ApplyDamage(T, StructureDamage, GetController(), this, UDamageType::StaticClass());
}

float AMLGAlien::ComputeDamageMultiplier(EMLGAlienKind InKind, EMLGAlienState InState, const FVector& ActorLoc, float CapsuleHalfHeight, const FHitResult* HitInfo, bool& bOutCrit)
{
	bOutCrit = false;
	if (InKind == EMLGAlienKind::Breaker)
	{
		if (InState == EMLGAlienState::Telegraph) { bOutCrit = true; return 1.5f; }
		return 0.5f;   // armoured except while winding up
	}
	if (HitInfo)
	{
		if (!HitInfo->BoneName.IsNone())
		{
			const FString Bone = HitInfo->BoneName.ToString().ToLower();
			if (Bone.Contains(TEXT("head")) || Bone.Contains(TEXT("neck")) || Bone.Contains(TEXT("skull")) || Bone.Contains(TEXT("jaw")))
			{
				bOutCrit = true;
				return 1.75f;
			}
		}
		const bool bHasLoc = !HitInfo->ImpactPoint.IsZero() || !HitInfo->Location.IsZero();
		if (bHasLoc)
		{
			const float HitZ = !HitInfo->ImpactPoint.IsZero() ? HitInfo->ImpactPoint.Z : HitInfo->Location.Z;
			if (HitZ > ActorLoc.Z + CapsuleHalfHeight * 0.38f)
			{
				bOutCrit = true;
				return 1.75f;
			}
		}
	}
	return 1.f;
}

bool AMLGAlien::WouldPointHitCrit(const FHitResult& HitInfo) const
{
	bool bCrit = false;
	ComputeDamageMultiplier(Kind, State, GetActorLocation(), GetCapsuleComponent()->GetScaledCapsuleHalfHeight(), &HitInfo, bCrit);
	return bCrit;
}

float AMLGAlien::TakeDamage(float D, FDamageEvent const& E, AController* By, AActor* C)
{
	if (State == EMLGAlienState::Dead) return 0.f;
	const bool bWindup = State == EMLGAlienState::Telegraph;
	const FHitResult* HitPtr = E.IsOfType(FPointDamageEvent::ClassID) ? &static_cast<const FPointDamageEvent&>(E).HitInfo : nullptr;
	bool bCrit = false;
	D *= ComputeDamageMultiplier(Kind, State, GetActorLocation(), GetCapsuleComponent()->GetScaledCapsuleHalfHeight(), HitPtr, bCrit);
	bLastHitWasCrit = bCrit;
	Health -= D;
	if ((By && By->IsPlayerController()) || (C && C->IsA<AMLGCharacter>())) AggroUntil = GetWorld()->GetTimeSeconds() + AggroSeconds;
	const FVector HitOrigin = HitPtr && !HitPtr->ImpactPoint.IsZero() ? FVector(HitPtr->ImpactPoint) : GetWeakspotLocation();
	const FLinearColor SparkCol = bCrit ? FLinearColor(1.f, 0.85f, 0.22f) * 1.8f : FLinearColor(0.65f, 0.25f, 0.95f) * 1.2f;
	SpawnBurstParticles(HitOrigin, SparkCol, FLinearColor(0.12f, 0.06f, 0.14f), bCrit ? 6 : 4, bCrit ? 300.f : 220.f, bCrit ? 0.10f : 0.07f, 0.28f, 750.f);
	MLGAssets::PlaySoundAtLocation(this, MLGAssets::Audio::AlienHit, HitOrigin, 1.f, bCrit ? 1.22f : 1.f);
	if (Health <= 0.f) { Die(); return D; }
	const float Now = GetWorld()->GetTimeSeconds();
	// Hit reaction: shooting any alien during Telegraph ALWAYS staggers & cancels its wind-up/lunge/slam.
	if ((Kind != EMLGAlienKind::Breaker || bWindup) && (bWindup || Now - LastStagger > 1.f))
	{
		LastStagger = Now;
		if (AAIController* AI = Cast<AAIController>(GetController())) AI->StopMovement();
		if (!bUsingSkeletalMesh) Body->SetRelativeScale3D(BaseScale);
		Enter(EMLGAlienState::Stagger);
		Tint(bCrit ? FLinearColor(1.f, 0.85f, 0.2f) : FLinearColor::White);
	}
	return D;
}

void AMLGAlien::Die()
{
	Enter(EMLGAlienState::Dead);
	PlasmaBolt->SetVisibility(false);
	WeakspotGlow->SetVisibility(false);
	SetActorEnableCollision(false);
	GetCapsuleComponent()->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	GetCapsuleComponent()->SetCollisionResponseToAllChannels(ECR_Ignore);
	GetMesh()->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	GetMesh()->SetCollisionResponseToAllChannels(ECR_Ignore);
	if (UCharacterMovementComponent* Move = GetCharacterMovement())
	{
		// Freeze capsule in place on the ground so disabling capsule collision does not drop or slide the corpse
		Move->StopMovementImmediately();
		Move->GravityScale = 0.f;
		Move->DisableMovement();
	}
	if (AAIController* AI = Cast<AAIController>(GetController())) AI->StopMovement();
	ApplyDeathPowerDown(0.f);
	const FVector CoreBurstOrigin = GetWeakspotLocation();
	const FLinearColor CoreCol = Kind == EMLGAlienKind::Breaker ? FLinearColor(1.f, 0.55f, 0.12f) * 1.8f
		: Kind == EMLGAlienKind::Gunner ? FLinearColor(0.25f, 0.72f, 1.f) * 1.7f
		: FLinearColor(0.85f, 0.24f, 1.f) * 1.6f;
	SpawnBurstParticles(CoreBurstOrigin, CoreCol, FLinearColor(0.14f, 0.05f, 0.08f), 11, Kind == EMLGAlienKind::Breaker ? 380.f : 290.f, Kind == EMLGAlienKind::Breaker ? 0.15f : 0.10f, 0.55f, 820.f);
	const float RoarPitch = Kind == EMLGAlienKind::Breaker ? 0.72f : Kind == EMLGAlienKind::Gunner ? 1.15f : 0.96f;
	MLGAssets::PlaySoundAtLocation(this, MLGAssets::Audio::AlienDeath, GetActorLocation(), 1.1f, RoarPitch);
	if (AMLGGameState* GS = GetWorld()->GetGameState<AMLGGameState>())
	{
		++GS->Kills;
		GS->LastKillTime = GetWorld()->GetTimeSeconds();
	}
	UE_LOG(LogTemp, Display, TEXT("MLG: %s neutralized"), *GetName());
}

void AMLGAlien::AlertToPlayer(float Seconds)
{
	if (!IsAlive() || Kind == EMLGAlienKind::Breaker || !GetWorld()) return;
	AggroUntil = FMath::Max(AggroUntil, GetWorld()->GetTimeSeconds() + Seconds);
	RetargetLeft = 0.f;
}

void AMLGAlien::SwarmDownedPlayer(AMLGCharacter* DownedPlayer)
{
	if (!IsAlive() || !DownedPlayer || !GetWorld()) return;
	Target = DownedPlayer;
	AggroUntil = GetWorld()->GetTimeSeconds() + 6.f;
	FVector Dir = (DownedPlayer->GetActorLocation() - GetActorLocation());
	Dir.Z = 0.f;
	const float Dist2D = Dir.Size();
	Dir = Dir.GetSafeNormal();
	if (!Dir.IsNearlyZero())
	{
		SetActorRotation(FRotator(0.f, Dir.Rotation().Yaw, 0.f));
		if (Dist2D > 110.f && Dist2D < 950.f)
		{
			const float RushSpd = Kind == EMLGAlienKind::Breaker ? 260.f : 520.f;
			LaunchCharacter(Dir * RushSpd + FVector(0.f, 0.f, 95.f), true, true);
		}
	}
	if (AAIController* AI = Cast<AAIController>(GetController()))
	{
		AI->MoveToActor(DownedPlayer, 65.f);
	}
	PlayAnimSlot(EMLGAlienAnimSlot::Telegraph, false, 0.65f);
	UpdateTelegraphVisuals(0.85f);
}
