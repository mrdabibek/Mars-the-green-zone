#pragma once
#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "MLGHUD.generated.h"

// Canvas HUD with responsive 100/125/150% text scaling, compass objective markers, hitmarker cross, damage direction indicator,
// and weapon/reload feedback.
UCLASS()
class MARSLASTGREEN_API AMLGHUD : public AHUD
{
	GENERATED_BODY()
public:
	virtual void DrawHUD() override;

	static FString FormatKitSpeedPenalty(int32 Weight);
	static FString FormatPlanningWeightLine(int32 Weight, int32 Budget);
	static void LayoutCompassMarkers(float CX, float StripW, const TArray<float>& RawXIn, TArray<float>& OutClampedX, TArray<int32>& OutStaggerRow, float MinSepPx = 68.f);
	static void ClampPanelRect(float& X, float& Y, float& W, float& H, float ClipX, float ClipY);

private:
	void DrawPrologue(float Time);
	void DrawPanel(float X, float Y, float W, float H, FLinearColor BgCol, FLinearColor BorderCol, float AccentW = 4.f);
	float MeasureHUDText(const FString& S, float Scale) const;
	TArray<FString> WrapHUDText(const FString& S, float MaxW, float Scale) const;
	void Bar(const TCHAR* Badge, const FString& Label, float Frac, FLinearColor Col, float X, float Y, float UIScale);
	void Text(const FString& S, float X, float Y, FLinearColor C = FLinearColor::White, float Scale = 1.f);
	void DrawTelemetryPill(float X, float Y, float UIScale, const class AMLGCharacter* C, const class AMLGGameState* GS);
	void DrawCompassMarkers(float CX, float W, float UIScale, const class AMLGCharacter* C, const class AMLGGameState* GS);
	void DrawThreatRadar(float W, float M, float UIScale, const class AMLGCharacter* C, const class AMLGGameState* GS);
};
