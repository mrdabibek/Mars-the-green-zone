#include "MLGAssets.h"
#include "MLGSettings.h"
#include "Sound/SoundAttenuation.h"
#include "Sound/SoundBase.h"
#include "Sound/SoundWave.h"
#include "Components/AudioComponent.h"
#include "Components/PrimitiveComponent.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Kismet/GameplayStatics.h"
#include "HAL/PlatformTime.h"
#include "Engine/Engine.h"
#include "Engine/World.h"

namespace MLGAssets
{
	static TMap<FString, double> GLastCuePlayTime;

	UObject* LoadOptionalObject(UClass* AssetClass, const TCHAR* ObjectPath)
	{
		if (!AssetClass || !ObjectPath || !*ObjectPath) return nullptr;
		const FString Raw(ObjectPath);
		const FString PkgName = FPackageName::ObjectPathToPackageName(Raw);
		if (PkgName.IsEmpty() || !FPackageName::DoesPackageExist(PkgName)) return nullptr;

		FString FullPath = Raw;
		if (!Raw.Contains(TEXT(".")))
		{
			const FString ShortName = FPackageName::GetShortName(PkgName);
			FullPath = PkgName + TEXT(".") + ShortName;
		}
		return StaticLoadObject(AssetClass, nullptr, *FullPath);
	}

	float ComputeChannelVolume(EMLGSoundChannel Channel, float VolumeMul, float MasterVol, float SFXVol, float MusicVol, float AmbienceVol, bool bMasterAppliedOnDevice)
	{
		const float Master = FMath::Clamp(MasterVol, 0.f, 1.f);
		if (Master <= KINDA_SMALL_NUMBER || VolumeMul <= 0.f) return 0.f;

		float ChannelScale = 1.f;
		switch (Channel)
		{
		case EMLGSoundChannel::Music:    ChannelScale = FMath::Clamp(MusicVol, 0.f, 1.f); break;
		case EMLGSoundChannel::Ambience: ChannelScale = FMath::Clamp(AmbienceVol, 0.f, 1.f); break;
		case EMLGSoundChannel::UI:       ChannelScale = FMath::Clamp(SFXVol, 0.f, 1.f); break;
		case EMLGSoundChannel::SFX:
		default:                         ChannelScale = FMath::Clamp(SFXVol, 0.f, 1.f); break;
		}
		if (ChannelScale <= KINDA_SMALL_NUMBER) return 0.f;

		const float EffectiveMaster = bMasterAppliedOnDevice ? 1.f : Master;
		return FMath::Max(0.f, VolumeMul) * ChannelScale * EffectiveMaster;
	}

	float GetEffectiveChannelVolume(EMLGSoundChannel Channel, float VolumeMul)
	{
		const UMLGSettings* Settings = UMLGSettings::Get();
		const float Master = Settings ? Settings->MasterVolume : 1.f;
		const float SFX = Settings ? Settings->SFXVolume : 0.9f;
		const float Music = Settings ? Settings->MusicVolume : 0.7f;
		const float Ambience = Settings ? Settings->AmbienceVolume : 0.8f;
		// ApplyAudio() sets TransientPrimaryVolume on the main audio device; avoid squaring MasterVolume when an audio device is active.
		const bool bHasAudioDevice = GEngine && GEngine->GetMainAudioDevice().IsValid();
		return ComputeChannelVolume(Channel, VolumeMul, Master, SFX, Music, Ambience, bHasAudioDevice);
	}

	EMLGSoundChannel ClassifySoundChannel(const TCHAR* AssetPath)
	{
		if (!AssetPath || !*AssetPath) return EMLGSoundChannel::SFX;
		const FString S(AssetPath);
		if (S.Contains(TEXT("Music_"))) return EMLGSoundChannel::Music;
		if (S.Contains(TEXT("Wind_Loop"))) return EMLGSoundChannel::Ambience;
		if (S.Contains(TEXT("UI_Click"))) return EMLGSoundChannel::UI;
		return EMLGSoundChannel::SFX;
	}

	float GetCueCooldownSeconds(const TCHAR* AssetPath)
	{
		if (!AssetPath || !*AssetPath) return 0.f;
		const FString S(AssetPath);
		if (S.Contains(TEXT("Alert_Low"))) return 1.5f;
		if (S.Contains(TEXT("LowO2_Heartbeat"))) return 1.8f;
		if (S.Contains(TEXT("Player_Hurt"))) return 0.25f;
		if (S.Contains(TEXT("Footstep_"))) return 0.18f;
		if (S.Contains(TEXT("Repair_Tick"))) return 0.14f;
		if (S.Contains(TEXT("Turret_Fire"))) return 0.09f;
		if (S.Contains(TEXT("Alien_Hit"))) return 0.08f;
		if (S.Contains(TEXT("Hit_Marker"))) return 0.05f;
		if (S.Contains(TEXT("UI_Click"))) return 0.04f;
		return 0.02f;
	}

