@echo off
rem ============================================================================================
rem  Job Search - ONE-CLICK SETUP for Windows 10 / 11            Built by Rahul Swargam
rem
rem  Double-click this file. It installs (or updates to the LATEST version) everything Job Search
rem  needs, then checks that it all works. Run it again any time to update everything.
rem
rem    setup-windows.bat               install / update everything (one click)
rem    setup-windows.bat /check        only show what is installed and what would change
rem    setup-windows.bat /yes          don't ask any questions
rem    setup-windows.bat /skip-system  only the Python packages (no winget installs)
rem
rem  Everything Job Search needs on Windows (all installed at their latest version):
rem    winget             Windows package manager (built into Windows 10 1809+ and 11)
rem    Python 3 (newest)  runs the tool; with pip, venv, Tkinter (the file and folder
rem                       windows) and the py launcher
rem    Python packages    rich            colours, tables, live progress
rem                       prompt_toolkit  arrow-key menus and checkboxes
rem                       pypdf           reads PDF resumes
rem                       certifi         up-to-date HTTPS certificates for the Apify API
rem                       PyMuPDF         better text from some PDF resumes (optional)
rem                       keyring         moves a key saved by an older version (optional)
rem    Git                downloads and updates this project
rem    Windows Terminal   full colours and clickable links
rem    Google Sans Code   the terminal font, also set in Windows Terminal (keeps a backup)
rem    Web browser        opens the job links page (Edge is built in; any browser works)
rem    Apify account      free at https://console.apify.com - the tool asks for its API key once
rem
rem  Plain batch only: no PowerShell. The fiddly parts (font, Terminal settings, PyPI versions,
rem  self-test) are done by jobsearch\setup_helper.py with the Python this file installs.
rem ============================================================================================
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
set "ROOT=%CD%"
set "REQUIRED=pip rich prompt_toolkit pypdf certifi"
set "OPTIONAL=PyMuPDF keyring"
set "PY_SWITCHES=Include_pip=1 Include_tcltk=1 Include_launcher=1 InstallLauncherAllUsers=0 Include_test=0"

rem ---- colours (ANSI; Windows 10 and 11 consoles support them)
for /f %%e in ('echo prompt $E^| cmd') do set "ESC=%%e"
set "G=%ESC%[92m"
set "Y=%ESC%[93m"
set "RD=%ESC%[91m"
set "CY=%ESC%[96m"
set "B=%ESC%[1m"
set "D=%ESC%[90m"
set "N=%ESC%[0m"
set "BG=%ESC%[44;97m"

rem ---- options
set "CHECK=0"
set "YES=0"
set "SKIP=0"
for %%a in (%*) do (
  for %%o in (/check -check --check) do if /i "%%~a"=="%%o" set "CHECK=1"
  for %%o in (/yes -yes --yes /y -y) do if /i "%%~a"=="%%o" set "YES=1"
  for %%o in (/skip-system -skip-system --skip-system) do if /i "%%~a"=="%%o" set "SKIP=1"
)

set "TMPD=%TEMP%\jobsearch-setup-%RANDOM%%RANDOM%"
mkdir "%TMPD%" >nul 2>&1
set "JS_SUMMARY=%TMPD%\summary.txt"
type nul > "%JS_SUMMARY%"
set "JS_CHECK=%CHECK%"
set "FAILED=0"
set "PY="
set "PYVER="
set "EXTRA="

echo.
echo   %CY%============================================================================%N%
echo      %B%%CY%J O B   S E A R C H   -   one-click setup for Windows%N%
echo      Installs or updates everything to the latest version, then checks it works
echo      %Y%Built by Rahul Swargam  -  https://rahulswargam.online/%N%
echo   %CY%============================================================================%N%
if "%CHECK%"=="1" call :warn "Check only: nothing will be installed or changed."
echo   %D%Folder: %ROOT%%N%

rem ============================================================================== 1. winget
call :step 1 "Windows package manager (winget)"
if "%SKIP%"=="1" (
  call :info "Skipped (/skip-system)."
) else (
  where winget >nul 2>&1
  if errorlevel 1 (
    call :bad "winget is missing. Install App Installer from the Microsoft Store, then run this file again."
    start "" "ms-windows-store://pdp/?productid=9NBLGGH4NNS1"
    goto :end
  )
  for /f "delims=" %%v in ('winget --version 2^>nul') do set "WGV=%%v"
  set "WGV=!WGV:v=!"
  call :ok "winget !WGV!"
  call :record "winget" "!WGV!" "present"
)

