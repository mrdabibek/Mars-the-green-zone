#pragma once
// Pure, world-free simulation models so the rules can be unit-tested headless.
// All numbers are gameplay-time (accelerated) and UNTUNED; they are simplified teaching models, not engineering data.
#include "CoreMinimal.h"
#include "MLGModels.generated.h"

UENUM(BlueprintType)
enum class EMLGPlantStage : uint8 { Empty, Seed, Seedling, Mature, Dead };

namespace MLGGeneTrait
{
	inline constexpr int32 None = 0;
	inline constexpr int32 CRY  = 1 << 0; // Cryo/Low-Pressure Shield: -55% hazard decay
	inline constexpr int32 PER  = 1 << 1; // Perchlorate Detox: +50% growth rate
	inline constexpr int32 XER  = 1 << 2; // Xerophyte Retention: -45% water drain
	inline constexpr int32 PHO  = 1 << 3; // Red-Spectrum Yield: +1 harvest seed & passive O2
	inline constexpr int32 All  = CRY | PER | XER | PHO;
}

USTRUCT(BlueprintType)
struct MARSLASTGREEN_API FMLGPlantModel
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadOnly) EMLGPlantStage Stage = EMLGPlantStage::Empty;
	UPROPERTY(BlueprintReadOnly) float Progress = 0.f;   // 0..1 inside the current stage
	UPROPERTY(BlueprintReadOnly) float Health = 1.f;     // 0..1
	UPROPERTY(BlueprintReadOnly) bool bStalled = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite) float SeedSeconds = 30.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) float SeedlingSeconds = 45.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) float DecayPerSec = 0.01f;       // ~100 s from full health to dead without water/power
	UPROPERTY(EditAnywhere, BlueprintReadWrite) float PressureDecayMult = 3.f;   // loss of pressure is the fastest killer
	UPROPERTY(EditAnywhere, BlueprintReadWrite) float RegenPerSec = 0.05f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) float CriticalHealth = 0.4f;     // HUD warns below this: death is permanent

	void Plant() { Stage = EMLGPlantStage::Seed; Progress = 0.f; Health = 1.f; bStalled = false; }
	void Clear() { Stage = EMLGPlantStage::Empty; Progress = 0.f; Health = 1.f; bStalled = false; }
	bool IsLiving() const { return Stage == EMLGPlantStage::Seed || Stage == EMLGPlantStage::Seedling || Stage == EMLGPlantStage::Mature; }
	bool IsCritical() const { return IsLiving() && Health < CriticalHealth; }

	void Tick(float Dt, bool bWater, bool bPower, bool bSealed, int32 GeneMask = MLGGeneTrait::None)
	{
		if (!IsLiving()) return;
		bStalled = !(bWater && bPower && bSealed);
		if (!bStalled)
		{
			Health = FMath::Min(1.f, Health + RegenPerSec * Dt);
			if (Stage != EMLGPlantStage::Mature)
			{
				const float GrowthMult = (GeneMask & MLGGeneTrait::PER) ? 1.5f : 1.f;
				Progress += (Dt * GrowthMult) / (Stage == EMLGPlantStage::Seed ? SeedSeconds : SeedlingSeconds);
				if (Progress >= 1.f)
				{
					Progress = 0.f;
					Stage = Stage == EMLGPlantStage::Seed ? EMLGPlantStage::Seedling : EMLGPlantStage::Mature;
				}
			}
		}
		else
		{
			const float CryoScale = (GeneMask & MLGGeneTrait::CRY) ? 0.45f : 1.f;
			Health -= DecayPerSec * CryoScale * (bSealed ? 1.f : PressureDecayMult) * Dt;
			if (Health <= 0.f) { Health = 0.f; Stage = EMLGPlantStage::Dead; }
		}
	}
};

struct FMLGResourceInputs
{
	int32 PowerGenerators = 0;      // operational solar/power units
	bool bOxygenGenOnline = false;
	bool bPurifierOnline = false;
	bool bGreenhouseSealed = false;
	int32 ConsumingPlots = 0;       // living, un-stalled plants
	int32 ActiveTurrets = 0;        // deployed sentry turrets drawing base battery
	float TankLeak = 0.f;           // litres/s lost through damaged tank/pipes
	float SolarEfficiency = 1.f;    // 1.0 clear sky; drops down to ~0.45 in peak Martian dust squall
	bool bSabatierActive = false;   // H2 + CO2 -> CH4 + 2H2O catalytic synthesis active
	float PlantWaterScale = 1.f;    // XER gene reduces crop water demand
	float PassiveSabatierWater = 0.f; // L/s condensed from Martian CO2 when Sabatier is powered
	float ExtraPowerLoad = 0.f;     // Sabatier / Overclock auxiliary draw
	float PowerBoost = 1.f;         // Grid overclock / solar substation boost multiplier
};

