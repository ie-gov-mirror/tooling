#!/usr/bin/env python3
"""Record an upstream disappearance without destroying the mirror.

Preserving repositories that upstream removed is the entire purpose of the
archive, so a 404 is never a reason to delete anything. This script:

  1. confirms the upstream is really gone (404/451, not a transient 5xx),
  2. marks the manifest row tombstoned with the date and HTTP status,
  3. GitHub-archives the mirror repo so it is visibly frozen and push-proof,
  4. appends a tombstones.csv row with a Wayback URL for corroboration.

A 404 is only acted on once the repository has been missing for GRACE_DAYS:
a repository made private for a day while its owner sorts out visibility is
not a deletion. Nothing is lost while waiting - the mirror still holds it.

Tombstones are not one-way. A repository tombstoned on a 404 whose upstream
becomes public again is brought back: its mirror is unarchived, its row returns
to status=pending so the next sync refreshes it, and its tombstones.csv entry
gets a `returned` date rather than being erased. Without this, ogcio/
wagtail-charts - private for a few days in November 2026 - kept its mirror
archived after it came back, and every sync failed pushing to it.

A 451 (unavailable for legal reasons) is flagged separately: it may indicate a
DMCA or court order that could also be served against the mirror, which is a
decision for a human under POLICY.md, not for this script. It is tombstoned at
once, and never brought back automatically.

Usage:
  tombstone.py --check CSOIreland/PxStat        # verify + record if gone
  tombstone.py --check-all                      # sweep every manifest row
  tombstone.py --check-all --returned-out FILE  # ...listing repos brought back

Exits 0, or 3 if a mirror could not be unarchived: everything else is still
written, so the caller commits it and then fails, as with enumerate.py.
"""

import argparse
import csv
import json
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
                    "http_status", "wayback_url", "note", "returned"]

# Days a repository must have been missing from the daily listing before a 404
# archives its mirror. Measured from last_seen, which enumerate.py advances
# every day a repository is listed, so 2 means "missing on two daily runs".
GRACE_DAYS = 2

EXIT_OK = 0
EXIT_PARTIAL = 3


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


def set_archived(mirror_name, archived):
    """Freeze (or unfreeze) the mirror repo. Archived repos reject pushes and
    render with a banner, which is exactly the signal a tombstone should give."""
    body = json.dumps({"archived": archived}).encode()
    req = urllib.request.Request(
        f"https://api.github.com/repos/{MIRROR_ORG}/{mirror_name}",
        data=body, method="PATCH")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("Authorization", f"Bearer {os.environ['GH_TOKEN']}")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status == 200
    except urllib.error.HTTPError as exc:
        verb = "archive" if archived else "unarchive"
        print(f"  could not {verb} mirror: HTTP {exc.code}", file=sys.stderr)
        return False
    except urllib.error.URLError as exc:
        print(f"  could not reach the API: {exc.reason}", file=sys.stderr)
        return False


def days_since(iso_date, today):
    try:
        return (today - date.fromisoformat(iso_date)).days
    except (TypeError, ValueError):
        return None


def load(path):
    with path.open() as fh:
        reader = csv.DictReader(fh)
        return list(reader), list(reader.fieldnames or [])


def load_tombstones():
    if not TOMBSTONES.exists() or TOMBSTONES.stat().st_size == 0:
        return []
    return load(TOMBSTONES)[0]


def write_tombstones(entries):
    # Always rewritten with the current header, so files that predate the
    # `returned` column gain it the first time anything changes.
    with TOMBSTONES.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=TOMBSTONE_FIELDS,
                                extrasaction="ignore")
        writer.writeheader()
        for entry in entries:
            writer.writerow({f: entry.get(f, "") for f in TOMBSTONE_FIELDS})


def bring_back(row, tombstones, today):
    """Upstream is public again: unarchive the mirror and reopen the row.

    Returns True on success. On failure the row stays tombstoned, so no sync
    tries to push to a mirror that is still archived.
    """
    if not set_archived(row["mirror_name"], False):
        return False
    row["status"] = "pending"
    # Close the open tombstone rather than deleting it: the disappearance
    # happened, and the record of it is part of the archive.
    for entry in reversed(tombstones):
        if entry["upstream"] == row["upstream"] and not entry.get("returned"):
            entry["returned"] = today
            break
    return True


def process(targets, dry_run=False):
    """Returns (tombstoned, returned, failed) lists of upstream names."""
    today = date.today()
    tombstones = load_tombstones()
    tombstoned, returned, failed = [], [], []
    for tier_file in TIER_FILES:
        path = MANIFEST_DIR / tier_file
        if not path.exists():
            continue
        rows, fields = load(path)
        dirty = False
        for row in rows:
            if targets and row["upstream"] not in targets:
                continue
            current = row.get("status", "")
            if current == "tombstoned-451":
                continue   # legal removal: a human decides, never automatic
            status = upstream_status(row["upstream"])

            if current.startswith("tombstoned"):
                if status != 200:
                    continue   # still gone, or inconclusive
                print(f"{row['upstream']}: public again -> unarchiving mirror")
                if dry_run:
                    continue
                if bring_back(row, tombstones, today.isoformat()):
                    returned.append(row["upstream"])
                    dirty = True
                else:
                    print(f"::error::{row['upstream']}: upstream is back but "
                          f"{MIRROR_ORG}/{row['mirror_name']} could not be "
                          f"unarchived; it stays tombstoned", file=sys.stderr)
                    failed.append(row["upstream"])
                continue

            if status in (200, 0) or status >= 500:
                continue   # alive, or inconclusive - never tombstone on doubt
            if status not in (404, 451):
                print(f"{row['upstream']}: unexpected HTTP {status}, skipping",
                      file=sys.stderr)
                continue

            missing = days_since(row.get("last_seen"), today)
            if status == 404 and missing is not None and missing < GRACE_DAYS:
                print(f"{row['upstream']}: HTTP 404, last seen "
                      f"{row['last_seen']} - waiting {GRACE_DAYS} days before "
                      f"tombstoning")
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
            set_archived(row["mirror_name"], True)
            tombstones.append({
                "upstream": row["upstream"],
                "mirror_name": row["mirror_name"],
                "last_seen": row.get("last_seen", ""),
                "detected_gone": today.isoformat(),
                "http_status": status,
                "wayback_url": f"https://web.archive.org/web/{row['web_url']}",
                "note": note,
            })
            tombstoned.append(row["upstream"])
        if dirty:
            with path.open("w", newline="") as fh:
                writer = csv.DictWriter(fh, fieldnames=fields)
                writer.writeheader()
                for row in sorted(rows, key=lambda r: r["upstream"].lower()):
                    writer.writerow(row)
    if tombstoned or returned:
        write_tombstones(tombstones)
    print(f"{len(tombstoned)} tombstone(s) recorded, "
          f"{len(returned)} repository(ies) brought back")
    return tombstoned, returned, failed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="append", default=[],
                    help="upstream owner/repo to verify")
    ap.add_argument("--check-all", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--returned-out", metavar="FILE",
                    help="write the upstreams brought back this run to FILE, "
                         "one per line (always written)")
    args = ap.parse_args()
    if not args.check and not args.check_all:
        ap.error("pass --check owner/repo or --check-all")
    _, returned, failed = process(set(args.check), dry_run=args.dry_run)
    if args.returned_out:
        with open(args.returned_out, "w") as fh:
            fh.writelines(f"{n}\n" for n in returned)
    return EXIT_PARTIAL if failed else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
