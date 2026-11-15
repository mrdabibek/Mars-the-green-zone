#pragma once
#include "CoreMinimal.h"
#include "Misc/PackageName.h"

class USoundBase;
class USoundAttenuation;
class UAudioComponent;
class UPrimitiveComponent;
class UMaterialInstanceDynamic;

enum class EMLGSoundChannel : uint8
{
	SFX = 0,
	Music,
	Ambience,
	UI
};

// Safe runtime asset & audio helpers: always verifies package existence before LoadObject so missing/unimported
// assets fall back cleanly without crashing or emitting linker errors in headless or partial builds.
namespace MLGAssets
{
	// Resolves "/Game/Foo/Bar" -> "/Game/Foo/Bar.Bar" and checks FPackageName::DoesPackageExist first.
	MARSLASTGREEN_API UObject* LoadOptionalObject(UClass* AssetClass, const TCHAR* ObjectPath);

	template <typename T>
	T* LoadOptional(const TCHAR* ObjectPath)
	{
		return Cast<T>(LoadOptionalObject(T::StaticClass(), ObjectPath));
	}

	template <typename T>
	T* LoadFirst(std::initializer_list<const TCHAR*> Candidates)
	{
		for (const TCHAR* Path : Candidates)
		{
			if (T* Obj = LoadOptional<T>(Path)) return Obj;
		}
		return nullptr;
	}

	MARSLASTGREEN_API float ComputeChannelVolume(EMLGSoundChannel Channel, float VolumeMul, float MasterVol, float SFXVol, float MusicVol, float AmbienceVol, bool bMasterAppliedOnDevice = false);
	MARSLASTGREEN_API float GetEffectiveChannelVolume(EMLGSoundChannel Channel, float VolumeMul = 1.f);
	MARSLASTGREEN_API EMLGSoundChannel ClassifySoundChannel(const TCHAR* AssetPath);
	MARSLASTGREEN_API float GetCueCooldownSeconds(const TCHAR* AssetPath);
	MARSLASTGREEN_API bool TryPassSoundCooldown(const TCHAR* AssetPath, double NowSeconds);
	MARSLASTGREEN_API void ResetSoundCooldowns();
	MARSLASTGREEN_API USoundAttenuation* GetSpatialAttenuation(bool bHeavyCombat = false);

	MARSLASTGREEN_API void PlaySound2D(const UObject* WorldContext, const TCHAR* AssetPath, float VolumeMul = 1.f, float PitchMul = 1.f);
	MARSLASTGREEN_API void PlaySoundAtLocation(const UObject* WorldContext, const TCHAR* AssetPath, const FVector& Location, float VolumeMul = 1.f, float PitchMul = 1.f);
	MARSLASTGREEN_API UAudioComponent* SpawnLoopingSound2D(const UObject* WorldContext, const TCHAR* AssetPath, float VolumeMul = 1.f);

	MARSLASTGREEN_API UMaterialInstanceDynamic* EnsureColorMID(UPrimitiveComponent* Comp, int32 Slot = 0);
	MARSLASTGREEN_API void EnsureEmissiveMIDs(UPrimitiveComponent* Comp, TArray<UMaterialInstanceDynamic*>& OutSlotMIDs, TArray<bool>& OutIsAccentSlot);
	MARSLASTGREEN_API void ApplyEmissiveTint(const TArray<UMaterialInstanceDynamic*>& SlotMIDs, const TArray<bool>& IsAccentSlot, const FLinearColor& BodyEmissive, const FLinearColor& AccentEmissive);

	// Uniform scale that fits a mesh of RawSize inside TargetSize (smallest per-axis ratio, so it never overflows the
	// legacy primitive footprint/collision). Degenerate axes are ignored; result clamped to [MinScale, MaxScale].
	MARSLASTGREEN_API float FitUniformScale(const FVector& RawSize, const FVector& TargetSize, float MinScale = 0.01f, float MaxScale = 50.f);

	// Canonical /Game/Audio paths (48kHz 16-bit PCM WAVs imported by ue_pipeline)
	namespace Audio
	{
		inline constexpr const TCHAR* IntroLanderBurn = TEXT("/Game/Audio/SFX_Intro_LanderBurn");
		inline constexpr const TCHAR* IntroEarthShatter = TEXT("/Game/Audio/SFX_Intro_EarthShatter");
		inline constexpr const TCHAR* RifleFire = TEXT("/Game/Audio/SFX_Rifle_Fire");
		inline constexpr const TCHAR* RifleReload = TEXT("/Game/Audio/SFX_Rifle_Reload");
		inline constexpr const TCHAR* HitMarker = TEXT("/Game/Audio/SFX_Hit_Marker");
		inline constexpr const TCHAR* RaiderTelegraph = TEXT("/Game/Audio/SFX_Alien_Raider_Telegraph");
		inline constexpr const TCHAR* BreakerSlam = TEXT("/Game/Audio/SFX_Alien_Breaker_Slam");
		inline constexpr const TCHAR* GunnerCharge = TEXT("/Game/Audio/SFX_Alien_Gunner_Charge");
		inline constexpr const TCHAR* AlienHit = TEXT("/Game/Audio/SFX_Alien_Hit");
		inline constexpr const TCHAR* AlienDeath = TEXT("/Game/Audio/SFX_Alien_Death");
		inline constexpr const TCHAR* RepairTick = TEXT("/Game/Audio/SFX_Repair_Tick");
		inline constexpr const TCHAR* RepairDone = TEXT("/Game/Audio/SFX_Repair_Done");
		inline constexpr const TCHAR* AlertLow = TEXT("/Game/Audio/SFX_Alert_Low");
		inline constexpr const TCHAR* Transmit = TEXT("/Game/Audio/SFX_Transmit");
		inline constexpr const TCHAR* MarsWindLoop = TEXT("/Game/Audio/SFX_Mars_Wind_Loop");
		inline constexpr const TCHAR* MusicCalmLoop = TEXT("/Game/Audio/SFX_Music_Calm_Loop");
		inline constexpr const TCHAR* MusicCombatLoop = TEXT("/Game/Audio/SFX_Music_Combat_Loop");

		// Increment 10 new cues (10 additional WAVs -> 25 total)
		inline constexpr const TCHAR* FootstepIndoor = TEXT("/Game/Audio/SFX_Footstep_Indoor");
		inline constexpr const TCHAR* FootstepMars = TEXT("/Game/Audio/SFX_Footstep_Mars");
		inline constexpr const TCHAR* Jump = TEXT("/Game/Audio/SFX_Jump");
		inline constexpr const TCHAR* Land = TEXT("/Game/Audio/SFX_Land");
		inline constexpr const TCHAR* PlayerHurt = TEXT("/Game/Audio/SFX_Player_Hurt");
		inline constexpr const TCHAR* LowO2Heartbeat = TEXT("/Game/Audio/SFX_LowO2_Heartbeat");
		inline constexpr const TCHAR* TurretFire = TEXT("/Game/Audio/SFX_Turret_Fire");
		inline constexpr const TCHAR* Pickup = TEXT("/Game/Audio/SFX_Pickup");
		inline constexpr const TCHAR* WaveStart = TEXT("/Game/Audio/SFX_Wave_Start");
		inline constexpr const TCHAR* UIClick = TEXT("/Game/Audio/SFX_UI_Click");
	}
}
