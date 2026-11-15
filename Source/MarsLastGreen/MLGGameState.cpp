#include "MLGGameState.h"
#include "MLGAlien.h"
#include "MLGAssets.h"
#include "MLGCharacter.h"
#include "MLGDefenseNode.h"
#include "MLGPickup.h"
#include "MLGPlantPlot.h"
#include "MLGWeaponComponent.h"
#include "EngineUtils.h"
#include "Kismet/GameplayStatics.h"

const TCHAR* AMLGGameState::KitName(int32 I)
{
	static const TCHAR* N[KitItems] = { TEXT("Extra seeds (+2)"), TEXT("Spare repair parts (+2)"), TEXT("Ammunition (+60 rounds)"),
		TEXT("Battery pack (+30 power)"), TEXT("Water reserve (+40 L)"), TEXT("Research drive (+60 science score)") };
	return N[I];
}
int32 AMLGGameState::KitWeightOf(int32 I) { static const int32 W[KitItems] = { 2, 2, 2, 3, 3, 2 }; return W[I]; }
int32 AMLGGameState::KitWeight() const { int32 W = 0; for (int32 I = 0; I < KitItems; ++I) if (HasKit(I)) W += KitWeightOf(I); return W; }

bool AMLGGameState::ToggleKit(int32 I)
{
	if (Phase != EMLGPhase::Planning || I < 0 || I >= KitItems) return false;
	if (!HasKit(I) && KitWeight() + KitWeightOf(I) > KitBudget) return false;
	KitMask ^= (1 << I);
	return true;
}

void AMLGGameState::ConfirmKit()
{
	if (Phase != EMLGPhase::Planning) return;
	if (HasKit(0)) Seeds += 2;
	if (HasKit(1)) Parts += 2;
	if (HasKit(3)) Sim.Power = FMath::Min(100.f, Sim.Power + 30.f);
	if (HasKit(4)) Sim.Water += 40.f;
	if (HasKit(2)) if (AMLGCharacter* C = Cast<AMLGCharacter>(UGameplayStatics::GetPlayerPawn(this, 0))) C->Weapon->Reserve += 60;
	Phase = EMLGPhase::Repair;
	Say(TEXT("Aster One, mission log. Earth relay is silent. Restoring power to the seed vault."));
	PushMessage(TEXT("Repair parts available on the habitat floor."));
}

bool AMLGGameState::IsOperational(EMLGDeviceType T) const
{
	for (TActorIterator<AMLGDevice> It(GetWorld()); It; ++It)
		if (It->Type == T && It->IsOperational()) return true;
	return false;
}

void AMLGGameState::PushMessage(const FString& M) { if (Messages.Num() && Messages.Last() == M) return; Messages.Add(M);   // consecutive duplicates (e.g. 3 checkpoints in a row) are dropped
	 if (Messages.Num() > 5) Messages.RemoveAt(0); }
void AMLGGameState::Say(const FString& L) { if (Dialogue.IsEmpty() && DialogueQueue.IsEmpty()) { Dialogue = L; DialogueLeft = 6.f; } else DialogueQueue.Add(L); }

void AMLGGameState::ResetCheckpointFeedback()
{
	Messages.Reset();
	Dialogue.Reset();
	DialogueQueue.Reset();
	DialogueLeft = 0.f;
	FabricatorTimer = 0.f;
	LowAlertCooldown = 0.f;
	LastKillTime = -100.f;
}

int32 AMLGGameState::CountLivingPlants() const
{
	int32 N = 0;
	for (TActorIterator<AMLGPlantPlot> It(GetWorld()); It; ++It) N += It->Plant.IsLiving();
	return N;
}

int32 AMLGGameState::CountAliens() const
{
	int32 N = 0;
	for (TActorIterator<AMLGAlien> It(GetWorld()); It; ++It) N += It->IsAlive();
	return N;
}

void AMLGGameState::Win()
{
	if (Phase == EMLGPhase::Won || Phase == EMLGPhase::Lost) return;
	Phase = EMLGPhase::Won;
	Objective = TEXT("Transmission sent.");
}

void AMLGGameState::Lose(const FString& Why)
{
	if (Phase == EMLGPhase::Won || Phase == EMLGPhase::Lost) return;
	Phase = EMLGPhase::Lost; LoseReason = Why; Objective = TEXT("Mission failed.");
}

