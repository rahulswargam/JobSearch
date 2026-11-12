<# :
@echo off
rem ============================================================================================
rem  Job Search - setup for Windows 10 / 11            Built by Rahul Swargam
rem  Double-click this file. It installs (or updates to the LATEST version) everything the tool
rem  needs, then checks that it all works. Safe to run again any time to update everything.
rem
rem    setup-windows.bat              install / update everything
rem    setup-windows.bat /check       only show what is installed and what would change
rem    setup-windows.bat /yes         don't ask questions (use the defaults)
rem    setup-windows.bat /skip-system only set up the Python packages (no winget installs)
rem ============================================================================================
setlocal
set "JS_ROOT=%~dp0"
set "JS_SELF=%~f0"
set "JS_ARGS=%*"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Invoke-Expression ([System.IO.File]::ReadAllText($env:JS_SELF))"
set "JS_CODE=%ERRORLEVEL%"
echo.
pause
exit /b %JS_CODE%
#>

# ==============================================================================================
#  Everything Job Search needs on Windows (all installed at their latest version):
#
#    winget                 Windows package manager (built into Windows 10 1809+ and 11)
#    Python 3 (newest)      runs the tool; includes pip, venv, Tkinter (the file and folder
#                           windows) and the "py" launcher
#    Python packages        rich            colours, tables, live progress
#                           prompt_toolkit  arrow-key menus and checkboxes
#                           pypdf           reads PDF resumes
#                           certifi         up-to-date HTTPS certificates for the Apify API
#                           PyMuPDF         better text from some PDF resumes   (optional)
#                           keyring         moves a key saved by an older version (optional)
#    Git                    downloads and updates this project
#    Windows Terminal       full colours and clickable links
#    Google Sans Code       the terminal font (optional: it can also set it in Windows Terminal)
#    Web browser            opens the job links page (Microsoft Edge is built in; any browser works)
#    Apify account          free at https://console.apify.com - the tool asks for its API key once
# ==============================================================================================
$ErrorActionPreference = 'Continue'   # native tools write progress to stderr; results are checked by exit code
$ProgressPreference = 'SilentlyContinue'
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch { }

