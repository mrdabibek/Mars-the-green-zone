#include "MLGWeaponComponent.h"
#include "MLGAlien.h"
#include "EngineUtils.h"
#include "MLGAssets.h"
#include "MLGCharacter.h"
#include "MLGPressureZone.h"
#include "Camera/CameraComponent.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Kismet/GameplayStatics.h"

void UMLGWeaponComponent::StartFire()
{
	bTrigger = true;
	if (!bReloading && Cooldown <= 0.f)
	{
		if (Mag <= 0) Reload();
		else FireOnce();
	}
}

void UMLGWeaponComponent::Reload()
{
	if (bReloading || Mag >= MagSize || Reserve <= 0) return;
	bReloading = true;
	ReloadLeft = ReloadSeconds;
	if (AMLGCharacter* C = Cast<AMLGCharacter>(GetOwner()))
	{
		MLGAssets::PlaySound2D(C, MLGAssets::Audio::RifleReload, 0.9f);
	}
}

void UMLGWeaponComponent::TickComponent(float Dt, ELevelTick, FActorComponentTickFunction*)
{
	Cooldown = FMath::Max(0.f, Cooldown - Dt);
	if (bReloading)
	{
		ReloadLeft -= Dt;
		if (ReloadLeft <= 0.f)
		{
			const int32 N = FMath::Min(MagSize - Mag, Reserve);
			Mag += N; Reserve -= N; bReloading = false;
		}
		return;
	}
	if (!bTrigger || Cooldown > 0.f) return;
	if (Mag <= 0) { Reload(); return; }
	FireOnce();
}

