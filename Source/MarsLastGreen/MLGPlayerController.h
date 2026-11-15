#pragma once
#include "CoreMinimal.h"
#include "GameFramework/PlayerController.h"
#include "MLGPlayerController.generated.h"

UENUM()
enum class EMLGMenu : uint8 { None, Title, Pause, Settings, Controls, Codex };

struct FMLGMenuItem { FName Id; FString Label; };
struct FMLGCodexPage { const TCHAR* Title; TArray<FString> Lines; };

// Keyboard-driven menus (Up/Down/Left/Right/Enter/Esc), drawn by AMLGHUD. They work while the game is paused.
UCLASS()
class MARSLASTGREEN_API AMLGPlayerController : public APlayerController
{
	GENERATED_BODY()
public:
	EMLGMenu Menu = EMLGMenu::None;
	int32 Sel = 0, CodexPage = 0;
	bool bCapturing = false;      // waiting for a key to bind
	FString Notice;

	void OpenMenu(EMLGMenu M);
	void CloseMenu();
	void TogglePause();
	void MenuUp();
	void MenuDown();
	void MenuLeft() { Adjust(-1); }
	void MenuRight() { Adjust(+1); }
	void MenuAccept();
	void MenuBack();
	TArray<FMLGMenuItem> Items() const;
	FString MenuTitle() const;
	static const TArray<FMLGCodexPage>& Codex();
	virtual bool InputKey(const FInputKeyParams& Params) override;   // captures the next key while rebinding

protected:
	virtual void BeginPlay() override;
	virtual void SetupInputComponent() override;
	void Adjust(int32 Dir);
	EMLGMenu Parent = EMLGMenu::None;
	void Push(EMLGMenu M) { Parent = Menu; Menu = M; Sel = 0; Notice.Empty(); }
};
