#include "MLGPrologue.h"

#include "MLGAssets.h"
#include "MLGGameMode.h"
#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "Components/AudioComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/SkyAtmosphereComponent.h"
#include "Engine/ExponentialHeightFog.h"
#include "Engine/PointLight.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshActor.h"
#include "EngineUtils.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Sound/SoundBase.h"

namespace
{
	const FVector Pad(-1850, -900, 0);
	const FVector Earth(0, 0, 8000000);
	constexpr float EarthScale = 7.f;
	constexpr int32 CrustCount = 12;
	constexpr int32 EjectaTypeCount = 6;
	constexpr int32 EjectaSpawnCount = 18;
	constexpr TCHAR Root[] = TEXT("/Game/Intro/Prologue/");

	struct FPlumeSpec
	{
		FVector Offset;
		FRotator LocalTilt;
		float WidthScale;
		float LengthScale;
		float GainScale;
	};

	const FPlumeSpec PlumeSpecs[] = {
		{ FVector(0.f, 0.f, 68.f), FRotator(0.f, 0.f, 0.f), 1.15f, 2.55f, 4.4f },
		{ FVector(135.f, 95.f, 75.f), FRotator(8.f, 0.f, -5.f), 0.52f, 1.75f, 3.0f },
		{ FVector(-135.f, 95.f, 75.f), FRotator(-8.f, 0.f, -5.f), 0.52f, 1.75f, 3.0f },
		{ FVector(135.f, -95.f, 75.f), FRotator(8.f, 0.f, 5.f), 0.52f, 1.75f, 3.0f },
		{ FVector(-135.f, -95.f, 75.f), FRotator(-8.f, 0.f, 5.f), 0.52f, 1.75f, 3.0f },
	};

	struct FDropShipPartState
	{
		TWeakObjectPtr<AActor> Actor;
		FVector OrigLocation = FVector::ZeroVector;
		FRotator OrigRotation = FRotator::ZeroRotator;
		bool bOrigCollision = true;
		EComponentMobility::Type OrigMobility = EComponentMobility::Static;
	};

	struct FEjectaState
	{
		TWeakObjectPtr<AStaticMeshActor> Actor;
		FVector Dir = FVector::UpVector;
		FVector SpinAxis = FVector::ForwardVector;
		float Speed = 300.f;
		float Accel = 90.f;
		float SpinRate = 1.5f;
		float Scale = 1.f;
	};

	struct FPrologueRuntimeState
	{
		TWeakObjectPtr<AMLGGameMode> Owner;
		TArray<FDropShipPartState> DropShipParts;
		TArray<TWeakObjectPtr<AStaticMeshActor>> PlumeCones;
		TArray<TWeakObjectPtr<UMaterialInstanceDynamic>> PlumeMats;
		TWeakObjectPtr<AStaticMeshActor> PlumeGlowCard;
		TWeakObjectPtr<AStaticMeshActor> TouchdownRing;
		TWeakObjectPtr<AStaticMeshActor> CoreActor;
		TWeakObjectPtr<UMaterialInstanceDynamic> CoreMat;
		TWeakObjectPtr<AStaticMeshActor> CoreCoronaActor;
		TWeakObjectPtr<UMaterialInstanceDynamic> CoreCoronaMat;
		TWeakObjectPtr<AStaticMeshActor> PlasmaWaveRing;
		TArray<TWeakObjectPtr<UMaterialInstanceDynamic>> CrustSurfaceMats;
		TArray<TWeakObjectPtr<UMaterialInstanceDynamic>> CrustMantleMats;
		TArray<FEjectaState> Ejecta;
		TArray<TWeakObjectPtr<AActor>> MarsAtmosActors;
		bool bMarsAtmosHidden = false;

		void Reset()
		{
			Owner.Reset();
			DropShipParts.Reset();
			PlumeCones.Reset();
			PlumeMats.Reset();
			PlumeGlowCard.Reset();
			TouchdownRing.Reset();
			CoreActor.Reset();
			CoreMat.Reset();
			CoreCoronaActor.Reset();
			CoreCoronaMat.Reset();
			PlasmaWaveRing.Reset();
			CrustSurfaceMats.Reset();
			CrustMantleMats.Reset();
			Ejecta.Reset();
			MarsAtmosActors.Reset();
			bMarsAtmosHidden = false;
		}
	};

	static FPrologueRuntimeState GPrologueState;

	float Ease(float T, float Start, float End)
	{
		return FMath::SmoothStep(0.f, 1.f, FMath::Clamp((T - Start) / (End - Start), 0.f, 1.f));
	}

	void SetGlow(AStaticMeshActor* Actor, const FVector& Location, const FRotator& Facing, float Radius, float Gain)
	{
		if (!IsValid(Actor)) return;
		Actor->SetActorHiddenInGame(Gain <= .005f);
		if (Gain <= .005f) return;
		Actor->SetActorLocationAndRotation(Location, Facing);
		Actor->SetActorScale3D(FVector(Radius / 50.f));
		if (UMaterialInstanceDynamic* MID = Cast<UMaterialInstanceDynamic>(Actor->GetStaticMeshComponent()->GetMaterial(0)))
			MID->SetScalarParameterValue(TEXT("Gain"), Gain);
	}

