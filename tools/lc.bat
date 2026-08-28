@echo off
rem LegacyClonk launcher shim for Windows.
rem Finds Python and delegates to the lc script.
setlocal
set "LC_DIR=%~dp0"
rem Prefer py launcher (Python 3), then python, then python3
where py >nul 2>&1
if %errorlevel%==0 (
    py "%LC_DIR%lc" %*
    goto :done
)
where python >nul 2>&1
if %errorlevel%==0 (
    python "%LC_DIR%lc" %*
    goto :done
)
echo Error: Python not found on PATH. Install Python 3 or add it to PATH. 1>&2
exit /b 1
:done
exit /b %errorlevel%
