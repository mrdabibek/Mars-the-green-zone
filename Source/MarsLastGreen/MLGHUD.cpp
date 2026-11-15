#include "MLGHUD.h"
#include "MLGGameMode.h"
#include "MLGPrologue.h"
#include "MLGAlien.h"
#include "MLGCharacter.h"
#include "MLGDefenseNode.h"
#include "MLGDevice.h"
#include "MLGGameState.h"
#include "MLGLogicValidator.h"
#include "MLGPickup.h"
#include "MLGPlayerController.h"
#include "MLGSettings.h"
#include "MLGWeaponComponent.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "EngineUtils.h"

FString AMLGHUD::FormatKitSpeedPenalty(int32 Weight)
{
	if (Weight <= 0)
	{
		return TEXT("0% speed penalty (no speed penalty)");
	}
	const float Pct = 1.5f * Weight;
	if (Weight % 2 == 0)
	{
		return FString::Printf(TEXT("heavier kit = slower on foot: -%d%% speed"), FMath::RoundToInt(Pct));
	}
	return FString::Printf(TEXT("heavier kit = slower on foot: -%.1f%% speed"), Pct);
}

FString AMLGHUD::FormatPlanningWeightLine(int32 Weight, int32 Budget)
{
	return FString::Printf(TEXT("Weight budget: %d / %d   (%s)"), Weight, Budget, *FormatKitSpeedPenalty(Weight));
}

void AMLGHUD::LayoutCompassMarkers(float CX, float StripW, const TArray<float>& RawXIn, TArray<float>& OutClampedX, TArray<int32>& OutStaggerRow, float MinSepPx)
{
	const int32 N = RawXIn.Num();
	OutClampedX.SetNum(N);
	OutStaggerRow.Init(0, N);
	if (N == 0) return;

	const float HalfSpan = StripW * 0.44f;
	const float MinX = CX - HalfSpan;
	const float MaxX = CX + HalfSpan;

	TArray<float> ClampedRaw;
	ClampedRaw.SetNum(N);
	TArray<int32> Order;
	Order.Reserve(N);
	for (int32 i = 0; i < N; ++i)
	{
		ClampedRaw[i] = FMath::Clamp(RawXIn[i], MinX, MaxX);
		OutClampedX[i] = ClampedRaw[i];
		Order.Add(i);
	}

	Order.Sort([&](int32 A, int32 B)
	{
		if (FMath::IsNearlyEqual(ClampedRaw[A], ClampedRaw[B], 0.01f)) return A < B;
		return ClampedRaw[A] < ClampedRaw[B];
	});

	const float EffectiveSep = FMath::Min(MinSepPx, (MaxX - MinX) / FMath::Max(1, N));
	const float StaggerThreshold = FMath::Max(65.f, MinSepPx * 1.15f);
	for (int32 k = 1; k < N; ++k)
	{
		const int32 Prev = Order[k - 1];
		const int32 Curr = Order[k];
		if (FMath::Abs(ClampedRaw[Curr] - ClampedRaw[Prev]) < StaggerThreshold)
		{
			OutStaggerRow[Curr] = (OutStaggerRow[Prev] + 1) % 2;
		}
		if (OutClampedX[Curr] - OutClampedX[Prev] < EffectiveSep)
		{
			OutClampedX[Curr] = OutClampedX[Prev] + EffectiveSep;
		}
	}

	OutClampedX[Order[N - 1]] = FMath::Min(OutClampedX[Order[N - 1]], MaxX);
	for (int32 k = N - 2; k >= 0; --k)
	{
		const int32 Next = Order[k + 1];
		const int32 Curr = Order[k];
		if (OutClampedX[Next] - OutClampedX[Curr] < EffectiveSep)
		{
			OutClampedX[Curr] = OutClampedX[Next] - EffectiveSep;
		}
	}

	for (int32 i = 0; i < N; ++i)
	{
		OutClampedX[i] = FMath::Clamp(OutClampedX[i], MinX, MaxX);
	}
	for (int32 k = 1; k < N; ++k)
	{
		const int32 Prev = Order[k - 1];
		const int32 Curr = Order[k];
		if (FMath::Abs(OutClampedX[Curr] - OutClampedX[Prev]) < StaggerThreshold && OutStaggerRow[Curr] == OutStaggerRow[Prev])
		{
			OutStaggerRow[Curr] = (OutStaggerRow[Prev] + 1) % 2;
		}
	}
}

void AMLGHUD::ClampPanelRect(float& X, float& Y, float& W, float& H, float ClipX, float ClipY)
{
	if (ClipX <= 0.f || ClipY <= 0.f) return;
	W = FMath::Clamp(W, 0.f, ClipX);
	H = FMath::Clamp(H, 0.f, ClipY);
	X = FMath::Clamp(X, 0.f, FMath::Max(0.f, ClipX - W));
	Y = FMath::Clamp(Y, 0.f, FMath::Max(0.f, ClipY - H));
}

void AMLGHUD::DrawPanel(float X, float Y, float W, float H, FLinearColor BgCol, FLinearColor BorderCol, float AccentW)
{
	if (Canvas)
	{
		ClampPanelRect(X, Y, W, H, Canvas->ClipX, Canvas->ClipY);
		if (!MLGLogicValidator::ValidateUIRect(X, Y, W, H, Canvas->ClipX, Canvas->ClipY)) return;
	}
	DrawRect(BgCol, X, Y, W, H);
	if (AccentW > 0.f)
	{
		DrawRect(FLinearColor(BorderCol.R, BorderCol.G, BorderCol.B, FMath::Min(1.f, BorderCol.A + 0.25f)), X, Y, FMath::Min(AccentW, W), H);
	}
	DrawLine(X, Y, X + W, Y, BorderCol, 1.f);
	DrawLine(X, Y + H, X + W, Y + H, BorderCol, 1.f);
	DrawLine(X, Y, X, Y + H, BorderCol, 1.f);
	DrawLine(X + W, Y, X + W, Y + H, BorderCol, 1.f);
}

float AMLGHUD::MeasureHUDText(const FString& S, float Scale) const
{
	if (S.IsEmpty()) return 0.f;
	const float Sc = Scale * FMath::Clamp(UMLGSettings::Get()->UIScale, 1.f, 1.5f);
	float TW = 0.f, TH = 0.f;
	if (Canvas && GEngine && GEngine->GetMediumFont())
	{
		Canvas->TextSize(GEngine->GetMediumFont(), S, TW, TH, Sc, Sc);
	}
	// Conservative advance floor prevents proportional Slate font clipping when Canvas->TextSize under-reports wide glyphs
	return FMath::Max(TW * 1.08f, S.Len() * 7.5f * Sc);
}

TArray<FString> AMLGHUD::WrapHUDText(const FString& S, float MaxW, float Scale) const
{
	TArray<FString> Out;
	if (S.IsEmpty()) return Out;
	if (MaxW <= 40.f || MeasureHUDText(S, Scale) <= MaxW)
	{
		Out.Add(S);
		return Out;
	}
	TArray<FString> Words;
	S.ParseIntoArrayWS(Words);
	FString Cur;
	for (const FString& W : Words)
	{
		const FString Cand = Cur.IsEmpty() ? W : (Cur + TEXT(" ") + W);
		if (!Cur.IsEmpty() && MeasureHUDText(Cand, Scale) > MaxW)
		{
			Out.Add(Cur);
			Cur = W;
		}
		else
		{
			Cur = Cand;
		}
	}
	if (!Cur.IsEmpty()) Out.Add(Cur);
	if (Out.Num() == 0) Out.Add(S);
	return Out;
}

void AMLGHUD::Text(const FString& S, float X, float Y, FLinearColor C, float Scale)
{
	const float Sc = Scale * UMLGSettings::Get()->UIScale;
	DrawText(S, FLinearColor(0.f, 0.f, 0.f, 0.88f), X + 1.5f, Y + 1.5f, GEngine->GetMediumFont(), Sc);   // shadow: HUD text sat on bright scenes unreadable
	DrawText(S, C, X, Y, GEngine->GetMediumFont(), Sc);
}

