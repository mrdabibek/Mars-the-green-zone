using UnrealBuildTool;
public class MarsLastGreenTarget : TargetRules
{
	public MarsLastGreenTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Game;
		DefaultBuildSettings = BuildSettingsVersion.V2;
		IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_2;
		ExtraModuleNames.Add("MarsLastGreen");
	}
}