void AMLGGameState::BeginPlay()
{
	Super::BeginPlay();
	OutsideTempC = -63.f;
	OutsidePressureMbar = 6.1f;
	DustStormIntensity = 0.f;
	SolarEfficiency = 1.f;
	bPlayerInPressurizedZone = false;
	GravityRatio = 0.38f;
	StormCooldown = 38.f;
	StormElapsed = 0.f;
	StormDuration = 0.f;
	StormPeak = 0.f;
	bStormNotified = false;
	PushMessage(TEXT("Repair parts are limited. If you run out, the fabricator prints 1 every 90 s."));
}

float AMLGGameState::TempC() const
{
	if (bPlayerInPressurizedZone) return Sim.HasPower() ? 21.f : 6.f;
	return OutsideTempC;
}

float AMLGGameState::PressureMbar() const
{
	return bPlayerInPressurizedZone ? 1013.f : OutsidePressureMbar;
}

float AMLGGameState::GetSuitThermalLoadScale() const
{
	if (bPlayerInPressurizedZone) return 1.f;
	const float ColdFactor = FMath::Clamp((-OutsideTempC - 40.f) / 38.f, 0.f, 1.f);
	return 1.f + 0.35f * DustStormIntensity + 0.15f * ColdFactor;
}

void AMLGGameState::SetEnvironmentOverride(bool bLock, float OverrideStorm)
{
	bEnvironmentOverridden = bLock;
	OverriddenStorm = FMath::Clamp(OverrideStorm, 0.f, 1.f);
	if (bEnvironmentOverridden)
	{
		DustStormIntensity = OverriddenStorm;
		SolarEfficiency = FMLGResourceModel::ComputeSolarEfficiency(DustStormIntensity);
		OutsideTempC = -54.f - 8.f * DustStormIntensity;
		OutsidePressureMbar = 6.1f + 0.3f * DustStormIntensity;
	}
}

void AMLGGameState::ResetEnvironmentAfterLoad()
{
	bEnvironmentOverridden = false;
	DustStormIntensity = 0.f;
	SolarEfficiency = 1.f;
	StormCooldown = 32.f;
	StormElapsed = 0.f;
	StormDuration = 0.f;
	StormPeak = 0.f;
	bStormNotified = false;
	GridOverclockLeft = 0.f;
	TurretOverclockLeft = 0.f;
}

FString AMLGGameState::GetCropGeneCode() const
{
	if (CropGeneMask == MLGGeneTrait::None) return TEXT("WT");
	TArray<FString> TraitTokens;
	if (HasGeneTrait(MLGGeneTrait::CRY)) TraitTokens.Add(TEXT("CRY"));
	if (HasGeneTrait(MLGGeneTrait::PER)) TraitTokens.Add(TEXT("PER"));
	if (HasGeneTrait(MLGGeneTrait::XER)) TraitTokens.Add(TEXT("XER"));
	if (HasGeneTrait(MLGGeneTrait::PHO)) TraitTokens.Add(TEXT("PHO"));
	return FString::Join(TraitTokens, TEXT("+"));
}

void AMLGGameState::CycleOrToggleGeneTrait()
{
	if (!HasGeneTrait(MLGGeneTrait::CRY))
	{
		CropGeneMask |= MLGGeneTrait::CRY;
		PushMessage(TEXT("CRISPR splice: CRY (-55% cold decay)"));
	}
	else if (!HasGeneTrait(MLGGeneTrait::PER))
	{
		CropGeneMask |= MLGGeneTrait::PER;
		PushMessage(TEXT("CRISPR splice: +PER (+50% growth)"));
	}
	else if (!HasGeneTrait(MLGGeneTrait::XER))
	{
		CropGeneMask |= MLGGeneTrait::XER;
		PushMessage(TEXT("CRISPR splice: +XER (-45% H2O use)"));
	}
	else if (!HasGeneTrait(MLGGeneTrait::PHO))
	{
		CropGeneMask |= MLGGeneTrait::PHO;
		PushMessage(TEXT("CRISPR splice: +PHO (+1 seed & O2)"));
	}
	else
	{
		CropGeneMask = MLGGeneTrait::None;
		PushMessage(TEXT("Gene matrix reset: WT"));
	}
}

