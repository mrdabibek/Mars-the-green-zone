#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Components/BoxComponent.h"
#include "MLGDevice.h"
#include "MLGPressureZone.generated.h"

UENUM(BlueprintType)
enum class EMLGZoneKind : uint8 { Habitat, Greenhouse };

// Invisible volume: the player refills suit oxygen inside it while it is pressurized.
UCLASS()
class MARSLASTGREEN_API AMLGPressureZone : public AActor
{
	GENERATED_BODY()
public:
	AMLGPressureZone();
	UPROPERTY(EditAnywhere, BlueprintReadWrite) EMLGZoneKind Kind = EMLGZoneKind::Habitat;
	UPROPERTY(VisibleAnywhere) UBoxComponent* Box;
	UFUNCTION(BlueprintPure) bool IsPressurized() const;
	UFUNCTION(BlueprintPure) float GetZonePressureMbar() const;
	UFUNCTION(BlueprintPure) float GetZoneTempC() const;
	UFUNCTION(BlueprintPure) float GetZoneGravityRatio() const;
};
