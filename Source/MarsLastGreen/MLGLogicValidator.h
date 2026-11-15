#pragma once
#include "CoreMinimal.h"
class UWorld;

// Pure predicates are shared by the live audit and automation tests.
namespace MLGLogicValidator
{
	MARSLASTGREEN_API bool ValidResource(float Value);
	MARSLASTGREEN_API bool ValidLocation(const FVector& Location);
	MARSLASTGREEN_API bool NeedsFloorRecovery(const FVector& Location);
	MARSLASTGREEN_API bool ValidateUIRect(float X, float Y, float Width, float Height, float ClipX, float ClipY);
	MARSLASTGREEN_API bool IsStuckCandidate(float Speed, float Distance, float Displacement, float Seconds);
	MARSLASTGREEN_API bool IsAmmoSoftlock(int32 Magazine, int32 Reserve, int32 Aliens, float Seconds);
	MARSLASTGREEN_API int32 Audit(UWorld* World, bool bLog);
	MARSLASTGREEN_API void Tick(UWorld* World, float DeltaSeconds, float& OutSoftlockSeconds);
}
