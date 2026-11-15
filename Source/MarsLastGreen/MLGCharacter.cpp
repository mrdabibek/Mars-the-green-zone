#include "MLGCharacter.h"
#include "MLGAlien.h"
#include "MLGAssets.h"
#include "MLGGameMode.h"
#include "MLGGameState.h"
#include "MLGInteractable.h"
#include "MLGPressureZone.h"
#include "MLGSettings.h"
#include "MLGWeaponComponent.h"
#include "Animation/AnimSequence.h"
#include "Camera/CameraComponent.h"
#include "Components/AudioComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/InputComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/SceneComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/DamageEvents.h"
#include "Engine/EngineTypes.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/StaticMesh.h"
#include "EngineUtils.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "UObject/ConstructorHelpers.h"

AMLGCharacter::AMLGCharacter()
{
	PrimaryActorTick.bCanEverTick = true;
	Cam = CreateDefaultSubobject<UCameraComponent>(TEXT("Cam"));
	Cam->SetupAttachment(GetCapsuleComponent());
	Cam->SetRelativeLocation(FVector(0, 0, 64.f));
	Cam->bUsePawnControlRotation = true;

	Weapon = CreateDefaultSubobject<UMLGWeaponComponent>(TEXT("Weapon"));
	GetMesh()->SetVisibility(false);

	WeaponPivot = CreateDefaultSubobject<USceneComponent>(TEXT("WeaponPivot"));
	WeaponPivot->SetupAttachment(Cam);
	WeaponPivot->SetRelativeLocation(FVector(34.f, 15.f, -15.f));

	FPArmsMesh = CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("FPArmsMesh"));
	FPArmsMesh->SetupAttachment(WeaponPivot);
	FPArmsMesh->SetCollisionProfileName(TEXT("NoCollision"));
	FPArmsMesh->SetCastShadow(false);
	FPArmsMesh->SetVisibility(false);

	FPGunMesh = CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("FPGunMesh"));
	FPGunMesh->SetupAttachment(WeaponPivot);
	FPGunMesh->SetCollisionProfileName(TEXT("NoCollision"));
	FPGunMesh->SetCastShadow(false);
	FPGunMesh->SetVisibility(false);

	RifleRoot = CreateDefaultSubobject<USceneComponent>(TEXT("RifleRoot"));
	RifleRoot->SetupAttachment(WeaponPivot);

	BuildFirstPersonRifle();

	MuzzlePoint = CreateDefaultSubobject<USceneComponent>(TEXT("MuzzlePoint"));
	MuzzlePoint->SetupAttachment(RifleRoot);
	MuzzlePoint->SetRelativeLocation(FVector(46.f, 0.f, 3.5f));

	static ConstructorHelpers::FObjectFinder<UStaticMesh> Sphere(TEXT("/Engine/BasicShapes/Sphere.Sphere"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> Cylinder(TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));

	MuzzleFlashMesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("MuzzleFlashMesh"));
	MuzzleFlashMesh->SetupAttachment(MuzzlePoint);
	if (Sphere.Succeeded()) MuzzleFlashMesh->SetStaticMesh(Sphere.Object);
	MuzzleFlashMesh->SetRelativeScale3D(FVector(0.14f, 0.08f, 0.08f));
	MuzzleFlashMesh->SetCollisionProfileName(TEXT("NoCollision"));
	MuzzleFlashMesh->SetCastShadow(false);
	MuzzleFlashMesh->SetVisibility(false);

	MuzzleFlashLight = CreateDefaultSubobject<UPointLightComponent>(TEXT("MuzzleFlashLight"));
	MuzzleFlashLight->SetupAttachment(MuzzlePoint);
	MuzzleFlashLight->SetIntensity(8000.f);
	MuzzleFlashLight->SetAttenuationRadius(500.f);
	MuzzleFlashLight->SetLightColor(FColor(255, 200, 110));
	MuzzleFlashLight->SetCastShadows(false);
	MuzzleFlashLight->SetVisibility(false);

	TracerBeam = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("TracerBeam"));
	TracerBeam->SetupAttachment(GetCapsuleComponent());
	if (Cylinder.Succeeded()) TracerBeam->SetStaticMesh(Cylinder.Object);
	TracerBeam->SetUsingAbsoluteLocation(true);
	TracerBeam->SetUsingAbsoluteRotation(true);
	TracerBeam->SetUsingAbsoluteScale(true);
	TracerBeam->SetCollisionProfileName(TEXT("NoCollision"));
	TracerBeam->SetCastShadow(false);
	TracerBeam->SetVisibility(false);

	ImpactFlash = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("ImpactFlash"));
	ImpactFlash->SetupAttachment(GetCapsuleComponent());
	if (Sphere.Succeeded()) ImpactFlash->SetStaticMesh(Sphere.Object);
	ImpactFlash->SetUsingAbsoluteLocation(true);
	ImpactFlash->SetUsingAbsoluteRotation(true);
	ImpactFlash->SetUsingAbsoluteScale(true);
	ImpactFlash->SetWorldScale3D(FVector(0.12f));
	ImpactFlash->SetCollisionProfileName(TEXT("NoCollision"));
	ImpactFlash->SetCastShadow(false);
	ImpactFlash->SetVisibility(false);

	GetCharacterMovement()->NavAgentProps.bCanCrouch = true;
	GetCharacterMovement()->MaxWalkSpeed = WalkSpeed;
	GetCharacterMovement()->MaxWalkSpeedCrouched = CrouchSpeed;
	bUseControllerRotationYaw = true;
}

