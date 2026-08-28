/*-- NetSyncSmoke.c4s -- network desync smoke test fixture. --*/
/* See spec network-desync-ci-smoke.
   Runs deterministic weather activity for N ticks. No assertions,
   no GameOver, no Log("... PASS") -- the orchestrator handles
   pass/fail via exit codes and log inspection.
   Exercises C4ControlSyncCheck fields:
     Random3, RandomCount -- SetWind/SetTemperature consume the RNG.
     AllCrewPosX          -- crew spawned by the network lobby (MaxPlayer=4).
     PXSCount             -- natural precipitation from the [Weather] section.
     MassMoverIndex       -- any landscape material movement.
     ObjectCount, ObjectEnumerationIndex -- objects created below.
     SectShapeSum         -- the static landscape shape sum. */

#strict 2

static const C4ID ROCK = C4Id("ROCK");
static const C4ID FLNT = C4Id("FLNT");

static g_iStep;

protected func Initialize()
{
	g_iStep = 0;
	// Run one activity step every 35 frames (~1s at 35 fps).
	AddEffect("RunTest", this, 1, 35, this);
	return true;
}

func FxRunTestStart(target, effect, temp) { return 1; }

func FxRunTestTimer(object target, int effect, int timer)
{
	// Vary weather deterministically to exercise the RNG (Random3,
	// RandomCount) and the weather engine on both peers.
	SetWind((g_iStep * 13) % 200 - 100);
	SetTemperature(50 + (g_iStep * 7) % 50);

	// Spawn a few objects at fixed positions during the first 10 steps
	// to exercise ObjectCount, ObjectEnumerationIndex, and
	// MassMoverIndex (objects fall and generate mass movers).
	// CreateObject returns nil silently if the id is undefined; that is
	// fine -- the sync check still compares all fields.
	if (g_iStep < 10)
	{
		CreateObject(ROCK, 50 + g_iStep * 8, 20, NO_OWNER);
		CreateObject(FLNT, 60 + g_iStep * 8, 20, NO_OWNER);
	}

	++g_iStep;
	return 1;
}
