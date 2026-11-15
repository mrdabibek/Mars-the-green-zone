#include "MLGPlayerController.h"
#include "MLGAssets.h"
#include "MLGSettings.h"
#include "MLGGameMode.h"
#include "MLGGameState.h"
#include "Components/InputComponent.h"
#include "Kismet/GameplayStatics.h"
#include "Kismet/KismetSystemLibrary.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "HAL/IConsoleManager.h"
#include "GameFramework/InputSettings.h"
#include "TimerManager.h"

void AMLGPlayerController::BeginPlay()
{
	Super::BeginPlay();
	UMLGSettings::Get();
	if (IsLocalController() && !FParse::Param(FCommandLine::Get(), TEXT("nomenu"))) OpenMenu(EMLGMenu::Title);
}

void AMLGPlayerController::SetupInputComponent()
{
	Super::SetupInputComponent();
	auto B = [this](const TCHAR* Name, void (AMLGPlayerController::*F)()) { InputComponent->BindAction(Name, IE_Pressed, this, F).bExecuteWhenPaused = true; };
	B(TEXT("MenuUp"), &AMLGPlayerController::MenuUp); B(TEXT("MenuDown"), &AMLGPlayerController::MenuDown);
	B(TEXT("MenuLeft"), &AMLGPlayerController::MenuLeft); B(TEXT("MenuRight"), &AMLGPlayerController::MenuRight);
	B(TEXT("MenuAccept"), &AMLGPlayerController::MenuAccept); B(TEXT("Pause"), &AMLGPlayerController::TogglePause);
}

bool AMLGPlayerController::InputKey(const FInputKeyParams& P)
{
	if (bCapturing && P.Event == IE_Pressed)
	{
		bCapturing = false;
		const TArray<FMLGMenuItem> It = Items();
		if (P.Key != EKeys::Escape && It.IsValidIndex(Sel) && It[Sel].Id.ToString().StartsWith("Bind_"))
		{
			const int32 I = FCString::Atoi(*It[Sel].Id.ToString().Mid(5));
			UMLGSettings::Get()->SetKey(I, P.Key);
			Notice = FString::Printf(TEXT("%s bound to %s"), UMLGSettings::Bindings()[I].Label, *P.Key.GetDisplayName().ToString());
		}
		return true;
	}
	if (AMLGGameMode* GM = GetWorld() ? GetWorld()->GetAuthGameMode<AMLGGameMode>() : nullptr)
	{
		if (GM->IsIntroActive() && Menu == EMLGMenu::None)
		{
			if (GM->IntroTime < 0.85f) return true;
			const bool bSkip = P.Key == EKeys::SpaceBar || P.Key == EKeys::Enter || P.Key == EKeys::Escape ||
				P.Key == EKeys::LeftMouseButton || P.Key == EKeys::Gamepad_FaceButton_Bottom;
			if (P.Event == IE_Pressed && bSkip) GM->EndIntro();
			return true;
		}
	}
	return Super::InputKey(P);
}

void AMLGPlayerController::OpenMenu(EMLGMenu M)
{
	Menu = M; Parent = EMLGMenu::None; Sel = 0; Notice.Empty(); bCapturing = false;
	UGameplayStatics::SetGamePaused(this, true);
	if (AMLGGameMode* GM = GetWorld() ? GetWorld()->GetAuthGameMode<AMLGGameMode>() : nullptr) GM->UpdateMusic();
}
void AMLGPlayerController::CloseMenu()
{
	Menu = EMLGMenu::None; bCapturing = false;
	UGameplayStatics::SetGamePaused(this, false);
	if (AMLGGameMode* GM = GetWorld() ? GetWorld()->GetAuthGameMode<AMLGGameMode>() : nullptr) GM->UpdateMusic();
}
void AMLGPlayerController::TogglePause()
{
	MLGAssets::PlaySound2D(this, MLGAssets::Audio::UIClick, 0.7f);
	if (Menu == EMLGMenu::None) OpenMenu(EMLGMenu::Pause);
	else MenuBack();
}
void AMLGPlayerController::MenuBack()
{
	if (bCapturing) { bCapturing = false; return; }
	MLGAssets::PlaySound2D(this, MLGAssets::Audio::UIClick, 0.7f);
	if (Menu == EMLGMenu::Pause) CloseMenu();
	else if (Parent != EMLGMenu::None && Menu != EMLGMenu::Title && Menu != EMLGMenu::Pause) { Menu = Parent; Parent = EMLGMenu::None; Sel = 0; Notice.Empty(); }
}
void AMLGPlayerController::MenuUp() { if (Menu == EMLGMenu::Codex) return; const int32 N = Items().Num(); if (N && !bCapturing) { Sel = (Sel + N - 1) % N; MLGAssets::PlaySound2D(this, MLGAssets::Audio::UIClick, 0.65f); } }
void AMLGPlayerController::MenuDown() { if (Menu == EMLGMenu::Codex) return; const int32 N = Items().Num(); if (N && !bCapturing) { Sel = (Sel + 1) % N; MLGAssets::PlaySound2D(this, MLGAssets::Audio::UIClick, 0.65f); } }