void AMLGCharacter::BuildFirstPersonRifle()
{
	static ConstructorHelpers::FObjectFinder<UStaticMesh> Cube(TEXT("/Engine/BasicShapes/Cube.Cube"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> Cylinder(TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));

	auto Part = [&](const TCHAR* Name, UStaticMesh* MeshAsset, FVector Loc, FRotator Rot, FVector Scale) -> UStaticMeshComponent*
	{
		UStaticMeshComponent* C = CreateDefaultSubobject<UStaticMeshComponent>(Name);
		C->SetupAttachment(RifleRoot);
		if (MeshAsset) C->SetStaticMesh(MeshAsset);
		C->SetRelativeLocation(Loc);
		C->SetRelativeRotation(Rot);
		C->SetRelativeScale3D(Scale);
		C->SetCollisionProfileName(TEXT("NoCollision"));
		C->SetCastShadow(false);
		return C;
	};

	UStaticMesh* CubeObj = Cube.Succeeded() ? Cube.Object : nullptr;
	UStaticMesh* CylObj = Cylinder.Succeeded() ? Cylinder.Object : nullptr;

	// Layered sci-fi pulse carbine geometry (all components clean & self-contained)
	Part(TEXT("RifleReceiver"), CubeObj, FVector(0.f, 0.f, 0.f), FRotator::ZeroRotator, FVector(0.36f, 0.055f, 0.085f));
	Part(TEXT("RifleShroud"), CubeObj, FVector(18.f, 0.f, 1.5f), FRotator::ZeroRotator, FVector(0.24f, 0.048f, 0.060f));
	Part(TEXT("RifleBarrel"), CylObj, FVector(34.f, 0.f, 3.5f), FRotator(90.f, 0.f, 0.f), FVector(0.022f, 0.022f, 0.24f));
	Part(TEXT("RifleOptic"), CubeObj, FVector(4.f, 0.f, 6.8f), FRotator::ZeroRotator, FVector(0.11f, 0.032f, 0.036f));
	Part(TEXT("RifleMag"), CubeObj, FVector(6.f, 0.f, -8.f), FRotator(-12.f, 0.f, 0.f), FVector(0.07f, 0.036f, 0.12f));
	Part(TEXT("RifleStock"), CubeObj, FVector(-20.f, 0.f, -1.5f), FRotator::ZeroRotator, FVector(0.16f, 0.045f, 0.075f));
	Part(TEXT("RifleCoreStrip"), CubeObj, FVector(10.f, -2.9f, 1.8f), FRotator::ZeroRotator, FVector(0.18f, 0.008f, 0.015f));
}

void AMLGCharacter::BeginPlay()
{
	Super::BeginPlay();

	// Tint composite sci-fi carbine parts cleanly
	TArray<UStaticMeshComponent*> Meshes;
	RifleRoot->GetOwner()->GetComponents(Meshes);
	for (UStaticMeshComponent* M : Meshes)
	{
		if (!M || M->GetAttachParent() != RifleRoot) continue;
		if (UMaterialInstanceDynamic* MID = MLGAssets::EnsureColorMID(M, 0))
		{
			const FString N = M->GetName();
			if (N == TEXT("RifleCoreStrip"))
			{
				RifleCoreMID = MID;
				MID->SetVectorParameterValue(TEXT("Color"), FLinearColor(0.15f, 0.85f, 1.f));
			}
			else if (N == TEXT("RifleBarrel") || N == TEXT("RifleOptic"))
			{
				MID->SetVectorParameterValue(TEXT("Color"), FLinearColor(0.08f, 0.09f, 0.11f));
			}
			else if (N == TEXT("RifleShroud"))
			{
				MID->SetVectorParameterValue(TEXT("Color"), FLinearColor(0.28f, 0.31f, 0.36f));
			}
			else
			{
				MID->SetVectorParameterValue(TEXT("Color"), FLinearColor(0.16f, 0.18f, 0.21f));
			}
		}
	}

	TracerMID = MLGAssets::EnsureColorMID(TracerBeam, 0);
	if (TracerMID) TracerMID->SetVectorParameterValue(TEXT("Color"), FLinearColor(1.f, 0.85f, 0.2f));
	MuzzleFlashMID = MLGAssets::EnsureColorMID(MuzzleFlashMesh, 0);
	if (MuzzleFlashMID) MuzzleFlashMID->SetVectorParameterValue(TEXT("Color"), FLinearColor(1.f, 0.78f, 0.25f));
	ImpactMID = MLGAssets::EnsureColorMID(ImpactFlash, 0);
	if (ImpactMID) ImpactMID->SetVectorParameterValue(TEXT("Color"), FLinearColor(1.f, 0.6f, 0.15f));

	// Load UE5 FirstPerson template arms + rifle if imported by ue_pipeline; otherwise keep composite sci-fi rifle
	USkeletalMesh* Arms = MLGAssets::LoadFirst<USkeletalMesh>({
		TEXT("/Game/FirstPersonArms/Character/Mesh/SK_Mannequin_Arms"),
		TEXT("/Game/FirstPerson/SK_FP_Arms") });
	USkeletalMesh* Gun = MLGAssets::LoadFirst<USkeletalMesh>({
		TEXT("/Game/FPWeapon/Mesh/SK_FPGun"),
		TEXT("/Game/FirstPerson/SK_Rifle") });

	if (Arms && Gun)
	{
		bUsingFPTemplate = true;
		FPArmsMesh->SetSkeletalMesh(Arms);
		FPArmsMesh->SetAnimationMode(EAnimationMode::AnimationSingleNode);
		FPArmsMesh->SetRelativeLocation(FVector(-42.f, -15.f, -140.f));
		FPArmsMesh->SetVisibility(true);

		FPGunMesh->SetSkeletalMesh(Gun);
		FPGunMesh->AttachToComponent(FPArmsMesh, FAttachmentTransformRules::SnapToTargetNotIncludingScale, TEXT("GripPoint"));
		FPGunMesh->SetVisibility(true);

		RifleRoot->SetVisibility(false, true);
		if (FPGunMesh->DoesSocketExist(TEXT("Muzzle")))
		{
			MuzzleFlashMesh->AttachToComponent(FPGunMesh, FAttachmentTransformRules::SnapToTargetNotIncludingScale, TEXT("Muzzle"));
			MuzzleFlashLight->AttachToComponent(FPGunMesh, FAttachmentTransformRules::SnapToTargetNotIncludingScale, TEXT("Muzzle"));
		}

		FPAnimIdle = MLGAssets::LoadOptional<UAnimSequence>(TEXT("/Game/FirstPersonArms/Animations/FP_Rifle_Idle"));
		FPAnimRun = MLGAssets::LoadOptional<UAnimSequence>(TEXT("/Game/FirstPersonArms/Animations/FP_Rifle_Run"));
		FPAnimFire = MLGAssets::LoadOptional<UAnimSequence>(TEXT("/Game/FirstPersonArms/Animations/FP_Rifle_Fire"));
		if (FPAnimIdle)
		{
			FPArmsMesh->PlayAnimation(FPAnimIdle, true);
			LastFPAnimState = 0;
		}
	}

	// Start looping Mars ambient wind (muffled indoors, louder outdoors)
	WindAudio = MLGAssets::SpawnLoopingSound2D(this, MLGAssets::Audio::MarsWindLoop, 0.35f);

	UE_LOG(LogTemp, Display, TEXT("MLG: player spawned at %s"), *GetActorLocation().ToString());
}

void AMLGCharacter::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (WindAudio)
	{
		WindAudio->Stop();
		WindAudio = nullptr;
	}
	Super::EndPlay(EndPlayReason);
}