rem ============================================================================== 2. Python
call :step 2 "Python (newest version, with pip, Tkinter and the py launcher)"
if "%SKIP%"=="1" (
  call :newest_installed_python
  if defined PY call :ok "Using the newest Python already installed: !PY!"
) else (
  call :latest_python_minor
  if "!PYMINOR!"=="0" (
    call :bad "Couldn't find Python in winget."
    goto :end
  )
  set "EXTRA=--scope user --installer-type burn --custom "%PY_SWITCHES%""
  call :ensure "Python.Python.3.!PYMINOR!" "Python 3.!PYMINOR!"
  set "EXTRA="
  call :python_exe !PYMINOR!
  set "PY=!PYEXE!"
  if not defined PY if "%CHECK%"=="1" call :newest_installed_python
)
if defined PY (
  "!PY!" -c "import sys;print('.'.join(map(str,sys.version_info[:3])))" > "%TMPD%\pyver.txt" 2>nul
  set /p PYVER=<"%TMPD%\pyver.txt"
  "!PY!" -c "import tkinter" >nul 2>&1
  if errorlevel 1 (
    call :bad "Tkinter is missing from Python !PYVER!. Run this file again; if it persists, reinstall Python with tcl/tk ticked."
  ) else (
    call :ok "Tkinter - the file and folder windows - works with Python !PYVER!"
  )
  if "%SKIP%"=="1" call :record "Python" "!PYVER!" "ready"
) else (
  if "%CHECK%"=="1" (
    call :info "Tkinter is checked once Python is installed."
  ) else (
    call :bad "No Python found."
    goto :end
  )
)

rem ============================================================================== 3. Git, Terminal, font
call :step 3 "Git, Windows Terminal and the Google Sans Code font"
if "%SKIP%"=="1" (
  call :info "Skipped (/skip-system)."
) else (
  call :ensure "Git.Git" "Git"
  call :ensure "Microsoft.WindowsTerminal" "Windows Terminal"
  if defined PY (
    "!PY!" -m jobsearch.setup_helper font
    if "%CHECK%"=="0" (
      set "SETFONT=1"
      if "%YES%"=="0" (
        choice /c YN /n /m "  ? Use Google Sans Code as the Windows Terminal font? [Y/N] "
        if errorlevel 2 set "SETFONT=0"
      )
      if "!SETFONT!"=="1" "!PY!" -m jobsearch.setup_helper terminal-font
    )
  ) else (
    call :info "Google Sans Code would install after Python."
    call :record "Google Sans Code font" "-" "would install"
  )
)

rem ============================================================================== 4. packages in .venv
call :step 4 "Python packages (latest versions) in this project's .venv"
set "VPY=%ROOT%\.venv\Scripts\python.exe"
if "%CHECK%"=="1" (
  if exist "%VPY%" (
    "%VPY%" -m jobsearch.setup_helper packages %REQUIRED% --optional %OPTIONAL%
  ) else (
    call :info ".venv would be created and the latest packages installed."
    call :record "Python packages (.venv)" "-" "would install"
  )
) else (
  if exist "%VPY%" (
    "%VPY%" -c "import sys;print(sys.version_info[1])" > "%TMPD%\vminor.txt" 2>nul
    "!PY!" -c "import sys;print(sys.version_info[1])" > "%TMPD%\pminor.txt" 2>nul
    set /p VMINOR=<"%TMPD%\vminor.txt"
    set /p PMINOR=<"%TMPD%\pminor.txt"
    if not "!VMINOR!"=="!PMINOR!" (
      call :info "Rebuilding .venv for Python !PYVER! ..."
      rmdir /s /q "%ROOT%\.venv"
    )
  )
  if not exist "%VPY%" (
    call :info "Creating .venv with Python !PYVER! ..."
    "!PY!" -m venv "%ROOT%\.venv"
    if errorlevel 1 (
      call :bad "Could not create .venv"
      goto :end
    )
  )
  "%VPY%" -m pip install --upgrade --disable-pip-version-check --quiet pip
  call :info "Installing the latest rich, prompt_toolkit, pypdf, certifi ..."
  "%VPY%" -m pip install --upgrade --disable-pip-version-check --quiet %REQUIRED%
  if errorlevel 1 call :bad "Required Python packages failed to install - see above."
  for %%p in (%OPTIONAL%) do "%VPY%" -m pip install --upgrade --disable-pip-version-check --quiet %%p >nul 2>&1
  "%VPY%" -m jobsearch.setup_helper packages %REQUIRED% --optional %OPTIONAL%
  if errorlevel 1 set "FAILED=1"
)

