#pragma once
#include "CoreMinimal.h"
#include "GameFramework/SaveGame.h"
#include "MLGModels.h"
#include "MLGPickup.h"
#include "MLGGameState.h"
#include "MLGDefenseNode.h"
#include "MLGSaveGame.generated.h"

USTRUCT()
struct FMLGPickupSave
{
	GENERATED_BODY()
	UPROPERTY() EMLGPickupKind Kind = EMLGPickupKind::RepairParts;
	UPROPERTY() int32 Amount = 1;
	UPROPERTY() FVector Loc = FVector::ZeroVector;
};

USTRUCT()
struct FMLGDefenseSave
{
	GENERATED_BODY()
	UPROPERTY() EMLGDefenseState State = EMLGDefenseState::Empty;
	UPROPERTY() float Integrity = 0.f;
};

// Checkpoint. Aliens are not saved: a reload mid-attack restores the state from before the wave spawned (checkpoints are written
// at phase changes and at each wave warning, only while no attacker is alive).
UCLASS()
class MARSLASTGREEN_API UMLGSaveGame : public USaveGame
{
	GENERATED_BODY()
public:
	UPROPERTY() FMLGResourceModel Sim;
	UPROPERTY() EMLGPhase Phase = EMLGPhase::Repair;
	UPROPERTY() int32 Seeds = 0;
	UPROPERTY() int32 Parts = 0;
	UPROPERTY() int32 Wave = 0;
	UPROPERTY() int32 Kills = 0;
	UPROPERTY() int32 IceCollected = 0;
	UPROPERTY() int32 Repairs = 0;
	UPROPERTY() int32 LogsRead = 0;
	UPROPERTY() int32 KitMask = 0;
	UPROPERTY() bool bBackup = false;
	UPROPERTY() float Elapsed = 0.f;
	UPROPERTY() float DirectorTimer = 0.f;
	UPROPERTY() float NextWaveIn = 45.f;
	UPROPERTY() bool bWarned = false;
	UPROPERTY() float FirstContactTimer = 0.f;
	UPROPERTY() bool bFirstContactTriggered = true; // Existing saves already bypassed the first-contact encounter.
	UPROPERTY() TMap<FString, float> Devices;
	UPROPERTY() TMap<FString, FMLGPlantModel> Plots;
	UPROPERTY() TMap<FString, FMLGDefenseSave> Defenses;
	UPROPERTY() TArray<FMLGPickupSave> Pickups;
	UPROPERTY() FVector PlayerLoc = FVector::ZeroVector;
	UPROPERTY() FRotator PlayerRot = FRotator::ZeroRotator;
	UPROPERTY() float Health = 100.f;
	UPROPERTY() float SuitOxygen = 100.f;
	UPROPERTY() int32 Mag = 24;
	UPROPERTY() int32 Reserve = 96;
};