void AMLGCharacter::SetupPlayerInputComponent(UInputComponent* In)
{
	In->BindAxis("MoveForward", this, &AMLGCharacter::MoveForward);
	In->BindAxis("MoveRight", this, &AMLGCharacter::MoveRight);
	In->BindAxis("Turn", this, &AMLGCharacter::Turn);
	In->BindAxis("LookUp", this, &AMLGCharacter::LookUp);
	In->BindAction("Jump", IE_Pressed, this, &ACharacter::Jump);
	In->BindAction("Jump", IE_Released, this, &ACharacter::StopJumping);
	In->BindAction("Sprint", IE_Pressed, this, &AMLGCharacter::SprintOn);
	In->BindAction("Sprint", IE_Released, this, &AMLGCharacter::SprintOff);
	In->BindAction("Crouch", IE_Pressed, this, &AMLGCharacter::CrouchPressed);
	In->BindAction("Crouch", IE_Released, this, &AMLGCharacter::CrouchReleased);
	In->BindAction("Interact", IE_Pressed, this, &AMLGCharacter::InteractPressed);
	In->BindAction("Interact", IE_Released, this, &AMLGCharacter::InteractReleased);
	In->BindAction("Fire", IE_Pressed, this, &AMLGCharacter::FirePressed);
	In->BindAction("Fire", IE_Released, this, &AMLGCharacter::FireReleased);
	In->BindAction("Aim", IE_Pressed, this, &AMLGCharacter::AimOn);
	In->BindAction("Aim", IE_Released, this, &AMLGCharacter::AimOff);
	In->BindAction("Reload", IE_Pressed, this, &AMLGCharacter::ReloadPressed);
	In->BindAction("QuickSave", IE_Pressed, this, &AMLGCharacter::QuickSave);
	In->BindAction("QuickLoad", IE_Pressed, this, &AMLGCharacter::QuickLoad);
	In->BindAction<FMLGKitDelegate>("Kit1", IE_Pressed, this, &AMLGCharacter::KitKey, 0);
	In->BindAction<FMLGKitDelegate>("Kit2", IE_Pressed, this, &AMLGCharacter::KitKey, 1);
	In->BindAction<FMLGKitDelegate>("Kit3", IE_Pressed, this, &AMLGCharacter::KitKey, 2);
	In->BindAction<FMLGKitDelegate>("Kit4", IE_Pressed, this, &AMLGCharacter::KitKey, 3);
	In->BindAction<FMLGKitDelegate>("Kit5", IE_Pressed, this, &AMLGCharacter::KitKey, 4);
	In->BindAction<FMLGKitDelegate>("Kit6", IE_Pressed, this, &AMLGCharacter::KitKey, 5);
}

bool AMLGCharacter::Frozen() const
{
	if (bDyingSequence) return true;
	const AMLGGameState* GS = GetWorld()->GetGameState<AMLGGameState>();
	return GS && (GS->Phase == EMLGPhase::Planning || GS->Phase == EMLGPhase::Won || GS->Phase == EMLGPhase::Lost);
}

void AMLGCharacter::Turn(float V)
{
	if (Frozen()) return;
	const float Scaled = V * LookSensitivity * UMLGSettings::Get()->MouseSensitivity;
	AddControllerYawInput(Scaled);
	LookSway.X = FMath::Clamp(LookSway.X + Scaled * 1.4f, -4.f, 4.f);
}

void AMLGCharacter::LookUp(float V)
{
	if (Frozen()) return;
	const float Scaled = V * LookSensitivity * UMLGSettings::Get()->MouseSensitivity * (UMLGSettings::Get()->bInvertY ? -1.f : 1.f);
	AddControllerPitchInput(Scaled);
	LookSway.Y = FMath::Clamp(LookSway.Y + Scaled * 1.4f, -4.f, 4.f);
}

