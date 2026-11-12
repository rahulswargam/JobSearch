@echo off
rem Windows: double-click to start a search. Options work too: run.bat --dry-run
cd /d "%~dp0"
python -m jobsearch %*
pause
