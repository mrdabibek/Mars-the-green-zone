#include "MLGLogicValidator.h"
#include "MLGAlien.h"
#include "MLGCharacter.h"
#include "MLGGameState.h"
#include "MLGWeaponComponent.h"
#include "MLGPickup.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "EngineUtils.h"
#include "HAL/IConsoleManager.h"
#include "Kismet/GameplayStatics.h"
#include "NavigationSystem.h"

bool MLGLogicValidator::ValidResource(float V) { return FMath::IsFinite(V) && V >= 0.f; }
bool MLGLogicValidator::ValidLocation(const FVector& V) { return !V.ContainsNaN(); }
bool MLGLogicValidator::NeedsFloorRecovery(const FVector& V) { return ValidLocation(V) && V.Z < -60.f; }
bool MLGLogicValidator::ValidateUIRect(float X, float Y, float Width, float Height, float ClipX, float ClipY)
{
 return FMath::IsFinite(X) && FMath::IsFinite(Y) && FMath::IsFinite(Width) && FMath::IsFinite(Height) && FMath::IsFinite(ClipX) && FMath::IsFinite(ClipY) && X >= 0 && Y >= 0 && Width >= 0 && Height >= 0 && ClipX > 0 && ClipY > 0 && X + Width <= ClipX && Y + Height <= ClipY;
}
bool MLGLogicValidator::IsStuckCandidate(float Speed, float Distance, float Displacement, float Seconds) { return Speed < 10.f && Distance > 350.f && Displacement < 30.f && Seconds > 3.5f; }
bool MLGLogicValidator::IsAmmoSoftlock(int32 M, int32 R, int32 A, float S) { return M <= 0 && R <= 0 && A > 0 && S > 10.f; }
int32 MLGLogicValidator::Audit(UWorld* W, bool bLog)
{
	int32 N = 0;
	auto Check = [&](bool b, const TCHAR* Name) { if (!b) { ++N; if (bLog) UE_LOG(LogTemp, Warning, TEXT("MLG-VALIDATE anomaly: %s"), Name); } };
	if (!W) { if (GEngine && GEngine->GameViewport && GEngine->GameViewport->Viewport) {
  const FIntPoint Size = GEngine->GameViewport->Viewport->GetSizeXY();
  if (Size.X > 0 && Size.Y > 0) {
   Check(ValidateUIRect(Size.X * .25f, 0, Size.X * .5f, Size.Y * .1f, Size.X, Size.Y), TEXT("compass bounds"));
   Check(ValidateUIRect(0, Size.Y * .88f, Size.X, Size.Y * .12f, Size.X, Size.Y), TEXT("bottom panel bounds"));
  }
 }
 if (bLog) UE_LOG(LogTemp, Display, TEXT("MLG-VALIDATE DONE anomalies=1 (no world)")); return 1; }
	AMLGGameState* G = W->GetGameState<AMLGGameState>();
	Check(G != nullptr, TEXT("game state missing"));
	if (G)
	{
		Check((uint8)G->Phase <= (uint8)EMLGPhase::Lost, TEXT("invalid phase"));
		Check(G->Wave >= 0 && G->Wave <= G->WavesTotal && G->WavesTotal >= 0, TEXT("invalid wave"));
		Check(ValidResource(G->Sim.Power) && ValidResource(G->Sim.Water) && ValidResource(G->Sim.BaseOxygen) && G->Seeds >= 0, TEXT("invalid resources"));
	}
	AMLGCharacter* C = Cast<AMLGCharacter>(UGameplayStatics::GetPlayerPawn(W, 0));
	Check(C != nullptr, TEXT("player missing"));
	if (C) Check(ValidResource(C->Health) && ValidResource(C->SuitOxygen) && ValidLocation(C->GetActorLocation()) && !NeedsFloorRecovery(C->GetActorLocation()), TEXT("player state/position"));
	for (TActorIterator<AMLGAlien> It(W); It; ++It) if (It->IsAlive()) Check(ValidLocation(It->GetActorLocation()) && !NeedsFloorRecovery(It->GetActorLocation()), TEXT("alien position"));
	if (GEngine && GEngine->GameViewport && GEngine->GameViewport->Viewport) {
  const FIntPoint Size = GEngine->GameViewport->Viewport->GetSizeXY();
  if (Size.X > 0 && Size.Y > 0) {
   Check(ValidateUIRect(Size.X * .25f, 0, Size.X * .5f, Size.Y * .1f, Size.X, Size.Y), TEXT("compass bounds"));
   Check(ValidateUIRect(0, Size.Y * .88f, Size.X, Size.Y * .12f, Size.X, Size.Y), TEXT("bottom panel bounds"));
  }
 }
 if (bLog) UE_LOG(LogTemp, Display, TEXT("MLG-VALIDATE DONE anomalies=%d"), N);
	return N;
}
void MLGLogicValidator::Tick(UWorld* W, float Dt, float& Seconds)
{
	if (!W) return;
	AMLGCharacter* C = Cast<AMLGCharacter>(UGameplayStatics::GetPlayerPawn(W, 0));
	AMLGGameState* G = W->GetGameState<AMLGGameState>();
	if (!C || !G) return;
	auto Recover = [W](AActor* A) {
		const FVector L = A->GetActorLocation();
		if (ValidLocation(L) && !NeedsFloorRecovery(L)) return;
		FNavLocation P;
		UNavigationSystemV1* Nav = FNavigationSystem::GetCurrent<UNavigationSystemV1>(W);
		if (Nav && Nav->ProjectPointToNavigation(ValidLocation(L) ? FVector(L.X, L.Y, 0.f) : FVector(-500.f, 0.f, 0.f), P, FVector(800.f, 800.f, 1000.f))) A->SetActorLocation(P.Location + FVector(0, 0, 110), false, nullptr, ETeleportType::TeleportPhysics);
	};
	Recover(C);
	struct FTrack { FVector Origin = FVector::ZeroVector; float Time = 0.f; float Cooldown = 0.f; };
 struct FWorldTrack { TMap<TWeakObjectPtr<AMLGAlien>, FTrack> Aliens; TWeakObjectPtr<AMLGPickup> Drop; int32 Recoveries = 0; };
 static TMap<TWeakObjectPtr<UWorld>, FWorldTrack> Worlds;
 for (auto It = Worlds.CreateIterator(); It; ++It) if (!It.Key().IsValid()) It.RemoveCurrent();
 FWorldTrack& State = Worlds.FindOrAdd(W);
 for (auto It = State.Aliens.CreateIterator(); It; ++It) if (!It.Key().IsValid()) It.RemoveCurrent();
 for (TActorIterator<AMLGAlien> It(W); It; ++It) if (It->IsAlive()) {
  AMLGAlien* A = *It; Recover(A);
  FTrack& Track = State.Aliens.FindOrAdd(A);
  Track.Cooldown = FMath::Max(0.f, Track.Cooldown - Dt);
  AActor* Target = A->GetCurrentTarget();
  const bool Trying = A->State == EMLGAlienState::Approach && IsValid(Target) && FVector::Dist2D(A->GetActorLocation(), Target->GetActorLocation()) > 350.f && A->GetVelocity().Size2D() < 10.f;
  if (!Trying || Track.Cooldown > 0.f) { Track.Time = 0.f; Track.Origin = A->GetActorLocation(); continue; }
  if (Track.Time == 0.f) Track.Origin = A->GetActorLocation();
  Track.Time += Dt;
  if (IsStuckCandidate(A->GetVelocity().Size2D(), FVector::Dist2D(A->GetActorLocation(), Target->GetActorLocation()), FVector::Dist2D(Track.Origin, A->GetActorLocation()), Track.Time)) {
   FNavLocation P; UNavigationSystemV1* Nav = FNavigationSystem::GetCurrent<UNavigationSystemV1>(W);
   const FVector Offset = (Target->GetActorLocation() - A->GetActorLocation()).GetSafeNormal2D() * 100.f;
   if (Nav && Nav->ProjectPointToNavigation(A->GetActorLocation() + Offset, P, FVector(350,350,500)) && A->SetActorLocation(P.Location + FVector(0,0,A->GetSimpleCollisionHalfHeight()+5.f), true, nullptr, ETeleportType::TeleportPhysics)) ++State.Recoveries;
   Track.Time = 0.f; Track.Cooldown = 8.f;
  } else if (Track.Time > 3.5f) { Track.Time = 0.f; }
 }
	if (C->Weapon && C->Weapon->Mag <= 0 && C->Weapon->Reserve <= 0 && G->CountAliens() > 0) Seconds += Dt; else Seconds = 0.f;
	if (C->Weapon && IsAmmoSoftlock(C->Weapon->Mag, C->Weapon->Reserve, G->CountAliens(), Seconds) && !State.Drop.IsValid()) {
  const FVector Location = C->GetActorLocation() + C->GetActorForwardVector() * 130.f;
  const FTransform Transform(FRotator::ZeroRotator, Location);
  AMLGPickup* Drop = W->SpawnActorDeferred<AMLGPickup>(AMLGPickup::StaticClass(), Transform, nullptr, nullptr, ESpawnActorCollisionHandlingMethod::AdjustIfPossibleButAlwaysSpawn);
  if (Drop) { Drop->Kind = EMLGPickupKind::Ammo; Drop->Amount = C->Weapon->MagSize; Drop->FinishSpawning(Transform); State.Drop = Drop; G->PushMessage(TEXT("EMERGENCY AMMO DROP NEARBY - PRESS E")); }
  else { C->Weapon->Reserve += C->Weapon->MagSize; G->PushMessage(TEXT("EMERGENCY AMMO SUPPLIED")); }
  Seconds = 0.f;
 }
}
static FAutoConsoleCommandWithWorld GMLGValidate(TEXT("mlg.validate"), TEXT("Audit live mission invariants"), FConsoleCommandWithWorldDelegate::CreateLambda([](UWorld* W) { MLGLogicValidator::Audit(W, true); }));
