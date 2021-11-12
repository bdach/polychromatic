#!/bin/bash
#
# Use this script to run unit tests for Polychromatic, which exclude
# backend-specific tests and should be tested separately.
#
# Optional parameter: --verbose
#

cd "$(dirname "$0")/../"

# For Python to find our "pylib" module.
export PYTHONPATH="$(realpath .)"

# Isolate save data to avoid clutter.
HOME_TEMP="$(mktemp -d)"
echo "Temporary test home directory: $HOME_TEMP"
export HOME="$HOME_TEMP"
mkdir $HOME/.config $HOME/.cache

# Fire up the runner!
python3 ./tests/runner.py $*
result=$?
[ $? != 0 ] && exit 1

# Clean up temporary home on successful run.
rm -rf "$HOME_TEMP"
exit 0