rem ============================================================================== 5. check it works
call :step 5 "Checking that Job Search works"
if "%CHECK%"=="1" (
  call :info "Skipped in check mode."
) else (
  "%VPY%" -m jobsearch.setup_helper selftest
  if errorlevel 1 set "FAILED=1"
)
if defined PY (
  "!PY!" -m jobsearch.setup_helper browser
) else (
  call :record "Web browser (for the HTML page)" "default" "present"
)

rem ============================================================================== summary
echo.
echo   %B%%CY%Summary%N%
echo   %D%----------------------------------------------------------------------------%N%
for /f "usebackq tokens=1-3 delims=|" %%a in ("%JS_SUMMARY%") do call :row "%%a" "%%b" "%%c"
echo.
if "%FAILED%"=="1" (
  echo   %RD%Something needs attention - marked FAIL above. Fix it and run setup-windows.bat again.%N%
  goto :end
)
if "%CHECK%"=="1" (
  echo   %Y%Check finished. Run setup-windows.bat without /check to install or update.%N%
) else (
  echo   %G%All set. Start a search by double-clicking jobsearch.bat%N%
  echo   or in a terminal:  .venv\Scripts\python -m jobsearch
  echo   The first run asks for your Apify API key: get one free at https://console.apify.com
  echo   Close and reopen Windows Terminal to see the new font.
)

:end
echo.
echo   %Y%Built by Rahul Swargam  -  https://rahulswargam.online/%N%
rmdir /s /q "%TMPD%" >nul 2>&1
if "%YES%"=="0" (
  echo.
  pause
)
endlocal & exit /b %FAILED%

rem ============================================================================== helpers
:step
echo.
echo %BG% STEP %~1 OF 5 %N%   %B%%CY%%~2%N%
echo   %CY%----------------------------------------------------------------------------%N%
exit /b

:ok
echo   %G%[ OK ]%N% %~1
exit /b

:info
echo   %CY%[ .. ]%N% %~1
exit /b

:warn
echo   %Y%[WARN]%N% %~1
exit /b

:bad
echo   %RD%[FAIL]%N% %~1
set "FAILED=1"
exit /b

:record
>>"%JS_SUMMARY%" echo %~1^|%~2^|%~3
exit /b

:row
set "st=%~3"
set "c=%G%"
if not "!st:would=!"=="!st!" set "c=%Y%"
if not "!st:newest for=!"=="!st!" set "c=%Y%"
if not "!st:skipped=!"=="!st!" set "c=%Y%"
if not "!st:failed=!"=="!st!" set "c=%Y%"
if /i "!st:~0,6!"=="failed" set "c=%RD%"
set "t=%~1                                        "
set "v=%~2                    "
echo   !t:~0,32! !v:~0,15! !c!!st!%N%
exit /b