void AMLGCharacter::KitKey(int32 I)
{
	AMLGGameState* GS = GetWorld()->GetGameState<AMLGGameState>();
	if (GS && GS->Phase == EMLGPhase::Planning && !GS->ToggleKit(I)) GS->PushMessage(TEXT("Over the weight budget: drop something first"));
}
void AMLGCharacter::QuickSave() { if (AMLGGameMode* GM = GetWorld()->GetAuthGameMode<AMLGGameMode>()) GM->SaveCheckpoint(true); }
void AMLGCharacter::QuickLoad() { if (AMLGGameMode* GM = GetWorld()->GetAuthGameMode<AMLGGameMode>()) if (!GM->LoadCheckpoint()) if (AMLGGameState* GS = GetWorld()->GetGameState<AMLGGameState>()) GS->PushMessage(TEXT("No checkpoint yet")); }

void AMLGCharacter::ApplySaved(FVector Loc, FRotator Rot, float InHealth, float InSuit, int32 Mag, int32 Reserve)
{
	bDead = false; bDyingSequence = false; DeathSeqTime = 0.f; MaulPulseTimer = 0.f; FatalAttacker = nullptr;
	Health = InHealth; SuitOxygen = InSuit;
	Weapon->Mag = Mag; Weapon->Reserve = Reserve; Weapon->bReloading = false;
	LastDamageTime = -100.f; bHasDamageOrigin = false; LastHitSourceTag.Empty();
	HitPunchPitch = 0.f; HitPunchRoll = 0.f;
	FireFovKick = 0.f; RecoilRecoverPending = 0.f; CamShakeLeft = 0.f;
	Cam->bUsePawnControlRotation = true;
	Cam->SetRelativeLocation(FVector(0.f, 0.f, 64.f));
	Cam->SetRelativeRotation(FRotator::ZeroRotator);
	GetCharacterMovement()->SetMovementMode(MOVE_Walking);
	TeleportTo(Loc, FRotator(0, Rot.Yaw, 0));
	if (AController* C = GetController()) C->SetControlRotation(Rot);
	bHolding = false; HoldTime = 0.f; HoldFraction = 0.f;
}

void AMLGCharacter::CrouchPressed() { if (bDead || bDyingSequence) return; if (UMLGSettings::Get()->bToggleCrouch && bIsCrouched) UnCrouch(); else Crouch(); }
void AMLGCharacter::CrouchReleased() { if (!UMLGSettings::Get()->bToggleCrouch) UnCrouch(); }
void AMLGCharacter::InteractPressed()
{
	if (bDyingSequence) return;
	AMLGGameState* GS = GetWorld()->GetGameState<AMLGGameState>();
	if (GS && GS->Phase == EMLGPhase::Won) { GetWorld()->GetFirstPlayerController()->ConsoleCommand("RestartLevel"); return; }
	if (bDead || (GS && GS->Phase == EMLGPhase::Lost))
	{
		AMLGGameMode* GM = GetWorld()->GetAuthGameMode<AMLGGameMode>();
		if (!GM || !GM->LoadCheckpoint()) GetWorld()->GetFirstPlayerController()->ConsoleCommand("RestartLevel");
		return;
	}
	bHolding = true; HoldTime = 0.f; RepairTickSoundTimer = 0.25f;
}
void AMLGCharacter::InteractReleased() { bHolding = false; HoldTime = 0.f; HoldFraction = 0.f; }
void AMLGCharacter::FirePressed() { if (!bDead && !bDyingSequence && !Frozen()) Weapon->StartFire(); }
void AMLGCharacter::FireReleased() { Weapon->StopFire(); }
void AMLGCharacter::AimOn() { if (!bDyingSequence) bAim = true; }
void AMLGCharacter::AimOff() { bAim = false; }
void AMLGCharacter::ReloadPressed() { if (!bDead && !bDyingSequence && !Frozen()) Weapon->Reload(); }

FVector AMLGCharacter::GetMuzzleWorldLocation() const
{
	if (bUsingFPTemplate && FPGunMesh && FPGunMesh->DoesSocketExist(TEXT("Muzzle")))
	{
		return FPGunMesh->GetSocketLocation(TEXT("Muzzle"));
	}
	return MuzzlePoint ? MuzzlePoint->GetComponentLocation() : (Cam->GetComponentLocation() + Cam->GetForwardVector() * 60.f - FVector(0, 0, 8.f));
}

void AMLGCharacter::TriggerCameraShake(float Intensity, float Duration)
{
	CamShakeIntensity = FMath::Max(CamShakeIntensity, Intensity);
	CamShakeDuration = FMath::Max(0.05f, Duration);
	CamShakeLeft = FMath::Max(CamShakeLeft, Duration);
}

