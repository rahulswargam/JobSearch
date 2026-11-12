@echo off
rem Windows: double-click to start a search. Options work too: run.bat --dry-run
rem Uses the .venv made by setup-windows.ps1; falls back to the Python on your PATH.
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m jobsearch %*
) else (
  echo Tip: right-click setup-windows.ps1 and choose "Run with PowerShell" to install everything Job Search needs.
  python -m jobsearch %*
)
pause
