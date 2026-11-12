#!/bin/bash
# Job Search for macOS: run  bash jobsearch.sh  in Terminal to start a search. Options work too: bash jobsearch.sh --dry-run
# Uses the .venv made by setup-mac.sh; falls back to python3 on your PATH.
cd "$(dirname "$0")" || exit 1
if [ -x ".venv/bin/python" ]; then
  .venv/bin/python -m jobsearch "$@"
else
  echo "Tip: run  bash setup-mac.sh  first to install everything Job Search needs."
  python3 -m jobsearch "$@"
fi
echo
read -n 1 -s -r -p "Press any key to close..."
