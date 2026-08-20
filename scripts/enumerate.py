#!/usr/bin/env python3
"""Re-enumerate the verified upstream namespaces and diff against the manifest.

The research snapshot is a point-in-time list; upstream orgs gain, rename and
lose repositories. This script is the only thing that decides what exists. It
never deletes manifest rows: disappearances are reported for the tombstone
flow, and new repositories are reported for a human to approve.

Usage:
  enumerate.py --report                 # human-readable drift report
  enumerate.py --emit-changed           # tab-separated worklist for sync
  enumerate.py --emit-changed --org CSOIreland
  enumerate.py --update-manifest        # apply last_seen / pushed_at / new rows
"""

import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

MANIFEST_DIR = Path(__file__).resolve().parent.parent / "manifest"
CORE = MANIFEST_DIR / "core.csv"

# The nine namespaces tied to a named public body by the research snapshot.
# Adding a namespace here is a deliberate, reviewable act.
VERIFIED_ORGS = [
    "CSOIreland",
    "Geological-Survey-Ireland",
    "HSEIreland",
    "IrishMarineInstitute",
    "MetEireann",
    "Oireachtas",
    "Teagasc",
    "ogcio",
    "revenue-ie",
]

API = "https://api.github.com"


def api_get(path):
    """Paginated GitHub REST GET. Authenticated to get 5,000 req/hr not 60."""
    url = f"{API}{path}"
    token = os.environ.get("GH_TOKEN", "")
    out = []
    while url:
        req = urllib.request.Request(url)
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("X-GitHub-Api-Version", "2022-11-28")
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(req) as resp:
                out.extend(json.load(resp))
                link = resp.headers.get("Link", "")
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode()
            except Exception:
                pass
            if exc.code in (403, 429) and "rate limit" in detail.lower():
                print("rate limited, sleeping 60s", file=sys.stderr)
                time.sleep(60)
                continue
            if exc.code in (401, 403):
                # Almost always a missing, expired or under-scoped token
                # rather than a bug. Say so instead of dumping a traceback.
                raise SystemExit(
                    f"HTTP {exc.code} on {path}\n"
                    "GH_TOKEN is missing, expired, or lacks Metadata: read on "
                    "the target org. Unauthenticated requests are also capped "
                    "at 60/hour, which this script will exceed."
                ) from None
            if exc.code == 404:
                raise SystemExit(
                    f"HTTP 404 on {path} - namespace renamed or deleted? "
                    "Check VERIFIED_ORGS."
                ) from None
            raise
        url = ""
        for part in link.split(","):
            if 'rel="next"' in part:
                url = part.split(";")[0].strip().strip("<>")
    return out


def mirror_name(owner, name):
    """Flatten owner/name into a single mirror-org repo name.

    A dot is used because GitHub owner names cannot contain dots, so splitting
    on the first dot always recovers the upstream exactly. Hyphen-joining is
    ambiguous (revenue-ie/dpl vs a repo literally named revenue-ie-dpl) and
    loses case. This matches the uk-gov-mirror convention.
    """
    return f"{owner}.{name}"


def load_manifest(path):
    if not path.exists():
        return [], []
    with path.open() as fh:
        reader = csv.DictReader(fh)
        return list(reader), list(reader.fieldnames or [])


def write_manifest(path, rows, fields):
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in sorted(rows, key=lambda r: r["upstream"].lower()):
            writer.writerow(row)


def enumerate_orgs(orgs):
    live = {}
    for org in orgs:
        repos = api_get(f"/orgs/{org}/repos?per_page=100&type=public")
        for repo in repos:
            live[repo["full_name"]] = repo
        print(f"{org}: {len(repos)} public repos", file=sys.stderr)
    return live


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--org", action="append", help="limit to one or more orgs")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--emit-changed", action="store_true")
    ap.add_argument("--update-manifest", action="store_true")
    ap.add_argument("--force-all", action="store_true",
                    help="emit every repo, not just those pushed since last sync")
    args = ap.parse_args()

    orgs = args.org or VERIFIED_ORGS
    rows, fields = load_manifest(CORE)
    by_upstream = {r["upstream"]: r for r in rows}
    live = enumerate_orgs(orgs)

    scoped = [r for r in rows if r["upstream"].split("/")[0] in orgs]
    new = sorted(set(live) - {r["upstream"] for r in rows})
    gone = sorted(r["upstream"] for r in scoped if r["upstream"] not in live)

    changed = []
    for full_name, repo in sorted(live.items()):
        row = by_upstream.get(full_name)
        pushed = repo.get("pushed_at") or ""
        if row is None:
            changed.append((full_name, mirror_name(*full_name.split("/", 1)),
                            repo.get("default_branch") or ""))
        elif args.force_all or not row.get("last_synced") \
                or pushed > (row.get("upstream_pushed_at") or ""):
            changed.append((full_name, row["mirror_name"],
                            repo.get("default_branch") or row.get("default_branch") or ""))

    if args.report:
        print(f"live upstream repos: {len(live)}")
        print(f"manifest rows in scope: {len(scoped)}")
        print(f"needing sync: {len(changed)}")
        print(f"new upstream (approve before mirroring): {len(new)}")
        for n in new:
            print(f"  + {n}")
        print(f"disappeared upstream (tombstone candidates): {len(gone)}")
        for g in gone:
            print(f"  - {g}")

    if args.emit_changed:
        for upstream, mirror, branch in changed:
            clone = f"https://github.com/{upstream}.git"
            print(f"{clone}\t{mirror}\t{branch}")

    if args.update_manifest:
        today = date.today().isoformat()
        for full_name, repo in live.items():
            row = by_upstream.get(full_name)
            if row is None:
                # New upstream repo: recorded as pending, never auto-synced.
                # A human approves it by merging the bot's PR.
                row = {f: "" for f in fields}
                row.update({
                    "upstream": full_name,
                    "mirror_name": mirror_name(*full_name.split("/", 1)),
                    "tier": "core",
                    "public_body": repo["owner"]["login"],
                    "ownership_confidence": "unreviewed",
                    "clone_url": f"https://github.com/{full_name}.git",
                    "web_url": f"https://github.com/{full_name}",
                    "first_seen": today,
                    "status": "pending-review",
                    "lfs": "unknown",
                })
                rows.append(row)
                by_upstream[full_name] = row
            row["last_seen"] = today
            row["upstream_pushed_at"] = repo.get("pushed_at") or ""
            row["upstream_archived"] = str(bool(repo.get("archived"))).lower()
            row["default_branch"] = repo.get("default_branch") or row.get("default_branch", "")
            row["size_kb"] = repo.get("size") or row.get("size_kb", 0)
        write_manifest(CORE, rows, fields)
        print(f"manifest updated: {len(rows)} rows", file=sys.stderr)

    # Non-zero exit signals drift needing human attention, for workflow gating.
    return 1 if (new or gone) else 0


if __name__ == "__main__":
    sys.exit(main())