void AMLGHUD::Bar(const TCHAR* Badge, const FString& Label, float Frac, FLinearColor Col, float X, float Y, float UIScale)
{
	Frac = FMath::Clamp(Frac, 0.f, 1.f);
	const bool bLow = Frac < 0.25f;
	const bool bBlink = bLow && FMath::Fmod(GetWorld()->GetTimeSeconds(), 0.8f) < 0.4f; // low-resource alert, not colour-only (label + blink)
	const float BarH = FMath::Max(16.f, 14.f * UIScale);
	const float BadgeW = 42.f * FMath::Lerp(1.f, UIScale, 0.35f);
	const FLinearColor ActiveCol = bBlink ? FLinearColor(1.f, 0.15f, 0.12f) : Col;

	// Status icon/badge pill
	DrawRect(FLinearColor(ActiveCol.R * 0.28f, ActiveCol.G * 0.28f, ActiveCol.B * 0.28f, 0.9f), X, Y, BadgeW, BarH);
	DrawLine(X, Y, X + BadgeW, Y, ActiveCol * 0.85f, 1.f);
	DrawLine(X, Y + BarH, X + BadgeW, Y + BarH, ActiveCol * 0.85f, 1.f);
	Text(Badge, X + 5.f, Y - 1.f, FLinearColor(0.95f, 0.98f, 1.f), 0.78f);

	// Bar track & fill
	const float TrackX = X + BadgeW + 4.f;
	const float TrackW = 164.f;
	DrawRect(FLinearColor(0.01f, 0.02f, 0.03f, 0.78f), TrackX, Y, TrackW, BarH);
	DrawRect(ActiveCol, TrackX + 2.f, Y + 2.f, (TrackW - 4.f) * Frac, BarH - 4.f);
	DrawLine(TrackX, Y, TrackX + TrackW, Y, FLinearColor(0.3f, 0.55f, 0.7f, 0.45f), 1.f);
	DrawLine(TrackX, Y + BarH, TrackX + TrackW, Y + BarH, FLinearColor(0.3f, 0.55f, 0.7f, 0.45f), 1.f);

	const FString BarVal = Label.IsEmpty()
		? FString::Printf(TEXT("%d%%%s"), FMath::RoundToInt(Frac * 100.f), bLow ? TEXT(" LOW") : TEXT(""))
		: FString::Printf(TEXT("%s %d%%%s"), *Label, FMath::RoundToInt(Frac * 100.f), bLow ? TEXT(" LOW") : TEXT(""));
	Text(BarVal, TrackX + TrackW + 8.f, Y - 1.f, bLow ? FLinearColor(1.f, 0.45f, 0.35f) : FLinearColor(0.92f, 0.96f, 1.f), 0.84f);
}

void AMLGHUD::DrawTelemetryPill(float X, float Y, float UIScale, const AMLGCharacter* C, const AMLGGameState* GS)
{
	if (!C || !GS) return;
	const bool bPressurized = GS->IsPlayerPressurized();
	const int32 Storm = GS->StormPct();
	const FString EnvTag = bPressurized ? TEXT("HAB") : TEXT("EVA");
	const FString StormTok = (!bPressurized && Storm > 5) ? FString::Printf(TEXT(" | DUST %d%%"), Storm) : TEXT("");
	const FString GeneTok = GS->GetCropGeneMask() != 0 ? FString::Printf(TEXT(" | G:%s"), *GS->GetCropGeneCode()) : TEXT("");
	const FString SabTok = GS->IsSabatierActive() ? TEXT(" | SAB") : TEXT("");
	const FString OcTok = (GS->IsGridOverclocked() || GS->IsTurretOverclocked()) ? TEXT(" | OC") : TEXT("");
	const FString Line = FString::Printf(TEXT("[%s] %.1fmb | %.0fC | %.2fG%s%s%s%s"),
		*EnvTag, GS->PressureMbar(), GS->TempC(), GS->GravityG(), *StormTok, *GeneTok, *SabTok, *OcTok);
	const float PillH = FMath::Max(20.f, 18.f * UIScale);
	const float PillW = FMath::Max(250.f, MeasureHUDText(Line, 0.78f) + 18.f);
	const FLinearColor BorderCol = (!bPressurized && Storm >= 55) ? FLinearColor(1.f, 0.48f, 0.14f, 0.82f)
		: bPressurized ? FLinearColor(0.3f, 0.92f, 0.65f, 0.65f) : FLinearColor(0.45f, 0.82f, 1.f, 0.65f);
	const FLinearColor TextCol = (!bPressurized && Storm >= 55) ? FLinearColor(1.f, 0.72f, 0.32f)
		: bPressurized ? FLinearColor(0.55f, 0.98f, 0.75f) : FLinearColor(0.75f, 0.92f, 1.f);
	DrawPanel(X, Y, PillW, PillH, FLinearColor(0.02f, 0.035f, 0.055f, 0.76f), BorderCol, 3.f);
	Text(Line, X + 8.f, Y + 2.f, TextCol, 0.78f);
}

void AMLGHUD::DrawCompassMarkers(float CX, float W, float UIScale, const AMLGCharacter* C, const AMLGGameState* GS)
{
	const float StripW = FMath::Min(W - 64.f, 620.f * FMath::Lerp(1.f, UIScale, 0.22f));
	const float StripH = FMath::Max(48.f, 36.f * UIScale + 12.f);
	const float TopY = 10.f;
	DrawPanel(CX - StripW * 0.5f, TopY, StripW, StripH, FLinearColor(0.02f, 0.04f, 0.06f, 0.76f), FLinearColor(0.25f, 0.65f, 0.85f, 0.55f), 0.f);
	DrawLine(CX, TopY + 2.f, CX, TopY + StripH - 2.f, FLinearColor(1.f, 1.f, 1.f, 0.35f), 1.5f);

	const FVector PlayerLoc = C->GetActorLocation();
	const float ViewYaw = C->GetControlRotation().Yaw;

	struct FMarker { FString Tag; FVector Loc; FLinearColor Col; bool bHighlight; };
	TArray<FMarker> Markers;

	// Water Line (nearest WaterTank device)
	FVector WaterLoc = FVector(-1400.f, 0.f, 50.f);
	float BestWaterD = 1e9f;
	bool bFoundWater = false;
	FVector CommsLoc = FVector(2500.f, 0.f, 60.f);
	bool bFoundComms = false;
	FVector BaseLoc = FVector(-860.f, 0.f, 60.f);
	bool bFoundBase = false;

	for (TActorIterator<AMLGDevice> It(GetWorld()); It; ++It)
	{
		if (It->Type == EMLGDeviceType::WaterTank)
		{
			const float D = FVector::Dist2D(PlayerLoc, It->GetActorLocation());
			if (!bFoundWater || D < BestWaterD) { BestWaterD = D; WaterLoc = It->GetActorLocation(); bFoundWater = true; }
		}
		else if (It->Type == EMLGDeviceType::Comms) { CommsLoc = It->GetActorLocation(); bFoundComms = true; }
		else if (It->Type == EMLGDeviceType::Transmitter) { BaseLoc = It->GetActorLocation(); bFoundBase = true; }
	}

	// Ice Field (nearest Ice pickup, or south ice field anchor)
	FVector IceLoc = FVector(380.f, -1540.f, 30.f);
	float BestIceD = 1e9f;
	bool bFoundIce = false;
	for (TActorIterator<AMLGPickup> It(GetWorld()); It; ++It)
	{
		if (It->Kind == EMLGPickupKind::Ice)
		{
			const float D = FVector::Dist2D(PlayerLoc, It->GetActorLocation());
			if (!bFoundIce || D < BestIceD) { BestIceD = D; IceLoc = It->GetActorLocation(); bFoundIce = true; }
		}
	}

	if (bFoundBase)
	{
		const bool bHi = GS->Phase == EMLGPhase::Repair || GS->Phase == EMLGPhase::FinalDefense || GS->Phase == EMLGPhase::Transmit;
		Markers.Add({ TEXT("BASE"), BaseLoc, FLinearColor(0.3f, 0.9f, 1.f), bHi });
	}
	if (bFoundWater)
	{
		const bool bHi = GS->Phase == EMLGPhase::Defend || GS->Phase == EMLGPhase::FinalDefense;
		Markers.Add({ TEXT("WATER"), WaterLoc, FLinearColor(0.25f, 0.65f, 1.f), bHi });
	}
	if (bFoundIce || GS->Phase == EMLGPhase::IceRun)
	{
		Markers.Add({ TEXT("ICE"), IceLoc, FLinearColor(0.6f, 0.95f, 1.f), GS->Phase == EMLGPhase::IceRun });
	}
	if (bFoundComms)
	{
		Markers.Add({ TEXT("COMMS"), CommsLoc, FLinearColor(1.f, 0.78f, 0.25f), GS->Phase == EMLGPhase::CommsRun });
	}

	const float HalfSpanDeg = 85.f;
	const float MaxOffset = StripW * 0.44f;
	TArray<float> RawXs;
	TArray<float> DistMs;
	RawXs.Reserve(Markers.Num());
	DistMs.Reserve(Markers.Num());
	for (const FMarker& Mk : Markers)
	{
		const FVector Delta = Mk.Loc - PlayerLoc;
		DistMs.Add(FMath::RoundToFloat(Delta.Size2D() / 100.f));
		const float DeltaYaw = FMath::FindDeltaAngleDegrees(ViewYaw, Delta.Rotation().Yaw);
		const float ClampedFrac = FMath::Clamp(DeltaYaw / HalfSpanDeg, -1.f, 1.f);
		RawXs.Add(CX + ClampedFrac * MaxOffset);
	}

	TArray<float> LayoutXs;
	TArray<int32> StaggerRows;
	LayoutCompassMarkers(CX, StripW, RawXs, LayoutXs, StaggerRows, 96.f * FMath::Lerp(1.f, UIScale, 0.35f));

	const float RowPitch = FMath::Max(16.f, 14.f * UIScale);
	const float StripLeft = CX - StripW * 0.48f;
	const float StripRight = CX + StripW * 0.48f;
	for (int32 i = 0; i < Markers.Num(); ++i)
	{
		const FMarker& Mk = Markers[i];
		const float MX = LayoutXs[i];
		const float PipX = FMath::Clamp(RawXs[i], CX - MaxOffset, CX + MaxOffset);
		const float LabelY = TopY + 7.f + StaggerRows[i] * RowPitch;
		const FLinearColor Col = Mk.bHighlight ? Mk.Col : (Mk.Col * 0.76f);
		const FString Label = FString::Printf(TEXT("%s %.0fm"), *Mk.Tag, DistMs[i]);
		const float LabelW = MeasureHUDText(Label, 0.70f);
		const float LabelX = FMath::Clamp(MX - LabelW * 0.5f, StripLeft, FMath::Max(StripLeft, StripRight - LabelW));
		DrawRect(Col, PipX - 3.f, TopY + 2.f, 6.f, 4.f);
		if (FMath::Abs(MX - PipX) > 4.f || StaggerRows[i] > 0)
		{
			DrawLine(PipX, TopY + 6.f, MX, LabelY + 3.f, Col * 0.55f, 1.f);
		}
		Text(Label, LabelX, LabelY, Col, 0.70f);
	}

	// Directional alien threat pips along the compass upper edge
	for (TActorIterator<AMLGAlien> It(GetWorld()); It; ++It)
	{
		if (!It->IsAlive()) continue;
		const FVector Delta = It->GetActorLocation() - PlayerLoc;
		const float DeltaYaw = FMath::FindDeltaAngleDegrees(ViewYaw, Delta.Rotation().Yaw);
		const float ClampedFrac = FMath::Clamp(DeltaYaw / HalfSpanDeg, -1.f, 1.f);
		const float PX = CX + ClampedFrac * MaxOffset;
		FLinearColor PCol = It->Kind == EMLGAlienKind::Breaker ? FLinearColor(0.85f, 0.25f, 1.f)
			: It->Kind == EMLGAlienKind::Gunner ? FLinearColor(0.25f, 0.6f, 1.f) : FLinearColor(1.f, 0.2f, 0.15f);
		if (It->IsTelegraphing()) PCol = FLinearColor(1.f, 0.9f, 0.12f);
		DrawRect(PCol, PX - 3.f, TopY - 3.f, 6.f, 6.f);
	}
}