USTRUCT(BlueprintType)
struct MARSLASTGREEN_API FMLGResourceModel
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly) float Power = 30.f;       // battery 0..100
	UPROPERTY(BlueprintReadOnly) float Water = 60.f;       // litres in tank 0..MaxWater
	UPROPERTY(BlueprintReadOnly) float BaseOxygen = 40.f;  // habitat air quality 0..100
	UPROPERTY(BlueprintReadOnly) float Ice = 0.f;          // units waiting for the purifier
	UPROPERTY(BlueprintReadOnly) float WaterUsed = 0.f;    // net litres consumed by plants (after recycling), for the debrief

	static constexpr float MaxWater = 200.f;
	static constexpr float GenPerUnit = 3.f;          // battery/s per power unit
	static constexpr float DustStormMinSolarEfficiency = 0.45f; // peak dust storm drops solar output to 45%
	static constexpr float OxygenGenLoad = 0.5f;      // battery/s
	static constexpr float PurifierLoad = 0.5f;       // battery/s
	static constexpr float PlotLightLoad = 0.4f;      // battery/s per plant
	static constexpr float TurretLoad = 0.5f;         // battery/s per active sentry turret
	static constexpr float OxygenGain = 2.f;          // per s while generator runs
	static constexpr float OxygenLeak = 0.15f;        // per s otherwise
	static constexpr float IceRate = 0.1f;            // ice units/s through purifier
	static constexpr float WaterPerIce = 8.f;         // litres out per ice unit (simplified)
	static constexpr float SabatierYieldMult = 2.2f;  // H2 + CO2 -> CH4 + 2H2O multiplies purified water output
	static constexpr float PlotWaterUse = 0.1f;       // litres/s per plant
	static constexpr float RecycleFraction = 0.6f;    // share of plant water returned when greenhouse is sealed

	static float ComputeSolarEfficiency(float DustStormIntensity)
	{
		return FMath::Lerp(1.f, DustStormMinSolarEfficiency, FMath::Clamp(DustStormIntensity, 0.f, 1.f));
	}

	bool HasPower() const { return Power > 0.f; }
	bool HasWater() const { return Water > 0.f; }

	void Step(float Dt, const FMLGResourceInputs& In)
	{
		const bool bPowered = HasPower();
		const bool bO2 = In.bOxygenGenOnline && bPowered;
		const bool bPur = In.bPurifierOnline && bPowered && Ice > 0.f;
		const float Load = (bO2 && BaseOxygen < 100.f ? OxygenGenLoad : 0.f) + (bPur ? PurifierLoad : 0.f)
			+ PlotLightLoad * In.ConsumingPlots + TurretLoad * In.ActiveTurrets + FMath::Max(0.f, In.ExtraPowerLoad);
		const float SolarScale = FMath::Clamp(In.SolarEfficiency * FMath::Max(0.f, In.PowerBoost), 0.f, 2.5f);
		Power = FMath::Clamp(Power + (GenPerUnit * In.PowerGenerators * SolarScale - Load) * Dt, 0.f, 100.f);
		BaseOxygen = FMath::Clamp(BaseOxygen + (bO2 ? OxygenGain : -OxygenLeak) * Dt, 0.f, 100.f);
		if (bPur)
		{
			const float Used = FMath::Min(Ice, IceRate * Dt);
			Ice -= Used;
			Water += Used * WaterPerIce * (In.bSabatierActive ? SabatierYieldMult : 1.f);
		}
		if (In.bSabatierActive && bPowered && In.PassiveSabatierWater > 0.f)
		{
			Water += In.PassiveSabatierWater * Dt;
		}
		const float WaterScale = FMath::Clamp(In.PlantWaterScale, 0.1f, 2.f);
		const float PlantUse = FMath::Min(Water, PlotWaterUse * WaterScale * In.ConsumingPlots * Dt);
		Water -= PlantUse;
		WaterUsed += PlantUse * (In.bGreenhouseSealed ? 1.f - RecycleFraction : 1.f);
		if (In.bGreenhouseSealed) Water += PlantUse * RecycleFraction;
		Water -= In.TankLeak * Dt;
		Water = FMath::Clamp(Water, 0.f, MaxWater);
	}
};
