#!/usr/bin/env bash
# The daily manifest refresh: observe upstream, auto-accept new repositories,
# record disappearances, and regenerate the public deleted-repository report.
#
# Run under commit_manifest.sh, which may call it more than once - every
# attempt starts from a fresh reset, so every step that writes the manifest
# has to be in here, not before it.
#
# Writes drift.txt (the human-readable report) and accepted.txt (upstreams
# auto-accepted this run, one per line) in the working directory.
#
# Exits with enumerate.py's status: 0, or 3 if a namespace could not be
# listed - in which case everything else is still refreshed, so the caller
# can commit it before failing.

set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

rc=0
python scripts/enumerate.py --report --update-manifest \
  --accepted-out accepted.txt > drift.txt || rc=$?
[ "$rc" -eq 0 ] || [ "$rc" -eq 3 ] || exit "$rc"

python scripts/tombstone.py --check-all || exit $?
python scripts/deleted_repo_report.py || exit $?
exit "$rc"
