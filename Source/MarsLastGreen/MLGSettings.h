#pragma once
#include "CoreMinimal.h"
#include "GameFramework/SaveGame.h"
#include "InputCoreTypes.h"
#include "MLGSettings.generated.h"

// One remappable control: an action (Jump...) or one direction of an axis (MoveForward +1 / -1).
struct FMLGBinding { const TCHAR* Label; const TCHAR* Name; bool bAxis; float Scale; const TCHAR* DefaultKey; };

// Player options, persisted in their own save slot (never in DefaultInput.ini, so they survive engine/source updates).
UCLASS()
class MARSLASTGREEN_API UMLGSettings : public USaveGame
{
	GENERATED_BODY()
public:
	UPROPERTY() float MouseSensitivity = 1.f;
	UPROPERTY() bool bInvertY = false;
	UPROPERTY() bool bToggleCrouch = true;
	UPROPERTY() float FOV = 90.f;
	UPROPERTY() float MasterVolume = 1.f;
	UPROPERTY() float SFXVolume = 0.9f;
	UPROPERTY() float MusicVolume = 0.7f;
	UPROPERTY() float AmbienceVolume = 0.8f;
	UPROPERTY() float UIScale = 1.f;        // HUD text scale
	UPROPERTY() float HoldScale = 1.f;      // interaction hold time multiplier (1 normal, 0.5 short, 0 instant)
	UPROPERTY() uint8 Difficulty = 1;       // 0 Easy, 1 Normal, 2 Hard
	UPROPERTY() TMap<FName, FKey> Keys;     // binding id -> key

	static UMLGSettings* Get();             // loaded once, kept alive; applies saved key overrides on first use
	static const TArray<FMLGBinding>& Bindings();
	static FString Id(const FMLGBinding& B);
	static FKey GetKey(const FMLGBinding& B);

	void Save() const;
	void ApplyAudio() const;
	void SetKey(int32 Index, FKey K);       // a key already used by another binding is swapped, never double-bound
	void ResetKeys();
	void ResetDefaults();
private:
	static void SetKeyRaw(const FMLGBinding& B, FKey K);
	void StoreKeys();
};