FString AMLGPlayerController::MenuTitle() const
{
	switch (Menu) { case EMLGMenu::Title: return TEXT("MARS: LAST GREEN"); case EMLGMenu::Pause: return TEXT("PAUSED"); case EMLGMenu::Settings: return TEXT("SETTINGS");
	case EMLGMenu::Controls: return TEXT("CONTROLS"); case EMLGMenu::Codex: return TEXT("SCIENCE CODEX"); default: return FString(); }
}

static FString Pct(float V) { return FString::Printf(TEXT("%d%%"), FMath::RoundToInt(V * 100.f)); }
static const TCHAR* DiffName(uint8 D) { return D == 0 ? TEXT("Easy") : D == 2 ? TEXT("Hard") : TEXT("Normal"); }

TArray<FMLGMenuItem> AMLGPlayerController::Items() const
{
	const UMLGSettings* S = UMLGSettings::Get();
	TArray<FMLGMenuItem> R;
	auto Add = [&R](const TCHAR* Id, const FString& L) { R.Add({ FName(Id), L }); };
	switch (Menu)
	{
	case EMLGMenu::Title:
		if (UGameplayStatics::DoesSaveGameExist(AMLGGameMode::SlotName(), 0)) Add(TEXT("Continue"), TEXT("Continue from checkpoint"));
		Add(TEXT("NewGame"), TEXT("New game")); Add(TEXT("Difficulty"), FString::Printf(TEXT("Difficulty:  < %s >"), DiffName(S->Difficulty)));
		Add(TEXT("Settings"), TEXT("Settings")); Add(TEXT("Controls"), TEXT("Controls")); Add(TEXT("Codex"), TEXT("Science codex")); Add(TEXT("Quit"), TEXT("Quit"));
		break;
	case EMLGMenu::Pause:
		Add(TEXT("Resume"), TEXT("Resume")); Add(TEXT("Save"), TEXT("Save checkpoint")); Add(TEXT("Load"), TEXT("Load checkpoint"));
		Add(TEXT("Difficulty"), FString::Printf(TEXT("Difficulty:  < %s >"), DiffName(S->Difficulty)));
		Add(TEXT("Settings"), TEXT("Settings")); Add(TEXT("Controls"), TEXT("Controls")); Add(TEXT("Codex"), TEXT("Science codex"));
		Add(TEXT("MainMenu"), TEXT("Main menu (unsaved progress lost)")); Add(TEXT("Quit"), TEXT("Quit"));
		break;
	case EMLGMenu::Settings:
		Add(TEXT("Sens"), FString::Printf(TEXT("Mouse sensitivity:  < %.1f >"), S->MouseSensitivity));
		Add(TEXT("Invert"), FString::Printf(TEXT("Invert look Y:  < %s >"), S->bInvertY ? TEXT("On") : TEXT("Off")));
		Add(TEXT("Crouch"), FString::Printf(TEXT("Crouch:  < %s >"), S->bToggleCrouch ? TEXT("Toggle") : TEXT("Hold")));
		Add(TEXT("Fov"), FString::Printf(TEXT("Field of view:  < %d >"), FMath::RoundToInt(S->FOV)));
		Add(TEXT("Volume"), FString::Printf(TEXT("Master volume:  < %s >"), *Pct(S->MasterVolume)));
		Add(TEXT("SFXVolume"), FString::Printf(TEXT("SFX volume:  < %s >"), *Pct(S->SFXVolume)));
		Add(TEXT("MusicVolume"), FString::Printf(TEXT("Music volume:  < %s >"), *Pct(S->MusicVolume)));
		Add(TEXT("AmbienceVolume"), FString::Printf(TEXT("Ambience volume:  < %s >"), *Pct(S->AmbienceVolume)));
		Add(TEXT("UIScale"), FString::Printf(TEXT("HUD text size:  < %s >"), *Pct(S->UIScale)));
		Add(TEXT("Hold"), FString::Printf(TEXT("Hold-to-interact time:  < %s >"), S->HoldScale >= 1.f ? TEXT("Normal") : S->HoldScale > 0.f ? TEXT("Short") : TEXT("Instant")));
		Add(TEXT("Difficulty"), FString::Printf(TEXT("Difficulty:  < %s >"), DiffName(S->Difficulty)));
		Add(TEXT("ResetAll"), TEXT("Reset all settings and controls to defaults")); Add(TEXT("Back"), TEXT("Back"));
		break;
	case EMLGMenu::Controls:
	{
		const TArray<FMLGBinding>& B = UMLGSettings::Bindings();
		for (int32 I = 0; I < B.Num(); ++I)
			R.Add({ FName(*FString::Printf(TEXT("Bind_%d"), I)), FString::Printf(TEXT("%s:  %s"), B[I].Label, (bCapturing && I == Sel) ? TEXT("[PRESS KEY]  ([ESC] CANCEL)") : *UMLGSettings::GetKey(B[I]).GetDisplayName().ToString()) });
		Add(TEXT("ResetKeys"), TEXT("Reset controls to defaults")); Add(TEXT("Back"), TEXT("Back"));
		break;
	}
	case EMLGMenu::Codex: Add(TEXT("Back"), TEXT("Back")); break;
	default: break;
	}
	return R;
}