void AMLGGameState::ToggleSabatier()
{
	bSabatierActive = !bSabatierActive;
	PushMessage(bSabatierActive
		? TEXT("Sabatier CO2->2H2O synthesis: ON (2.2x H2O yield)")
		: TEXT("Sabatier synthesis: OFF"));
}

void AMLGGameState::TriggerGridOverclock(float Seconds)
{
	GridOverclockLeft = FMath::Max(GridOverclockLeft, Seconds);
	PushMessage(TEXT("Grid overclock active (+35% output)"));
}

void AMLGGameState::TriggerTurretOverclock(float Seconds)
{
	TurretOverclockLeft = FMath::Max(TurretOverclockLeft, Seconds);
	PushMessage(TEXT("Defense network overclocked"));
}

void AMLGGameState::UpdateMarsEnvironment(float Dt)
{
	const AMLGCharacter* Pl = Cast<AMLGCharacter>(UGameplayStatics::GetPlayerPawn(this, 0));
	bPlayerInPressurizedZone = Pl ? Pl->IsInPressurizedZone() : false;
	GravityRatio = bPlayerInPressurizedZone ? 1.0f : 0.38f;

	if (bEnvironmentOverridden)
	{
		DustStormIntensity = OverriddenStorm;
		SolarEfficiency = FMLGResourceModel::ComputeSolarEfficiency(DustStormIntensity);
		return;
	}

	if (Phase == EMLGPhase::Planning || Phase == EMLGPhase::Won || Phase == EMLGPhase::Lost)
	{
		DustStormIntensity = 0.f;
		SolarEfficiency = 1.f;
		OutsideTempC = -63.f;
		OutsidePressureMbar = 6.1f;
		return;
	}

	// Accelerated Martian diurnal cycle (-22C to -78C with storm cooling)
	const float SolPhase = Elapsed * (2.f * PI / 240.f) - 0.58f;
	const float DiurnalTemp = -50.f + 22.f * FMath::Sin(SolPhase);

	float TargetStorm = 0.f;
	if (StormDuration > 0.f)
	{
		StormElapsed += Dt;
		const float Ramp = 10.f;
		if (StormElapsed < Ramp)
		{
			TargetStorm = StormPeak * (StormElapsed / Ramp);
		}
		else if (StormElapsed < StormDuration - Ramp)
		{
			TargetStorm = StormPeak;
		}
		else if (StormElapsed < StormDuration)
		{
			TargetStorm = StormPeak * FMath::Max(0.f, (StormDuration - StormElapsed) / Ramp);
		}
		else
		{
			StormDuration = 0.f;
			StormElapsed = 0.f;
			StormCooldown = FMath::FRandRange(65.f, 95.f);
			TargetStorm = 0.f;
		}
	}
	else
	{
		StormCooldown -= Dt;
		if (StormCooldown <= 0.f)
		{
			StormDuration = FMath::FRandRange(34.f, 44.f);
			StormElapsed = 0.f;
			StormPeak = (Phase >= EMLGPhase::Defend) ? FMath::FRandRange(0.85f, 1.0f) : FMath::FRandRange(0.60f, 0.80f);
		}
	}

	DustStormIntensity = FMath::FInterpTo(DustStormIntensity, TargetStorm, Dt, 0.9f);
	if (!bStormNotified && DustStormIntensity >= 0.25f)
	{
		bStormNotified = true;
		PushMessage(TEXT("Dust squall incoming: solar array output dropping"));
	}
	else if (bStormNotified && DustStormIntensity < 0.08f && StormDuration <= 0.f)
	{
		bStormNotified = false;
		PushMessage(TEXT("Dust squall cleared: solar array nominal"));
	}

	SolarEfficiency = FMLGResourceModel::ComputeSolarEfficiency(DustStormIntensity);
	OutsideTempC = FMath::Clamp(DiurnalTemp - 8.f * DustStormIntensity, -78.f, -22.f);
	OutsidePressureMbar = 6.1f + 0.35f * DustStormIntensity + 0.12f * FMath::Cos(SolPhase);
}

