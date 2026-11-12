#!/bin/bash
# ==============================================================================================
#  Job Search - setup for macOS (Apple Silicon and Intel)          Built by Rahul Swargam
#  Double-click this file in Finder (the first time: right-click > Open), or run:
#
#    bash setup-mac.command                install / update everything to the LATEST version
#    bash setup-mac.command --check        only show what is installed and what would change
#    bash setup-mac.command --yes          don't ask questions (use the defaults)
#    bash setup-mac.command --skip-system  only set up the Python packages (no Homebrew installs)
#
#  Safe to run again any time: it updates everything to the newest version.
#
#  Everything Job Search needs on a Mac (all installed at their latest version):
#
#    Homebrew               macOS package manager (installs Apple's command line tools too)
#    Python 3 (newest)      python@3.x from Homebrew: runs the tool, with pip and venv
#    python-tk              Tkinter for that Python: the file and folder windows
#    Python packages        rich            colours, tables, live progress
#                           prompt_toolkit  arrow-key menus and checkboxes
#                           pypdf           reads PDF resumes
#                           certifi         up-to-date HTTPS certificates for the Apify API
#                           PyMuPDF         better text from some PDF resumes   (optional)
#                           keyring         moves a key saved by an older version (optional)
#    Git                    downloads and updates this project
#    Google Sans Code       the terminal font (Homebrew font)
#    Terminal               full colours and clickable links (Terminal.app is built in)
#    Web browser            opens the job links page (Safari is built in; any browser works)
#    Apify account          free at https://console.apify.com - the tool asks for its API key once
# ==============================================================================================

cd "$(dirname "$0")" || exit 1
ROOT="$(pwd)"

CHECK=0; YES=0; SKIP=0
for arg in "$@"; do
  case "$(echo "$arg" | tr '[:upper:]' '[:lower:]')" in
    --check|-check|/check) CHECK=1 ;;
    --yes|-y|--quiet) YES=1 ;;
    --skip-system) SKIP=1 ;;
  esac
done

REQUIRED="pip rich prompt_toolkit pypdf certifi"
OPTIONAL="PyMuPDF keyring"
FAILED=0
SUMMARY=()

# ---------------------------------------------------------------------------------------------- output
B=$'\033[1m'; DIM=$'\033[2m'; R=$'\033[0m'
BLUE=$'\033[38;5;33m'; GREEN=$'\033[38;5;35m'; YELLOW=$'\033[38;5;220m'; RED=$'\033[38;5;203m'; CYAN=$'\033[38;5;45m'
BG=$'\033[48;5;27m\033[97m'

step()   { echo; printf "%s STEP %s OF %s %s   %s%s%s\n" "$BG" "$1" "$2" "$R" "$CYAN$B" "$3" "$R"; printf "  %s%s%s\n" "$BLUE" "----------------------------------------------------------------------------" "$R"; }
ok()     { printf "  %s[ OK ]%s %s\n" "$GREEN" "$R" "$1"; }
info()   { printf "  %s[ .. ]%s %s\n" "$CYAN" "$R" "$1"; }
warn()   { printf "  %s[ !! ]%s %s\n" "$YELLOW" "$R" "$1"; }
bad()    { printf "  %s[FAIL]%s %s\n" "$RED" "$R" "$1"; FAILED=1; }
record() { SUMMARY+=("$1|$2|$3"); }
ask() {  # ask "question" default(y/n)
  if [ "$YES" = 1 ] || [ "$CHECK" = 1 ]; then [ "$2" = y ]; return; fi
  local hint="y/N"; [ "$2" = y ] && hint="Y/n"
  read -r -p "  ? $1 ($hint) " a
  a="$(echo "$a" | tr '[:upper:]' '[:lower:]')"
  if [ -z "$a" ]; then [ "$2" = y ]; else [ "${a:0:1}" = y ]; fi
}
finish() {
  echo
  printf "  %sBuilt by Rahul Swargam  -  https://rahulswargam.online/%s\n" "$YELLOW" "$R"
  if [ -t 0 ] && [ "$YES" = 0 ]; then echo; read -n 1 -s -r -p "  Press any key to close..."; echo; fi
  exit "$1"
}

# ---------------------------------------------------------------------------------------------- Homebrew helpers
load_brew() {
  for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do
    if [ -x "$b" ]; then eval "$("$b" shellenv)"; return 0; fi
  done
  command -v brew >/dev/null 2>&1
}