void AMLGCharacter::NotifyWeaponFired(const FVector& TargetPoint, bool bHitTarget, bool bCritHit, bool bKilledTarget)
{
	RecoilKickOffset = bAim ? -3.6f : -5.2f;
	RecoilKickPitch = (bAim ? 2.4f : 3.8f);
	RecoilKickRoll = FMath::RandRange(-1.9f, 1.9f) * (bAim ? 0.55f : 1.f);
	FireFovKick = bAim ? 2.2f : 3.4f;
	RecoilRecoverPending = FMath::Min(3.5f, RecoilRecoverPending + Weapon->RecoilPitchDeg * (bAim ? 0.38f : 0.62f));
	const float ShotShake = bKilledTarget ? 2.6f : bCritHit ? 2.1f : bHitTarget ? 1.75f : (bAim ? 1.05f : 1.55f);
	TriggerCameraShake(ShotShake, bKilledTarget ? 0.14f : 0.09f);
	if (bUsingFPTemplate && FPAnimFire)
	{
		FPArmsMesh->PlayAnimation(FPAnimFire, false);
		LastFPAnimState = 2;
		FPFireAnimLeft = FMath::Max(0.18f, FPAnimFire->GetPlayLength() * 0.85f);
	}

	MuzzleFlashLight->SetIntensity(FMath::RandRange(7500.f, 10500.f));
	MuzzleFlashLight->SetVisibility(true);
	MuzzleFlashMesh->SetRelativeScale3D(FVector(FMath::RandRange(0.14f, 0.21f), FMath::RandRange(0.08f, 0.13f), FMath::RandRange(0.08f, 0.13f)));
	MuzzleFlashMesh->SetRelativeRotation(FRotator(0.f, 0.f, FMath::RandRange(0.f, 360.f)));
	MuzzleFlashMesh->SetVisibility(true);
	MuzzleFlashTimer = 0.048f;

	const FVector Start = GetMuzzleWorldLocation();
	const FVector Delta = TargetPoint - Start;
	const float Len = Delta.Size();
	if (Len > 5.f)
	{
		TracerBeam->SetWorldLocation((Start + TargetPoint) * 0.5f);
		TracerBeam->SetWorldRotation(FRotationMatrix::MakeFromZ(Delta / Len).Rotator());
		TracerBeam->SetWorldScale3D(FVector(0.016f, 0.016f, Len / 100.f));
		TracerBeam->SetVisibility(true);
	}
	if (bHitTarget)
	{
		ImpactFlash->SetWorldLocation(TargetPoint);
		ImpactFlash->SetWorldScale3D(FVector(bKilledTarget ? 0.28f : bCritHit ? 0.22f : 0.12f));
		if (ImpactMID)
		{
			const FLinearColor FlashCol = bKilledTarget ? FLinearColor(1.f, 0.22f, 0.12f)
				: bCritHit ? FLinearColor(1.f, 0.9f, 0.15f)
				: FLinearColor(1.f, 0.6f, 0.15f);
			ImpactMID->SetVectorParameterValue(TEXT("Color"), FlashCol);
		}
		ImpactFlash->SetVisibility(true);
	}
	TracerTimer = 0.06f;
}

bool AMLGCharacter::IsInPressurizedZone() const
{
	TArray<AActor*> Zones;
	GetOverlappingActors(Zones, AMLGPressureZone::StaticClass());
	for (AActor* A : Zones)
		if (CastChecked<AMLGPressureZone>(A)->IsPressurized()) return true;
	return false;
}

void AMLGCharacter::UpdateViewmodel(float Dt, bool bMoving, bool bSprinting)
{
	if (MuzzleFlashTimer > 0.f)
	{
		MuzzleFlashTimer -= Dt;
		if (MuzzleFlashTimer <= 0.f)
		{
			MuzzleFlashLight->SetVisibility(false);
			MuzzleFlashMesh->SetVisibility(false);
		}
	}
	if (TracerTimer > 0.f)
	{
		TracerTimer -= Dt;
		if (TracerTimer <= 0.f)
		{
			TracerBeam->SetVisibility(false);
			ImpactFlash->SetVisibility(false);
		}
	}

	const bool bHideWeapon = Frozen() || bDead || bDyingSequence;
	RifleRoot->SetVisibility(!bHideWeapon && !bUsingFPTemplate, true);
	FPArmsMesh->SetVisibility(!bHideWeapon && bUsingFPTemplate);
	FPGunMesh->SetVisibility(!bHideWeapon && bUsingFPTemplate);
	if (bHideWeapon)
	{
		MuzzleFlashLight->SetVisibility(false);
		MuzzleFlashMesh->SetVisibility(false);
		return;
	}

	if (MuzzleFlashTimer <= 0.f) { MuzzleFlashLight->SetVisibility(false); MuzzleFlashMesh->SetVisibility(false); }

	if (bUsingFPTemplate)
	{
		if (FPFireAnimLeft > 0.f) FPFireAnimLeft -= Dt;
		if (FPFireAnimLeft <= 0.f)
		{
			const uint8 Desired = bSprinting ? 1 : 0;
			if (Desired != LastFPAnimState)
			{
				UAnimSequence* Seq = (Desired == 1 && FPAnimRun) ? FPAnimRun : FPAnimIdle;
				if (Seq)
				{
					FPArmsMesh->PlayAnimation(Seq, true);
					LastFPAnimState = Desired;
				}
			}
		}
	}

	AdsAlpha = FMath::FInterpTo(AdsAlpha, (bAim && !Weapon->bReloading && !bSprinting) ? 1.f : 0.f, Dt, 14.f);
	SprintAlpha = FMath::FInterpTo(SprintAlpha, bSprinting ? 1.f : 0.f, Dt, 10.f);
	ReloadAlpha = FMath::FInterpTo(ReloadAlpha, Weapon->bReloading ? 1.f : 0.f, Dt, 10.f);

	LookSway = FMath::Vector2DInterpTo(LookSway, FVector2D::ZeroVector, Dt, 10.f);
	RecoilKickOffset = FMath::FInterpTo(RecoilKickOffset, 0.f, Dt, 18.f);
	RecoilKickPitch = FMath::FInterpTo(RecoilKickPitch, 0.f, Dt, 18.f);
	RecoilKickRoll = FMath::FInterpTo(RecoilKickRoll, 0.f, Dt, 18.f);
	HitPunchPitch = FMath::FInterpTo(HitPunchPitch, 0.f, Dt, 11.f);
	HitPunchRoll = FMath::FInterpTo(HitPunchRoll, 0.f, Dt, 11.f);

	if (bMoving && !GetCharacterMovement()->IsFalling())
	{
		BobTime += Dt * (bSprinting ? 11.f : 7.f);
	}
	const float BobScale = (bMoving ? (bSprinting ? 1.2f : 0.65f) : 0.1f) * (1.f - 0.8f * AdsAlpha);
	const FVector BobOffset(0.f, FMath::Cos(BobTime * 0.5f) * 0.7f * BobScale, FMath::Sin(BobTime) * 0.6f * BobScale);

	const FVector HipPos(34.f, 15.f, -15.f);
	const FVector AdsPos(26.f, 0.f, -9.2f);
	FVector TargetPos = FMath::Lerp(HipPos, AdsPos, AdsAlpha);
	TargetPos.X += RecoilKickOffset;
	TargetPos.Y -= LookSway.X * 0.35f * (1.f - 0.7f * AdsAlpha);
	TargetPos.Z -= LookSway.Y * 0.35f * (1.f - 0.7f * AdsAlpha);
	TargetPos += BobOffset;
	TargetPos += FVector(-2.f, 2.f, -3.5f) * SprintAlpha;
	TargetPos += FVector(0.f, 1.f, -7.f) * ReloadAlpha;

	FRotator TargetRot(
		RecoilKickPitch + HitPunchPitch * 0.65f - 10.f * SprintAlpha - 24.f * ReloadAlpha,
		-26.f * SprintAlpha - LookSway.X * 0.9f * (1.f - 0.7f * AdsAlpha),
		12.f * SprintAlpha - 18.f * ReloadAlpha + LookSway.X * 0.8f + RecoilKickRoll + HitPunchRoll * 0.85f);

	WeaponPivot->SetRelativeLocation(TargetPos);
	WeaponPivot->SetRelativeRotation(TargetRot);

	if (RifleCoreMID)
	{
		const FLinearColor CoreCol = Weapon->bReloading ? FLinearColor(1.f, 0.65f, 0.1f)
			: Weapon->Mag == 0 ? FLinearColor(0.95f, 0.15f, 0.1f)
			: FLinearColor(0.15f, 0.85f, 1.f);
		RifleCoreMID->SetVectorParameterValue(TEXT("Color"), CoreCol);
	}
}