void AMLGPlayerController::Adjust(int32 Dir)
{
	if (bCapturing) return;
	if (Menu == EMLGMenu::Codex) { const int32 N = Codex().Num(); CodexPage = (CodexPage + Dir + N) % N; MLGAssets::PlaySound2D(this, MLGAssets::Audio::UIClick, 0.7f); return; }
	const TArray<FMLGMenuItem> It = Items(); if (!It.IsValidIndex(Sel)) return;
	UMLGSettings* S = UMLGSettings::Get(); const FString Id = It[Sel].Id.ToString(); bool bChanged = true;
	if (Id == "Sens") S->MouseSensitivity = FMath::Clamp(FMath::RoundToFloat((S->MouseSensitivity + 0.1f * Dir) * 10.f) / 10.f, 0.2f, 3.f);
	else if (Id == "Invert") S->bInvertY = !S->bInvertY;
	else if (Id == "Crouch") S->bToggleCrouch = !S->bToggleCrouch;
	else if (Id == "Fov") S->FOV = FMath::Clamp(S->FOV + 5.f * Dir, 70.f, 110.f);
	else if (Id == "Volume") S->MasterVolume = FMath::Clamp(FMath::RoundToFloat((S->MasterVolume + 0.1f * Dir) * 10.f) / 10.f, 0.f, 1.f);
	else if (Id == "SFXVolume") S->SFXVolume = FMath::Clamp(FMath::RoundToFloat((S->SFXVolume + 0.1f * Dir) * 10.f) / 10.f, 0.f, 1.f);
	else if (Id == "MusicVolume") S->MusicVolume = FMath::Clamp(FMath::RoundToFloat((S->MusicVolume + 0.1f * Dir) * 10.f) / 10.f, 0.f, 1.f);
	else if (Id == "AmbienceVolume") S->AmbienceVolume = FMath::Clamp(FMath::RoundToFloat((S->AmbienceVolume + 0.1f * Dir) * 10.f) / 10.f, 0.f, 1.f);
	else if (Id == "UIScale") S->UIScale = S->UIScale < 1.1f ? (Dir > 0 ? 1.25f : 1.5f) : S->UIScale < 1.4f ? (Dir > 0 ? 1.5f : 1.f) : (Dir > 0 ? 1.f : 1.25f);
	else if (Id == "Hold") S->HoldScale = S->HoldScale >= 1.f ? (Dir > 0 ? 0.5f : 0.f) : S->HoldScale > 0.f ? (Dir > 0 ? 0.f : 1.f) : (Dir > 0 ? 1.f : 0.5f);
	else if (Id == "Difficulty")
	{
		S->Difficulty = (S->Difficulty + 3 + Dir) % 3;
		if (AMLGGameMode* GM = GetWorld()->GetAuthGameMode<AMLGGameMode>()) GM->Difficulty = (EMLGDifficulty)S->Difficulty;
	}
	else bChanged = false;
	if (bChanged)
	{
		S->Save();
		S->ApplyAudio();
		if (AMLGGameMode* GM = GetWorld() ? GetWorld()->GetAuthGameMode<AMLGGameMode>() : nullptr) GM->UpdateMusic();
		MLGAssets::PlaySound2D(this, MLGAssets::Audio::UIClick, 0.7f);
	}
}

