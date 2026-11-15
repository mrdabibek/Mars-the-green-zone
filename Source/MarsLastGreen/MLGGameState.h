#pragma once
#include "CoreMinimal.h"
#include "GameFramework/GameStateBase.h"
#include "MLGModels.h"
#include "MLGDevice.h"
#include "MLGGameState.generated.h"

UENUM(BlueprintType)
enum class EMLGPhase : uint8 { Planning, Repair, Plant, Grow, IceRun, Defend, CommsRun, FinalDefense, Transmit, Won, Lost };

// Owns the shared base simulation, carried inventory, mission phase chain, kit planning, dialogue and the end states.
UCLASS()
class MARSLASTGREEN_API AMLGGameState : public AGameStateBase
{
	GENERATED_BODY()
public:
	AMLGGameState() { PrimaryActorTick.bCanEverTick = true; }

	UPROPERTY(BlueprintReadOnly) FMLGResourceModel Sim;
	UPROPERTY(BlueprintReadWrite) int32 Seeds = 3;
	UPROPERTY(BlueprintReadWrite) int32 Parts = 2;
	UPROPERTY(BlueprintReadOnly) FString Objective;
	UPROPERTY(BlueprintReadOnly) TArray<FString> Messages;   // newest last, max 5
	UPROPERTY(BlueprintReadOnly) bool bPlayerDead = false;
	UPROPERTY(BlueprintReadWrite) int32 Wave = 0;
	UPROPERTY(BlueprintReadWrite) int32 WavesTotal = 3;
	UPROPERTY(BlueprintReadWrite) int32 Kills = 0;
	UPROPERTY(BlueprintReadOnly) float LastKillTime = -100.f;

	UPROPERTY(BlueprintReadWrite) EMLGPhase Phase = EMLGPhase::Planning;
	UPROPERTY(BlueprintReadWrite) int32 IceCollected = 0;
	UPROPERTY(BlueprintReadWrite) bool bBackupRecovered = false;
	UPROPERTY(BlueprintReadWrite) int32 Repairs = 0;
	UPROPERTY(BlueprintReadWrite) int32 LogsRead = 0;
	UPROPERTY(BlueprintReadWrite) float Elapsed = 0.f;
	UPROPERTY(BlueprintReadWrite) int32 KitMask = 0;
	UPROPERTY(BlueprintReadOnly) FString LoseReason;
	UPROPERTY(BlueprintReadOnly) FString Dialogue;           // line currently on screen

	// Authentic Mars surface & habitat physical telemetry
	UPROPERTY(BlueprintReadOnly) float OutsideTempC = -63.f;          // diurnal/storm cycle (-22C to -78C)
	UPROPERTY(BlueprintReadOnly) float OutsidePressureMbar = 6.1f;    // ~6.1 mbar CO2 vs 1013 mbar pressurized
	UPROPERTY(BlueprintReadOnly) float GravityRatio = 0.38f;          // 0.38G exterior vs 1.0G stabilized inside
	UPROPERTY(BlueprintReadOnly) float DustStormIntensity = 0.f;      // 0..1 dynamic passing Martian dust squalls
	UPROPERTY(BlueprintReadOnly) float SolarEfficiency = 1.f;         // 1.0 clear sky down to 0.45 in peak storm
	UPROPERTY(BlueprintReadOnly) bool bPlayerInPressurizedZone = false;

	// CRISPR Mars-crop gene matrix & Sabatier CO2->H2O catalytic synthesis
	UPROPERTY(BlueprintReadWrite) int32 CropGeneMask = 0;             // bitmask of MLGGeneTrait::{CRY,PER,XER,PHO}
	UPROPERTY(BlueprintReadWrite) bool bSabatierActive = false;       // H2 + CO2 -> CH4 + 2H2O active
	UPROPERTY(BlueprintReadOnly) float GridOverclockLeft = 0.f;       // seconds of +35% solar/power boost remaining
	UPROPERTY(BlueprintReadOnly) float TurretOverclockLeft = 0.f;     // seconds of turret fire-rate overclock remaining

