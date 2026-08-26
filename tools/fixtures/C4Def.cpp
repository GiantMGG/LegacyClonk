// Synthetic fixture for harvest tests.
void C4DefCore::CompileFunc(StdCompiler *pComp)
{
	pComp->Value(mkNamingAdapt(Timer,                "Timer",      35));
	pComp->Value(mkNamingAdapt(toC4CStr(STimerCall), "TimerCall",  ""));
	pComp->Value(mkNamingAdapt(Mass,                 "Mass",       0));
}