	bool TryPassSoundCooldown(const TCHAR* AssetPath, double NowSeconds)
	{
		if (!AssetPath || !*AssetPath) return false;
		const float Cooldown = GetCueCooldownSeconds(AssetPath);
		if (Cooldown <= 0.f) return true;
		const FString Key(AssetPath);
		if (const double* LastTime = GLastCuePlayTime.Find(Key))
		{
			if ((NowSeconds - *LastTime) < (double)Cooldown)
			{
				return false;
			}
		}
		GLastCuePlayTime.Add(Key, NowSeconds);
		return true;
	}

	void ResetSoundCooldowns()
	{
		GLastCuePlayTime.Empty();
	}

	static USoundAttenuation* CreateConfiguredAttenuation(float FalloffDist)
	{
		USoundAttenuation* Att = NewObject<USoundAttenuation>(GetTransientPackage());
		Att->AddToRoot();
		FSoundAttenuationSettings& A = Att->Attenuation;
		A.bAttenuate = true;
		A.bSpatialize = true;
		A.AttenuationShape = EAttenuationShape::Sphere;
		A.AttenuationShapeExtents = FVector(350.f, 0.f, 0.f);
		A.FalloffDistance = FalloffDist;
		A.DistanceAlgorithm = EAttenuationDistanceModel::NaturalSound;
		A.dBAttenuationAtMax = -42.f;
		A.bAttenuateWithLPF = true;
		A.LPFRadiusMin = 600.f;
		A.LPFRadiusMax = 3000.f;
		A.LPFFrequencyAtMin = 20000.f;
		A.LPFFrequencyAtMax = 2400.f;
		return Att;
	}

	USoundAttenuation* GetSpatialAttenuation(bool bHeavyCombat)
	{
		static USoundAttenuation* StandardAtt = nullptr;
		static USoundAttenuation* HeavyCombatAtt = nullptr;
		if (bHeavyCombat)
		{
			if (!IsValid(HeavyCombatAtt)) HeavyCombatAtt = CreateConfiguredAttenuation(4200.f);
			return HeavyCombatAtt;
		}
		if (!IsValid(StandardAtt)) StandardAtt = CreateConfiguredAttenuation(2800.f);
		return StandardAtt;
	}

	static bool IsHeavyCombatSound(const TCHAR* AssetPath)
	{
		if (!AssetPath || !*AssetPath) return false;
		const FString S(AssetPath);
		return S.Contains(TEXT("Breaker_Slam"))
			|| S.Contains(TEXT("Gunner_Charge"))
			|| S.Contains(TEXT("Raider_Telegraph"))
			|| S.Contains(TEXT("Rifle_Fire"))
			|| S.Contains(TEXT("Turret_Fire"))
			|| S.Contains(TEXT("Alien_Death"))
			|| S.Contains(TEXT("Alert_Low"));
	}

	void PlaySound2D(const UObject* WorldContext, const TCHAR* AssetPath, float VolumeMul, float PitchMul)
	{
		if (!WorldContext || IsRunningDedicatedServer()) return;
		const UWorld* World = GEngine ? GEngine->GetWorldFromContextObject(WorldContext, EGetWorldErrorMode::ReturnNull) : nullptr;
		if (!World || !World->IsGameWorld()) return;
		const float Vol = GetEffectiveChannelVolume(ClassifySoundChannel(AssetPath), VolumeMul);
		if (Vol <= KINDA_SMALL_NUMBER) return;
		if (!TryPassSoundCooldown(AssetPath, FPlatformTime::Seconds())) return;
		if (USoundBase* Sound = LoadOptional<USoundBase>(AssetPath))
		{
			UGameplayStatics::PlaySound2D(WorldContext, Sound, Vol, PitchMul);
		}
	}

	void PlaySoundAtLocation(const UObject* WorldContext, const TCHAR* AssetPath, const FVector& Location, float VolumeMul, float PitchMul)
	{
		if (!WorldContext || IsRunningDedicatedServer()) return;
		const UWorld* World = GEngine ? GEngine->GetWorldFromContextObject(WorldContext, EGetWorldErrorMode::ReturnNull) : nullptr;
		if (!World || !World->IsGameWorld()) return;
		const float Vol = GetEffectiveChannelVolume(ClassifySoundChannel(AssetPath), VolumeMul);
		if (Vol <= KINDA_SMALL_NUMBER) return;
		if (!TryPassSoundCooldown(AssetPath, FPlatformTime::Seconds())) return;
		if (USoundBase* Sound = LoadOptional<USoundBase>(AssetPath))
		{
			USoundAttenuation* Attenuation = GetSpatialAttenuation(IsHeavyCombatSound(AssetPath));
			UGameplayStatics::PlaySoundAtLocation(WorldContext, Sound, Location, FRotator::ZeroRotator, Vol, PitchMul, 0.f, Attenuation);
		}
	}