$Root = $env:JS_ROOT.TrimEnd('\')
$Opts = " " + ("" + $env:JS_ARGS).ToLower() + " "
$CheckOnly  = $Opts -match '\s[/-]{1,2}check\s'
$AssumeYes  = $Opts -match '\s[/-]{1,2}(yes|y|quiet)\s'
$SkipSystem = $Opts -match '\s[/-]{1,2}skip-system\s'

$Required = @('pip', 'rich', 'prompt_toolkit', 'pypdf', 'certifi')
$Optional = @('PyMuPDF', 'keyring')
$Results  = New-Object System.Collections.ArrayList
$Failed   = $false

# ---------------------------------------------------------------------------------------------- output
function Line([string]$text = '', [string]$color = 'Gray') { Write-Host $text -ForegroundColor $color }
function Step([int]$n, [int]$total, [string]$title) {
    Write-Host ''
    Write-Host (" STEP {0} OF {1} " -f $n, $total) -BackgroundColor DarkBlue -ForegroundColor White -NoNewline
    Write-Host ("   " + $title) -ForegroundColor Cyan
    Write-Host ('  ' + ('-' * 76)) -ForegroundColor DarkBlue
}
function Ok([string]$t)   { Write-Host '  [ OK ] ' -ForegroundColor Green -NoNewline; Write-Host $t }
function Info([string]$t) { Write-Host '  [ .. ] ' -ForegroundColor Cyan -NoNewline; Write-Host $t }
function Warn([string]$t) { Write-Host '  [ !! ] ' -ForegroundColor Yellow -NoNewline; Write-Host $t }
function Bad([string]$t)  { Write-Host '  [FAIL] ' -ForegroundColor Red -NoNewline; Write-Host $t; $script:Failed = $true }
function Record([string]$tool, [string]$version, [string]$status) {
    [void]$Results.Add([pscustomobject]@{ Tool = $tool; Version = $version; Status = $status })
}
function Ask([string]$question, [bool]$default = $true) {
    if ($AssumeYes -or $CheckOnly) { return $default }
    $hint = if ($default) { 'Y/n' } else { 'y/N' }
    $a = Read-Host ("  ? {0} ({1})" -f $question, $hint)
    if ([string]::IsNullOrWhiteSpace($a)) { return $default }
    return $a.Trim().ToLower().StartsWith('y')
}

# ---------------------------------------------------------------------------------------------- winget
function Has-Winget { return [bool](Get-Command winget -ErrorAction SilentlyContinue) }

function Winget-Latest([string]$id) {
    $out = winget show --id $id --exact --source winget --accept-source-agreements 2>$null | Out-String
    if ($out -match '(?m)^\s*Version:\s*(\S+)') { return $Matches[1] }
    return $null
}

function Winget-Installed([string]$id) {
    $out = winget list --id $id --exact --accept-source-agreements 2>$null | Out-String
    foreach ($row in ($out -split "`r?`n")) {
        if ($row -match ([regex]::Escape($id) + '\s+(\d[^\s]*)')) { return $Matches[1] }
    }
    return $null
}

function Winget-Ensure([string]$id, [string]$name, [string[]]$extra = @()) {
    $latest = Winget-Latest $id
    $have = Winget-Installed $id
    if ($CheckOnly) {
        if (-not $have) { Info "$name is not installed; it would install $latest"; Record $name $latest 'would install' }
        elseif ($latest -and $have -ne $latest) { Info "$name $have is installed; it would update to $latest"; Record $name $have "would update to $latest" }
        else { Ok "$name $have (latest)"; Record $name $have 'latest' }
        return $true
    }
    $common = @('--id', $id, '--exact', '--source', 'winget', '--silent', '--accept-package-agreements', '--accept-source-agreements', '--disable-interactivity')
    if (-not $have) {
        Info "Installing $name $latest ..."
        & winget install @common @extra | Out-Host
    } elseif ($latest -and $have -ne $latest) {
        Info "Updating $name $have -> $latest ..."
        & winget upgrade @common @extra | Out-Host
    } else {
        Ok "$name $have is already the latest"
        Record $name $have 'latest'
        return $true
    }
    $now = Winget-Installed $id
    if ($now) { Ok "$name $now"; Record $name $now 'installed / updated'; return $true }
    Bad "$name could not be installed (winget exit code $LASTEXITCODE)"
    Record $name '-' 'failed'
    return $false
}

function Refresh-Path {
    $machine = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $user = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = "$machine;$user"
}

# ---------------------------------------------------------------------------------------------- Python
function Python-Exe([int]$minor) {
    foreach ($hive in 'HKCU:\Software\Python\PythonCore', 'HKLM:\Software\Python\PythonCore', 'HKLM:\Software\WOW6432Node\Python\PythonCore') {
        $key = Join-Path $hive ("3.{0}\InstallPath" -f $minor)
        if (Test-Path $key) {
            $props = Get-ItemProperty $key
            $exe = $props.ExecutablePath
            if (-not $exe -and $props.'(default)') { $exe = Join-Path $props.'(default)' 'python.exe' }
            if ($exe -and (Test-Path $exe)) { return $exe }
        }
    }
    $guess = Join-Path $env:LOCALAPPDATA ("Programs\Python\Python3{0}\python.exe" -f $minor)
    if (Test-Path $guess) { return $guess }
    return $null
}

function Newest-Installed-Python {
    for ($m = 30; $m -ge 10; $m--) { $exe = Python-Exe $m; if ($exe) { return @{ Minor = $m; Exe = $exe } } }
    return $null
}

function Latest-Python-Minor {
    $out = winget search --id Python.Python.3 --source winget --accept-source-agreements 2>$null | Out-String
    $minors = [regex]::Matches($out, 'Python\.Python\.3\.(\d+)\b') | ForEach-Object { [int]$_.Groups[1].Value }
    if (-not $minors) { return $null }
    return ($minors | Measure-Object -Maximum).Maximum
}

# ---------------------------------------------------------------------------------------------- font
function Install-GoogleSansCode {
    $api = 'https://api.github.com/repos/googlefonts/googlesans-code/releases/latest'
    try { $rel = Invoke-RestMethod $api -Headers @{ 'User-Agent' = 'jobsearch-setup' } -ErrorAction Stop }
    catch { Warn "Couldn't reach GitHub for the font ($($_.Exception.Message)); skipped."; Record 'Google Sans Code font' '-' 'skipped'; return $false }
    $tag = $rel.tag_name
    $asset = $rel.assets | Where-Object { $_.name -match '^GoogleSansCode-v[\d.]+\.zip$' } | Select-Object -First 1
    if (-not $asset) { Warn "No font download found in release $tag; skipped."; Record 'Google Sans Code font' '-' 'skipped'; return $false }
    $fontDir = Join-Path $env:LOCALAPPDATA 'Microsoft\Windows\Fonts'
    $regKey = 'HKCU:\Software\Microsoft\Windows NT\CurrentVersion\Fonts'
    $have = (Get-ItemProperty $regKey -ErrorAction SilentlyContinue).'Google Sans Code (TrueType)'
    $marker = Join-Path $fontDir 'GoogleSansCode.version.txt'
    $haveTag = if (Test-Path $marker) { (Get-Content $marker -Raw).Trim() } else { '' }
    if ($CheckOnly) {
        if ($have -and $haveTag -eq $tag) { Ok "Google Sans Code $tag (latest)"; Record 'Google Sans Code font' $tag 'latest' }
        else { Info "Google Sans Code would install $tag"; Record 'Google Sans Code font' $tag 'would install' }
        return $true
    }
    if ($have -and $haveTag -eq $tag -and (Test-Path $have)) { Ok "Google Sans Code $tag is already the latest"; Record 'Google Sans Code font' $tag 'latest'; return $true }
    Info "Installing Google Sans Code $tag for your account ..."
    $tmp = Join-Path $env:TEMP ("jobsearch-font-" + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $tmp | Out-Null
    try {
        $zip = Join-Path $tmp $asset.name
        Invoke-WebRequest $asset.browser_download_url -OutFile $zip -UseBasicParsing -ErrorAction Stop
        Expand-Archive -Path $zip -DestinationPath $tmp -Force -ErrorAction Stop
        $ttf = Get-ChildItem $tmp -Recurse -Filter '*.ttf' | Where-Object { $_.Name -match '\[wght\]' }
        if (-not $ttf) { $ttf = Get-ChildItem $tmp -Recurse -Filter '*.ttf' }
        New-Item -ItemType Directory -Force -Path $fontDir | Out-Null
        foreach ($f in $ttf) {
            $dest = Join-Path $fontDir $f.Name
            try { Copy-Item $f.FullName $dest -Force -ErrorAction Stop } catch { Warn "$($f.Name) is in use; close Windows Terminal and run setup again to update it." }
            $face = if ($f.Name -match 'Italic') { 'Google Sans Code Italic (TrueType)' } else { 'Google Sans Code (TrueType)' }
            New-ItemProperty -Path $regKey -Name $face -Value $dest -PropertyType String -Force -ErrorAction Stop | Out-Null
        }
        Set-Content -Path $marker -Value $tag -Encoding ASCII
        Ok "Google Sans Code $tag installed ($($ttf.Count) font files)"
        Record 'Google Sans Code font' $tag 'installed / updated'
        return $true
    } catch {
        Warn "The font couldn't be installed: $($_.Exception.Message)"
        Record 'Google Sans Code font' '-' 'skipped'
        return $false
    } finally {
        Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
    }
}

function Set-TerminalFont {
    $paths = @(
        (Join-Path $env:LOCALAPPDATA 'Packages\Microsoft.WindowsTerminal_8wekyb3d8bbwe\LocalState\settings.json'),
        (Join-Path $env:LOCALAPPDATA 'Packages\Microsoft.WindowsTerminalPreview_8wekyb3d8bbwe\LocalState\settings.json'),
        (Join-Path $env:LOCALAPPDATA 'Microsoft\Windows Terminal\settings.json')
    ) | Where-Object { Test-Path $_ }
    if (-not $paths) { Info "Open Windows Terminal once, then run setup again to set its font (or: Settings > Defaults > Appearance > Font face)."; return }
    foreach ($p in $paths) {
        try {
            $json = Get-Content $p -Raw -Encoding UTF8 -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
        } catch {
            Warn "Couldn't read $p (it has comments). Set it by hand: Settings > Defaults > Appearance > Font face > Google Sans Code."
            continue
        }
        if (-not $json.profiles) { $json | Add-Member -NotePropertyName profiles -NotePropertyValue ([pscustomobject]@{}) }
        if ($json.profiles -is [System.Array]) { Warn "Unusual Windows Terminal settings; set the font by hand."; continue }
        if (-not $json.profiles.defaults) { $json.profiles | Add-Member -NotePropertyName defaults -NotePropertyValue ([pscustomobject]@{}) -Force }
        if (-not $json.profiles.defaults.font) { $json.profiles.defaults | Add-Member -NotePropertyName font -NotePropertyValue ([pscustomobject]@{}) -Force }
        if ($json.profiles.defaults.font.face -eq 'Google Sans Code') { Ok "Windows Terminal already uses Google Sans Code"; continue }
        Copy-Item $p "$p.before-jobsearch.bak" -Force
        $json.profiles.defaults.font | Add-Member -NotePropertyName face -NotePropertyValue 'Google Sans Code' -Force
        $text = $json | ConvertTo-Json -Depth 64
        [System.IO.File]::WriteAllText($p, $text, (New-Object System.Text.UTF8Encoding $false))
        Ok "Windows Terminal font set to Google Sans Code (backup: settings.json.before-jobsearch.bak)"
    }
}

function Default-Browser {
    try {
        $id = (Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\Shell\Associations\UrlAssociations\https\UserChoice' -ErrorAction Stop).ProgId
    } catch { return 'Microsoft Edge' }
    switch -Regex ($id) {
        '^MSEdge' { 'Microsoft Edge' } '^Chrome' { 'Google Chrome' } '^Firefox' { 'Mozilla Firefox' }
        '^Brave' { 'Brave' } '^Opera' { 'Opera' } default { $id }
    }
}

# ============================================================================================== run
Line ''
Line '  ============================================================================' DarkCyan
Line '     J O B   S E A R C H   -   setup for Windows' Cyan
Line '     Installs or updates everything to the latest version, then checks it works' Gray
Line '     Built by Rahul Swargam  -  https://rahulswargam.online/' Yellow
Line '  ============================================================================' DarkCyan
if ($CheckOnly) { Warn 'Check only: nothing will be installed or changed.' }
Line ("  Folder: {0}" -f $Root) DarkGray

$total = 5

# 1. winget
Step 1 $total 'Windows package manager (winget)'
if ($SkipSystem) {
    Info 'Skipped (/skip-system).'
} elseif (-not (Has-Winget)) {
    Bad 'winget is missing. Install "App Installer" from the Microsoft Store, then run this file again.'
    try { Start-Process 'ms-windows-store://pdp/?productid=9NBLGGH4NNS1' } catch { }
    exit 1
} else {
    $wv = (winget --version) -replace '^v', ''
    Ok "winget $wv"
    Record 'winget' $wv 'present'
}

# 2. Python
Step 2 $total 'Python (newest version, with pip, Tkinter and the py launcher)'
$py = $null
if ($SkipSystem) {
    $py = Newest-Installed-Python
    if ($py) { Ok ("Using Python 3.{0} that's already installed: {1}" -f $py.Minor, $py.Exe) }
} else {
    $minor = Latest-Python-Minor
    if (-not $minor) { Bad "Couldn't find Python in winget."; exit 1 }
    $custom = @('--scope', 'user', '--installer-type', 'burn', '--custom', 'Include_pip=1 Include_tcltk=1 Include_launcher=1 InstallLauncherAllUsers=0 Include_test=0')
    [void](Winget-Ensure ("Python.Python.3.{0}" -f $minor) ("Python 3.{0}" -f $minor) $custom)
    Refresh-Path
    $exe = Python-Exe $minor
    if ($exe) { $py = @{ Minor = $minor; Exe = $exe } }
}
if ($CheckOnly -and -not $py) {
    Info ("Tkinter (file and folder windows) is checked once Python 3.{0} is installed" -f $minor)
    $pyVersion = "3.$minor (after install)"
} else {
    if (-not $py) { Bad 'No Python found. Run this file again without /skip-system.'; exit 1 }
    $pyVersion = (& $py.Exe -c "import sys; print('%d.%d.%d' % sys.version_info[:3])").Trim()
    & $py.Exe -c "import tkinter" 2>$null
    if ($LASTEXITCODE -eq 0) { Ok "Tkinter (file and folder windows) works with Python $pyVersion" }
    else { Bad "Tkinter is missing from Python $pyVersion. Re-run this file; if it persists, reinstall Python with 'tcl/tk' ticked." }
    if ($SkipSystem) { Record 'Python' $pyVersion 'ready' }
}

# 3. Git, Windows Terminal, font
Step 3 $total 'Git, Windows Terminal and the Google Sans Code font'
if ($SkipSystem) {
    Info 'Skipped (/skip-system).'
} else {
    [void](Winget-Ensure 'Git.Git' 'Git')
    [void](Winget-Ensure 'Microsoft.WindowsTerminal' 'Windows Terminal')
    $fontOk = Install-GoogleSansCode
    if ($fontOk -and -not $CheckOnly -and (Ask 'Use Google Sans Code as the Windows Terminal font?' $true)) { Set-TerminalFont }
}

# 4. Python packages in the project's own environment (.venv)
Step 4 $total 'Python packages (latest versions) in this project''s .venv'
$venv = Join-Path $Root '.venv'
$venvPy = Join-Path $venv 'Scripts\python.exe'
if ($CheckOnly) {
    if (Test-Path $venvPy) {
        $vv = (& $venvPy -c "import sys; print('%d.%d.%d' % sys.version_info[:3])").Trim()
        Ok ".venv exists (Python $vv)"
        $outdated = & $venvPy -m pip list --outdated --format=json 2>$null | ConvertFrom-Json
        foreach ($pkg in $Required + $Optional) {
            $ver = (& $venvPy -m pip show $pkg 2>$null | Select-String '^Version:') -replace 'Version:\s*', ''
            $new = ($outdated | Where-Object { $_.name -ieq $pkg }).latest_version
            if (-not $ver) { Info "$pkg would install"; Record $pkg '-' 'would install' }
            elseif ($new) { Info "$pkg $ver would update to $new"; Record $pkg $ver "would update to $new" }
            else { Ok "$pkg $ver (latest)"; Record $pkg $ver 'latest' }
        }
    } else { Info ".venv would be created with Python $pyVersion and the latest packages installed"; Record 'Python packages (.venv)' '-' 'would install' }
} else {
    if (Test-Path $venvPy) {
        $vv = (& $venvPy -c "import sys; print('%d.%d' % sys.version_info[:2])").Trim()
        if ($vv -ne ("3.{0}" -f $py.Minor)) { Info "Rebuilding .venv for Python $pyVersion (it used $vv) ..."; Remove-Item $venv -Recurse -Force }
    }
    if (-not (Test-Path $venvPy)) {
        Info "Creating .venv with Python $pyVersion ..."
        & $py.Exe -m venv $venv
        if ($LASTEXITCODE -ne 0) { Bad 'Could not create .venv'; exit 1 }
    }
    & $venvPy -m pip install --upgrade --disable-pip-version-check --quiet pip | Out-Host
    Info ("Installing the latest " + (($Required | Where-Object { $_ -ne 'pip' }) -join ', ') + ' ...')
    & $venvPy -m pip install --upgrade --disable-pip-version-check --quiet @Required | Out-Host
    if ($LASTEXITCODE -ne 0) { Bad 'Required Python packages failed to install (see above).' }
    foreach ($pkg in $Optional) {
        & $venvPy -m pip install --upgrade --disable-pip-version-check --quiet $pkg 2>$null | Out-Null
        if ($LASTEXITCODE -ne 0) { Warn "$pkg (optional) isn't available for Python $pyVersion yet; the tool works without it." }
    }
    foreach ($pkg in $Required + $Optional) {
        $ver = (& $venvPy -m pip show $pkg 2>$null | Select-String '^Version:') -replace 'Version:\s*', ''
        if ($ver) { Ok "$pkg $ver"; Record $pkg $ver 'latest' }
        elseif ($Optional -contains $pkg) { Record $pkg '-' 'optional, skipped' }
        else { Bad "$pkg is missing"; Record $pkg '-' 'failed' }
    }
}

# 5. Check that it all works
Step 5 $total 'Checking that Job Search works'
if ($CheckOnly) {
    Info 'Skipped in check mode.'
} else {
    Push-Location $Root
    try {
        $out = cmd /c "`"$venvPy`" -m unittest discover -s tests 2>&1" | Out-String
        $ran = if ($out -match 'Ran (\d+) tests?') { $Matches[1] } else { '?' }
        if ($LASTEXITCODE -eq 0 -and $out -match '(?m)^OK') { Ok "All $ran offline checks passed" }
        else { Bad "Some checks failed:"; Line $out DarkGray }
        & $venvPy -m jobsearch sources > $null 2>&1
        if ($LASTEXITCODE -eq 0) { Ok 'python -m jobsearch starts' } else { Bad 'python -m jobsearch did not start' }
    } finally { Pop-Location }
}
$browser = Default-Browser
Ok "Job links pages open in your default browser: $browser"
Record 'Web browser (for the HTML page)' $browser 'present'

# ---------------------------------------------------------------------------------------------- summary
Line ''
Line '  Summary' Cyan
Line ('  ' + ('-' * 76)) DarkBlue
foreach ($r in $Results) {
    $color = switch -Regex ($r.Status) { 'fail' { 'Red' } 'would|skipped|optional' { 'Yellow' } default { 'Green' } }
    Write-Host ('  {0,-34} {1,-18} ' -f $r.Tool, $r.Version) -NoNewline
    Write-Host $r.Status -ForegroundColor $color
}
Line ''
if ($Failed) {
    Line '  Something needs attention (marked FAIL above). Fix it and run setup-windows.bat again.' Red
    exit 1
}
if ($CheckOnly) {
    Line '  Check finished. Run setup-windows.bat without /check to install or update.' Yellow
} else {
    Line '  All set. Start a search by double-clicking run.bat' Green
    Line '  (or in a terminal:  .venv\Scripts\python -m jobsearch )' Gray
    Line '  The first run asks for your Apify API key: get one free at https://console.apify.com' Gray
    Line '  If you installed the font, close and reopen Windows Terminal to see it.' Gray
}
Line ''
Line '  Built by Rahul Swargam  -  https://rahulswargam.online/' Yellow
exit 0