void AMLGPlayerController::MenuAccept()
{
	if (Menu == EMLGMenu::None)
	{
		if (AMLGGameState* GS = GetWorld()->GetGameState<AMLGGameState>(); GS && GS->Phase == EMLGPhase::Planning)
		{
			GS->ConfirmKit();
			MLGAssets::PlaySound2D(this, MLGAssets::Audio::UIClick, 0.75f);
		}
		return;
	}

	if (Menu == EMLGMenu::Codex) { MenuRight(); return; }
	const TArray<FMLGMenuItem> It = Items(); if (!It.IsValidIndex(Sel) || bCapturing) return;
	const FString Id = It[Sel].Id.ToString();
	MLGAssets::PlaySound2D(this, MLGAssets::Audio::UIClick, 0.75f);
	AMLGGameMode* GM = GetWorld()->GetAuthGameMode<AMLGGameMode>();
	if (Id == "Continue" || Id == "Load") { if (GM && GM->LoadCheckpoint()) CloseMenu(); else Notice = TEXT("No checkpoint yet"); }
	else if (Id == "NewGame") { CloseMenu(); if (GM) GM->StartIntro(); }
	else if (Id == "Resume") CloseMenu();
	else if (Id == "Save") Notice = (GM && GM->SaveCheckpoint(true)) ? TEXT("Checkpoint saved") : TEXT("Cannot save right now (attack in progress, planning, or an end screen)");
	else if (Id == "Settings") Push(EMLGMenu::Settings);
	else if (Id == "Controls") Push(EMLGMenu::Controls);
	else if (Id == "Codex") { Push(EMLGMenu::Codex); CodexPage = 0; }
	else if (Id == "MainMenu") { UGameplayStatics::SetGamePaused(this, false); ConsoleCommand(TEXT("RestartLevel")); }
	else if (Id == "Quit") UKismetSystemLibrary::QuitGame(this, this, EQuitPreference::Quit, false);
	else if (Id == "Back") MenuBack();
	else if (Id == "ResetKeys") { UMLGSettings::Get()->ResetKeys(); Notice = TEXT("Controls reset"); }
	else if (Id == "ResetAll") { UMLGSettings::Get()->ResetDefaults(); Notice = TEXT("Defaults restored"); }
	else if (Id.StartsWith("Bind_")) bCapturing = true;
	else Adjust(+1);
}

