#strict 2

func Initialize()
{
    // Script-visible flag so the smoke test can assert this callback fired.
    LocalN("g_initialized") = true;
    Message("Glow Stone online!", this);
    return true;
}