rem ---- winget: install or update a package to its newest version (EXTRA = extra winget arguments)
:ensure
set "E_ID=%~1"
set "E_NAME=%~2"
set "E_LATEST="
winget show --id %E_ID% --exact --source winget --accept-source-agreements > "%TMPD%\show.txt" 2>nul
for /f "usebackq tokens=1,*" %%a in (`findstr /b /c:"Version:" "%TMPD%\show.txt"`) do set "E_LATEST=%%b"
call :installed "%E_ID%"
set "E_BEFORE=!E_HAVE!"
if "%CHECK%"=="1" (
  if not defined E_HAVE (
    call :info "!E_NAME! is not installed; it would install !E_LATEST!"
    call :record "!E_NAME!" "!E_LATEST!" "would install"
  ) else if not "!E_HAVE!"=="!E_LATEST!" (
    call :info "!E_NAME! !E_HAVE! is installed; it would update to !E_LATEST!"
    call :record "!E_NAME!" "!E_HAVE!" "would update to !E_LATEST!"
  ) else (
    call :ok "!E_NAME! !E_HAVE! - latest"
    call :record "!E_NAME!" "!E_HAVE!" "latest"
  )
  exit /b
)
if defined E_HAVE if "!E_HAVE!"=="!E_LATEST!" (
  call :ok "!E_NAME! !E_HAVE! is already the latest"
  call :record "!E_NAME!" "!E_HAVE!" "latest"
  exit /b
)
for /l %%t in (1,1,2) do (
  if not "!E_HAVE!"=="!E_LATEST!" (
    if %%t==2 call :info "Trying !E_NAME! again - downloads sometimes time out ..."
    if not defined E_HAVE (
      call :info "Installing !E_NAME! !E_LATEST! ..."
      winget install --id %E_ID% --exact --source winget --silent --accept-package-agreements --accept-source-agreements --disable-interactivity !EXTRA!
    ) else (
      call :info "Updating !E_NAME! !E_HAVE! to !E_LATEST! ..."
      winget upgrade --id %E_ID% --exact --source winget --silent --accept-package-agreements --accept-source-agreements --disable-interactivity !EXTRA!
    )
    call :installed "%E_ID%"
  )
)
if defined E_HAVE if "!E_HAVE!"=="!E_LATEST!" (
  call :ok "!E_NAME! !E_HAVE!"
  if defined E_BEFORE (
    call :record "!E_NAME!" "!E_HAVE!" "updated from !E_BEFORE!"
  ) else (
    call :record "!E_NAME!" "!E_HAVE!" "installed"
  )
  exit /b
)
if defined E_HAVE (
  call :warn "!E_NAME! couldn't be updated to !E_LATEST! - it's still !E_HAVE! and works. Run setup again later."
  call :record "!E_NAME!" "!E_HAVE!" "update to !E_LATEST! failed"
  exit /b
)
call :bad "!E_NAME! could not be installed"
call :record "!E_NAME!" "-" "failed"
exit /b

rem ---- the installed version of a winget package (E_HAVE), or nothing
:installed
set "E_HAVE="
winget list --id %~1 --exact --accept-source-agreements > "%TMPD%\list.txt" 2>nul
for /f "usebackq delims=" %%L in (`findstr /i /c:"%~1" "%TMPD%\list.txt"`) do (
  set "NEXTV="
  for %%W in (%%L) do (
    if defined NEXTV if not defined E_HAVE set "E_HAVE=%%W"
    if /i "%%W"=="%~1" set "NEXTV=1"
  )
)
exit /b

rem ---- the newest Python 3.x offered by winget (PYMINOR)
:latest_python_minor
set "PYMINOR=0"
winget search --id Python.Python.3 --source winget --accept-source-agreements > "%TMPD%\search.txt" 2>nul
for /f "usebackq delims=" %%L in (`findstr /r /c:"Python\.Python\.3\.[0-9]" "%TMPD%\search.txt"`) do (
  for %%W in (%%L) do (
    set "w=%%W"
    if /i "!w:~0,16!"=="Python.Python.3." (
      set "m=!w:~16!"
      set /a "mn=m" 2>nul
      if !mn! GTR !PYMINOR! set "PYMINOR=!mn!"
    )
  )
)
exit /b

rem ---- where Python 3.<minor> is installed (PYEXE), from the registry
:python_exe
set "PYEXE="
for %%H in (HKCU HKLM) do if not defined PYEXE (
  for /f "tokens=2,*" %%a in ('reg query "%%H\Software\Python\PythonCore\3.%~1\InstallPath" /v ExecutablePath 2^>nul ^| findstr /i "ExecutablePath"') do (
    if exist "%%b" set "PYEXE=%%b"
  )
)
if not defined PYEXE if exist "%LOCALAPPDATA%\Programs\Python\Python3%~1\python.exe" set "PYEXE=%LOCALAPPDATA%\Programs\Python\Python3%~1\python.exe"
exit /b

rem ---- the newest Python already installed (PY), for /skip-system and /check
:newest_installed_python
set "PY="
for /l %%m in (30,-1,10) do if not defined PY (
  call :python_exe %%m
  if defined PYEXE set "PY=!PYEXE!"
)
exit /b
