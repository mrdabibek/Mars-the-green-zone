#include "MLGPressureZone.h"
#include "MLGGameState.h"

AMLGPressureZone::AMLGPressureZone()
{
	Box = CreateDefaultSubobject<UBoxComponent>("Box");
	RootComponent = Box;
	Box->SetCollisionProfileName("OverlapAllDynamic");
	Box->SetGenerateOverlapEvents(true);
	Box->SetBoxExtent(FVector(400, 400, 150));
}

bool AMLGPressureZone::IsPressurized() const
{
	const AMLGGameState* GS = GetWorld() ? GetWorld()->GetGameState<AMLGGameState>() : nullptr;
	if (!GS) return false;
	return Kind == EMLGZoneKind::Habitat ? GS->Sim.BaseOxygen >= 20.f : GS->IsOperational(EMLGDeviceType::GreenhouseSeal);
}

float AMLGPressureZone::GetZonePressureMbar() const
{
	const AMLGGameState* GS = GetWorld() ? GetWorld()->GetGameState<AMLGGameState>() : nullptr;
	if (IsPressurized()) return 1013.f;
	return GS ? GS->OutsidePressureMbar : 6.1f;
}

float AMLGPressureZone::GetZoneTempC() const
{
	const AMLGGameState* GS = GetWorld() ? GetWorld()->GetGameState<AMLGGameState>() : nullptr;
	if (!GS) return -63.f;
	if (IsPressurized()) return GS->Sim.HasPower() ? 21.f : 6.f;
	return GS->OutsideTempC;
}

float AMLGPressureZone::GetZoneGravityRatio() const
{
	return IsPressurized() ? 1.0f : 0.38f;
}