	UAudioComponent* StartCue(UWorld* World, const TCHAR* Name, EMLGSoundChannel Channel)
	{
		const float Volume = MLGAssets::GetEffectiveChannelVolume(Channel, 1.f);
		if (Volume <= 0.f || !World->AllowAudioPlayback()) return nullptr;
		if (USoundBase* Sound = MLGAssets::LoadOptional<USoundBase>(*(FString(Root) + Name)))
			return UGameplayStatics::SpawnSound2D(World, Sound, Volume);
		return nullptr;
	}
}

void AMLGGameMode::StartIntro(bool bForce)
{
	if (bIntroActive || (!bForce && FParse::Param(FCommandLine::Get(), TEXT("nomenu")))) return;
	APlayerController* PC = UGameplayStatics::GetPlayerController(this, 0);
	if (!PC || !PC->GetPawn()) return;

	UStaticMesh* Globe = MLGAssets::LoadOptional<UStaticMesh>(*(FString(Root) + TEXT("SM_Prologue_Earth")));
	UMaterialInterface* Space = MLGAssets::LoadOptional<UMaterialInterface>(*(FString(Root) + TEXT("M_OrbitalBackdrop")));
	UStaticMesh* Plane = MLGAssets::LoadOptional<UStaticMesh>(TEXT("/Engine/BasicShapes/Plane"));
	if (!Globe || !Space || !Plane)
	{
		UE_LOG(LogTemp, Warning, TEXT("MLG: prologue assets unavailable; starting mission planning"));
		return;
	}

	auto Spawn = [this](UStaticMesh* Mesh, const FVector& Location, float Scale)
	{
		if (!Mesh) return static_cast<AStaticMeshActor*>(nullptr);
		AStaticMeshActor* Actor = GetWorld()->SpawnActor<AStaticMeshActor>(Location, FRotator::ZeroRotator);
		if (!Actor) return Actor;
		Actor->SetActorEnableCollision(false);
		UStaticMeshComponent* C = Actor->GetStaticMeshComponent();
		C->SetMobility(EComponentMobility::Movable);
		C->SetCanEverAffectNavigation(false);
		C->SetStaticMesh(Mesh);
		C->SetCastShadow(false);
		Actor->SetActorScale3D(FVector(Scale));
		IntroActors.Add(Actor);
		return Actor;
	};

	GPrologueState.Reset();
	GPrologueState.Owner = this;

	bIntroActive = true;
	bIntroShattered = false;
	IntroTime = 0.f;
	IntroCamera = GetWorld()->SpawnActor<ACameraActor>();
	IntroEarth = Spawn(Globe, Earth, EarthScale);
	IntroBackdrop = Spawn(Plane, Earth + FVector(4400, 0, 0), 140.f);
	if (!IntroCamera || !IntroEarth || !IntroBackdrop)
	{
		EndIntro();
		return;
	}
	IntroBackdrop->SetActorRotation(FRotationMatrix::MakeFromZ(-FVector::ForwardVector).Rotator());
	IntroBackdrop->GetStaticMeshComponent()->SetMaterial(0, Space);
	IntroEarthMaterial = IntroEarth->GetStaticMeshComponent()->CreateDynamicMaterialInstance(0);

	// Multi-layered incandescent magma mantle core + outer plasma corona shell
	if (UStaticMesh* CoreMesh = MLGAssets::LoadOptional<UStaticMesh>(*(FString(Root) + TEXT("SM_Prologue_Core"))))
	{
		if (AStaticMeshActor* Core = Spawn(CoreMesh, Earth, EarthScale))
		{
			if (UMaterialInterface* CoreMat = MLGAssets::LoadOptional<UMaterialInterface>(*(FString(Root) + TEXT("M_PrologueCore"))))
				GPrologueState.CoreMat = Core->GetStaticMeshComponent()->CreateDynamicMaterialInstance(0, CoreMat);
			Core->SetActorHiddenInGame(true);
			GPrologueState.CoreActor = Core;
		}
		if (AStaticMeshActor* Corona = Spawn(CoreMesh, Earth, EarthScale * 1.075f))
		{
			if (UMaterialInterface* CoronaMat = MLGAssets::LoadOptional<UMaterialInterface>(*(FString(Root) + TEXT("M_PrologueCoreCorona"))))
				GPrologueState.CoreCoronaMat = Corona->GetStaticMeshComponent()->CreateDynamicMaterialInstance(0, CoronaMat);
			Corona->SetActorHiddenInGame(true);
			GPrologueState.CoreCoronaActor = Corona;
		}
	}

	for (int32 I = 0; I < CrustCount; ++I)
	{
		const FString Path = FString::Printf(TEXT("%sSM_Prologue_Crust_%02d"), Root, I);
		if (AStaticMeshActor* Shell = Spawn(MLGAssets::LoadOptional<UStaticMesh>(*Path), Earth, EarthScale))
		{
			GPrologueState.CrustSurfaceMats.Add(Shell->GetStaticMeshComponent()->CreateDynamicMaterialInstance(0));
			if (Shell->GetStaticMeshComponent()->GetNumMaterials() > 1)
				GPrologueState.CrustMantleMats.Add(Shell->GetStaticMeshComponent()->CreateDynamicMaterialInstance(1));
			Shell->SetActorHiddenInGame(true);
			IntroCrust.Add(Shell);
		}
	}

	// Tumbling 3D crustal asteroid ejecta fragments
	TArray<UStaticMesh*> EjectaMeshes;
	for (int32 I = 0; I < EjectaTypeCount; ++I)
	{
		const FString EPath = FString::Printf(TEXT("%sSM_Prologue_Ejecta_%02d"), Root, I);
		if (UStaticMesh* EM = MLGAssets::LoadOptional<UStaticMesh>(*EPath))
			EjectaMeshes.Add(EM);
	}
	if (EjectaMeshes.Num() > 0)
	{
		for (int32 I = 0; I < EjectaSpawnCount; ++I)
		{
			UStaticMesh* EM = EjectaMeshes[I % EjectaMeshes.Num()];
			const float EscScale = EarthScale * (0.35f + 0.14f * (I % 5));
			if (AStaticMeshActor* Frag = Spawn(EM, Earth, EscScale))
			{
				Frag->SetActorHiddenInGame(true);
				const float Theta = I * 2.39996323f;
				const float ZSpread = -0.65f + 1.30f * ((I % 7) / 6.f);
				const float RXY = FMath::Sqrt(FMath::Max(0.05f, 1.f - ZSpread * ZSpread));
				FEjectaState State;
				State.Actor = Frag;
				State.Dir = FVector(-0.42f + 0.30f * FMath::Cos(Theta * 1.7f), FMath::Cos(Theta) * RXY, FMath::Sin(Theta) * RXY + ZSpread * 0.45f).GetSafeNormal();
				State.SpinAxis = FVector(FMath::Sin(Theta * 2.1f), FMath::Cos(Theta * 1.3f), 0.6f + 0.4f * (I % 3)).GetSafeNormal();
				State.Speed = 230.f + 26.f * (I % 6);
				State.Accel = 85.f + 18.f * (I % 4);
				State.SpinRate = 0.85f + 0.35f * (I % 5);
				State.Scale = EscScale;
				GPrologueState.Ejecta.Add(State);
			}
		}
	}

	UMaterialInterface* Glow = MLGAssets::LoadOptional<UMaterialInterface>(*(FString(Root) + TEXT("M_PrologueGlow")));
	UMaterialInterface* PlumeMat = MLGAssets::LoadOptional<UMaterialInterface>(*(FString(Root) + TEXT("M_ProloguePlume")));
	UStaticMesh* Cone = MLGAssets::LoadOptional<UStaticMesh>(TEXT("/Engine/BasicShapes/Cone"));

	auto GlowCard = [&](const FLinearColor& Tint, bool bRing = false)
	{
		AStaticMeshActor* Actor = Glow ? Spawn(Plane, Pad, 1.f) : nullptr;
		if (Actor)
		{
			if (UMaterialInstanceDynamic* MID = Actor->GetStaticMeshComponent()->CreateDynamicMaterialInstance(0, Glow))
			{
				MID->SetVectorParameterValue(TEXT("Tint"), Tint);
				MID->SetScalarParameterValue(TEXT("Ring"), bRing ? 1.f : 0.f);
			}
			Actor->SetActorHiddenInGame(true);
		}
		return Actor;
	};

	IntroFlash = GlowCard(FLinearColor(1.f, .52f, .18f));
	IntroShockwave = GlowCard(FLinearColor(1.f, .34f, .09f), true);
	GPrologueState.PlasmaWaveRing = GlowCard(FLinearColor(.52f, .82f, 1.f), true);
	GPrologueState.TouchdownRing = GlowCard(FLinearColor(.92f, .44f, .18f), true);
	GPrologueState.PlumeGlowCard = GlowCard(FLinearColor(1.f, .52f, .16f));

	UMaterialInterface* PlumeBaseMat = PlumeMat ? PlumeMat : Glow;
	if (Cone && PlumeBaseMat)
	{
		for (int32 I = 0; I < UE_ARRAY_COUNT(PlumeSpecs); ++I)
		{
			if (AStaticMeshActor* Plume = Spawn(Cone, Pad, 1.f))
			{
				UMaterialInstanceDynamic* MID = Plume->GetStaticMeshComponent()->CreateDynamicMaterialInstance(0, PlumeBaseMat);
				if (MID)
				{
					MID->SetVectorParameterValue(TEXT("Tint"), I == 0 ? FLinearColor(1.f, .58f, .20f) : FLinearColor(1.f, .40f, .10f));
					MID->SetScalarParameterValue(TEXT("Ring"), 0.f);
				}
				Plume->SetActorHiddenInGame(true);
				GPrologueState.PlumeCones.Add(Plume);
				GPrologueState.PlumeMats.Add(MID);
			}
		}
	}

	for (int32 I = 0; I < 24; ++I)
		if (AStaticMeshActor* Ember = GlowCard(FLinearColor(1.f, .34f + .08f * (I % 4), .095f)))
			IntroDebris.Add(Ember);
	for (int32 I = 0; I < 12; ++I)
		if (AStaticMeshActor* Puff = GlowCard(FLinearColor(.72f, .28f, .08f)))
			IntroDust.Add(Puff);

	// Coordinate cleanly with the larger enterable DropShip compound at (-1850, -900, 0)
	IntroLander = nullptr;
	for (TActorIterator<AActor> It(GetWorld()); It; ++It)
	{
		AActor* Candidate = *It;
		if (!Candidate || FVector::Dist2D(Candidate->GetActorLocation(), Pad) > 850.f) continue;
		bool bMatched = Candidate->ActorHasTag(TEXT("DropShip"));
#if WITH_EDITOR
		if (!bMatched)
		{
			const FString Label = Candidate->GetActorLabel();
			if (!Label.StartsWith(TEXT("LandingPad_")) && !Label.Contains(TEXT("Rim")))
				bMatched = Label.StartsWith(TEXT("DropShip_")) || Label.StartsWith(TEXT("SM_Tripo_DropLander"));
		}
#endif
		if (!bMatched)
		{
			if (const AStaticMeshActor* SMA = Cast<AStaticMeshActor>(Candidate))
			{
				const UStaticMesh* Mesh = SMA->GetStaticMeshComponent() ? SMA->GetStaticMeshComponent()->GetStaticMesh() : nullptr;
				bMatched = Mesh && (Mesh->GetName().Contains(TEXT("DropLander")) || Mesh->GetName().Contains(TEXT("DropShip")));
			}
		}
		if (!bMatched) continue;

		FDropShipPartState Part;
		Part.Actor = Candidate;
		Part.OrigLocation = Candidate->GetActorLocation();
		Part.OrigRotation = Candidate->GetActorRotation();
		Part.bOrigCollision = Candidate->GetActorEnableCollision();
		if (USceneComponent* RootComp = Candidate->GetRootComponent())
		{
			Part.OrigMobility = RootComp->Mobility;
			RootComp->SetMobility(EComponentMobility::Movable);
		}
		Candidate->SetActorEnableCollision(false);
		GPrologueState.DropShipParts.Add(Part);
	}

	if (GPrologueState.DropShipParts.Num() > 0)
	{
		IntroLandingPosition = Pad;
		IntroLandingRotation = FRotator::ZeroRotator;
	}
	else
	{
		IntroLander = Spawn(MLGAssets::LoadOptional<UStaticMesh>(TEXT("/Game/Tripo/SM_Tripo_DropLander")), Pad, MLGPrologue::LanderPadScale);
		if (IntroLander)
		{
			IntroLander->SetActorRotation(FRotator(0, -25, 0));
			IntroLandingPosition = IntroLander->GetActorLocation();
			IntroLandingRotation = IntroLander->GetActorRotation();
			bIntroLanderCollision = IntroLander->GetActorEnableCollision();
		}
		else
		{
			IntroLandingPosition = Pad;
			IntroLandingRotation = FRotator(0, -25, 0);
		}
	}

	IntroThruster = GetWorld()->SpawnActor<APointLight>();
	if (IntroThruster)
	{
		IntroThruster->GetLightComponent()->SetMobility(EComponentMobility::Movable);
		IntroThruster->PointLightComponent->SetAttenuationRadius(1500.f);
		IntroThruster->GetLightComponent()->SetLightColor(FLinearColor(1.f, .36f, .09f));
		IntroThruster->GetLightComponent()->SetCastShadows(false);
	}

	UCameraComponent* Camera = IntroCamera->GetCameraComponent();
	Camera->PostProcessBlendWeight = 1.f;
	Camera->PostProcessSettings.bOverride_MotionBlurAmount = true;
	Camera->PostProcessSettings.MotionBlurAmount = .22f;
	Camera->PostProcessSettings.bOverride_VignetteIntensity = true;
	Camera->PostProcessSettings.VignetteIntensity = .34f;
	for (TActorIterator<ASkyAtmosphere> It(GetWorld()); It; ++It) GPrologueState.MarsAtmosActors.Add(*It);
	for (TActorIterator<AExponentialHeightFog> It(GetWorld()); It; ++It) GPrologueState.MarsAtmosActors.Add(*It);
	TickIntro(0.f);
	PC->SetViewTarget(IntroCamera);
	IntroScore = StartCue(GetWorld(), TEXT("Prologue_Score"), EMLGSoundChannel::Music);
	IntroDialogue = StartCue(GetWorld(), TEXT("Prologue_Radio"), EMLGSoundChannel::SFX);
	UE_LOG(LogTemp, Display, TEXT("MLG: prologue started (crust=%d dropshipParts=%d ejecta=%d score=%d radio=%d)"),
		IntroCrust.Num(), GPrologueState.DropShipParts.Num(), GPrologueState.Ejecta.Num(),
		IntroScore != nullptr, IntroDialogue != nullptr);
}