void AMLGHUD::DrawThreatRadar(float W, float M, float UIScale, const AMLGCharacter* C, const AMLGGameState* GS)
{
	const float Size = 124.f * FMath::Lerp(1.f, UIScale, 0.2f);
	const float RX = W - M - Size;
	const float RY = 12.f;
	const float RadCX = RX + Size * 0.5f;
	const float RadCY = RY + Size * 0.5f;
	const float HalfR = Size * 0.44f;
	const float MaxRangeCm = 3200.f;

	DrawPanel(RX, RY, Size, Size, FLinearColor(0.02f, 0.03f, 0.05f, 0.75f), FLinearColor(0.25f, 0.65f, 0.85f, 0.55f), 0.f);
	DrawLine(RadCX - HalfR, RadCY, RadCX + HalfR, RadCY, FLinearColor(1.f, 1.f, 1.f, 0.14f), 1.f);
	DrawLine(RadCX, RadCY - HalfR, RadCX, RadCY + HalfR, FLinearColor(1.f, 1.f, 1.f, 0.14f), 1.f);

	// Player forward sight cone
	DrawLine(RadCX, RadCY, RadCX - HalfR * 0.42f, RadCY - HalfR * 0.72f, FLinearColor(0.4f, 0.9f, 1.f, 0.35f), 1.f);
	DrawLine(RadCX, RadCY, RadCX + HalfR * 0.42f, RadCY - HalfR * 0.72f, FLinearColor(0.4f, 0.9f, 1.f, 0.35f), 1.f);
	DrawRect(FLinearColor(0.85f, 0.98f, 1.f), RadCX - 2.5f, RadCY - 2.5f, 5.f, 5.f);

	const FVector PlayerLoc = C->GetActorLocation();
	const float ViewYaw = C->GetControlRotation().Yaw;
	int32 Threats = 0;
	for (TActorIterator<AMLGAlien> It(GetWorld()); It; ++It)
	{
		if (!It->IsAlive()) continue;
		++Threats;
		const FVector Delta = It->GetActorLocation() - PlayerLoc;
		const float Dist = FMath::Min(Delta.Size2D(), MaxRangeCm);
		const float RelYawRad = FMath::DegreesToRadians(FMath::FindDeltaAngleDegrees(ViewYaw, Delta.Rotation().Yaw));
		const float Norm = (Dist / MaxRangeCm) * HalfR;
		const float BX = RadCX + FMath::Sin(RelYawRad) * Norm;
		const float BY = RadCY - FMath::Cos(RelYawRad) * Norm;
		FLinearColor Col = It->Kind == EMLGAlienKind::Breaker ? FLinearColor(0.85f, 0.25f, 1.f)
			: It->Kind == EMLGAlienKind::Gunner ? FLinearColor(0.25f, 0.6f, 1.f) : FLinearColor(1.f, 0.22f, 0.15f);
		if (It->IsTelegraphing()) Col = FLinearColor(1.f, 0.92f, 0.15f);
		const float Pip = It->Kind == EMLGAlienKind::Breaker ? 7.f : 5.5f;
		DrawRect(Col, BX - Pip * 0.5f, BY - Pip * 0.5f, Pip, Pip);
	}

	const FString Header = Threats > 0 ? FString::Printf(TEXT("RDR:%d"), Threats) : TEXT("RDR:OK");
	DrawRect(FLinearColor(0.02f, 0.03f, 0.05f, 0.75f), RX, RY + Size + 2.f, Size, 18.f * FMath::Max(1.f, UIScale));
	Text(Header, RX + 6.f, RY + Size + 4.f, Threats > 0 ? FLinearColor(1.f, 0.4f, 0.25f) : FLinearColor(0.45f, 0.9f, 0.75f), 0.76f);
}

void AMLGHUD::DrawPrologue(float T)
{
	using namespace MLGPrologue;
	const float W = Canvas->ClipX, H = Canvas->ClipY;
	const float S = UMLGSettings::Get()->UIScale;
	const float Fit = FMath::Clamp(FMath::Min(W / 1170.f, H / 660.f), .58f, 1.38f);
	const float Top = 54.f * Fit;
	const float Bottom = FMath::Max(84.f * Fit, H * .12f);
	const float Margin = W * .057f;
	const FLinearColor Ice(.56f, .84f, .94f);
	const FLinearColor Amber(1.f, .65f, .38f);
	const bool bOrbital = T >= OrbitalCut && T < SurfaceCut;

	auto Center = [&](const FString& Label, float Y, FLinearColor Color, float Size)
	{
		float Width, Height;
		GetTextSize(Label, Width, Height, GEngine->GetMediumFont(), Size * Fit * S);
		const float WidthFit = FMath::Min(1.f, (W - 2.f*Margin) / FMath::Max(Width, 1.f));
		Text(Label, (W - Width * WidthFit) * .5f, Y, Color, Size * Fit * WidthFit);
	};

	const float Age = T - Rupture;
	if (Age >= 0.f && Age < .58f)
		DrawRect(FLinearColor(1.f, .68f, .41f, .54f * FMath::Exp(-Age*12.f)), 0, 0, W, H);

	DrawRect(FLinearColor(.004f, .006f, .010f), 0, 0, W, Top);
	DrawRect(FLinearColor(.004f, .006f, .010f), 0, H - Bottom, W, Bottom);
	DrawLine(Margin, Top - 1.f, W - Margin, Top - 1.f, FLinearColor(.19f, .29f, .34f, .62f));
	DrawLine(Margin, H - Bottom, W - Margin, H - Bottom, FLinearColor(.19f, .29f, .34f, .62f));

	const TCHAR* Header = T < OrbitalCut ? TEXT("ASTER ONE / MARS DESCENT") :
		bOrbital ? TEXT("EARTH RELAY / LAST RECEIVED IMAGE") : TEXT("ASTER OUTPOST / MARS");
	Text(Header, Margin, Top*.31f, Ice, .80f*Fit);
	if (bOrbital)
	{
		const TCHAR* Signal = Age >= 0.f ? TEXT("LINK LOST") :
			T >= FirstFissures ? TEXT("SIGNAL DEGRADING") : TEXT("SIGNAL LOCKED");
		const float MarkerW = 139.f * Fit * S;
		DrawRect(Age >= 0.f ? Amber : Ice, W - Margin - MarkerW, Top*.45f, 5.f*Fit, 5.f*Fit);
		Text(Signal, W - Margin - MarkerW + 13.f*Fit, Top*.31f, Age >= 0.f ? Amber : Ice, .68f*Fit);
	}
	else if (T < OrbitalCut)
	{
		const int32 Height = FMath::RoundToInt(12.8f * FMath::Square(1.f - FMath::SmoothStep(0.f, 1.f, FMath::Clamp(T/Touchdown, 0.f, 1.f))));
		const FString Status = Height > 0 ? FString::Printf(TEXT("RADAR ALT  %02d M"), Height) : TEXT("TOUCHDOWN");
		Text(Status, W - Margin - 137.f*Fit*S, Top*.31f, Height > 0 ? Ice : Amber, .72f*Fit);
	}

	for (const FRadioLine& Line : Radio)
	{
		if (T < Line.In || T >= Line.Out) continue;
		Center(Line.Speaker, H - Bottom + 8.f*Fit, Ice, .77f);
		Center(Line.Subtitle, H - Bottom + 28.f*Fit, FLinearColor::White, 1.10f);
		break;
	}

	if (T >= Title)
	{
		const float Reveal = FMath::SmoothStep(0.f, 1.f, FMath::Clamp((T-Title)/.75f, 0.f, 1.f));
		DrawRect(FLinearColor(.004f, .007f, .012f, .58f*Reveal), 0, Top, W, H - Top - Bottom);
		Center(TEXT("M A R S"), H*.362f, FLinearColor(.60f, .83f, .88f, Reveal), 1.19f);
		Center(TEXT("LAST GREEN"), H*.411f, FLinearColor(.94f, .98f, .99f, Reveal), 3.3f);
	}

	const FString Skip = TEXT("[SPACE] SKIP");
	float SkipW, SkipH;
	GetTextSize(Skip, SkipW, SkipH, GEngine->GetMediumFont(), .70f * Fit * S);
	Text(Skip, W - Margin - SkipW, H - 20.f * Fit * S, FLinearColor(.57f, .66f, .72f), .70f*Fit);

	const float Fade = FMath::Max(1.f - FMath::Clamp(T/.55f, 0.f, 1.f),
		FMath::Clamp((T-(Duration-.65f))/.65f, 0.f, 1.f));
	if (Fade > 0.f) DrawRect(FLinearColor(0, 0, 0, Fade), 0, 0, W, H);
}

