#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "MLGInteractable.h"
#include "MLGLogTerminal.generated.h"

// Optional environmental log: reading it plays one line of dialogue. Never required for progress.
UCLASS()
class MARSLASTGREEN_API AMLGLogTerminal : public AActor, public IMLGInteractable
{
	GENERATED_BODY()
public:
	AMLGLogTerminal();
	UPROPERTY(EditAnywhere, BlueprintReadWrite) FString LogText;
	UPROPERTY(VisibleAnywhere) UStaticMeshComponent* Mesh;
	static const TCHAR* GetMeshPath() { return TEXT("/Game/Environment/SM_Log_Terminal"); }
	bool UsesImportedMesh() const { return bUsingCustomMesh; }
	virtual FText GetPrompt(const AMLGCharacter*) const override { return FText::FromString(TEXT("[E] read log")); }
	virtual void Interact(AMLGCharacter*) override;
protected:
	virtual void BeginPlay() override;
	bool bUsingCustomMesh = false;
};
