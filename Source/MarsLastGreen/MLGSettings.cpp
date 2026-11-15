#include "MLGSettings.h"
#include "GameFramework/InputSettings.h"
#include "Kismet/GameplayStatics.h"
#include "AudioDevice.h"
#include "Engine/Engine.h"

static const TCHAR* GSlot = TEXT("MLG_Settings");

const TArray<FMLGBinding>& UMLGSettings::Bindings()
{
	static const TArray<FMLGBinding> B = {
		{ TEXT("Move forward"), TEXT("MoveForward"), true, 1.f, TEXT("W") }, { TEXT("Move back"), TEXT("MoveForward"), true, -1.f, TEXT("S") },
		{ TEXT("Move right"), TEXT("MoveRight"), true, 1.f, TEXT("D") }, { TEXT("Move left"), TEXT("MoveRight"), true, -1.f, TEXT("A") },
		{ TEXT("Jump"), TEXT("Jump"), false, 0.f, TEXT("SpaceBar") }, { TEXT("Sprint"), TEXT("Sprint"), false, 0.f, TEXT("LeftShift") },
		{ TEXT("Crouch"), TEXT("Crouch"), false, 0.f, TEXT("LeftControl") }, { TEXT("Interact / repair"), TEXT("Interact"), false, 0.f, TEXT("E") },
		{ TEXT("Fire"), TEXT("Fire"), false, 0.f, TEXT("LeftMouseButton") }, { TEXT("Aim"), TEXT("Aim"), false, 0.f, TEXT("RightMouseButton") },
		{ TEXT("Reload"), TEXT("Reload"), false, 0.f, TEXT("R") }, { TEXT("Quick save"), TEXT("QuickSave"), false, 0.f, TEXT("F5") },
		{ TEXT("Quick load"), TEXT("QuickLoad"), false, 0.f, TEXT("F9") } };
	return B;
}

FString UMLGSettings::Id(const FMLGBinding& B) { return B.bAxis ? FString::Printf(TEXT("%s%c"), B.Name, B.Scale > 0.f ? '+' : '-') : FString(B.Name); }

FKey UMLGSettings::GetKey(const FMLGBinding& B)
{
	UInputSettings* IS = UInputSettings::GetInputSettings();
	if (B.bAxis) { for (const FInputAxisKeyMapping& M : IS->GetAxisMappings()) if (M.AxisName == B.Name && (M.Scale > 0.f) == (B.Scale > 0.f)) return M.Key; }
	else { for (const FInputActionKeyMapping& M : IS->GetActionMappings()) if (M.ActionName == B.Name) return M.Key; }
	return EKeys::Invalid;
}

void UMLGSettings::SetKeyRaw(const FMLGBinding& B, FKey K)
{
	UInputSettings* IS = UInputSettings::GetInputSettings();
	if (B.bAxis)
	{
		TArray<FInputAxisKeyMapping> Old = IS->GetAxisMappings();
		for (const FInputAxisKeyMapping& M : Old) if (M.AxisName == B.Name && (M.Scale > 0.f) == (B.Scale > 0.f)) IS->RemoveAxisMapping(M, false);
		IS->AddAxisMapping(FInputAxisKeyMapping(B.Name, K, B.Scale), false);
	}
	else
	{
		TArray<FInputActionKeyMapping> Old = IS->GetActionMappings();
		for (const FInputActionKeyMapping& M : Old) if (M.ActionName == B.Name) IS->RemoveActionMapping(M, false);
		IS->AddActionMapping(FInputActionKeyMapping(B.Name, K), false);
	}
	IS->ForceRebuildKeymaps();
}

void UMLGSettings::StoreKeys() { Keys.Reset(); for (const FMLGBinding& B : Bindings()) Keys.Add(*Id(B), GetKey(B)); }

void UMLGSettings::SetKey(int32 Index, FKey K)
{
	const TArray<FMLGBinding>& B = Bindings();
	if (!B.IsValidIndex(Index) || !K.IsValid()) return;
	const FKey Old = GetKey(B[Index]);
	for (int32 J = 0; J < B.Num(); ++J) if (J != Index && GetKey(B[J]) == K) SetKeyRaw(B[J], Old);   // swap on conflict
	SetKeyRaw(B[Index], K);
	StoreKeys(); Save();
}

void UMLGSettings::ResetKeys()
{
	for (const FMLGBinding& B : Bindings()) SetKeyRaw(B, FKey(B.DefaultKey));
	StoreKeys(); Save();
}

void UMLGSettings::ResetDefaults()
{
	MouseSensitivity = 1.f; bInvertY = false; bToggleCrouch = true; FOV = 90.f;
	MasterVolume = 1.f; SFXVolume = 0.9f; MusicVolume = 0.7f; AmbienceVolume = 0.8f;
	UIScale = 1.f; HoldScale = 1.f; Difficulty = 1;
	ResetKeys(); ApplyAudio();
}

void UMLGSettings::Save() const { UGameplayStatics::SaveGameToSlot(const_cast<UMLGSettings*>(this), GSlot, 0); }

void UMLGSettings::ApplyAudio() const
{
	if (GEngine) if (FAudioDeviceHandle D = GEngine->GetMainAudioDevice()) D->SetTransientPrimaryVolume(MasterVolume);
}

UMLGSettings* UMLGSettings::Get()
{
	static UMLGSettings* Inst = nullptr;
	if (Inst) return Inst;
	Inst = Cast<UMLGSettings>(UGameplayStatics::LoadGameFromSlot(GSlot, 0));
	if (!Inst) Inst = Cast<UMLGSettings>(UGameplayStatics::CreateSaveGameObject(UMLGSettings::StaticClass()));
	Inst->AddToRoot();
	for (const FMLGBinding& B : Bindings()) if (const FKey* K = Inst->Keys.Find(*Id(B))) if (K->IsValid()) SetKeyRaw(B, *K);
	Inst->ApplyAudio();
	return Inst;
}