void AMLGHUD::DrawHUD()
{
	Super::DrawHUD();
	const float S = FMath::Clamp(UMLGSettings::Get()->UIScale, 1.f, 1.5f);
	auto Step = [S](float Base) { return Base * FMath::Max(1.f, S); };

	if (const AMLGPlayerController* PC = Cast<AMLGPlayerController>(GetOwningPlayerController()); PC && PC->Menu != EMLGMenu::None)
	{
		const float MW = Canvas->ClipX, MH = Canvas->ClipY;
		DrawRect(FLinearColor(0.01f, 0.015f, 0.025f, PC->Menu == EMLGMenu::Title ? 0.98f : 0.90f), 0, 0, MW, MH);

		const float CardW = FMath::Min(MW - 48.f, 760.f * FMath::Lerp(1.f, S, 0.32f));
		const float CardH = FMath::Min(MH - 40.f, 620.f * FMath::Lerp(1.f, S, 0.20f));
		const float CardX = (MW - CardW) * 0.5f;
		const float CardY = FMath::Max(20.f, (MH - CardH) * 0.5f);
		DrawPanel(CardX, CardY, CardW, CardH, FLinearColor(0.02f, 0.035f, 0.055f, 0.92f), FLinearColor(0.25f, 0.72f, 0.95f, 0.7f), 5.f);

		const float MX = CardX + 26.f;
		const float InnerW = CardW - 52.f;
		const float HeaderH = FMath::Min(Step(48.f), CardH * 0.12f);
		const float FooterH = FMath::Min(Step(32.f), CardH * 0.09f);
		float MY = CardY + 14.f;
		DrawRect(FLinearColor(0.06f, 0.14f, 0.22f, 0.65f), CardX + 5.f, CardY + 2.f, CardW - 7.f, HeaderH);
		Text(PC->MenuTitle(), MX, MY, FLinearColor(1.f, 0.74f, 0.22f), FMath::Min(1.55f, 1.35f / FMath::Lerp(1.f, S, 0.25f)));
		MY += HeaderH + 6.f;

		if (PC->Menu == EMLGMenu::Codex)
		{
			const FMLGCodexPage& Pg = AMLGPlayerController::Codex()[PC->CodexPage];
			const float CodexHeadH = Step(28.f);
			DrawPanel(MX - 6.f, MY - 2.f, InnerW + 12.f, CodexHeadH, FLinearColor(0.04f, 0.08f, 0.12f, 0.8f), FLinearColor(0.3f, 0.8f, 1.f, 0.45f), 3.f);
			Text(FString::Printf(TEXT("%s   [%d/%d]   [A/D] PAGE"), Pg.Title, PC->CodexPage + 1, AMLGPlayerController::Codex().Num()), MX + 4.f, MY + 2.f, FLinearColor(0.45f, 0.92f, 1.f), 0.96f);
			MY += CodexHeadH + 8.f;
			const float CodexScale = FMath::Clamp(0.88f / FMath::Lerp(1.f, S, 0.35f), 0.68f, 0.92f);
			const float CodexStep = FMath::Max(16.f, 20.f * CodexScale * S);
			const float CodexMaxY = CardY + CardH - FooterH - Step(38.f);
			for (const FString& L : Pg.Lines)
			{
				for (const FString& WL : WrapHUDText(L, InnerW, CodexScale))
				{
					if (MY + CodexStep > CodexMaxY) break;
					Text(WL, MX, MY, FLinearColor(0.92f, 0.95f, 0.98f), CodexScale);
					MY += CodexStep;
				}
			}
			MY += 6.f;
		}

		const TArray<FMLGMenuItem> Its = PC->Items();
		const float NoticeReserve = PC->Notice.IsEmpty() ? 6.f : (Step(24.f) + 8.f);
		const float AvailListH = FMath::Max(28.f, (CardY + CardH - FooterH - NoticeReserve) - MY);
		const float RawStep = Step(26.f);
		const float RowStep = FMath::Min(RawStep, AvailListH / FMath::Max(1, Its.Num()));
		const float ItemScale = FMath::Clamp((RowStep * 0.86f) / (23.f * S), 0.66f, 1.0f);
		for (int32 I = 0; I < Its.Num(); ++I)
		{
			const bool bSel = (I == PC->Sel);
			if (bSel)
			{
				DrawPanel(MX - 8.f, MY - 1.f, InnerW + 16.f, FMath::Max(16.f, RowStep - 2.f), FLinearColor(0.08f, 0.28f, 0.22f, 0.72f), FLinearColor(0.3f, 0.95f, 0.55f, 0.85f), 4.f);
			}
			Text((bSel ? TEXT("> ") : TEXT("   ")) + Its[I].Label, MX, MY, bSel ? FLinearColor(0.4f, 1.f, 0.55f) : FLinearColor(0.9f, 0.94f, 0.98f), ItemScale);
			MY += RowStep;
		}
		if (!PC->Notice.IsEmpty())
		{
			Text(PC->Notice, MX, FMath::Min(MY + 4.f, CardY + CardH - FooterH - Step(22.f)), FLinearColor(0.55f, 0.92f, 1.f), 0.86f);
		}
		DrawRect(FLinearColor(0.01f, 0.02f, 0.03f, 0.85f), CardX + 5.f, CardY + CardH - FooterH - 2.f, CardW - 7.f, FooterH);
		Text(TEXT("[W/S] NAV   [A/D] SET   [ENTER] OK   [ESC] BACK"), MX, CardY + CardH - FooterH + 4.f, FLinearColor(0.68f, 0.78f, 0.86f), 0.82f);
		return;
	}

	if (const AMLGGameMode* GM = GetWorld()->GetAuthGameMode<AMLGGameMode>(); GM && GM->IsIntroActive())
	{
		DrawPrologue(GM->IntroTime);
		return;
	}
	const AMLGCharacter* C = Cast<AMLGCharacter>(GetOwningPawn());
	const AMLGGameState* GS = GetWorld()->GetGameState<AMLGGameState>();
	if (!C || !GS) return;
	const float W = Canvas->ClipX, H = Canvas->ClipY, M = 24.f;

	// Mission planning, win and lose screens (scaled cleanly for 150% HUD text size)
	if (GS->Phase == EMLGPhase::Planning)
	{
		DrawRect(FLinearColor(0.01f, 0.015f, 0.025f, 0.90f), 0, 0, W, H);
		const float CardW = FMath::Min(W - 48.f, 780.f * FMath::Lerp(1.f, S, 0.35f));
		const float CardH = FMath::Min(H - 40.f, 610.f * FMath::Lerp(1.f, S, 0.22f));
		const float CardX = (W - CardW) * 0.5f;
		const float CardY = FMath::Max(20.f, (H - CardH) * 0.5f);
		DrawPanel(CardX, CardY, CardW, CardH, FLinearColor(0.02f, 0.035f, 0.055f, 0.92f), FLinearColor(0.28f, 0.75f, 0.95f, 0.72f), 5.f);

		const float PX = CardX + 26.f;
		const float BarTotalW = CardW - 52.f;
		float PY = CardY + 14.f;
		DrawRect(FLinearColor(0.07f, 0.15f, 0.24f, 0.65f), CardX + 5.f, CardY + 2.f, CardW - 7.f, Step(40.f));
		Text(TEXT("DROP LOADOUT  //  KIT ALLOCATION"), PX, PY, FLinearColor(1.f, 0.74f, 0.22f), 1.30f);
		PY += Step(44.f);

		const int32 CurWeight = GS->KitWeight();
		const int32 MaxBudget = AMLGGameState::KitBudget;
		const FString WtLine = FormatPlanningWeightLine(CurWeight, MaxBudget);
		const float WtScale = MeasureHUDText(WtLine, 0.92f) > BarTotalW ? 0.78f : 0.92f;
		Text(WtLine, PX, PY, FLinearColor(0.92f, 0.96f, 1.f), WtScale);
		PY += Step(22.f);

		// Visual kit weight progress bar (8 segments)
		const float SegGap = 4.f;
		const float SegW = (BarTotalW - SegGap * (MaxBudget - 1)) / (float)MaxBudget;
		for (int32 Seg = 0; Seg < MaxBudget; ++Seg)
		{
			const float SX = PX + Seg * (SegW + SegGap);
			const bool bFilled = Seg < CurWeight;
			const FLinearColor SegCol = bFilled
				? (CurWeight >= MaxBudget ? FLinearColor(1.f, 0.65f, 0.18f) : FLinearColor(0.25f, 0.85f, 0.95f))
				: FLinearColor(0.08f, 0.12f, 0.16f, 0.85f);
			DrawRect(SegCol, SX, PY, SegW, 9.f);
		}
		PY += 15.f;

		// Framed cards for items [1]-[6]
		const float FooterReserve = Step(96.f) + GS->Messages.Num() * Step(18.f);
		const float AvailKitH = FMath::Max(120.f, (CardY + CardH - FooterReserve) - PY);
		const float ItemRowH = FMath::Min(Step(29.f), AvailKitH / FMath::Max(1, (int32)AMLGGameState::KitItems));
		const float ItemScale = FMath::Clamp((ItemRowH * 0.85f) / (24.f * S), 0.70f, 0.94f);
		for (int32 i = 0; i < AMLGGameState::KitItems; ++i)
		{
			const bool bPacked = GS->HasKit(i);
			const int32 ItemW = AMLGGameState::KitWeightOf(i);
			const FLinearColor Bg = bPacked ? FLinearColor(0.06f, 0.24f, 0.18f, 0.82f) : FLinearColor(0.03f, 0.05f, 0.08f, 0.75f);
			const FLinearColor Brd = bPacked ? FLinearColor(0.3f, 0.95f, 0.55f, 0.85f) : FLinearColor(0.2f, 0.38f, 0.5f, 0.45f);
			DrawPanel(PX, PY, BarTotalW, ItemRowH - 3.f, Bg, Brd, 4.f);
			Text(FString::Printf(TEXT("[%d]  %s   %s"), i + 1, bPacked ? TEXT("[PACKED]") : TEXT("[  --  ]"), AMLGGameState::KitName(i)),
				PX + 10.f, PY + 2.f, bPacked ? FLinearColor(0.45f, 1.f, 0.6f) : FLinearColor(0.88f, 0.92f, 0.96f), ItemScale);
			const FString WtTag = FString::Printf(TEXT("WT %d"), ItemW);
			Text(WtTag, PX + BarTotalW - MeasureHUDText(WtTag, ItemScale) - 10.f, PY + 2.f,
				bPacked ? FLinearColor(0.45f, 1.f, 0.6f) : FLinearColor(0.65f, 0.78f, 0.88f), ItemScale * 0.95f);
			PY += ItemRowH;
		}
		PY += 6.f;

		// Predicted telemetry card (wrapped cleanly inside CardW)
		const FString PredStr = FString::Printf(TEXT("DROP: SEEDS %d | PARTS %d | AMMO %d | PWR %d%% | H2O %dL | SCI %d"),
			3 + (GS->HasKit(0) ? 2 : 0), 2 + (GS->HasKit(1) ? 2 : 0), 96 + (GS->HasKit(2) ? 60 : 0),
			FMath::Min(100, 30 + (GS->HasKit(3) ? 30 : 0)), 60 + (GS->HasKit(4) ? 40 : 0), 100 + (GS->HasKit(5) ? 60 : 0));
		const TArray<FString> PredLines = WrapHUDText(PredStr, BarTotalW - 20.f, 0.84f);
		const float PredBoxH = FMath::Max(Step(26.f), PredLines.Num() * Step(18.f) + 8.f);
		DrawPanel(PX, PY, BarTotalW, PredBoxH, FLinearColor(0.03f, 0.08f, 0.12f, 0.82f), FLinearColor(0.3f, 0.75f, 0.95f, 0.5f), 3.f);
		for (int32 LIdx = 0; LIdx < PredLines.Num(); ++LIdx)
		{
			Text(PredLines[LIdx], PX + 10.f, PY + 4.f + LIdx * Step(18.f), FLinearColor(0.55f, 0.92f, 1.f), 0.84f);
		}
		PY += PredBoxH + 8.f;

		Text(TEXT("[1]-[6] TOGGLE KIT   |   [ENTER] DEPLOY"), PX, PY, FLinearColor(0.95f, 0.85f, 0.55f), 0.90f);
		PY += Step(22.f);
		for (int32 i = 0; i < GS->Messages.Num(); ++i)
		{
			Text(GS->Messages[i], PX, PY, FLinearColor(1.f, 0.4f, 0.35f), 0.84f);
			PY += Step(18.f);
		}
		return;
	}
	if (GS->Phase == EMLGPhase::Won || GS->Phase == EMLGPhase::Lost)
	{
		const bool bWon = GS->Phase == EMLGPhase::Won;
		DrawRect(FLinearColor(0.01f, 0.015f, 0.02f, 0.90f), 0, 0, W, H);
		const float CardW = FMath::Min(W - 48.f, 760.f * FMath::Lerp(1.f, S, 0.32f));
		const float CardH = FMath::Min(H - 48.f, 470.f * FMath::Lerp(1.f, S, 0.25f));
		const float CardX = (W - CardW) * 0.5f;
		const float CardY = FMath::Max(20.f, (H - CardH) * 0.5f);
		const float X = CardX + 26.f;
		const float InnerW = CardW - 52.f;
		float Y = CardY + 18.f;
		DrawPanel(CardX, CardY, CardW, CardH, FLinearColor(0.02f, 0.03f, 0.05f, 0.92f),
			bWon ? FLinearColor(0.3f, 0.95f, 0.55f, 0.75f) : FLinearColor(1.f, 0.25f, 0.2f, 0.75f), 5.f);
		Text(bWon ? TEXT("TRANSMISSION SENT") : TEXT("MISSION FAILED"), X, Y, bWon ? FLinearColor::Green : FLinearColor::Red, 1.60f); Y += Step(42.f);
		if (!bWon)
		{
			for (const FString& L : WrapHUDText(GS->LoseReason, InnerW, 0.92f)) { Text(L, X, Y, FLinearColor(1.f, 0.55f, 0.5f), 0.92f); Y += Step(22.f); }
			Y += 6.f;
		}
		else
		{
			for (const FString& L : WrapHUDText(TEXT("Telemetry & distress beacon uplinked. Unknown carrier reply detected."), InnerW, 0.88f)) { Text(L, X, Y, FLinearColor(0.6f, 0.9f, 1.f), 0.88f); Y += Step(22.f); }
			Y += 6.f;
		}
		Text(FString::Printf(TEXT("SEEDS SAVED: %d (%d RESERVE | %d GROWING)"), GS->Seeds + GS->CountLivingPlants(), GS->Seeds, GS->CountLivingPlants()), X, Y, FLinearColor::White, 0.90f); Y += Step(22.f);
		Text(FString::Printf(TEXT("H2O NET: %.0f L   |   TANK: %.0f L"), GS->Sim.WaterUsed, GS->Sim.Water), X, Y, FLinearColor::White, 0.90f); Y += Step(22.f);
		Text(FString::Printf(TEXT("REPAIRS: %d   |   HOSTILES: %d   |   LOGS: %d"), GS->Repairs, GS->Kills, GS->LogsRead), X, Y, FLinearColor::White, 0.90f); Y += Step(22.f);
		Text(FString::Printf(TEXT("UPLINK: %s   |   SCIENCE: %d   |   TIME: %d:%02d"), bWon ? TEXT("YES") : TEXT("NO"), GS->ScienceScore(), (int32)GS->Elapsed / 60, (int32)GS->Elapsed % 60), X, Y, FLinearColor::White, 0.90f); Y += Step(30.f);
		Text(bWon ? TEXT("[E] NEW MISSION") : TEXT("[E] LOAD CHECKPOINT"), X, FMath::Min(Y, CardY + CardH - Step(28.f)), FLinearColor(1.f, 0.85f, 0.35f), 0.98f);
		return;
	}

	const float CX = W * 0.5f, CY = H * 0.5f;
	const float Now = GetWorld()->GetTimeSeconds();

	// Pre-death swarm/devour HUD sequence: cracked EVA visor fractures, crimson claw slashes, suit breach banner
	if (C->bDyingSequence)
	{
		const float SeqAlpha = FMath::Clamp(C->DeathSeqTime / FMath::Max(0.1f, C->DeathSeqDuration), 0.f, 1.f);
		const float Pulse = 0.65f + 0.35f * FMath::Abs(FMath::Sin(C->DeathSeqTime * 22.f));
		DrawRect(FLinearColor(0.08f, 0.0f, 0.0f, 0.18f + 0.56f * SeqAlpha), 0.f, 0.f, W, H);
		const float EdgeT = 18.f + 26.f * SeqAlpha;
		const FLinearColor BleedCol(0.95f, 0.06f, 0.04f, 0.45f * Pulse + 0.30f * SeqAlpha);
		DrawRect(BleedCol, 0.f, 0.f, W, EdgeT);
		DrawRect(BleedCol, 0.f, H - EdgeT, W, EdgeT);
		DrawRect(BleedCol, 0.f, 0.f, EdgeT, H);
		DrawRect(BleedCol, W - EdgeT, 0.f, EdgeT, H);

		auto DrawVisorCrack = [&](float OX, float OY, float SpreadScale)
		{
			const FLinearColor GlassCol(0.86f, 0.94f, 1.0f, 0.72f * (0.4f + 0.6f * SeqAlpha));
			const FLinearColor ShadowCol(0.45f, 0.02f, 0.02f, 0.78f);
			static const float RayDirs[7][4] = {
				{ -0.82f, -0.57f, -1.25f, -0.78f },
				{  0.74f, -0.68f,  1.18f, -1.02f },
				{ -0.45f,  0.88f, -0.78f,  1.42f },
				{  0.90f,  0.42f,  1.48f,  0.65f },
				{  0.12f, -0.96f,  0.24f, -1.55f },
				{ -0.95f,  0.18f, -1.58f,  0.32f },
				{  0.40f,  0.86f,  0.62f,  1.48f }
			};
			const float BaseLen = FMath::Min(W, H) * 0.22f * SpreadScale;
			for (int32 r = 0; r < 7; ++r)
			{
				const float X1 = OX + RayDirs[r][0] * BaseLen * 0.55f;
				const float Y1 = OY + RayDirs[r][1] * BaseLen * 0.55f;
				const float X2 = OX + RayDirs[r][2] * BaseLen;
				const float Y2 = OY + RayDirs[r][3] * BaseLen;
				DrawLine(OX + 1.5f, OY + 1.5f, X1 + 1.5f, Y1 + 1.5f, ShadowCol, 3.0f);
				DrawLine(X1 + 1.5f, Y1 + 1.5f, X2 + 1.5f, Y2 + 1.5f, ShadowCol, 2.2f);
				DrawLine(OX, OY, X1, Y1, GlassCol, 1.8f);
				DrawLine(X1, Y1, X2, Y2, GlassCol, 1.1f);
			}
		};
		DrawVisorCrack(CX * 0.66f, CY * 0.44f, 0.85f + 0.35f * SeqAlpha);
		if (SeqAlpha > 0.22f)
		{
			DrawVisorCrack(CX * 1.28f, CY * 0.72f, 0.70f + 0.45f * SeqAlpha);
		}
		if (SeqAlpha > 0.10f)
		{
			const FLinearColor ClawCol(1.f, 0.08f, 0.05f, 0.78f * Pulse);
			for (int32 s = -1; s <= 1; ++s)
			{
				const float Off = s * 28.f;
				DrawLine(CX - 190.f + Off, CY - 140.f, CX + 170.f + Off, CY + 120.f, ClawCol, 4.5f);
			}
		}

		const FString BreachTitle = TEXT("[!] SUIT BREACH // KIA");
		const FString BreachSub = FString::Printf(TEXT("HP: 0  |  O2: %.0f%%  |  %s"),
			C->SuitOxygen, C->LastHitSourceTag.IsEmpty() ? TEXT("SWARM") : *C->LastHitSourceTag);
		const float BoxW = FMath::Clamp(FMath::Max(MeasureHUDText(BreachTitle, 1.12f), MeasureHUDText(BreachSub, 0.86f)) + 34.f, 280.f, W * 0.65f);
		const float BoxH = Step(24.f) + Step(20.f) + 16.f;
		float BX = CX - BoxW * 0.5f, BY = H * 0.74f, BW = BoxW, BH = BoxH;
		ClampPanelRect(BX, BY, BW, BH, W, H);
		DrawPanel(BX, BY, BW, BH, FLinearColor(0.14f, 0.01f, 0.01f, 0.88f), FLinearColor(1.f, 0.18f, 0.12f, 0.92f), 4.f);
		Text(BreachTitle, BX + 16.f, BY + 6.f, FLinearColor(1.f, 0.32f, 0.24f), 1.12f);
		Text(BreachSub, BX + 16.f, BY + 8.f + Step(24.f), FLinearColor(1.f, 0.76f, 0.68f), 0.86f);
		return;
	}

	// Subtle Mars EVA visor frost, dust storm border, and hypoxia breathing vignette (center kept clear)
	if (!GS->IsPlayerPressurized())
	{
		const float ColdAlpha = FMath::Clamp((-GS->TempC() - 35.f) / 45.f, 0.f, 1.f) * 0.11f;
		const float DustAlpha = FMath::Clamp(GS->GetDustStormIntensity(), 0.f, 1.f) * 0.14f;
		if (ColdAlpha > 0.01f)
		{
			const FLinearColor FrostCol(0.55f, 0.85f, 1.0f, ColdAlpha);
			DrawRect(FrostCol, 0.f, 0.f, W, 6.f);
			DrawRect(FrostCol, 0.f, H - 6.f, W, 6.f);
			DrawRect(FrostCol, 0.f, 0.f, 6.f, H);
			DrawRect(FrostCol, W - 6.f, 0.f, 6.f, H);
		}
		if (DustAlpha > 0.01f)
		{
			const FLinearColor DustCol(0.76f, 0.42f, 0.18f, DustAlpha);
			DrawRect(DustCol, 0.f, 0.f, W, 12.f);
			DrawRect(DustCol, 0.f, H - 12.f, W, 12.f);
		}
	}
	if (C->SuitOxygen < 28.f)
	{
		const float Pulse = 0.55f + 0.45f * FMath::Abs(FMath::Sin(Now * 5.2f));
		const float LowA = FMath::Clamp((28.f - C->SuitOxygen) / 28.f, 0.f, 1.f) * 0.20f * Pulse;
		const FLinearColor O2Col(0.95f, 0.18f, 0.14f, LowA);
		DrawRect(O2Col, 0.f, 0.f, 14.f, H);
		DrawRect(O2Col, W - 14.f, 0.f, 14.f, H);
	}

	// Damage vignette, directional edge flash, chevron & LastHitSourceTag alert
	const float DmgAge = Now - C->LastDamageTime;
	if (DmgAge >= 0.f && DmgAge < 1.1f)
	{
		const float Alpha = 1.f - DmgAge / 1.1f;
		if (DmgAge < 0.35f)
		{
			const float VigA = 0.28f * (1.f - DmgAge / 0.35f);
			DrawRect(FLinearColor(0.9f, 0.06f, 0.05f, VigA), 0, 0, W, 16.f);
			DrawRect(FLinearColor(0.9f, 0.06f, 0.05f, VigA), 0, H - 16.f, W, 16.f);
			DrawRect(FLinearColor(0.9f, 0.06f, 0.05f, VigA), 0, 0, 16.f, H);
			DrawRect(FLinearColor(0.9f, 0.06f, 0.05f, VigA), W - 16.f, 0, 16.f, H);
		}
		if (C->bHasDamageOrigin)
		{
			const FVector Dv = C->LastDamageOrigin - C->GetActorLocation();
			const float Rad = FMath::DegreesToRadians(FMath::FindDeltaAngleDegrees(C->GetControlRotation().Yaw, Dv.Rotation().Yaw));
			const float DirX = FMath::Sin(Rad), DirY = -FMath::Cos(Rad);
			const float PerpX = -DirY, PerpY = DirX;
			const FVector2D Tip(CX + DirX * 195.f, CY + DirY * 195.f);
			const FVector2D L(CX + DirX * 172.f + PerpX * 18.f, CY + DirY * 172.f + PerpY * 18.f);
			const FVector2D R(CX + DirX * 172.f - PerpX * 18.f, CY + DirY * 172.f - PerpY * 18.f);
			const FLinearColor DmgCol(1.f, 0.14f, 0.1f, Alpha);
			DrawLine(L.X, L.Y, Tip.X, Tip.Y, DmgCol, 4.f);
			DrawLine(R.X, R.Y, Tip.X, Tip.Y, DmgCol, 4.f);

			// Directional screen-edge flash bar
			const float EdgeA = 0.42f * Alpha;
			if (DirY < -0.35f) DrawRect(FLinearColor(1.f, 0.12f, 0.08f, EdgeA), CX - 220.f, 0.f, 440.f, 10.f);
			if (DirY > 0.35f)  DrawRect(FLinearColor(1.f, 0.12f, 0.08f, EdgeA), CX - 220.f, H - 10.f, 440.f, 10.f);
			if (DirX < -0.35f) DrawRect(FLinearColor(1.f, 0.12f, 0.08f, EdgeA), 0.f, CY - 160.f, 12.f, 320.f);
			if (DirX > 0.35f)  DrawRect(FLinearColor(1.f, 0.12f, 0.08f, EdgeA), W - 12.f, CY - 160.f, 12.f, 320.f);
		}
		if (!C->LastHitSourceTag.IsEmpty())
		{
			const FString HitTagStr = FString::Printf(TEXT("HIT // %s"), *C->LastHitSourceTag);
			const float TagW = FMath::Clamp(MeasureHUDText(HitTagStr, 0.84f) + 22.f, 190.f, W * 0.45f);
			DrawPanel(CX - TagW * 0.5f, CY + 82.f, TagW, Step(22.f),
				FLinearColor(0.22f, 0.02f, 0.02f, 0.78f * Alpha), FLinearColor(1.f, 0.25f, 0.18f, 0.85f * Alpha), 3.f);
			Text(HitTagStr, CX - TagW * 0.5f + 10.f, CY + 84.f,
				FLinearColor(1.f, 0.45f, 0.35f, Alpha), 0.84f);
		}
	}

	// Compass + distance markers + tactical threat radar
	DrawCompassMarkers(CX, W, S, C, GS);
	DrawThreatRadar(W, M, S, C, GS);

	// Objective + latest alert badge (top-left, compact letter codes instead of multi-line prose)
	const float CompassBottomY = 10.f + FMath::Max(48.f, 36.f * S + 12.f);
	float TopLeftY = FMath::Max(M + 40.f, CompassBottomY + 8.f);
	const TCHAR* PhaseCode = [&]() {
		switch (GS->Phase)
		{
		case EMLGPhase::Repair:       return TEXT("REP // [E] PWR+O2+AIR");
		case EMLGPhase::Plant:        return TEXT("PLT // [E] SEED");
		case EMLGPhase::Grow:         return TEXT("GRW // HOLD AIR+PWR");
		case EMLGPhase::IceRun:       return TEXT("ICE // [E] ICE+H2O");
		case EMLGPhase::Defend:       return TEXT("DEF // CLR WAVE");
		case EMLGPhase::CommsRun:     return TEXT("COM // [E] RELAY");
		case EMLGPhase::FinalDefense: return TEXT("DEF // FINAL");
		case EMLGPhase::Transmit:     return TEXT("TX  // [E] UPLINK");
		case EMLGPhase::Won:          return TEXT("OK  // TX");
		case EMLGPhase::Lost:         return TEXT("ERR // KIA");
		default:                      return TEXT("OPS");
		}
	}();
	const FString HeaderStr = FString::Printf(TEXT("[W%d/%d] %s"), GS->Wave, GS->WavesTotal, PhaseCode);
	const FString LastAlert = GS->Messages.Num() > 0 ? GS->Messages.Last() : TEXT("");
	const TArray<FString> AlertLines = LastAlert.IsEmpty() ? TArray<FString>() : WrapHUDText(LastAlert, FMath::Max(240.f, W * 0.28f - 20.f), 0.78f);
	float MaxObjTextW = MeasureHUDText(HeaderStr, 0.88f);
	for (const FString& L : AlertLines) MaxObjTextW = FMath::Max(MaxObjTextW, MeasureHUDText(L, 0.78f));
	const float ObjPanelW = FMath::Clamp(MaxObjTextW + 22.f, 250.f, W * 0.34f);
	const float ObjPanelH = Step(22.f) + AlertLines.Num() * Step(17.f) + 10.f;
	DrawPanel(M - 6.f, TopLeftY - 4.f, ObjPanelW, ObjPanelH, FLinearColor(0.02f, 0.035f, 0.055f, 0.74f), FLinearColor(0.25f, 0.68f, 0.9f, 0.5f), 4.f);
	Text(HeaderStr, M + 4.f, TopLeftY, FLinearColor(1.f, 0.74f, 0.22f), 0.88f);
	TopLeftY += Step(21.f);
	for (const FString& L : AlertLines)
	{
		Text(L, M + 4.f, TopLeftY, FLinearColor(0.75f, 0.86f, 0.94f), 0.78f);
		TopLeftY += Step(17.f);
	}

	// Resource bars + compact letter codes + EVA telemetry pill (bottom-left)
	const float RowH = FMath::Max(22.f, 18.f * S);
	const float SummaryH = Step(20.f);
	const FString DefStr = [&]() {
		int32 DefOnline = 0, DefBroken = 0;
		for (TActorIterator<AMLGDefenseNode> It(GetWorld()); It; ++It)
		{
			if (It->IsActive()) ++DefOnline;
			else if (It->DefenseState == EMLGDefenseState::Broken) ++DefBroken;
		}
		return DefBroken > 0 ? FString::Printf(TEXT(" | DF:%d(%d!)"), DefOnline, DefBroken)
			: (DefOnline > 0 ? FString::Printf(TEXT(" | DF:%d"), DefOnline) : TEXT(""));
	}();
	const FString SummaryLine = FString::Printf(TEXT("L:%.0f  I:%.0f  S:%d  P:%d%s"), GS->Sim.Water, GS->Sim.Ice, GS->Seeds, GS->Parts, *DefStr);
	const float VitalsH = 5.f * RowH + SummaryH + 16.f;
	const float BadgeTrackW = 42.f * FMath::Lerp(1.f, S, 0.35f) + 164.f + 16.f;
	const float RightBarTxtW = MeasureHUDText(TEXT("100% LOW"), 0.84f);
	const float VitalsW = FMath::Clamp(FMath::Max3(275.f, BadgeTrackW + RightBarTxtW + 14.f, MeasureHUDText(SummaryLine, 0.80f) + 20.f), 270.f, W * 0.40f);
	const float BY = H - M - VitalsH + 8.f;
	const float TelePillH = FMath::Max(20.f, 18.f * S);
	DrawTelemetryPill(M - 6.f, BY - 8.f - TelePillH - 6.f, S, C, GS);
	DrawPanel(M - 6.f, BY - 8.f, VitalsW, VitalsH, FLinearColor(0.02f, 0.035f, 0.055f, 0.74f), FLinearColor(0.25f, 0.65f, 0.85f, 0.5f), 4.f);
	Bar(TEXT("HP"),  TEXT(""), C->Health / 100.f,                         FLinearColor(0.85f, 0.22f, 0.22f), M + 4.f, BY, S);
	Bar(TEXT("O2"),  TEXT(""), C->SuitOxygen / 100.f,                     FLinearColor(0.30f, 0.75f, 1.00f), M + 4.f, BY + RowH, S);
	Bar(TEXT("AIR"), TEXT(""), GS->Sim.BaseOxygen / 100.f,                FLinearColor(0.35f, 0.92f, 0.88f), M + 4.f, BY + RowH * 2.f, S);
	Bar(TEXT("PWR"), TEXT(""), GS->Sim.Power / 100.f,                     FLinearColor(1.00f, 0.82f, 0.20f), M + 4.f, BY + RowH * 3.f, S);
	Bar(TEXT("H2O"), TEXT(""), GS->Sim.Water / FMLGResourceModel::MaxWater, FLinearColor(0.22f, 0.50f, 1.00f), M + 4.f, BY + RowH * 4.f, S);
	Text(SummaryLine, M + 4.f, BY + RowH * 5.f + 3.f, FLinearColor(0.82f, 0.92f, 0.98f), 0.80f);

	// Weapon & Reload feedback panel (bottom-right, compact keycap letters)
	const UMLGWeaponComponent* Wp = C->Weapon;
	const FString AmmoStr = Wp->bReloading
		? FString::Printf(TEXT("RLD %d%%"), FMath::RoundToInt(Wp->ReloadProgress() * 100.f))
		: FString::Printf(TEXT("%d / %d"), Wp->Mag, Wp->Reserve);
	const FString WpHints = TEXT("[M1] FIRE  [M2] ADS  [R] RLD  [F] LGT");
	const float CardW = FMath::Clamp(FMath::Max3(215.f, MeasureHUDText(AmmoStr, 1.48f) + 28.f, MeasureHUDText(WpHints, 0.74f) + 24.f), 215.f, W * 0.30f);
	const float CardH = Step(76.f) + 20.f;
	const float WX = W - M - CardW, WY = H - M - CardH;
	DrawPanel(WX, WY, CardW, CardH, FLinearColor(0.02f, 0.035f, 0.055f, 0.76f), FLinearColor(0.25f, 0.68f, 0.9f, 0.55f), 4.f);
	Text(TEXT("MK-IV"), WX + 12.f, WY + 6.f, FLinearColor(0.55f, 0.88f, 0.98f), 0.82f);
	Text(AmmoStr, WX + 12.f, WY + 6.f + Step(18.f),
		Wp->bReloading ? FLinearColor(1.f, 0.72f, 0.2f) : (Wp->Mag == 0 ? FLinearColor::Red : FLinearColor::White), 1.48f);
	if (Wp->bReloading)
	{
		const float BarW = CardW - 24.f;
		const float BarY = WY + CardH - 16.f;
		DrawRect(FLinearColor(0, 0, 0, 0.7f), WX + 12.f, BarY, BarW, 8.f);
		DrawRect(FLinearColor(1.f, 0.72f, 0.2f), WX + 13.f, BarY + 1.f, (BarW - 2.f) * FMath::Clamp(Wp->ReloadProgress(), 0.f, 1.f), 6.f);
	}
	else
	{
		Text(WpHints, WX + 12.f, WY + CardH - Step(19.f) - 2.f, FLinearColor(0.62f, 0.76f, 0.86f), 0.74f);
	}

	// Dialogue subtitle above bottom HUD (wrapped cleanly inside panel)
	if (!GS->Dialogue.IsEmpty())
	{
		const float DialW = FMath::Min(W - 80.f, 760.f * FMath::Lerp(1.f, S, 0.30f));
		const TArray<FString> DialLines = WrapHUDText(GS->Dialogue, DialW - 28.f, 0.88f);
		const float DialH = DialLines.Num() * Step(20.f) + 12.f;
		const float DialY = FMath::Min(BY - 14.f - TelePillH, WY) - DialH - 12.f;
		DrawPanel(CX - DialW * 0.5f, DialY, DialW, DialH, FLinearColor(0.01f, 0.02f, 0.04f, 0.82f), FLinearColor(0.35f, 0.8f, 1.f, 0.55f), 4.f);
		for (int32 LIdx = 0; LIdx < DialLines.Num(); ++LIdx)
		{
			Text(DialLines[LIdx], CX - DialW * 0.5f + 14.f, DialY + 5.f + LIdx * Step(20.f), FLinearColor(0.92f, 0.97f, 1.f), 0.88f);
		}
	}

	// Top-center Contacts + Incoming Attack Telegraph Banner + Compact Warnings
	float CenterTopY = CompassBottomY + 8.f;
	int32 Contacts = 0;
	const AMLGAlien* ThreatAlien = nullptr;
	for (TActorIterator<AMLGAlien> It(GetWorld()); It; ++It)
	{
		if (!It->IsAlive()) continue;
		++Contacts;
		if (It->IsThreateningPlayer(C))
		{
			if (!ThreatAlien || It->Kind == EMLGAlienKind::Breaker || It->Kind == EMLGAlienKind::Gunner)
			{
				ThreatAlien = *It;
			}
		}
	}
	if (Contacts > 0)
	{
		const FString ContactStr = FString::Printf(TEXT("TGT %d | W%d/%d"), Contacts, GS->Wave, GS->WavesTotal);
		const float CW = MeasureHUDText(ContactStr, 0.86f);
		Text(ContactStr, CX - CW * 0.5f, CenterTopY, FLinearColor(1.f, 0.35f, 0.28f), 0.86f);
		CenterTopY += Step(20.f);
	}
	if (ThreatAlien)
	{
		const FString WarnMsg = ThreatAlien->GetTelegraphWarningText();
		const float WarnW = FMath::Clamp(MeasureHUDText(WarnMsg, 0.96f) + 26.f, 260.f, W * 0.68f);
		const float WarnY = CY - 108.f - 10.f * S;
		const FLinearColor WarnCol = ThreatAlien->Kind == EMLGAlienKind::Breaker ? FLinearColor(1.f, 0.72f, 0.12f)
			: ThreatAlien->Kind == EMLGAlienKind::Gunner ? FLinearColor(1.f, 0.25f, 0.15f)
			: FLinearColor(1.f, 0.38f, 0.1f);
		DrawPanel(CX - WarnW * 0.5f, WarnY - 4.f, WarnW, Step(24.f) + 6.f, FLinearColor(0.18f, 0.02f, 0.01f, 0.82f), WarnCol, 4.f);
		Text(WarnMsg, CX - WarnW * 0.5f + 12.f, WarnY, WarnCol, 0.96f);
	}

	TArray<FString> Warn;
	if (C->SuitOxygen < 25.f) Warn.Add(TEXT("! O2 LOW // AIRLOCK"));
	if (GS->Sim.Power < 15.f) Warn.Add(TEXT("! PWR LOW"));
	if (GS->Sim.Water < 20.f) Warn.Add(TEXT("! H2O LOW"));
	if (GS->Sim.BaseOxygen < 25.f) Warn.Add(TEXT("! AIR LOW"));
	if (GS->Sim.Power <= 0.f) Warn.Add(TEXT("! NO PWR // STALL"));
	for (int32 i = 0; i < Warn.Num(); ++i)
	{
		const float WW = MeasureHUDText(Warn[i], 0.84f) + 20.f;
		DrawPanel(CX - WW * 0.5f, CenterTopY - 1.f, WW, Step(19.f), FLinearColor(0.20f, 0.02f, 0.02f, 0.74f), FLinearColor(1.f, 0.3f, 0.25f, 0.75f), 3.f);
		Text(Warn[i], CX - WW * 0.5f + 10.f, CenterTopY, FLinearColor(1.f, 0.42f, 0.35f), 0.84f);
		CenterTopY += Step(22.f);
	}

	// Dynamic crosshair (tightens during ADS, blooms briefly on shot)
	const float ShotBloom = FMath::Clamp(1.f - (Now - Wp->LastShotTime) / 0.14f, 0.f, 1.f) * 6.f;
	const float Gap = (Wp->bAiming ? 3.f : 6.f) + ShotBloom;
	const float Arm = Wp->bAiming ? 5.f : 7.f;
	DrawLine(CX - Gap - Arm, CY, CX - Gap, CY, FLinearColor::White, 1.5f);
	DrawLine(CX + Gap, CY, CX + Gap + Arm, CY, FLinearColor::White, 1.5f);
	DrawLine(CX, CY - Gap - Arm, CX, CY - Gap, FLinearColor::White, 1.5f);
	DrawLine(CX, CY + Gap, CX, CY + Gap + Arm, FLinearColor::White, 1.5f);

	// Crisp diagonal hitmarker cross + distinct crimson kill-confirm flash + gold crit callout
	const float HitAge = Now - Wp->LastHitTime;
	const float KillAge = Now - Wp->LastKillTime;
	const float CritAge = Now - Wp->LastCritTime;
	const bool bKillPulse = (KillAge >= 0.f && KillAge < 0.28f);
	const bool bCritPulse = (CritAge >= 0.f && CritAge < 0.24f);
	const bool bHitPulse = (HitAge >= 0.f && HitAge < 0.18f);
	if (bHitPulse || bCritPulse || bKillPulse)
	{
		const float Age = bKillPulse ? KillAge : (bCritPulse ? CritAge : HitAge);
		const float MaxAge = bKillPulse ? 0.28f : (bCritPulse ? 0.24f : 0.18f);
		const float A = 1.f - FMath::Clamp(Age / MaxAge, 0.f, 1.f);
		const FLinearColor HMCol = bKillPulse ? FLinearColor(1.f, 0.16f, 0.12f, A)
			: (bCritPulse ? FLinearColor(1.f, 0.88f, 0.12f, A) : FLinearColor(1.f, 0.95f, 0.85f, A));
		const float Inner = bKillPulse ? 6.f : 5.f;
		const float Outer = bKillPulse ? 19.f : (bCritPulse ? 16.f : 12.f);
		const float Thick = bKillPulse ? 3.0f : (bCritPulse ? 2.6f : 2.0f);
		DrawLine(CX - Outer, CY - Outer, CX - Inner, CY - Inner, HMCol, Thick);
		DrawLine(CX + Inner, CY - Inner, CX + Outer, CY - Outer, HMCol, Thick);
		DrawLine(CX - Outer, CY + Outer, CX - Inner, CY + Inner, HMCol, Thick);
		DrawLine(CX + Inner, CY + Inner, CX + Outer, CY + Outer, HMCol, Thick);
		if (bKillPulse || bCritPulse)
		{
			const float O2 = Outer + 6.f, I2 = Outer + 2.f;
			const FLinearColor Accent = bKillPulse ? FLinearColor(1.f, 0.35f, 0.15f, A) : FLinearColor(0.35f, 0.95f, 1.f, A);
			DrawLine(CX - O2, CY - O2, CX - I2, CY - I2, Accent, 2.2f);
			DrawLine(CX + I2, CY - I2, CX + O2, CY - O2, Accent, 2.2f);
			DrawLine(CX - O2, CY + O2, CX - I2, CY + I2, Accent, 2.2f);
			DrawLine(CX + I2, CY + I2, CX + O2, CY + O2, Accent, 2.2f);
		}
		if (bCritPulse)
		{
			Text(FString::Printf(TEXT("CRIT +%.0f"), Wp->LastCritDamage), CX + 22.f, CY - 26.f - CritAge * 55.f, FLinearColor(1.f, 0.9f, 0.18f, A), 0.92f);
		}
		if (bKillPulse)
		{
			const FString KillTag = bCritPulse ? TEXT("CRIT KILL") : TEXT("KILL");
			Text(KillTag, CX - MeasureHUDText(KillTag, 0.86f) * 0.5f, CY + 22.f + KillAge * 24.f, FLinearColor(1.f, 0.25f, 0.18f, A), 0.86f);
		}
	}

	// Interaction prompt & hold bar (measured width + wrapped if long)
	if (!C->FocusPrompt.IsEmpty())
	{
		const FString PromptStr = C->FocusPrompt.ToString();
		const TArray<FString> PromptLines = WrapHUDText(PromptStr, W * 0.55f, 0.90f);
		float PromptMaxW = 0.f;
		for (const FString& PL : PromptLines) PromptMaxW = FMath::Max(PromptMaxW, MeasureHUDText(PL, 0.90f));
		const float PromptW = FMath::Clamp(PromptMaxW + 24.f, 240.f, W * 0.62f);
		const float PromptH = PromptLines.Num() * Step(20.f) + 8.f;
		DrawPanel(CX - PromptW * 0.5f, CY + 38.f, PromptW, PromptH,
			FLinearColor(0.02f, 0.04f, 0.06f, 0.80f), FLinearColor(0.3f, 0.8f, 1.f, 0.55f), 3.f);
		for (int32 LIdx = 0; LIdx < PromptLines.Num(); ++LIdx)
		{
			Text(PromptLines[LIdx], CX - PromptW * 0.5f + 10.f, CY + 41.f + LIdx * Step(20.f), C->bFocusCanAct ? FLinearColor::White : FLinearColor(0.7f, 0.7f, 0.7f), 0.90f);
		}
		if (C->HoldFraction > 0.f)
		{
			const float BarY = CY + 42.f + PromptH;
			DrawRect(FLinearColor(0, 0, 0, 0.75f), CX - 102.f, BarY, 204.f, 12.f);
			DrawRect(FLinearColor(0.3f, 1.f, 0.4f), CX - 100.f, BarY + 2.f, 200.f * C->HoldFraction, 8.f);
		}
	}
}