brew_latest() {   # newest stable version Homebrew offers for a formula or cask
  if [ "$2" = cask ]; then
    brew info --cask "$1" 2>/dev/null | head -1 | sed -E 's/^==> [^:]+: ([^ ,]+).*/\1/'
  else
    brew info "$1" 2>/dev/null | head -1 | sed -E 's/.*stable ([^ ,]+).*/\1/'
  fi
}

brew_have() {     # installed version, or nothing
  if [ "$2" = cask ]; then brew list --cask --versions "$1" 2>/dev/null | awk '{print $2}'
  else brew list --versions "$1" 2>/dev/null | awk '{print $NF}'; fi
}

brew_ensure() {   # brew_ensure name "Label" [cask]
  local name="$1" label="$2" kind="$3" latest have flag=""
  [ "$kind" = cask ] && flag="--cask"
  latest="$(brew_latest "$name" "$kind")"; have="$(brew_have "$name" "$kind")"
  if [ "$CHECK" = 1 ]; then
    if [ -z "$have" ]; then info "$label is not installed; it would install $latest"; record "$label" "$latest" "would install"
    elif [ -n "$latest" ] && [ "$have" != "$latest" ]; then info "$label $have is installed; it would update to $latest"; record "$label" "$have" "would update to $latest"
    else ok "$label $have (latest)"; record "$label" "$have" "latest"; fi
    return 0
  fi
  if [ -n "$have" ] && { [ -z "$latest" ] || [ "$have" = "$latest" ]; }; then
    ok "$label $have is already the latest"; record "$label" "$have" "latest"; return 0
  fi
  local before="$have" now="$have" try
  for try in 1 2; do
    [ "$try" = 2 ] && info "Trying $label again (downloads sometimes time out) ..."
    if [ -z "$now" ]; then info "Installing $label $latest ..."; brew install $flag "$name"
    else info "Updating $label $now -> $latest ..."; brew upgrade $flag "$name"; fi
    now="$(brew_have "$name" "$kind")"
    if [ -n "$now" ] && { [ -z "$latest" ] || [ "$now" = "$latest" ]; }; then break; fi
  done
  if [ -n "$now" ] && { [ -z "$latest" ] || [ "$now" = "$latest" ]; }; then
    ok "$label $now"; record "$label" "$now" "$([ -n "$before" ] && echo "updated from $before" || echo installed)"; return 0
  fi
  if [ -n "$now" ]; then
    warn "$label couldn't be updated to $latest (it's still $now and works). Run this setup again later."
    record "$label" "$now" "update to $latest failed"; return 0
  fi
  bad "$label could not be installed"; record "$label" "-" "failed"; return 1
}

pypi_latest() {   # newest version of a package on PyPI
  curl -fsS --max-time 20 "https://pypi.org/pypi/$1/json" 2>/dev/null \
    | "$VPY" -c 'import json,sys; print(json.load(sys.stdin)["info"]["version"])' 2>/dev/null
}

newest_python_formula() {
  brew formulae 2>/dev/null | grep -E '^python@3\.[0-9]+$' | sort -t. -k2 -n | tail -1
}

newest_installed_python() {
  for m in $(seq 30 -1 10); do
    for p in "$(brew --prefix 2>/dev/null)/opt/python@3.$m/bin/python3.$m" "/Library/Frameworks/Python.framework/Versions/3.$m/bin/python3.$m" "/usr/local/bin/python3.$m"; do
      [ -x "$p" ] && { echo "$p"; return 0; }
    done
  done
  command -v python3
}

# ============================================================================================== run
echo
printf "  %s============================================================================%s\n" "$BLUE" "$R"
printf "     %sJ O B   S E A R C H   -   setup for macOS%s\n" "$CYAN$B" "$R"
printf "     Installs or updates everything to the latest version, then checks it works\n"
printf "     %sBuilt by Rahul Swargam  -  https://rahulswargam.online/%s\n" "$YELLOW" "$R"
printf "  %s============================================================================%s\n" "$BLUE" "$R"
[ "$CHECK" = 1 ] && warn "Check only: nothing will be installed or changed."
printf "  %sFolder: %s%s\n" "$DIM" "$ROOT" "$R"
TOTAL=5

# 1. Homebrew
step 1 $TOTAL "Homebrew (macOS package manager)"
if [ "$SKIP" = 1 ]; then
  info "Skipped (--skip-system)."
