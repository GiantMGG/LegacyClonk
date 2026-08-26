// Synthetic fixture for harvest tests.

static bool FnExplode(C4AulContext *cthr, C4ValueInt iLevel, C4Object *pObj, C4ID idEffect, C4String *szEffect)
{
	return true;
}

static bool FnMessage(C4AulContext *cthr, C4String *szMessage, C4Object *pObj)
{
	return true;
}

void InitFunctionMap(C4AulScriptEngine *pEngine)
{
	AddFunc(pEngine, "Explode", FnExplode);
	AddFunc(pEngine, "Message", FnMessage);
	AddFunc(pEngine, "Call", FnCall, false);
}

static constexpr C4ScriptConstDef C4ScriptConstMap[] =
{
	{ "C4D_All",         C4V_Int, C4D_All },
	{ "OCF_Construct",   C4V_Int, OCF_Construct },
	{ "COMD_None",       C4V_Int, COMD_None },
};