void AMLGGameState::Tick(float Dt)
{
	Super::Tick(Dt);
	if (!Dialogue.IsEmpty() && (DialogueLeft -= Dt) <= 0.f)
	{
		Dialogue = DialogueQueue.IsEmpty() ? FString() : DialogueQueue[0];
		if (!DialogueQueue.IsEmpty()) { DialogueQueue.RemoveAt(0); DialogueLeft = 6.f; }
	}
	UpdateMarsEnvironment(Dt);
	if (Phase == EMLGPhase::Planning) { Objective = TEXT("Mission planning: choose your kit (weight budget), then confirm."); return; }
	if (Phase == EMLGPhase::Won || Phase == EMLGPhase::Lost) return;   // simulation freezes on both end states
	Elapsed += Dt;
	GridOverclockLeft = FMath::Max(0.f, GridOverclockLeft - Dt);
	TurretOverclockLeft = FMath::Max(0.f, TurretOverclockLeft - Dt);

	FMLGResourceInputs In;
	In.SolarEfficiency = SolarEfficiency;
	bool bSolarSubOnline = false;
	for (TActorIterator<AMLGDevice> It(GetWorld()); It; ++It)
	{
		if (It->Type == EMLGDeviceType::WaterTank) In.TankLeak += 1.f - It->Integrity / It->MaxIntegrity;
		if (!It->IsOperational()) continue;
		switch (It->Type)
		{
		case EMLGDeviceType::Power: ++In.PowerGenerators; break;
		case EMLGDeviceType::Oxygen: In.bOxygenGenOnline = true; break;
		case EMLGDeviceType::WaterPurifier: In.bPurifierOnline = true; break;
		case EMLGDeviceType::GreenhouseSeal: In.bGreenhouseSealed = true; break;
		case EMLGDeviceType::SolarSub: bSolarSubOnline = true; break;
		default: break;
		}
	}
	for (TActorIterator<AMLGPlantPlot> It(GetWorld()); It; ++It) In.ConsumingPlots += It->IsConsuming();
	for (TActorIterator<AMLGDefenseNode> It(GetWorld()); It; ++It) if (It->DrawsPower()) ++In.ActiveTurrets;

	In.bSabatierActive = bSabatierActive && In.bPurifierOnline;
	In.PlantWaterScale = HasGeneTrait(MLGGeneTrait::XER) ? 0.55f : 1.f;
	In.PassiveSabatierWater = In.bSabatierActive ? 0.35f : 0.f;
	In.ExtraPowerLoad = (In.bSabatierActive ? 0.35f : 0.f) + (IsGridOverclocked() ? 0.25f : 0.f) + (IsTurretOverclocked() ? 0.4f : 0.f);
	In.PowerBoost = 1.f + (bSolarSubOnline ? 0.15f : 0.f) + (IsGridOverclocked() ? 0.35f : 0.f);
	Sim.Step(Dt, In);

	if (HasGeneTrait(MLGGeneTrait::PHO) && In.ConsumingPlots > 0 && Sim.HasPower() && In.bGreenhouseSealed)
	{
		Sim.BaseOxygen = FMath::Min(100.f, Sim.BaseOxygen + 0.35f * In.ConsumingPlots * Dt);
	}

	LowAlertCooldown = FMath::Max(0.f, LowAlertCooldown - Dt);
	const AMLGCharacter* Pl = Cast<AMLGCharacter>(UGameplayStatics::GetPlayerPawn(this, 0));
	const bool bAnyLowAlert = (Pl && !Pl->bDead && Pl->SuitOxygen < 25.f) || Sim.Power < 15.f || Sim.Water < 20.f || Sim.BaseOxygen < 25.f;
	if (bAnyLowAlert && LowAlertCooldown <= 0.f)
	{
		LowAlertCooldown = 15.f;
		MLGAssets::PlaySound2D(this, MLGAssets::Audio::AlertLow, 0.7f);
	}

	// Softlock guard: with no parts left, none on the map and something damaged, a fabricator prints 1 part per 90 s.
	bool bDamaged = false, bPartsOnMap = false;
	for (TActorIterator<AMLGDevice> It(GetWorld()); It; ++It) bDamaged |= It->Integrity < It->MaxIntegrity;
	for (TActorIterator<AMLGPickup> It(GetWorld()); It; ++It) bPartsOnMap |= It->Kind == EMLGPickupKind::RepairParts;
	if (Parts <= 0 && bDamaged && !bPartsOnMap) { FabricatorTimer += Dt; if (FabricatorTimer >= 90.f) { FabricatorTimer = 0.f; ++Parts; PushMessage(TEXT("Fabricator printed 1 repair part")); } }
	else FabricatorTimer = 0.f;

	UpdatePhase();

	// Lose: every viable seed gone with no recovery route (backup pickup still on the map counts as a route).
	if (Phase >= EMLGPhase::Plant && Phase < EMLGPhase::Won && Seeds == 0 && CountLivingPlants() == 0)
	{
		bool bBackup = false;
		for (TActorIterator<AMLGPickup> It(GetWorld()); It; ++It) bBackup |= It->Kind == EMLGPickupKind::SeedBank || It->Kind == EMLGPickupKind::Seeds;
		if (!bBackup) Lose(TEXT("Every viable seed was lost and no backup remains."));
	}
}