elif load_brew; then
  ok "Homebrew $(brew --version | head -1 | awk '{print $2}')"
  if [ "$CHECK" = 0 ]; then info "Updating Homebrew's package list ..."; brew update --quiet >/dev/null 2>&1; fi
  record "Homebrew" "$(brew --version | head -1 | awk '{print $2}')" "present"
elif [ "$CHECK" = 1 ]; then
  info "Homebrew is not installed; it would be installed (with Apple's command line tools)"
  record "Homebrew" "-" "would install"
else
  info "Installing Homebrew (it asks for your Mac password) ..."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  if load_brew; then
    BREW_BIN="$(command -v brew)"
    PROFILE="$HOME/.zprofile"; [ "$(basename "${SHELL:-zsh}")" = bash ] && PROFILE="$HOME/.bash_profile"
    if ! grep -qs "brew shellenv" "$PROFILE"; then
      printf '\neval "$(%s shellenv)"\n' "$BREW_BIN" >> "$PROFILE"
      ok "Added Homebrew to $PROFILE so new terminals find it"
    fi
    ok "Homebrew $(brew --version | head -1 | awk '{print $2}')"; record "Homebrew" "$(brew --version | head -1 | awk '{print $2}')" "installed"
  else
    bad "Homebrew didn't install. See https://brew.sh and run this file again."; finish 1
  fi
fi

# 2. Python + Tkinter
step 2 $TOTAL "Python (newest version) with Tkinter"
PY=""
if [ "$SKIP" = 1 ]; then
  load_brew >/dev/null 2>&1
  PY="$(newest_installed_python)"
  [ -n "$PY" ] && ok "Using the newest Python already installed: $PY"
elif [ "$CHECK" = 1 ] && ! command -v brew >/dev/null 2>&1; then
  info "Python and Tkinter would be installed with Homebrew"; record "Python" "-" "would install"
else
  PYF="$(newest_python_formula)"
  if [ -z "$PYF" ]; then bad "Couldn't find Python in Homebrew."; finish 1; fi
  MINOR="${PYF#python@3.}"
  brew_ensure "$PYF" "Python 3.$MINOR"
  brew_ensure "python-tk@3.$MINOR" "Tkinter for Python 3.$MINOR"
  CAND="$(brew --prefix)/opt/$PYF/bin/python3.$MINOR"
  [ -x "$CAND" ] && PY="$CAND"
fi
if [ -n "$PY" ]; then
  PYV="$("$PY" -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])')"
  if "$PY" -c "import tkinter" 2>/dev/null; then ok "Tkinter (file and folder windows) works with Python $PYV"
  else bad "Tkinter is missing from Python $PYV. Run: brew install python-tk@${PYV%.*}"; fi
  [ "$SKIP" = 1 ] && record "Python" "$PYV" "ready"
elif [ "$CHECK" = 0 ]; then
  bad "No Python found."; finish 1
fi

# 3. Git and the font
step 3 $TOTAL "Git and the Google Sans Code font"
if [ "$SKIP" = 1 ]; then
  info "Skipped (--skip-system)."
elif command -v brew >/dev/null 2>&1; then
  brew_ensure git "Git"
  brew_ensure font-google-sans-code "Google Sans Code font" cask
  if [ "$CHECK" = 0 ]; then
    info "To use it in Terminal: Terminal > Settings > Profiles > Text > Font > Change > Google Sans Code, style Monospace"
    info "(iTerm2: Settings > Profiles > Text > Font)"
  fi
else
  info "Git and the font would be installed with Homebrew"; record "Git" "-" "would install"; record "Google Sans Code font" "-" "would install"
fi

# 4. Python packages in .venv
step 4 $TOTAL "Python packages (latest versions) in this project's .venv"
VENV="$ROOT/.venv"; VPY="$VENV/bin/python"
if [ "$CHECK" = 1 ]; then
  if [ -x "$VPY" ]; then
    ok ".venv exists (Python $("$VPY" -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])'))"
    OUTDATED="$("$VPY" -m pip list --outdated --format=freeze 2>/dev/null)"
    for pkg in $REQUIRED $OPTIONAL; do
      ver="$("$VPY" -m pip show "$pkg" 2>/dev/null | awk '/^Version:/{print $2}')"
      if [ -z "$ver" ]; then info "$pkg would install"; record "$pkg" "-" "would install"
      elif echo "$OUTDATED" | grep -qi "^$pkg=="; then info "$pkg $ver would update"; record "$pkg" "$ver" "would update"
      else ok "$pkg $ver (latest)"; record "$pkg" "$ver" "latest"; fi
    done
  else
    info ".venv would be created and the latest packages installed"; record "Python packages (.venv)" "-" "would install"
  fi
