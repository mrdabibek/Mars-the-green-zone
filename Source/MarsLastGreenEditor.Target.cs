using UnrealBuildTool;
public class MarsLastGreenEditorTarget : TargetRules
{
	public MarsLastGreenEditorTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Editor;
		DefaultBuildSettings = BuildSettingsVersion.V2;
		IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_2;
		ExtraModuleNames.Add("MarsLastGreen");
	}
}