void AMLGGameState::Advance(EMLGPhase P) { Phase = P; }

void AMLGGameState::UpdatePhase()
{
	bool bPlanted = false, bSeedling = false;
	for (TActorIterator<AMLGPlantPlot> It(GetWorld()); It; ++It)
	{
		bPlanted |= It->Plant.Stage != EMLGPlantStage::Empty;
		bSeedling |= It->Plant.Stage == EMLGPlantStage::Seedling || It->Plant.Stage == EMLGPlantStage::Mature;
	}
	switch (Phase)
	{
	case EMLGPhase::Repair:
		Objective = TEXT("Restore the power unit, oxygen generator and greenhouse seal.");
		if (IsOperational(EMLGDeviceType::Power) && IsOperational(EMLGDeviceType::Oxygen) && IsOperational(EMLGDeviceType::GreenhouseSeal)) Advance(EMLGPhase::Plant);
		break;
	case EMLGPhase::Plant:
		Objective = TEXT("Plant a seed in a greenhouse plot.");
		if (bPlanted) Advance(EMLGPhase::Grow);
		break;
	case EMLGPhase::Grow:
		Objective = TEXT("Keep the seed alive until it becomes a seedling: it needs power, water and a sealed greenhouse.");
		if (bSeedling) { Advance(EMLGPhase::IceRun); Say(TEXT("The tank is dropping. There is an ice field to the south. Repair the purifier, bring ice back. Watch your suit oxygen.")); }
		break;
	case EMLGPhase::IceRun:
		Objective = FString::Printf(TEXT("Collect ice from the field south of the base (%d/%d) and repair the water purifier."), FMath::Min<int32>(IceCollected, IceNeeded), IceNeeded);
		if (IceCollected >= IceNeeded && IsOperational(EMLGDeviceType::WaterPurifier)) { Advance(EMLGPhase::Defend); Say(TEXT("Motion on the ridge. They go for the water first. Hold the line.")); }
		break;
	case EMLGPhase::Defend:
		Objective = FString::Printf(TEXT("Defend the water line and greenhouse (wave %d/2). Shoot attackers to stagger them; repair damage."), FMath::Min(Wave, 2));
		if (Wave >= 2 && CountAliens() == 0) { Advance(EMLGPhase::CommsRun); Say(TEXT("Quiet. The comms relay is out east. The seed-bank backup is stored there. Go before they regroup.")); }
		break;
	case EMLGPhase::CommsRun:
		Objective = FString::Printf(TEXT("Go east: repair the comms relay (%s) and recover the seed-bank backup (%s)."), IsOperational(EMLGDeviceType::Comms) ? TEXT("done") : TEXT("pending"), bBackupRecovered ? TEXT("done") : TEXT("pending"));
		if (IsOperational(EMLGDeviceType::Comms) && bBackupRecovered) { Advance(EMLGPhase::FinalDefense); Say(TEXT("Relay is live. Contacts returning in force. Back to the habitat and hold.")); }
		break;
	case EMLGPhase::FinalDefense:
		Objective = TEXT("Hold the habitat against the final attack.");
		if (Wave >= 3 && CountAliens() == 0) { Advance(EMLGPhase::Transmit); Say(TEXT("All clear. The console in the habitat can send the research and the distress signal.")); }
		break;
	case EMLGPhase::Transmit:
		Objective = TEXT("Send the research from the habitat transmitter.");
		break;
	default: break;
	}
}
