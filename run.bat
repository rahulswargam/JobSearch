@echo off
rem Double-click to search with config.json. Pass options too: run.bat --dry-run
cd /d "%~dp0"
python -m jobsearch --open %*
pause