void AMLGCharacter::Tick(float Dt)
{
	Super::Tick(Dt);

	const bool bPressurized = IsInPressurizedZone();
	if (WindAudio)
	{
		const float TargetWind = bDead ? 0.f : MLGAssets::GetEffectiveChannelVolume(EMLGSoundChannel::Ambience, bPressurized ? 0.16f : 0.52f);
		WindVolCurrent = FMath::FInterpTo(WindVolCurrent, TargetWind, Dt, 4.f);
		WindAudio->SetVolumeMultiplier(WindVolCurrent);
	}

	if (bDead) return;

	if (bDyingSequence)
	{
		DeathSeqTime += Dt;
		UpdateViewmodel(Dt, false, false);
		const float Collapse = FMath::Clamp(DeathSeqTime / 0.42f, 0.f, 1.f);
		const float ZHeight = FMath::Lerp(64.f, 18.f, Collapse);
		const float ShakeAmp = 4.2f * (1.f - 0.35f * (DeathSeqTime / FMath::Max(0.2f, DeathSeqDuration)));
		Cam->SetRelativeLocation(FVector(
			FMath::FRandRange(-ShakeAmp, ShakeAmp) * 0.4f,
			FMath::FRandRange(-ShakeAmp, ShakeAmp) * 0.5f,
			ZHeight + FMath::FRandRange(-ShakeAmp, ShakeAmp) * 0.4f));

		float TargetLocalYaw = 0.f;
		if (FatalAttacker.IsValid())
		{
			const float WorldYawDelta = FMath::FindDeltaAngleDegrees(GetActorRotation().Yaw, (FatalAttacker->GetActorLocation() - GetActorLocation()).Rotation().Yaw);
			TargetLocalYaw = FMath::Clamp(WorldYawDelta, -85.f, 85.f) * Collapse;
		}
		Cam->SetRelativeRotation(FRotator(
			FMath::Lerp(0.f, 16.f, Collapse) + FMath::Sin(DeathSeqTime * 26.f) * 5.f,
			TargetLocalYaw,
			FMath::Lerp(0.f, 24.f, Collapse) + FMath::Cos(DeathSeqTime * 21.f) * 7.f));

		MaulPulseTimer -= Dt;
		if (MaulPulseTimer <= 0.f)
		{
			MaulPulseTimer = 0.32f;
			LastDamageTime = GetWorld()->GetTimeSeconds();
			MLGAssets::PlaySound2D(this, MLGAssets::Audio::AlienHit, 0.92f, FMath::RandRange(0.75f, 1.05f));
			MLGAssets::PlaySound2D(this, MLGAssets::Audio::PlayerHurt, 0.78f, FMath::RandRange(0.82f, 0.98f));
			TriggerCameraShake(6.5f, 0.25f);
			for (TActorIterator<AMLGAlien> It(GetWorld()); It; ++It)
			{
				if (It->IsAlive() && FVector::DistSquared(It->GetActorLocation(), GetActorLocation()) <= FMath::Square(650.f))
				{
					It->SwarmDownedPlayer(this);
				}
			}
		}

		if (DeathSeqTime >= DeathSeqDuration)
		{
			bDyingSequence = false;
			Cam->SetRelativeRotation(FRotator::ZeroRotator);
			Cam->bUsePawnControlRotation = true;
			Die();
		}
		return;
	}

	// Movement state & Martian 0.38G exterior vs 1.0G pressurized interior gravity
	const bool bMoving = GetVelocity().SizeSquared2D() > 100.f;
	const bool bSprinting = bSprint && !bAim && !bIsCrouched && !Weapon->bReloading && bMoving;
	const AMLGGameState* GSt = GetWorld()->GetGameState<AMLGGameState>();
	if (UCharacterMovementComponent* Move = GetCharacterMovement())
	{
		Move->MaxWalkSpeed = (bSprinting ? SprintSpeed : WalkSpeed) * (GSt ? GSt->WalkScale() : 1.f);
		const float TargetGrav = bPressurized ? 1.0f : (GSt ? FMath::Clamp(GSt->GetGravityRatio(), 0.38f, 1.0f) : 0.38f);
		Move->GravityScale = TargetGrav;
		Move->JumpZVelocity = bPressurized ? 420.f : 355.f;
		Move->AirControl = bPressurized ? 0.22f : 0.40f;
	}

	// Grounded footsteps (indoor deck vs Mars regolith)
	if (bMoving && !GetCharacterMovement()->IsFalling())
	{
		FootstepTimer -= Dt;
		if (FootstepTimer <= 0.f)
		{
			FootstepTimer = bSprinting ? 0.30f : (bIsCrouched ? 0.58f : 0.45f);
			const TCHAR* StepCue = bPressurized ? MLGAssets::Audio::FootstepIndoor : MLGAssets::Audio::FootstepMars;
			const float StepVol = bSprinting ? 0.62f : (bIsCrouched ? 0.32f : 0.48f);
			MLGAssets::PlaySound2D(this, StepCue, StepVol, FMath::RandRange(0.94f, 1.06f));
		}
	}
	else
	{
		FootstepTimer = 0.08f;
	}

	// Low suit oxygen audible warning pulse
	if (SuitOxygen > 0.f && SuitOxygen < 30.f)
	{
		LowO2HeartbeatTimer -= Dt;
		if (LowO2HeartbeatTimer <= 0.f)
		{
			LowO2HeartbeatTimer = (SuitOxygen < 12.f) ? 1.35f : 2.1f;
			MLGAssets::PlaySound2D(this, MLGAssets::Audio::LowO2Heartbeat, (SuitOxygen < 12.f) ? 0.9f : 0.65f);
		}
	}
	else
	{
		LowO2HeartbeatTimer = 0.25f;
	}
	Weapon->bAiming = bAim;
	FireFovKick = FMath::FInterpTo(FireFovKick, 0.f, Dt, 16.f);
	Cam->SetFieldOfView(FMath::FInterpTo(Cam->FieldOfView, UMLGSettings::Get()->FOV - (bAim ? 25.f : 0.f) + FireFovKick, Dt, 14.f));

	if (RecoilRecoverPending > 0.f && (GetWorld()->GetTimeSeconds() - Weapon->LastShotTime) > 0.08f)
	{
		const float RecoverStep = FMath::Min(RecoilRecoverPending, Dt * 6.5f);
		AddControllerPitchInput(RecoverStep);
		RecoilRecoverPending -= RecoverStep;
	}

	if (CamShakeLeft > 0.f)
	{
		CamShakeLeft = FMath::Max(0.f, CamShakeLeft - Dt);
		const float Alpha = CamShakeLeft / FMath::Max(0.05f, CamShakeDuration);
		const float Amp = CamShakeIntensity * Alpha;
		Cam->SetRelativeLocation(FVector(0.f, FMath::FRandRange(-Amp, Amp) * 0.45f, 64.f + FMath::FRandRange(-Amp, Amp) * 0.55f));
		if (CamShakeLeft <= 0.f) CamShakeIntensity = 0.f;
	}
	else
	{
		Cam->SetRelativeLocation(FVector(0.f, 0.f, 64.f));
	}

	UpdateViewmodel(Dt, bMoving, bSprinting);

	// Suit oxygen: refills in a pressurized zone, otherwise drains (faster while sprinting or in peak cold dust storm).
	const float EnvThermalScale = GSt ? GSt->GetSuitThermalLoadScale() : 1.f;
	if (bPressurized) SuitOxygen = FMath::Min(100.f, SuitOxygen + SuitRefillPerSec * Dt);
	else SuitOxygen = FMath::Max(0.f, SuitOxygen - SuitDrainPerSec * (bSprinting ? 1.5f : 1.f) * EnvThermalScale * Dt);
	if (SuitOxygen <= 0.f) TakeDamage(8.f * Dt, FDamageEvent(), nullptr, nullptr);

	// Interaction: look-at focus; hold timing lives here so interruption (looking away / moving out of range) resets progress.
	FHitResult Hit;
	const FVector S = Cam->GetComponentLocation();
	FCollisionQueryParams P(SCENE_QUERY_STAT(MLGInteract), false, this);
	AActor* Found = nullptr;
	if (GetWorld()->SweepSingleByChannel(Hit, S, S + Cam->GetForwardVector() * InteractRange, FQuat::Identity, ECC_Visibility, FCollisionShape::MakeSphere(15.f), P)
		&& Cast<IMLGInteractable>(Hit.GetActor()))
		Found = Hit.GetActor();
	if (Found != Focus.Get()) { Focus = Found; HoldTime = 0.f; }
	HoldFraction = 0.f; FocusPrompt = FText(); bFocusCanAct = false;
	if (IMLGInteractable* I = Cast<IMLGInteractable>(Found))
	{
		FocusPrompt = I->GetPrompt(this);
		bFocusCanAct = I->CanInteract(this);
		if (bHolding && bFocusCanAct)
		{
			const float Need = I->GetHoldSeconds() * UMLGSettings::Get()->HoldScale;
			HoldTime += Dt;
			HoldFraction = Need <= 0.f ? 1.f : FMath::Clamp(HoldTime / Need, 0.f, 1.f);
			if (Need > 0.4f)
			{
				RepairTickSoundTimer += Dt;
				if (RepairTickSoundTimer >= 0.65f)
				{
					RepairTickSoundTimer = 0.f;
					MLGAssets::PlaySound2D(this, MLGAssets::Audio::RepairTick, 0.65f);
				}
			}
			if (HoldTime >= Need) { I->Interact(this); bHolding = false; HoldTime = 0.f; HoldFraction = 0.f; }
		}
	}
}

