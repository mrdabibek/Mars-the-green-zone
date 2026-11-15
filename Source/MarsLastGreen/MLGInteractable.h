#pragma once
#include "CoreMinimal.h"
#include "UObject/Interface.h"
#include "MLGInteractable.generated.h"

class AMLGCharacter;

UINTERFACE(MinimalAPI)
class UMLGInteractable : public UInterface { GENERATED_BODY() };

// Native-only interface. The character owns hold timing and interruption; the actor only answers what/how long/whether.
class MARSLASTGREEN_API IMLGInteractable
{
	GENERATED_BODY()
public:
	virtual FText GetPrompt(const AMLGCharacter* Who) const = 0;                  // always shown while focused (status or action)
	virtual float GetHoldSeconds() const { return 0.f; }
	virtual bool CanInteract(const AMLGCharacter* Who) const { return true; }     // false = prompt is informational only
	virtual void Interact(AMLGCharacter* Who) = 0;
};
