#!/usr/bin/env python3
"""Record an upstream disappearance without destroying the mirror.

Preserving repositories that upstream removed is the entire purpose of the
archive, so a 404 is never a reason to delete anything. This script:

  1. confirms the upstream is really gone (404/451, not a transient 5xx),
  2. marks the manifest row tombstoned with the date and HTTP status,
  3. GitHub-archives the mirror repo so it is visibly frozen and push-proof,
  4. appends a tombstones.csv row with a Wayback URL for corroboration.

A 451 (unavailable for legal reasons) is flagged separately: it may indicate a
DMCA or court order that could also be served against the mirror, which is a
decision for a human under POLICY.md, not for this script.

Usage:
  tombstone.py --check CSOIreland/PxStat        # verify + record if gone
  tombstone.py --check-all                      # sweep every manifest row
"""

import argparse
import csv
import os
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

MANIFEST_DIR = Path(__file__).resolve().parent.parent / "manifest"
TOMBSTONES = MANIFEST_DIR / "tombstones.csv"
TIER_FILES = ["core.csv", "extended.csv"]
MIRROR_ORG = os.environ.get("MIRROR_ORG", "ie-gov-mirror")

TOMBSTONE_FIELDS = ["upstream", "mirror_name", "last_seen", "detected_gone",
                    "http_status", "wayback_url", "note"]


def upstream_status(full_name):
    """Return the HTTP status for the upstream repo's API record."""
    req = urllib.request.Request(f"https://api.github.com/repos/{full_name}")
    req.add_header("Accept", "application/vnd.github+json")
    token = os.environ.get("GH_TOKEN", "")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except urllib.error.URLError:
        return 0   # network problem: treat as inconclusive, never tombstone


def archive_mirror(mirror_name):
    """Freeze the mirror repo. Archived repos reject pushes and render with a
    banner, which is exactly the signal a tombstone should give."""
    import json
    body = json.dumps({"archived": True}).encode()
    req = urllib.request.Request(
        f"https://api.github.com/repos/{MIRROR_ORG}/{mirror_name}",
        data=body, method="PATCH")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("Authorization", f"Bearer {os.environ['GH_TOKEN']}")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status == 200
    except urllib.error.HTTPError as exc:
        print(f"  could not archive mirror: HTTP {exc.code}", file=sys.stderr)
        return False


def load(path):
    with path.open() as fh:
        reader = csv.DictReader(fh)
        return list(reader), list(reader.fieldnames or [])


def append_tombstone(entry):
    exists = TOMBSTONES.exists() and TOMBSTONES.stat().st_size > 0
    with TOMBSTONES.open("a", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=TOMBSTONE_FIELDS)
        if not exists:
            writer.writeheader()
        writer.writerow(entry)


def process(targets, dry_run=False):
    today = date.today().isoformat()
    recorded = 0
    for tier_file in TIER_FILES:
        path = MANIFEST_DIR / tier_file
        if not path.exists():
            continue
        rows, fields = load(path)
        dirty = False
        for row in rows:
            if targets and row["upstream"] not in targets:
                continue
            if row.get("status", "").startswith("tombstoned"):
                continue
            status = upstream_status(row["upstream"])
            if status in (200, 0) or status >= 500:
                continue   # alive, or inconclusive - never tombstone on doubt
            if status not in (404, 451):
                print(f"{row['upstream']}: unexpected HTTP {status}, skipping",
                      file=sys.stderr)
                continue

            note = ("upstream returned 451 - possible legal removal, review "
                    "POLICY.md before serving the mirror copy"
                    if status == 451 else
                    "upstream deleted or made private; mirror preserved")
            print(f"{row['upstream']}: HTTP {status} -> tombstoning")
            if dry_run:
                continue
            row["status"] = f"tombstoned-{status}"
            dirty = True
            archive_mirror(row["mirror_name"])
            append_tombstone({
                "upstream": row["upstream"],
                "mirror_name": row["mirror_name"],
                "last_seen": row.get("last_seen", ""),
                "detected_gone": today,
                "http_status": status,
                "wayback_url": f"https://web.archive.org/web/{row['web_url']}",
                "note": note,
            })
            recorded += 1
        if dirty:
            with path.open("w", newline="") as fh:
                writer = csv.DictWriter(fh, fieldnames=fields)
                writer.writeheader()
                for row in sorted(rows, key=lambda r: r["upstream"].lower()):
                    writer.writerow(row)
    print(f"{recorded} tombstone(s) recorded")
    return recorded


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="append", default=[],
                    help="upstream owner/repo to verify")
    ap.add_argument("--check-all", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if not args.check and not args.check_all:
        ap.error("pass --check owner/repo or --check-all")
    process(set(args.check), dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