float AMLGCharacter::TakeDamage(float D, FDamageEvent const& E, AController* By, AActor* C)
{
	if (bDead || bDyingSequence) return 0.f;
	Health = FMath::Max(0.f, Health - D);
	AActor* SourceActor = C ? C : (By ? By->GetPawn() : nullptr);
	if (D > 0.f)
	{
		LastDamageTime = GetWorld()->GetTimeSeconds();
		if (SourceActor)
		{
			LastDamageOrigin = SourceActor->GetActorLocation();
			bHasDamageOrigin = true;
			if (const AMLGAlien* Alien = Cast<AMLGAlien>(SourceActor))
			{
				LastHitSourceTag = AMLGAlien::GetAttackSourceTag(Alien->Kind);
			}
			else
			{
				LastHitSourceTag = TEXT("SUIT IMPACT");
			}

			const FVector ToSource = (LastDamageOrigin - GetActorLocation()).GetSafeNormal2D(UE_SMALL_NUMBER, GetActorForwardVector());
			const float ForwardDot = FVector::DotProduct(GetActorForwardVector(), ToSource);
			const float RightDot = FVector::DotProduct(GetActorRightVector(), ToSource);
			const float PunchScale = FMath::Clamp(D / 12.f, 0.65f, 2.2f);
			HitPunchPitch = FMath::Clamp((-ForwardDot * 4.5f - 2.5f) * PunchScale, -12.f, 12.f);
			HitPunchRoll = FMath::Clamp((RightDot * 6.5f + (FMath::Abs(RightDot) < 0.1f ? 3.5f : 0.f)) * PunchScale, -14.f, 14.f);
			RecoilKickPitch += 3.2f * PunchScale;
			RecoilKickOffset -= 2.5f * PunchScale;
			TriggerCameraShake(2.2f * PunchScale, 0.22f);
			MLGAssets::PlaySound2D(this, MLGAssets::Audio::PlayerHurt, 0.88f, FMath::RandRange(0.95f, 1.05f));
		}
		else
		{
			bHasDamageOrigin = false;
			if (SuitOxygen <= 0.f) LastHitSourceTag = TEXT("SUIT HYPOXIA");
			if (D >= 1.f) MLGAssets::PlaySound2D(this, MLGAssets::Audio::PlayerHurt, 0.7f, 0.92f);
		}
	}
	if (Health <= 0.f)
	{
		const AMLGGameMode* GM = GetWorld() ? GetWorld()->GetAuthGameMode<AMLGGameMode>() : nullptr;
		// Preserve instant Lost transition for scripted automation tests (IsSuppressingKillDrops or null non-alien damage); play maul collapse sequence in live alien combat
		if (SourceActor && SourceActor->IsA<AMLGAlien>() && (!GM || !GM->IsSuppressingKillDrops()))
		{
			StartDyingSequence(SourceActor);
		}
		else
		{
			Die();
		}
	}
	return D;
}