void AMLGGameMode::EndIntro()
{
	if (!bIntroActive) return;
	bIntroActive = false;
	if (APlayerController* PC = UGameplayStatics::GetPlayerController(this, 0))
		if (APawn* Pawn = PC->GetPawn()) PC->SetViewTarget(Pawn);

	for (const FDropShipPartState& Part : GPrologueState.DropShipParts)
	{
		if (AActor* Actor = Part.Actor.Get())
		{
			Actor->SetActorLocationAndRotation(Part.OrigLocation, Part.OrigRotation);
			Actor->SetActorEnableCollision(Part.bOrigCollision);
			if (USceneComponent* RootComp = Actor->GetRootComponent())
				RootComp->SetMobility(Part.OrigMobility);
		}
	}
	if (IsValid(IntroLander))
	{
		IntroLander->SetActorLocationAndRotation(IntroLandingPosition, IntroLandingRotation);
		IntroLander->SetActorEnableCollision(bIntroLanderCollision);
	}
	IntroLander = nullptr;
	if (IsValid(IntroScore)) IntroScore->FadeOut(.15f, 0.f);
	if (IsValid(IntroDialogue)) IntroDialogue->FadeOut(.12f, 0.f);
	IntroScore = nullptr;
	IntroDialogue = nullptr;
	for (AStaticMeshActor* Actor : IntroActors)
		if (IsValid(Actor)) Actor->Destroy();
	IntroActors.Reset();
	IntroCrust.Reset();
	IntroDebris.Reset();
	IntroDust.Reset();
	IntroEarth = IntroBackdrop = IntroFlash = IntroShockwave = nullptr;
	IntroEarthMaterial = nullptr;
	if (IsValid(IntroThruster)) IntroThruster->Destroy();
	IntroThruster = nullptr;
	if (IsValid(IntroCamera)) IntroCamera->Destroy();
	IntroCamera = nullptr;
	for (const TWeakObjectPtr<AActor>& Atmos : GPrologueState.MarsAtmosActors)
	{
		if (AActor* A = Atmos.Get()) A->SetActorHiddenInGame(false);
	}
	GPrologueState.Reset();
	UE_LOG(LogTemp, Display, TEXT("MLG: prologue ended at %.2f"), IntroTime);
}

