#!/usr/bin/env python3
"""Regression test for the sync gate (bug 8).

The gate once compared the live upstream pushed_at against the manifest's
upstream_pushed_at. Because `enumerate.py --update-manifest` overwrites that
field with the live value every day, the daily job silently disarmed the weekly
one: upstream pushes, enumeration advances the watermark, the comparison goes
equal, and the repository is never re-synced. Mirrors went stale while the
manifest reported them current, and every workflow run stayed green.

This reconstructs those exact conditions and asserts the repository is still
flagged after enumeration has run. It works on a throwaway copy of the
manifest, so the real one is never touched.

Requires GH_TOKEN (Metadata: read is enough) because the gate compares against
live API data. Run:

    GH_TOKEN=... python3 tests/test_sync_gate.py
"""

import csv
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Any repository in a discovery namespace works; this one is stable and small.
SUBJECT = "CSOIreland.PxStat"
NAMESPACE = "CSOIreland"


def run(workdir, *args):
    proc = subprocess.run(
        [sys.executable, "scripts/enumerate.py", *args],
        cwd=workdir, capture_output=True, text=True)
    return proc.stdout, proc.stderr, proc.returncode


def flagged(workdir, namespace):
    out, _, _ = run(workdir, "--ns", namespace, "--emit-changed")
    return {line.split("\t")[1] for line in out.splitlines() if "\t" in line}


def main():
    if not os.environ.get("GH_TOKEN"):
        print("SKIP: GH_TOKEN not set (the gate compares against live API data)")
        return 0

    tmp = Path(tempfile.mkdtemp(prefix="sync-gate-test-"))
    try:
        shutil.copytree(ROOT / "scripts", tmp / "scripts")
        shutil.copytree(ROOT / "manifest", tmp / "manifest")

        # Arrange: the subject was last synced long before upstream's latest
        # push, i.e. its mirror is stale and must be picked up.
        core = tmp / "manifest" / "core.csv"
        rows = list(csv.DictReader(core.open()))
        fields = list(rows[0].keys())
        found = False
        for r in rows:
            if r["mirror_name"] == SUBJECT:
                r["synced_pushed_at"] = "2020-01-01T00:00:00Z"
                found = True
        if not found:
            print(f"FAIL: {SUBJECT} not present in manifest/core.csv")
            return 1
        with core.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)

        # Assert 1: a stale mirror is flagged before enumeration runs.
        if SUBJECT not in flagged(tmp, NAMESPACE):
            print(f"FAIL: {SUBJECT} not flagged even before enumeration")
            return 1
        print(f"ok: {SUBJECT} flagged before enumeration")

        # Act: the daily enumeration, which advances upstream_pushed_at. This is
        # the step that used to erase the signal.
        _, err, rc = run(tmp, "--ns", NAMESPACE, "--update-manifest")
        if "manifest updated" not in err:
            print(f"FAIL: --update-manifest did not run cleanly:\n{err}")
            return 1
        print("ok: enumeration advanced upstream_pushed_at")

        # Assert 2: the repository is STILL flagged. This is the regression.
        if SUBJECT not in flagged(tmp, NAMESPACE):
            print(f"FAIL: {SUBJECT} no longer flagged after enumeration — "
                  f"bug 8 has regressed; the gate is reading a watermark that "
                  f"enumeration overwrites")
            return 1
        print(f"ok: {SUBJECT} still flagged after enumeration")

        # Assert 3: a repository stamped as current is NOT flagged, so the gate
        # is genuinely discriminating rather than flagging everything.
        rows = list(csv.DictReader(core.open()))
        for r in rows:
            if r["mirror_name"] == SUBJECT:
                r["synced_pushed_at"] = r["upstream_pushed_at"]
        with core.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
        if SUBJECT in flagged(tmp, NAMESPACE):
            print(f"FAIL: {SUBJECT} flagged despite being stamped current — "
                  f"the gate would re-clone everything every run")
            return 1
        print(f"ok: {SUBJECT} not flagged once stamped current")

        print("\nPASS: sync gate survives enumeration and still discriminates")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
