#pragma once
#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "MLGGameMode.generated.h"

class UAudioComponent;
class UMaterialInstanceDynamic;
class AStaticMeshActor;
class ACameraActor;
class APointLight;
class AMLGAlien;
enum class EMLGPhase : uint8;

UENUM(BlueprintType)
enum class EMLGDifficulty : uint8 { Easy, Normal, Hard };

UENUM(BlueprintType)
enum class EMLGMusicState : uint8 { Silent, Calm, Combat };

UCLASS()
class MARSLASTGREEN_API AMLGGameMode : public AGameModeBase
{
	GENERATED_BODY()
public:
	AMLGGameMode();
	// Wave director. Waves start only once power, oxygen and greenhouse seal are up and a plant is alive (nothing attacks an
	// unprepared base), wait for the previous wave to die, warn 20 s ahead, and hold while the player is nearly dead.
	UPROPERTY(EditAnywhere, BlueprintReadWrite) EMLGDifficulty Difficulty = EMLGDifficulty::Normal;  // URL option ?Difficulty=Easy|Normal|Hard
	UPROPERTY(EditAnywhere, BlueprintReadWrite) int32 MaxWaves = 3;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) float FirstWaveDelay = 45.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) float WaveGap = 90.f;
	void SpawnWave(int32 Raiders, int32 Breakers = 0, int32 Gunners = 0);
	void RunEnemyTest();
	void RunShots();
	void StartIntro(bool bForce = false);
	void EndIntro();
	bool IsIntroActive() const { return bIntroActive; }
	bool IsSuppressingKillDrops() const { return bSuppressKillDrops; }
	float IntroTime = 0.f;
	void RunDiag();    // dev only: console "mlg.diag" bisects a rendering problem with view flags (rendered run)   // dev only: console "mlg.shots" saves a tour of screenshots (needs a rendering run)   // dev only: console "mlg.enemytest"
	void RunSelfTest();  // dev only: console "mlg.selftest"
	void RunMissionTest();  // dev only: console "mlg.missiontest"
	bool SaveCheckpoint(bool bManual);   // false if refused (attackers alive / not in a saveable phase)
	bool LoadCheckpoint();               // false if no checkpoint exists
	static const TCHAR* SlotName() { return TEXT("MLG_Checkpoint"); }
	static EMLGMusicState SelectMusicState(EMLGPhase Phase, int32 AliveAliens, bool bWaveWarned, bool bPlayerDead);
	EMLGMusicState GetCurrentMusicState() const { return CurrentMusicState; }
	void UpdateMusic();
	// If the loaded map contains no AMLGDevice, a TEMPORARY blockout base is built from engine primitives so the slice is playable
	// before the real level/assets exist. Remove when Maps/Base has real placed content.
	virtual void InitGame(const FString& Map, const FString& Options, FString& Err) override;
	virtual void StartPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
protected:
	virtual void Tick(float Dt) override;
private:
	float DirectorTimer = 0.f, NextWaveIn = 45.f;
	bool bIntroActive = false;
	bool bIntroShattered = false;
	bool bIntroLanderCollision = false;
	FVector IntroLandingPosition = FVector::ZeroVector;
	FRotator IntroLandingRotation = FRotator::ZeroRotator;
	UPROPERTY(Transient) ACameraActor* IntroCamera = nullptr;
	UPROPERTY(Transient) AStaticMeshActor* IntroLander = nullptr;
	UPROPERTY(Transient) AStaticMeshActor* IntroEarth = nullptr;
	UPROPERTY(Transient) AStaticMeshActor* IntroBackdrop = nullptr;
	UPROPERTY(Transient) AStaticMeshActor* IntroFlash = nullptr;
	UPROPERTY(Transient) AStaticMeshActor* IntroShockwave = nullptr;
	UPROPERTY(Transient) APointLight* IntroThruster = nullptr;
	UPROPERTY(Transient) UMaterialInstanceDynamic* IntroEarthMaterial = nullptr;
	UPROPERTY(Transient) UAudioComponent* IntroScore = nullptr;
	UPROPERTY(Transient) UAudioComponent* IntroDialogue = nullptr;
	UPROPERTY(Transient) TArray<AStaticMeshActor*> IntroActors;
	UPROPERTY(Transient) TArray<AStaticMeshActor*> IntroCrust;
	UPROPERTY(Transient) TArray<AStaticMeshActor*> IntroDebris;
	UPROPERTY(Transient) TArray<AStaticMeshActor*> IntroDust;
	void TickIntro(float Dt);
	float FirstContactTimer = 0.f;
	float SoftlockSeconds = 0.f;
	float KillDropCooldown = 0.f;
	bool bFirstContactTriggered = false;
	bool bFirstContactArmed = false;
	bool bCheckpointPending = false;
	bool bSuppressKillDrops = false;
	TSet<TWeakObjectPtr<AMLGAlien>> ProcessedDeadAliens;
	void ProcessAlienKillDrops(float Dt, class AMLGGameState* GS);
	float CalmMusicAlpha = 0.f, CombatMusicAlpha = 0.f;
	bool bWarned = false, bHeldNotice = false, bInit = false;
	uint8 LastPhase = 255;
	EMLGMusicState CurrentMusicState = EMLGMusicState::Silent;
	UPROPERTY(Transient) UAudioComponent* CalmMusicComp = nullptr;
	UPROPERTY(Transient) UAudioComponent* CombatMusicComp = nullptr;
	void TickMusic(float Dt, const class AMLGGameState* GS, int32 AliveAliens);
	void BuildPrototypeBase();
};