else
  if [ -x "$VPY" ]; then
    VV="$("$VPY" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
    if [ "$VV" != "${PYV%.*}" ]; then info "Rebuilding .venv for Python $PYV (it used $VV) ..."; rm -rf "$VENV"; fi
  fi
  if [ ! -x "$VPY" ]; then
    info "Creating .venv with Python $PYV ..."
    "$PY" -m venv "$VENV" || { bad "Could not create .venv"; finish 1; }
  fi
  "$VPY" -m pip install --upgrade --disable-pip-version-check --quiet pip
  info "Installing the latest rich, prompt_toolkit, pypdf, certifi ..."
  "$VPY" -m pip install --upgrade --disable-pip-version-check --quiet $REQUIRED || bad "Required Python packages failed to install (see above)."
  for pkg in $OPTIONAL; do
    "$VPY" -m pip install --upgrade --disable-pip-version-check --quiet "$pkg" >/dev/null 2>&1 \
      || warn "$pkg (optional) isn't available for Python $PYV yet; the tool works without it."
  done
  for pkg in $REQUIRED $OPTIONAL; do
    ver="$("$VPY" -m pip show "$pkg" 2>/dev/null | awk '/^Version:/{print $2}')"
    if [ -n "$ver" ]; then
      newest="$(pypi_latest "$pkg")"
      if [ -z "$newest" ] || [ "$newest" = "$ver" ]; then ok "$pkg $ver"; record "$pkg" "$ver" "latest"
      else ok "$pkg $ver (newest for Python ${PYV%.*}; PyPI has $newest)"; record "$pkg" "$ver" "newest for Python ${PYV%.*} (PyPI has $newest)"; fi
    elif echo " $OPTIONAL " | grep -q " $pkg "; then record "$pkg" "-" "optional, skipped"
    else bad "$pkg is missing"; record "$pkg" "-" "failed"; fi
  done
fi

# 5. Check that it works
step 5 $TOTAL "Checking that Job Search works"
if [ "$CHECK" = 1 ]; then
  info "Skipped in check mode."
else
  OUT="$("$VPY" -m unittest discover -s tests 2>&1)"; CODE=$?
  RAN="$(echo "$OUT" | sed -nE 's/^Ran ([0-9]+) tests?.*/\1/p')"
  if [ $CODE -eq 0 ] && echo "$OUT" | grep -q '^OK'; then ok "All ${RAN:-?} offline checks passed"
  else bad "Some checks failed:"; echo "$OUT" | tail -20; fi
  if "$VPY" -m jobsearch sources >/dev/null 2>&1; then ok "python -m jobsearch starts"; else bad "python -m jobsearch did not start"; fi
fi
ok "Job links pages open in your default browser (Safari is built in)"
record "Web browser (for the HTML page)" "default" "present"

# ---------------------------------------------------------------------------------------------- summary
echo
printf "  %sSummary%s\n" "$CYAN$B" "$R"
printf "  %s----------------------------------------------------------------------------%s\n" "$BLUE" "$R"
for row in "${SUMMARY[@]}"; do
  tool="${row%%|*}"; rest="${row#*|}"; ver="${rest%%|*}"; status="${rest#*|}"
  case "$status" in failed*) c="$RED" ;; *would*|*skipped*|*optional*|*failed*|*"newest for"*) c="$YELLOW" ;; *) c="$GREEN" ;; esac
  printf "  %-32s %-15s %s%s%s\n" "$tool" "$ver" "$c" "$status" "$R"
done
echo
if [ "$FAILED" = 1 ]; then
  printf "  %sSomething needs attention (marked FAIL above). Fix it and run setup-mac.command again.%s\n" "$RED" "$R"
  finish 1
fi
if [ "$CHECK" = 1 ]; then
  printf "  %sCheck finished. Run setup-mac.command without --check to install or update.%s\n" "$YELLOW" "$R"
else
  printf "  %sAll set. Start a search by double-clicking run.command%s\n" "$GREEN" "$R"
  printf "  (or in Terminal:  .venv/bin/python -m jobsearch )\n"
  printf "  The first run asks for your Apify API key: get one free at https://console.apify.com\n"
fi
finish 0