void UMLGWeaponComponent::FireOnce()
{
	AMLGCharacter* C = Cast<AMLGCharacter>(GetOwner());
	if (!C || !GetWorld()) return;
	const float Now = GetWorld()->GetTimeSeconds();
	const float TimeSinceLastShot = Now - LastShotTime;
	for (TActorIterator<AMLGAlien> It(GetWorld()); It; ++It)
		if (It->IsAlive() && FVector::DistSquared(It->GetActorLocation(), C->GetActorLocation()) <= FMath::Square(3500.f)) It->AlertToPlayer(8.f);
	--Mag;
	Cooldown = 60.f / RoundsPerMinute;
	LastShotTime = Now;

	MLGAssets::PlaySound2D(C, MLGAssets::Audio::RifleFire, 0.85f, FMath::RandRange(0.96f, 1.04f));

	const FVector Start = C->Cam->GetComponentLocation();
	const FVector CenterDir = C->Cam->GetForwardVector().GetSafeNormal();
	FCollisionQueryParams P(SCENE_QUERY_STAT(MLGShot), true, C);
	// Never let corpses or atmospheric overlap volumes intercept gunfire
	for (TActorIterator<AMLGAlien> It(GetWorld()); It; ++It)
	{
		if (!It->IsAlive()) P.AddIgnoredActor(*It);
	}
	for (TActorIterator<AMLGPressureZone> It(GetWorld()); It; ++It)
	{
		P.AddIgnoredActor(*It);
	}

	// Converge strictly along the camera center crosshair ray onto exact world target
	FHitResult CenterHit;
	const FVector CenterEnd = Start + CenterDir * Range;
	const bool bCenterHit = GetWorld()->LineTraceSingleByChannel(CenterHit, Start, CenterEnd, ECC_Visibility, P);
	const FVector AimTarget = bCenterHit ? CenterHit.ImpactPoint : CenterEnd;
	const FVector AimDir = (AimTarget - Start).GetSafeNormal(UE_SMALL_NUMBER, CenterDir);

	// Tap / first shot of burst is pinpoint 0-deg spread; sustained fire uses tight spread
	const float BaseSpreadDeg = (TimeSinceLastShot > 0.16f) ? 0.f : (bAiming ? AimSpreadDeg : HipSpreadDeg);
	const float SpreadRad = FMath::DegreesToRadians(BaseSpreadDeg);
	const FVector Dir = SpreadRad > 0.f ? FMath::VRandCone(AimDir, SpreadRad) : AimDir;

	FHitResult Hit;
	const FVector End = Start + Dir * Range;
	bool bHit = GetWorld()->LineTraceSingleByChannel(Hit, Start, End, ECC_Visibility, P);

	// Close/mid-range skeletal silhouette fallback: if thin ray slipped past a PhysicsAsset bone gap, check tight 7cm pawn capsule sweep clipped to world hit
	if (!bHit || !Cast<AMLGAlien>(Hit.GetActor()))
	{
		const float MaxSweepDist = bHit ? FVector::Dist(Start, Hit.ImpactPoint) : Range;
		FHitResult PawnHit;
		if (GetWorld()->SweepSingleByChannel(PawnHit, Start, Start + Dir * MaxSweepDist, FQuat::Identity, ECC_Pawn, FCollisionShape::MakeSphere(7.f), P))
		{
			if (AMLGAlien* SwAlien = Cast<AMLGAlien>(PawnHit.GetActor()); SwAlien && SwAlien->IsAlive())
			{
				Hit = PawnHit;
				if (Hit.ImpactPoint.IsZero()) Hit.ImpactPoint = Hit.Location;
				bHit = true;
			}
		}
	}
	const FVector TargetPoint = bHit ? Hit.ImpactPoint : End;

	bool bCritHit = false;
	bool bKilledTarget = false;
	if (bHit && Hit.GetActor())
	{
		AMLGAlien* Alien = Cast<AMLGAlien>(Hit.GetActor());
		const bool bWasAlive = Alien && Alien->IsAlive();
		const float Applied = UGameplayStatics::ApplyPointDamage(Hit.GetActor(), Damage, Dir, Hit, C->GetController(), C, nullptr);
		if (Alien)
		{
			LastHitTime = Now;
			LastHitDamage = Applied;
			bCritHit = Alien->WasLastHitCrit();
			bKilledTarget = bWasAlive && !Alien->IsAlive();
			if (bCritHit)
			{
				LastCritTime = Now;
				LastCritDamage = Applied;
			}
			if (bKilledTarget)
			{
				LastKillTime = Now;
				MLGAssets::PlaySound2D(C, MLGAssets::Audio::HitMarker, 1.0f, 1.55f);
			}
			else if (bCritHit)
			{
				MLGAssets::PlaySound2D(C, MLGAssets::Audio::HitMarker, 0.95f, 1.35f);
			}
			else
			{
				MLGAssets::PlaySound2D(C, MLGAssets::Audio::HitMarker, 0.85f, 1.0f);
			}

			// Tier-scaled physical ballistic knockback on live aliens (skip once dead so collapsed bodies stay anchored)
			if (!bKilledTarget && Alien->IsAlive())
			{
				FVector KnockDir = Dir;
				KnockDir.Z = 0.f;
				KnockDir = KnockDir.GetSafeNormal();
				if (!KnockDir.IsNearlyZero())
				{
					const float BaseImpulse = Alien->Kind == EMLGAlienKind::Breaker ? (bCritHit ? 140.f : 45.f)
						: Alien->Kind == EMLGAlienKind::Gunner ? 190.f : 310.f;
					const float CritScale = (bCritHit && Alien->Kind != EMLGAlienKind::Breaker) ? 1.35f : 1.0f;
					const float LiftZ = Alien->Kind == EMLGAlienKind::Breaker ? 25.f : (Alien->Kind == EMLGAlienKind::Gunner ? 65.f : 110.f);
					const FVector Impulse = KnockDir * (BaseImpulse * CritScale) + FVector(0.f, 0.f, LiftZ);
					Alien->LaunchCharacter(Impulse, false, false);
				}
			}
		}
	}

	// Visible tracer beam + muzzle flash + recoil impulse + FOV kick in ALL builds
	C->NotifyWeaponFired(TargetPoint, bHit, bCritHit, bKilledTarget);

	// Recoil kick: pitch up (negative pitch input) with a little yaw wobble.
	C->AddControllerPitchInput(-RecoilPitchDeg * (bAiming ? 0.52f : 1.f));
	C->AddControllerYawInput(FMath::RandRange(-RecoilYawDeg, RecoilYawDeg));
}