	UFUNCTION(BlueprintPure) float TempC() const;
	UFUNCTION(BlueprintPure) float PressureMbar() const;
	UFUNCTION(BlueprintPure) float GravityG() const { return GravityRatio; }
	UFUNCTION(BlueprintPure) int32 StormPct() const { return FMath::Clamp(FMath::RoundToInt(DustStormIntensity * 100.f), 0, 100); }
	UFUNCTION(BlueprintPure) float GetOutsideTempC() const { return OutsideTempC; }
	UFUNCTION(BlueprintPure) float GetOutsidePressureMbar() const { return OutsidePressureMbar; }
	UFUNCTION(BlueprintPure) float GetGravityRatio() const { return GravityRatio; }
	UFUNCTION(BlueprintPure) float GetDustStormIntensity() const { return DustStormIntensity; }
	UFUNCTION(BlueprintPure) float GetSolarEfficiency() const { return SolarEfficiency; }
	UFUNCTION(BlueprintPure) float GetSuitThermalLoadScale() const;
	UFUNCTION(BlueprintPure) bool IsDustStormActive() const { return DustStormIntensity >= 0.25f; }
	UFUNCTION(BlueprintPure) bool IsPlayerPressurized() const { return bPlayerInPressurizedZone; }
	UFUNCTION(BlueprintPure) int32 GetCropGeneMask() const { return CropGeneMask; }
	UFUNCTION(BlueprintPure) bool HasGeneTrait(int32 Flag) const { return (CropGeneMask & Flag) != 0; }
	UFUNCTION(BlueprintPure) FString GetCropGeneCode() const;
	UFUNCTION(BlueprintPure) bool IsSabatierActive() const { return bSabatierActive; }
	UFUNCTION(BlueprintPure) bool IsGridOverclocked() const { return GridOverclockLeft > 0.f; }
	UFUNCTION(BlueprintPure) bool IsTurretOverclocked() const { return TurretOverclockLeft > 0.f; }
	UFUNCTION(BlueprintPure) float GetSabatierYieldMult() const { return FMLGResourceModel::SabatierYieldMult; }

	void CycleOrToggleGeneTrait();
	void ToggleSabatier();
	void TriggerGridOverclock(float Seconds = 35.f);
	void TriggerTurretOverclock(float Seconds = 35.f);
	void SetEnvironmentOverride(bool bLock, float OverrideStorm = 0.f);
	void ResetEnvironmentAfterLoad();

	static constexpr int32 IceNeeded = 4;
	static constexpr int32 KitBudget = 8;
	static constexpr int32 KitItems = 6;
	static const TCHAR* KitName(int32 I);
	static int32 KitWeightOf(int32 I);
	int32 KitWeight() const;
	bool HasKit(int32 I) const { return (KitMask >> I) & 1; }
	bool ToggleKit(int32 I);                 // false if it would exceed the weight budget
	void ConfirmKit();
	float WalkScale() const { return Phase == EMLGPhase::Planning ? 1.f : 1.f - 0.015f * KitWeight(); }  // heavier kit = slower
	int32 ScienceScore() const { return 100 + (HasKit(5) ? 60 : 0) + 15 * LogsRead; }

	bool IsOperational(EMLGDeviceType T) const;
	void PushMessage(const FString& M);
	void ResetCheckpointFeedback();
	void Say(const FString& Line);           // queued dialogue, 6 s each
	int32 CountLivingPlants() const;
	int32 CountAliens() const;
	void Win();
	void Lose(const FString& Why);
	void ForcePhase(EMLGPhase P) { Phase = P; }

protected:
	virtual void BeginPlay() override;
	virtual void Tick(float Dt) override;
	void UpdateMarsEnvironment(float Dt);
	void UpdatePhase();
	void Advance(EMLGPhase P);
	TArray<FString> DialogueQueue;
	float DialogueLeft = 0.f, FabricatorTimer = 0.f, LowAlertCooldown = 0.f;
	float StormCooldown = 38.f, StormElapsed = 0.f, StormDuration = 0.f, StormPeak = 0.f;
	bool bStormNotified = false, bEnvironmentOverridden = false;
	float OverriddenStorm = 0.f;
};