void AMLGCharacter::OnJumped_Implementation()
{
	Super::OnJumped_Implementation();
	MLGAssets::PlaySound2D(this, MLGAssets::Audio::Jump, 0.68f, FMath::RandRange(0.96f, 1.05f));
}

void AMLGCharacter::Landed(const FHitResult& Hit)
{
	Super::Landed(Hit);
	const float ImpactSpeed = FMath::Abs(GetVelocity().Z);
	if (ImpactSpeed > 180.f)
	{
		const float LandVol = FMath::Clamp((ImpactSpeed - 150.f) / 600.f, 0.35f, 0.95f);
		MLGAssets::PlaySound2D(this, MLGAssets::Audio::Land, LandVol, FMath::RandRange(0.94f, 1.06f));
	}
}

void AMLGCharacter::StartDyingSequence(AActor* Attacker)
{
	if (bDead || bDyingSequence) return;
	bDyingSequence = true;
	DeathSeqTime = 0.f;
	MaulPulseTimer = 0.05f;
	FatalAttacker = Attacker;
	bHolding = false; bAim = false;
	Weapon->StopFire();
	GetCharacterMovement()->StopMovementImmediately();
	GetCharacterMovement()->DisableMovement();
	Cam->bUsePawnControlRotation = false;
	TriggerCameraShake(9.5f, DeathSeqDuration);
	MLGAssets::PlaySound2D(this, MLGAssets::Audio::AlienDeath, 0.85f, 0.85f);
	if (GetWorld())
	{
		for (TActorIterator<AMLGAlien> It(GetWorld()); It; ++It)
		{
			if (It->IsAlive() && FVector::DistSquared(It->GetActorLocation(), GetActorLocation()) <= FMath::Square(950.f))
			{
				It->SwarmDownedPlayer(this);
			}
		}
	}
}

void AMLGCharacter::Die()
{
	bDyingSequence = false;
	bDead = true;
	Weapon->StopFire();
	Cam->bUsePawnControlRotation = true;
	Cam->SetRelativeRotation(FRotator::ZeroRotator);
	if (AMLGGameState* GS = GetWorld()->GetGameState<AMLGGameState>()) { GS->bPlayerDead = true; GS->Lose(TEXT("You died.")); }
	GetCharacterMovement()->DisableMovement();
}
