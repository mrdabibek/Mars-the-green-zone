#pragma once

#include "CoreMinimal.h"

namespace MLGPrologue
{
	inline constexpr float Touchdown = 6.4f;
	inline constexpr float OrbitalCut = 11.0f;
	inline constexpr float FirstFissures = 16.5f;
	inline constexpr float Rupture = 24.0f;
	inline constexpr float SurfaceCut = 30.8f;
	inline constexpr float Title = 33.2f;
	inline constexpr float Duration = 38.0f;
	inline constexpr float LanderPadScale = 3.2f;
	inline constexpr float ThrusterLightOffsetZ = -65.f;

	struct FRadioLine
	{
		float In;
		float Out;
		const TCHAR* Speaker;
		const TCHAR* Subtitle;
	};

	inline constexpr FRadioLine Radio[] = {
		{ .8f,  5.6f, TEXT("LANDER COMPUTER"), TEXT("Retro-burn nominal. Heatshield holding over Jezero crater rim.") },
		{ 6.8f, 10.6f, TEXT("ASTER ONE"), TEXT("Touchdown confirmed. Hull dust settling -- patching Earth relay now.") },
		{ 11.4f, 16.0f, TEXT("EARTH CONTROL"), TEXT("Aster One, telemetry locked. Look closely at the Pacific seismic belt.") },
		{ 16.8f, 21.0f, TEXT("EARTH CONTROL"), TEXT("Mantle harmonics are spiking past threshold. Our core cannot hold.") },
		{ 21.3f, 23.8f, TEXT("EARTH CONTROL"), TEXT("There are no rescue windows left. Guard the cryo-seed vault.") },
		{ 24.3f, 28.2f, TEXT("EARTH CONTROL"), TEXT("Make Mars bloom. Make something grow--") },
		{ 28.5f, 30.6f, TEXT("RELAY"), TEXT("[CARRIER LOST // DEEP-SPACE TELEMETRY SEVERED]") },
		{ 31.2f, 35.8f, TEXT("ASTER ONE"), TEXT("Earth? ... Earth, come in. You're the last green left, Aster.") },
	};
}