const TArray<FMLGCodexPage>& AMLGPlayerController::Codex()
{
	static const TArray<FMLGCodexPage> P = {
		{ TEXT("The Martian atmosphere"), { TEXT("Mars has a thin atmosphere that is about 95% carbon dioxide."),
			TEXT("Its surface pressure is under 1% of Earth's, so a person outside a pressurized habitat or suit cannot survive."),
			TEXT("That is why the game has sealed rooms and a suit oxygen supply that drains outdoors and refills indoors.") } },
		{ TEXT("Water on Mars"), { TEXT("Liquid water is not stable for long on the open surface of Mars: the air is too thin and cold."),
			TEXT("Water is found as ice, at the poles and buried underground. Missions would have to extract and purify it."),
			TEXT("GAME SIMPLIFICATION: 1 ice unit gives 8 litres, and 60% of plant water is recycled in the sealed greenhouse."),
			TEXT("These are teaching numbers, not engineering data.") } },
		{ TEXT("Growing food"), { TEXT("Martian soil (regolith) is hard to farm: it is low in nutrients and contains perchlorates, toxic salts."),
			TEXT("NASA plant researchers study which crops could be grown in deep space and how (see Sources)."),
			TEXT("GAME SIMPLIFICATION: plants grow in minutes, not weeks. Growth stops when water, power or the greenhouse seal fails."),
			TEXT("A few plants do not make Mars breathable and do not terraform it.") } },
		{ TEXT("Threat guide (fictional)"), { TEXT("Red raiders: fast and fragile. They raid the water line and lunge at you within 9 m. Shoot during their lunge telegraph to stagger them."),
			TEXT("Purple breakers: slow and armoured (50% damage). Shoot while it rears up for 1.5x weakspot damage + stagger, or JUMP over its expanding ground shockwave."),
			TEXT("Blue gunners: armed flankers. A pulsing red-orange laser sight warns of a plasma bolt in 0.9 s. Break line of sight behind cover and it misses."),
			TEXT("Gunners circle round from the north-west and favour the greenhouse. The tactical radar and compass pips track all active hostiles.") } },
		{ TEXT("What is fiction"), { TEXT("The loss of contact with Earth is a story event. It is not a prediction about Earth's future,"),
			TEXT("and nothing in this game says pollution or climate would make Earth vanish."),
			TEXT("The attackers are fictional. No life has been found on Mars."),
			TEXT("Repair costs, power, water and wave sizes are simplified for play.") } },
		{ TEXT("Sources"), { TEXT("NASA, Mars facts: https://science.nasa.gov/mars/facts/"),
			TEXT("NASA, plant researchers explore deep space food crops:"), TEXT("https://www.nasa.gov/science-research/nasa-plant-researchers-explore-question-of-deep-space-food-crops/"),
			TEXT("This game is not affiliated with or endorsed by NASA.") } } };
	return P;
}

