#!/usr/bin/env bash
# The daily manifest refresh: observe upstream, auto-accept new repositories,
# record disappearances, and regenerate the public deleted-repository report.
#
# Run under commit_manifest.sh, which may call it more than once - every
# attempt starts from a fresh reset, so every step that writes the manifest
# has to be in here, not before it.
#
# Writes drift.txt (the human-readable report), accepted.txt (upstreams
# auto-accepted this run) and returned.txt (tombstoned upstreams that are
# public again and were brought back), one per line, in the working directory.
#
# Exits 0, or 3 if a step partly failed (a namespace could not be listed, or a
# returned mirror could not be unarchived) - everything else is still
# refreshed, so the caller can commit it before failing.

set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

rc=0
python scripts/enumerate.py --report --update-manifest \
  --accepted-out accepted.txt > drift.txt || rc=$?
[ "$rc" -eq 0 ] || [ "$rc" -eq 3 ] || exit "$rc"

trc=0
python scripts/tombstone.py --check-all --returned-out returned.txt || trc=$?
[ "$trc" -eq 0 ] || [ "$trc" -eq 3 ] || exit "$trc"
[ "$trc" -eq 3 ] && rc=3

python scripts/deleted_repo_report.py || exit $?
exit "$rc"