	UAudioComponent* SpawnLoopingSound2D(const UObject* WorldContext, const TCHAR* AssetPath, float VolumeMul)
	{
		if (!WorldContext || IsRunningDedicatedServer()) return nullptr;
		const UWorld* World = GEngine ? GEngine->GetWorldFromContextObject(WorldContext, EGetWorldErrorMode::ReturnNull) : nullptr;
		if (!World || !World->IsGameWorld()) return nullptr;
		if (USoundBase* Sound = LoadOptional<USoundBase>(AssetPath))
		{
			if (USoundWave* SW = Cast<USoundWave>(Sound)) SW->bLooping = true;
			const float Vol = GetEffectiveChannelVolume(ClassifySoundChannel(AssetPath), VolumeMul);
			UAudioComponent* AC = UGameplayStatics::SpawnSound2D(WorldContext, Sound, Vol, 1.f, 0.f, nullptr, false, false);
			return AC;
		}
		return nullptr;
	}

	UMaterialInstanceDynamic* EnsureColorMID(UPrimitiveComponent* Comp, int32 Slot)
	{
		if (!Comp) return nullptr;
		if (UMaterialInstanceDynamic* Existing = Cast<UMaterialInstanceDynamic>(Comp->GetMaterial(Slot))) return Existing;
		UMaterialInterface* Mat = Comp->GetMaterial(Slot);
		// Engine primitives default to WorldGridMaterial, which has no "Color" parameter (tints silently did nothing). Swap only that one.
		if (Mat && Mat->GetName() == TEXT("WorldGridMaterial"))
			if (UMaterialInterface* Tintable = LoadObject<UMaterialInterface>(nullptr, TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"))) Mat = Tintable;
		if (Mat) return Comp->CreateDynamicMaterialInstance(Slot, Mat);
		return nullptr;
	}

	void EnsureEmissiveMIDs(UPrimitiveComponent* Comp, TArray<UMaterialInstanceDynamic*>& OutSlotMIDs, TArray<bool>& OutIsAccentSlot)
	{
		OutSlotMIDs.Reset();
		OutIsAccentSlot.Reset();
		if (!Comp) return;
		const int32 NumMats = Comp->GetNumMaterials();
		OutSlotMIDs.Reserve(NumMats);
		OutIsAccentSlot.Reserve(NumMats);
		for (int32 Slot = 0; Slot < NumMats; ++Slot)
		{
			UMaterialInterface* Mat = Comp->GetMaterial(Slot);
			const bool bAccent = Mat && Mat->GetName().Contains(TEXT("Emissive"));
			OutIsAccentSlot.Add(bAccent);
			OutSlotMIDs.Add(EnsureColorMID(Comp, Slot));
		}
	}

	void ApplyEmissiveTint(const TArray<UMaterialInstanceDynamic*>& SlotMIDs, const TArray<bool>& IsAccentSlot, const FLinearColor& BodyEmissive, const FLinearColor& AccentEmissive)
	{
		for (int32 Slot = 0; Slot < SlotMIDs.Num(); ++Slot)
		{
			UMaterialInstanceDynamic* MID = SlotMIDs[Slot];
			if (!MID) continue;
			const bool bAccent = IsAccentSlot.IsValidIndex(Slot) && IsAccentSlot[Slot];
			if (bAccent)
			{
				MID->SetVectorParameterValue(TEXT("Color"), AccentEmissive);
				MID->SetVectorParameterValue(TEXT("EmissiveColor"), AccentEmissive);
			}
			else if (Slot == 0)
			{
				MID->SetVectorParameterValue(TEXT("EmissiveColor"), BodyEmissive);
			}
		}
	}

	float FitUniformScale(const FVector& RawSize, const FVector& TargetSize, float MinScale, float MaxScale)
	{
		float Best = TNumericLimits<float>::Max();
		for (int32 Axis = 0; Axis < 3; ++Axis)
		{
			if (RawSize[Axis] > 0.1f && TargetSize[Axis] > 0.1f) Best = FMath::Min(Best, TargetSize[Axis] / RawSize[Axis]);
		}
		if (Best == TNumericLimits<float>::Max()) return 1.f;
		return FMath::Clamp(Best, MinScale, MaxScale);
	}
}
