/*-- NetSettingsSync.c4s -- host->client settings sync smoke fixture. --*/
/* Spec net-preround-settings-fix §5. Both peers run this script; the
   orchestrator compares the logged fingerprints across peers. */

#strict 2

static g_iStep;
static g_matEarth, g_matWater;

protected func Initialize()
{
	// resolve material indices (the LandscapeSeed step-0 pattern)
	g_matEarth = Material("Earth");
	g_matWater = Material("Water");
	if (g_matEarth < 0 || g_matWater < 0)
		FatalError("NetSettingsSync FAIL: Earth/Water missing from material map");
	g_iStep = 0;
	AddEffect("RunTest", 0, 1, 35);
	return true;
}

global func FxRunTestTimer(target, effect, time)
{
	if (g_iStep == 3)
	{
		// anti-vacuity: the classic generator must have produced earth
		if (GetMaterialCount(g_matEarth, true) <= 0)
			FatalError("NetSettingsSync FAIL: no Earth material in landscape");
		var checksum = LandscapeChecksum();
		Log(Format("LandscapeFP: %d", checksum));
		Log(Format("RulesObjects: %d", ObjectCount(C4Id("ENRG"))));
		Log(Format("GoalsObjects: %d", ObjectCount(C4Id("MELE"))));
		Log("NetSettingsSync PASS");
		GameOver();
		return -1;
	}
	++g_iStep;
	return 1;
}

global func LandscapeChecksum()
{
	// bounded deterministic checksum (the LandscapeSeed fingerprint
	// pattern): 8x4 GetMaterial probe grid + material counts, mod 1000003.
	var w = LandscapeWidth(), h = LandscapeHeight();
	var sum = 0;
	for (var gx = 0; gx < 8; gx++)
		for (var gy = 0; gy < 4; gy++)
			sum = (sum * 3 + GetMaterial((gx * 2 + 1) * w / 16, (gy * 2 + 1) * h / 8) + 1) % 1000003;
	sum = (sum * 3 + GetMaterialCount(g_matEarth, true)) % 1000003;
	sum = (sum * 3 + GetMaterialCount(g_matWater, true)) % 1000003;
	return sum;
}
