#strict 2

protected func Initialize()
{
	// Create the win-condition goal object at the map centre.
	CreateObject(GOAL, 50, 20, NO_OWNER);
	Log("MyFirstScenario online!");
	return true;
}

protected func InitializePlayer(int plr, int x, int y, object base, int team)
{
	// Equip the player's first Clonk with a flint (a basic item from Objects.c4d).
	var clonk = GetHiRank(plr);
	if (clonk) clonk->CreateContents(FLNT);
	return true;
}