#if !UE_BUILD_SHIPPING
// Scripted menu/settings check (headless): run with -nomenu, console "mlg.uitest".
static void RunUiTest(UWorld* W)
{
	AMLGPlayerController* PC = Cast<AMLGPlayerController>(UGameplayStatics::GetPlayerController(W, 0));
	AMLGGameMode* GM = W->GetAuthGameMode<AMLGGameMode>();
	int32 Fail = 0;
	auto Chk = [&Fail](const TCHAR* N, bool Ok) { UE_LOG(LogTemp, Display, TEXT("MLG-UI %s: %s"), Ok ? TEXT("PASS") : TEXT("FAIL"), N); if (!Ok) ++Fail; };
	if (!PC || !GM) { UE_LOG(LogTemp, Display, TEXT("MLG-UI FAIL: no controller/game mode")); return; }
	UMLGSettings* S = UMLGSettings::Get(); S->ResetDefaults();
	const TArray<FMLGBinding>& B = UMLGSettings::Bindings();
	auto Idx = [&B](const TCHAR* Id) { for (int32 I = 0; I < B.Num(); ++I) if (UMLGSettings::Id(B[I]) == Id) return I; return -1; };

	// menus + pause
	Chk(TEXT("no menu at start with -nomenu"), PC->Menu == EMLGMenu::None && !UGameplayStatics::IsGamePaused(W));
	PC->TogglePause(); Chk(TEXT("Esc opens pause menu and pauses"), PC->Menu == EMLGMenu::Pause && UGameplayStatics::IsGamePaused(W));
	Chk(TEXT("pause menu has items"), PC->Items().Num() >= 8);
	PC->TogglePause(); Chk(TEXT("Esc resumes"), PC->Menu == EMLGMenu::None && !UGameplayStatics::IsGamePaused(W));
	PC->OpenMenu(EMLGMenu::Title); Chk(TEXT("title menu has New game"), PC->Items().ContainsByPredicate([](const FMLGMenuItem& I) { return I.Id == "NewGame"; }));
	PC->TogglePause(); Chk(TEXT("Esc does not leave the title menu"), PC->Menu == EMLGMenu::Title);
	PC->Sel = PC->Items().IndexOfByPredicate([](const FMLGMenuItem& I) { return I.Id == "NewGame"; }); PC->MenuAccept();
	Chk(TEXT("New game closes menu and unpauses"), PC->Menu == EMLGMenu::None && !UGameplayStatics::IsGamePaused(W));

	// settings through the menu
	PC->OpenMenu(EMLGMenu::Pause); PC->Sel = PC->Items().IndexOfByPredicate([](const FMLGMenuItem& I) { return I.Id == "Settings"; }); PC->MenuAccept();
	Chk(TEXT("settings submenu"), PC->Menu == EMLGMenu::Settings);
	auto Pick = [PC](const TCHAR* Id) { PC->Sel = PC->Items().IndexOfByPredicate([Id](const FMLGMenuItem& I) { return I.Id == Id; }); };
	Pick(TEXT("Sens")); PC->MenuRight(); PC->MenuRight(); Chk(TEXT("sensitivity 1.0 -> 1.2"), FMath::IsNearlyEqual(S->MouseSensitivity, 1.2f, 0.001f));
	for (int32 I = 0; I < 40; ++I) PC->MenuRight(); Chk(TEXT("sensitivity clamps at 3.0"), FMath::IsNearlyEqual(S->MouseSensitivity, 3.f, 0.001f));
	Pick(TEXT("Invert")); PC->MenuAccept(); Chk(TEXT("invert Y on"), S->bInvertY);
	Pick(TEXT("Fov")); PC->MenuLeft(); Chk(TEXT("fov 85"), S->FOV == 85.f);
	Pick(TEXT("Volume")); for (int32 I = 0; I < 12; ++I) PC->MenuLeft(); Chk(TEXT("volume clamps at 0"), S->MasterVolume == 0.f);
	Pick(TEXT("UIScale")); PC->MenuRight(); Chk(TEXT("HUD text 125%"), FMath::IsNearlyEqual(S->UIScale, 1.25f));
	Pick(TEXT("Hold")); PC->MenuRight(); PC->MenuRight(); Chk(TEXT("hold time -> instant"), S->HoldScale == 0.f);
	Pick(TEXT("Difficulty")); PC->MenuRight(); Chk(TEXT("difficulty Hard reaches game mode"), S->Difficulty == 2 && GM->Difficulty == EMLGDifficulty::Hard);
	PC->MenuBack(); Chk(TEXT("Esc returns to pause menu"), PC->Menu == EMLGMenu::Pause); PC->CloseMenu();

	// persistence round-trip
	S->Save(); const float Sens = S->MouseSensitivity; S->MouseSensitivity = 0.5f; S->bInvertY = false;
	UMLGSettings* L = Cast<UMLGSettings>(UGameplayStatics::LoadGameFromSlot(TEXT("MLG_Settings"), 0));
	Chk(TEXT("settings persist to disk"), L && FMath::IsNearlyEqual(L->MouseSensitivity, Sens, 0.001f) && L->bInvertY && L->Difficulty == 2);

	// remapping
	const int32 J = Idx(TEXT("Jump")), Sp = Idx(TEXT("Sprint")), Mf = Idx(TEXT("MoveForward+")), Mb = Idx(TEXT("MoveForward-"));
	Chk(TEXT("defaults: Jump=Space Sprint=LeftShift W/S"), UMLGSettings::GetKey(B[J]) == EKeys::SpaceBar && UMLGSettings::GetKey(B[Sp]) == EKeys::LeftShift && UMLGSettings::GetKey(B[Mf]) == EKeys::W);
	S->SetKey(J, EKeys::X); Chk(TEXT("remap Jump -> X"), UMLGSettings::GetKey(B[J]) == EKeys::X);
	S->SetKey(Sp, EKeys::X); Chk(TEXT("conflict swaps: Sprint=X, Jump gets old LeftShift"), UMLGSettings::GetKey(B[Sp]) == EKeys::X && UMLGSettings::GetKey(B[J]) == EKeys::LeftShift);
	S->SetKey(Mf, EKeys::Up); Chk(TEXT("axis remap forward -> Up, back stays S"), UMLGSettings::GetKey(B[Mf]) == EKeys::Up && UMLGSettings::GetKey(B[Mb]) == EKeys::S);
	int32 Axes = 0; for (const FInputAxisKeyMapping& M : UInputSettings::GetInputSettings()->GetAxisMappings()) Axes += M.AxisName == "MoveForward";
	Chk(TEXT("exactly 2 MoveForward axis mappings"), Axes == 2);
	Chk(TEXT("remaps stored for next launch"), S->Keys.Num() == B.Num() && S->Keys.FindRef(TEXT("Sprint")) == EKeys::X);
	// in-menu capture
	PC->OpenMenu(EMLGMenu::Controls); PC->Sel = Idx(TEXT("Reload")); PC->MenuAccept(); Chk(TEXT("Accept starts key capture"), PC->bCapturing);
	PC->InputKey(FInputKeyParams(EKeys::G, IE_Pressed, 1.0)); Chk(TEXT("captured key binds Reload=G"), !PC->bCapturing && UMLGSettings::GetKey(B[Idx(TEXT("Reload"))]) == EKeys::G);
	PC->MenuAccept(); PC->InputKey(FInputKeyParams(EKeys::Escape, IE_Pressed, 1.0)); Chk(TEXT("Esc cancels capture, binding unchanged"), !PC->bCapturing && UMLGSettings::GetKey(B[Idx(TEXT("Reload"))]) == EKeys::G);
	PC->CloseMenu();
	S->ResetKeys(); Chk(TEXT("reset restores defaults"), UMLGSettings::GetKey(B[J]) == EKeys::SpaceBar && UMLGSettings::GetKey(B[Sp]) == EKeys::LeftShift && UMLGSettings::GetKey(B[Mf]) == EKeys::W);

	// codex
	bool bOk = AMLGPlayerController::Codex().Num() >= 5; for (const FMLGCodexPage& P : AMLGPlayerController::Codex()) bOk &= P.Lines.Num() > 0;
	PC->OpenMenu(EMLGMenu::Codex); PC->MenuRight(); Chk(TEXT("codex pages exist and turn"), bOk && PC->CodexPage == 1); PC->CloseMenu();

	S->ResetDefaults();

	// Exercise the same key mapping as the live planning screen. Exactly filling the budget is valid.
	AMLGGameState* GS = W->GetGameState<AMLGGameState>();
	if (GS && GS->Phase == EMLGPhase::Planning)
	{
		GS->ToggleKit(3);
		GS->ToggleKit(4);
		GS->ToggleKit(5);
		Chk(TEXT("kit fills weight budget and refuses an extra item"), GS->KitWeight() == GS->KitBudget && !GS->ToggleKit(1));
		PC->InputKey(FInputKeyParams(EKeys::Enter, IE_Pressed, 1.0));
		W->GetTimerManager().SetTimerForNextTick([PC, GS, Fail]()
		{
			PC->InputKey(FInputKeyParams(EKeys::Enter, IE_Released, 0.0));
			const bool bDeployed = GS->Phase == EMLGPhase::Repair;
			UE_LOG(LogTemp, Display, TEXT("MLG-UI %s: Enter deploys at the maximum kit weight"), bDeployed ? TEXT("PASS") : TEXT("FAIL"));
			UE_LOG(LogTemp, Display, TEXT("MLG-UI DONE failures=%d"), Fail + (bDeployed ? 0 : 1));
		});
	}
	else
	{
		UE_LOG(LogTemp, Display, TEXT("MLG-UI FAIL: planning phase required for Enter check"));
		UE_LOG(LogTemp, Display, TEXT("MLG-UI DONE failures=%d"), Fail + 1);
	}
}
static FAutoConsoleCommandWithWorld GMLGUiTestCmd(TEXT("mlg.uitest"), TEXT("Scripted menu/settings test"), FConsoleCommandWithWorldDelegate::CreateStatic(&RunUiTest));
#endif
