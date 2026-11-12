#!/bin/bash
# macOS: double-click this file in Finder to start a search (first time: right-click > Open).
cd "$(dirname "$0")"
python3 -m jobsearch "$@"
echo
read -n 1 -s -r -p "Press any key to close..."