void AMLGGameMode::TickIntro(float Dt)
{
	using namespace MLGPrologue;
	if (!bIntroActive || !IsValid(IntroCamera)) return;
	IntroTime += Dt;
	const float T = IntroTime;
	if (T >= Duration)
	{
		EndIntro();
		return;
	}

	const float Settle = Ease(T, 0.f, Touchdown);
	const float Height = 1280.f * FMath::Square(1.f - Settle);
	const float Stabilize = 1.f - Ease(T, Touchdown * 0.45f, Touchdown * 0.94f);
	const float Sway = (1.f - Settle) * FMath::Sin(T * 2.9f);
	const float PostTouch = FMath::Max(0.f, T - Touchdown);
	const float BounceZ = (T >= Touchdown && PostTouch < 0.65f)
		? -5.f * FMath::Exp(-PostTouch * 6.5f) * FMath::Sin(PostTouch * 15.f)
		: 0.f;
	const float BouncePitch = (T >= Touchdown && PostTouch < 0.65f)
		? -0.85f * FMath::Exp(-PostTouch * 6.f) * FMath::Sin(PostTouch * 13.f)
		: 0.f;

	const FRotator LanderTilt(
		7.5f * Stabilize + 0.8f * Sway + BouncePitch,
		9.0f * Stabilize,
		-3.5f * Stabilize + 1.1f * Sway);
	const FRotator LanderRot = IntroLandingRotation + LanderTilt;
	const FVector BasePad = GPrologueState.DropShipParts.Num() > 0 ? Pad : (IsValid(IntroLander) ? IntroLandingPosition : Pad);
	const FVector Lander = BasePad + FVector(0.f, 0.f, Height + BounceZ);

	if (GPrologueState.Owner == this && GPrologueState.DropShipParts.Num() > 0)
	{
		const FQuat TiltQuat = LanderTilt.Quaternion();
		for (const FDropShipPartState& Part : GPrologueState.DropShipParts)
		{
			if (AActor* Actor = Part.Actor.Get())
			{
				const FVector Rel = Part.OrigLocation - Pad;
				const FVector NewPos = Lander + TiltQuat.RotateVector(Rel);
				const FQuat NewRot = TiltQuat * Part.OrigRotation.Quaternion();
				Actor->SetActorLocationAndRotation(NewPos, NewRot);
			}
		}
	}
	else if (IsValid(IntroLander))
	{
		IntroLander->SetActorLocationAndRotation(Lander, LanderRot);
	}

	const float BurnCutoff = Touchdown + 0.35f;
	const float BurnFade = (T < Touchdown)
		? (1.f - 0.25f * Ease(T, Touchdown - 0.35f, Touchdown))
		: (1.f - Ease(T, Touchdown, BurnCutoff));
	const float ThrusterFlicker = 0.88f + 0.14f * FMath::Sin(T * 37.f) + 0.08f * FMath::Cos(T * 61.f);

	if (IsValid(IntroThruster))
	{
		IntroThruster->SetActorLocation(Lander + LanderTilt.RotateVector(FVector(0.f, 0.f, ThrusterLightOffsetZ)));
		IntroThruster->GetLightComponent()->SetIntensity(
			(T < BurnCutoff) ? 520.f * ThrusterFlicker * BurnFade : 0.f);
	}

	FVector CameraLoc;
	FVector Target;
	float FOV;
	const bool bOrbit = T >= OrbitalCut && T < SurfaceCut;
	if (GPrologueState.Owner == this && GPrologueState.bMarsAtmosHidden != bOrbit)
	{
		GPrologueState.bMarsAtmosHidden = bOrbit;
		for (const TWeakObjectPtr<AActor>& Atmos : GPrologueState.MarsAtmosActors)
		{
			if (AActor* A = Atmos.Get()) A->SetActorHiddenInGame(bOrbit);
		}
	}
	const float BurstAge = FMath::Max(0.f, T - Rupture);
	if (T < OrbitalCut)
	{
		CameraLoc = BasePad + FMath::Lerp(FVector(-1950, -1380, 1120), FVector(-1480, -860, 520), Ease(T, 0.f, OrbitalCut));
		Target = Lander + FVector(30, -20, 220);
		FOV = FMath::Lerp(58.f, 50.f, Settle);
	}
	else if (bOrbit)
	{
		const float Drift = Ease(T, OrbitalCut, Rupture);
		const float Pullback = Ease(T, Rupture, SurfaceCut);
		CameraLoc = Earth + FVector(-2850 + 260 * Drift - 1150 * Pullback, -225 + 430 * Drift, 45 - 110 * Drift);
		Target = Earth + FVector(0, 235 - 195 * Pullback, 42);
		FOV = 48.f + 14.f * Pullback;
	}
	else
	{
		const float Reveal = Ease(T, SurfaceCut, Duration);
		CameraLoc = FMath::Lerp(FVector(-3260, -2170, 920), FVector(-2840, -1750, 790), Reveal);
		Target = FMath::Lerp(BasePad + FVector(0, 0, 220), FVector(-60, 70, 360), Reveal);
		FOV = 64.f;
	}

	const float PreRuptureTremor = bOrbit && T >= FirstFissures && T < Rupture
		? 0.28f * Ease(T, FirstFissures, Rupture)
		: 0.f;
	const float Shake = bOrbit && T >= Rupture ? FMath::Exp(-BurstAge * 3.4f) :
		(T >= Touchdown && T < OrbitalCut ? .42f * FMath::Exp(-(T - Touchdown) * 5.f) : PreRuptureTremor);
	CameraLoc += FVector(1.5f * FMath::Cos(77 * T), 9.f * FMath::Sin(53 * T), 7.f * FMath::Cos(68 * T)) * Shake;
	FRotator View = (Target - CameraLoc).Rotation();
	View.Roll += .5f * FMath::Sin(64 * T) * Shake;
	IntroCamera->SetActorLocationAndRotation(CameraLoc, View);
	IntroCamera->GetCameraComponent()->SetFieldOfView(FOV);

	if (GPrologueState.Owner == this)
	{
		const bool bPlumeVisible = T < BurnCutoff && T < OrbitalCut && BurnFade > 0.01f;
		const float ClearanceScale = FMath::Clamp((Height + 115.f) / 260.f, 0.34f, 1.38f);
		const FQuat LanderQuat = (GPrologueState.DropShipParts.Num() > 0 ? LanderTilt : LanderRot).Quaternion();
		for (int32 I = 0; I < GPrologueState.PlumeCones.Num() && I < UE_ARRAY_COUNT(PlumeSpecs); ++I)
		{
			AStaticMeshActor* Plume = GPrologueState.PlumeCones[I].Get();
			if (!IsValid(Plume)) continue;
			Plume->SetActorHiddenInGame(!bPlumeVisible);
			if (!bPlumeVisible) continue;

			const FPlumeSpec& Spec = PlumeSpecs[I];
			const FQuat PlumeQuat = LanderQuat * Spec.LocalTilt.Quaternion() * FQuat(FRotator(180.f, 0.f, 0.f));
			const float LenScale = Spec.LengthScale * ClearanceScale * (0.94f + 0.06f * ThrusterFlicker);
			const FVector AxisDown = (LanderQuat * Spec.LocalTilt.Quaternion()).RotateVector(-FVector::UpVector);
			const FVector PlumePos = Lander + LanderQuat.RotateVector(Spec.Offset) + AxisDown * (50.f * LenScale);
			Plume->SetActorLocationAndRotation(PlumePos, PlumeQuat);
			Plume->SetActorScale3D(FVector(Spec.WidthScale, Spec.WidthScale, LenScale));

			if (I < GPrologueState.PlumeMats.Num())
			{
				if (UMaterialInstanceDynamic* MID = GPrologueState.PlumeMats[I].Get())
				{
					MID->SetScalarParameterValue(TEXT("Gain"), Spec.GainScale * BurnFade * ThrusterFlicker);
					MID->SetScalarParameterValue(TEXT("Time"), T);
				}
			}
		}

		const FVector UnderBellPos = Lander + LanderQuat.RotateVector(FVector(0.f, 0.f, 24.f));
		SetGlow(
			GPrologueState.PlumeGlowCard.Get(),
			UnderBellPos,
			FRotationMatrix::MakeFromZ((CameraLoc - UnderBellPos).GetSafeNormal()).Rotator(),
			230.f * (0.65f + 0.35f * BurnFade),
			bPlumeVisible ? 2.6f * BurnFade * ThrusterFlicker : 0.f);
	}

	const FRotator FaceCamera = FRotationMatrix::MakeFromZ((CameraLoc - Earth).GetSafeNormal()).Rotator();
	const FRotator GlobeRotation(4.f, 16.f + FMath::Clamp(T - OrbitalCut, 0.f, Rupture - OrbitalCut) * 2.3f, -16.f);
	const float Crack = Ease(T, FirstFissures, Rupture);
	if (IsValid(IntroEarth))
	{
		IntroEarth->SetActorRotation(GlobeRotation);
		IntroEarth->SetActorHiddenInGame(T >= Rupture && IntroCrust.Num() == CrustCount);
	}
	if (IntroEarthMaterial)
	{
		IntroEarthMaterial->SetScalarParameterValue(TEXT("CrackAmount"), Crack);
		IntroEarthMaterial->SetScalarParameterValue(TEXT("Heat"), Crack);
		IntroEarthMaterial->SetScalarParameterValue(TEXT("Time"), T);
	}

	const bool bShatteredNow = (T >= Rupture);
	if (bShatteredNow && !bIntroShattered)
	{
		bIntroShattered = true;
		UE_LOG(LogTemp, Display, TEXT("MLG: prologue rupture"));
	}
	else if (!bShatteredNow)
	{
		bIntroShattered = false;
	}

	if (GPrologueState.Owner == this)
	{
		if (AStaticMeshActor* Core = GPrologueState.CoreActor.Get())
		{
			Core->SetActorHiddenInGame(!bShatteredNow);
			if (bShatteredNow)
			{
				Core->SetActorLocationAndRotation(Earth, GlobeRotation + FRotator(0.f, BurstAge * 4.5f, 0.f));
				if (UMaterialInstanceDynamic* MID = GPrologueState.CoreMat.Get())
				{
					MID->SetScalarParameterValue(TEXT("Gain"), 1.25f + 1.85f * FMath::Exp(-BurstAge * 0.65f));
					MID->SetScalarParameterValue(TEXT("Time"), T);
				}
			}
		}
		if (AStaticMeshActor* Corona = GPrologueState.CoreCoronaActor.Get())
		{
			Corona->SetActorHiddenInGame(!bShatteredNow);
			if (bShatteredNow)
			{
				Corona->SetActorLocationAndRotation(Earth, GlobeRotation - FRotator(0.f, BurstAge * 3.0f, 0.f));
				if (UMaterialInstanceDynamic* MID = GPrologueState.CoreCoronaMat.Get())
				{
					MID->SetScalarParameterValue(TEXT("Gain"), 0.70f + 1.45f * FMath::Exp(-BurstAge * 0.52f));
					MID->SetScalarParameterValue(TEXT("Time"), T);
				}
			}
		}
	}

	for (int32 I = 0; I < IntroCrust.Num(); ++I)
	{
		AStaticMeshActor* Shell = IntroCrust[I];
		if (!IsValid(Shell)) continue;
		Shell->SetActorHiddenInGame(!bShatteredNow);
		if (!bShatteredNow) continue;

		const FVector Pivot = Shell->GetStaticMeshComponent()->GetStaticMesh()->GetBounds().Origin * EarthScale;
		const FVector Direction = GlobeRotation.RotateVector(Pivot.GetSafeNormal());
		const FQuat Spin(Direction.Cross(FVector(.4f, .7f, 1.f)).GetSafeNormal(), BurstAge * (.16f + .045f * (I % 4)));
		const FQuat Orientation = Spin * GlobeRotation.Quaternion();
		const float RadialDisp = BurstAge * (145.f + 16.f * (I % 5)) + 56.f * BurstAge * BurstAge;
		const FVector Offset = Direction * RadialDisp;
		Shell->SetActorLocationAndRotation(Earth + Offset + GlobeRotation.RotateVector(Pivot) - Orientation.RotateVector(Pivot), Orientation);

		if (GPrologueState.Owner == this)
		{
			if (I < GPrologueState.CrustSurfaceMats.Num() && GPrologueState.CrustSurfaceMats[I].IsValid())
			{
				GPrologueState.CrustSurfaceMats[I]->SetScalarParameterValue(TEXT("CrackAmount"), 1.f);
				GPrologueState.CrustSurfaceMats[I]->SetScalarParameterValue(TEXT("Time"), T);
			}
			if (I < GPrologueState.CrustMantleMats.Num() && GPrologueState.CrustMantleMats[I].IsValid())
			{
				GPrologueState.CrustMantleMats[I]->SetScalarParameterValue(TEXT("Gain"), 1.25f + 0.65f * FMath::Exp(-BurstAge * 0.8f));
				GPrologueState.CrustMantleMats[I]->SetScalarParameterValue(TEXT("Time"), T);
			}
		}
	}

	if (GPrologueState.Owner == this)
	{
		for (const FEjectaState& FragState : GPrologueState.Ejecta)
		{
			AStaticMeshActor* Frag = FragState.Actor.Get();
			if (!IsValid(Frag)) continue;
			Frag->SetActorHiddenInGame(!bShatteredNow || !bOrbit);
			if (!bShatteredNow || !bOrbit) continue;

			const float Dist = 660.f + FragState.Speed * BurstAge + 0.5f * FragState.Accel * BurstAge * BurstAge;
			const FQuat FragSpin(FragState.SpinAxis, BurstAge * FragState.SpinRate);
			Frag->SetActorLocationAndRotation(Earth + FragState.Dir * Dist, FragSpin);
			Frag->SetActorScale3D(FVector(FragState.Scale));
		}
	}

	for (int32 I = 0; I < IntroDebris.Num(); ++I)
	{
		const float Angle = I * 2.39996323f;
		const FVector Drift(70.f * (I % 5 - 2), FMath::Cos(Angle) * (410.f + 29.f * I), FMath::Sin(Angle) * (410.f + 29.f * I));
		SetGlow(IntroDebris[I], Earth + Drift * (BurstAge + 0.85f), FaceCamera, 12.f + (I % 6) * 5.f,
			(bOrbit && bShatteredNow) ? 7.5f * FMath::Exp(-BurstAge * .52f) : 0.f);
	}

	const float Preflash = .9f * Ease(T, Rupture - .22f, Rupture);
	const float Flare = T < Rupture ? Preflash : 22.f * FMath::Exp(-BurstAge * 2.9f);
	SetGlow(IntroFlash, Earth + FVector(-730, -50, 25), FaceCamera, 750 + BurstAge * 180,
		bOrbit ? Flare : 0.f);
	SetGlow(IntroShockwave, Earth + FVector(-120, 0, 0), FaceCamera, 720 + BurstAge * 1350,
		bOrbit && bShatteredNow ? 1.15f * FMath::Exp(-BurstAge * 1.35f) : 0.f);
	if (GPrologueState.Owner == this)
	{
		SetGlow(GPrologueState.PlasmaWaveRing.Get(), Earth + FVector(-150, 0, 0), FaceCamera, 740 + BurstAge * 1780,
			bOrbit && bShatteredNow ? 0.95f * FMath::Exp(-BurstAge * 1.65f) : 0.f);
	}

	const FVector TouchdownGround = BasePad + FVector(0.f, 0.f, 12.f);
	if (GPrologueState.Owner == this)
	{
		const float RingAge = T - Touchdown;
		const bool bShowRing = T >= Touchdown && T < OrbitalCut;
		SetGlow(
			GPrologueState.TouchdownRing.Get(),
			TouchdownGround + FVector(0.f, 0.f, 4.f),
			FRotator::ZeroRotator,
			320.f + FMath::Max(0.f, RingAge) * 820.f,
			bShowRing ? 1.25f * Ease(RingAge, 0.f, 0.10f) * FMath::Exp(-RingAge * 1.45f) : 0.f);
	}

	for (int32 I = 0; I < IntroDust.Num(); ++I)
	{
		const float Age = T - 3.38f - .07f * I;
		const float Angle = I * 2.39996323f;
		const FVector Dust = TouchdownGround + FVector(FMath::Cos(Angle), FMath::Sin(Angle), 0) * (110.f + FMath::Max(0.f, Age) * (250.f + 12.f * I))
			+ FVector(0, 0, 14 + (I % 4) * 12 + FMath::Max(0.f, Age) * 24.f);
		SetGlow(IntroDust[I], Dust, FRotationMatrix::MakeFromZ((CameraLoc - Dust).GetSafeNormal()).Rotator(),
			220 + FMath::Max(0.f, Age) * 85.f, T < OrbitalCut ? .48f * Ease(Age, 0.f, .65f) * (1.f - Ease(Age, 1.3f, 4.f)) : 0.f);
	}
}
