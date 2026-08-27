#!/usr/bin/env python3
"""Re-enumerate upstream namespaces and diff against the manifest.

The research snapshot is a point-in-time list; upstream orgs gain, rename and
lose repositories. This script decides what exists.

Two classes of namespace, treated differently on purpose:

  * DISCOVERY namespaces (the nine verified public bodies) are enumerated
    wholesale. Every public repo in them is in scope, because the namespace
    itself is what was verified as belonging to a public body. New
    repositories found here are accepted automatically and mirrored on the
    next sync - no human review step.

  * LISTED namespaces (extended and candidate tiers) are NOT enumerated.
    Only the specific repositories recorded in the manifest are synced.
    `covidgreen`, `Cavancoco` and `govdataie` are not government namespaces;
    enumerating them wholesale would pull in arbitrary unrelated repos.

Usage:
  enumerate.py --report                 # drift report across all namespaces
  enumerate.py --emit-changed           # tab-separated worklist for sync
  enumerate.py --emit-changed --ns CSOIreland
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

# Tier file -> whether the namespace is enumerated wholesale.
#
# candidates.csv and adjacent.csv are deliberately absent: they are
# documentation, never mirrored. The 18 candidates were checked against
# data.gov.ie on 2026-08-20 (CKAN resource_search, package_search and
# organization_show) and no cross-link between any candidate namespace and a
# public body was found - the portal references exactly one GitHub namespace in
# total, IrishMarineInstitute, which is already core. Keeping the file records
# that verification was attempted and failed, so a future crawl need not redo it.
TIER_FILES = {
    "core.csv": True,
    "extended.csv": False,
}

# Namespaces tied to a named public body by the research snapshot. Adding one
# here means "every public repo in this namespace is government code", which is
# a deliberate, reviewable claim.
#
# Note that not all of these are Organizations. Geological-Survey-Ireland is a
# User account - its profile carries the official gsi.ie domain and describes
# the body, so it is no less verified, but /orgs/{name}/repos returns 404 for
# it. Listing goes through /users/{name}/repos, which returns public
# owner-held repositories for Users and Organizations alike (verified to give
# identical counts to /orgs/{org}/repos?type=public on four organisations).
DISCOVERY_NAMESPACES = [
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


def api_request(path):
    """Single GitHub REST GET returning (payload, link header)."""
    req = urllib.request.Request(f"{API}{path}" if path.startswith("/") else path)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    token = os.environ.get("GH_TOKEN", "")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req) as resp:
        return json.load(resp), resp.headers.get("Link", "")


def api_get(path, allow_missing=False):
    """Paginated GET. Authenticated for 5,000 req/hr rather than 60."""
    out = []
    url = path
    while url:
        try:
            payload, link = api_request(url)
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
                raise SystemExit(
                    f"HTTP {exc.code} on {url}\n"
                    "GH_TOKEN is missing, expired, or lacks Metadata: read. "
                    "Unauthenticated requests are capped at 60/hour, which "
                    "this script will exceed."
                ) from None
            if exc.code == 404:
                if allow_missing:
                    return None
                print(f"HTTP 404 on {url}", file=sys.stderr)
                return None
            raise
        out.extend(payload) if isinstance(payload, list) else out.append(payload)
        url = ""
        for part in link.split(","):
            if 'rel="next"' in part:
                url = part.split(";")[0].strip().strip("<>")
    return out


def mirror_name(owner, name):
    """Flatten owner/name into a single mirror-org repo name.

    A dot is used because GitHub owner names cannot contain dots, so splitting
    on the first dot always recovers the upstream exactly. Hyphen-joining is
    ambiguous (revenue-ie/dpl vs a repo named revenue-ie-dpl) and loses case.
    Matches the uk-gov-mirror convention.
    """
    return f"{owner}.{name}"


def body_for_namespace(rows, ns):
    """The public body name already recorded for a namespace.

    Taken from the manifest rather than a hardcoded table, so the proper name
    ("Central Statistics Office") is reused instead of the GitHub login. Falls
    back to the login for a namespace with no existing rows.
    """
    for row in rows:
        if row["upstream"].split("/")[0] == ns and row.get("public_body"):
            return row["public_body"]
    return ns


def load_tier(filename):
    path = MANIFEST_DIR / filename
    if not path.exists():
        return [], []
    with path.open() as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        return rows, list(reader.fieldnames or [])


def write_tier(filename, rows, fields):
    with (MANIFEST_DIR / filename).open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in sorted(rows, key=lambda r: r["upstream"].lower()):
            writer.writerow(row)


def load_all():
    """Return {filename: (rows, fields)} for every mirrored tier."""
    return {name: load_tier(name) for name in TIER_FILES}


def namespaces(tiers):
    """Every namespace present in the manifest, in sync-shard order.

    A namespace can span tiers - `derilinx` holds one extended repo and two
    candidates - so this is a set over all tier files, not a per-tier list.
    """
    seen = set()
    for rows, _ in tiers.values():
        for row in rows:
            seen.add(row["upstream"].split("/")[0])
    return sorted(seen, key=str.lower)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ns", "--org", action="append", dest="ns",
                    help="limit to one or more namespaces")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--emit-changed", action="store_true")
    ap.add_argument("--update-manifest", action="store_true")
    ap.add_argument("--mark-synced", metavar="FILE",
                    help="file of mirror names (one per line) that synced "
                         "successfully; stamps last_synced and status=active")
    ap.add_argument("--list-namespaces", action="store_true")
    ap.add_argument("--force-all", action="store_true",
                    help="emit every repo, not just those pushed since last sync")
    args = ap.parse_args()

    tiers = load_all()

    # Stamping last_synced is what makes the weekly refresh incremental: the
    # sync gate compares upstream pushed_at against it, so without this every
    # run would re-clone every repository.
    if args.mark_synced:
        today = date.today().isoformat()
        wanted = {line.strip() for line in open(args.mark_synced) if line.strip()}
        stamped = 0
        for filename, (rows, fields) in tiers.items():
            dirty = False
            for row in rows:
                if row["mirror_name"] in wanted:
                    row["last_synced"] = today
                    row["status"] = "active"
                    dirty = True
                    stamped += 1
            if dirty:
                write_tier(filename, rows, fields)
        print(f"stamped last_synced on {stamped} rows", file=sys.stderr)
        missing = wanted - {r["mirror_name"] for rs, _ in tiers.values() for r in rs}
        if missing:
            print(f"warning: {len(missing)} names not in manifest: "
                  f"{sorted(missing)[:5]}", file=sys.stderr)
        if not args.report and not args.emit_changed and not args.update_manifest:
            return 0

    if args.list_namespaces:
        for ns in namespaces(tiers):
            print(ns)
        return 0

    scope = args.ns or namespaces(tiers)
    live = {}          # upstream full_name -> API record
    new_upstream = []  # discovered, not yet in the manifest
    unreachable = []   # namespaces that could not be listed at all

    # Discovery namespaces: enumerate wholesale.
    for ns in scope:
        if ns not in DISCOVERY_NAMESPACES:
            continue
        repos = api_get(f"/users/{ns}/repos?per_page=100&type=owner",
                        allow_missing=True)
        if repos is None:
            # One renamed or deleted namespace must not abort the other eight.
            print(f"{ns}: NOT FOUND - renamed, deleted, or no longer public. "
                  f"Skipping; other namespaces continue.", file=sys.stderr)
            unreachable.append(ns)
            continue
        # Defensive: never mirror a private repository even if the token can
        # somehow see one. The archive is of published material only.
        public = [r for r in repos if not r.get("private")]
        skipped = len(repos) - len(public)
        for repo in public:
            live[repo["full_name"]] = repo
        note = f" ({skipped} non-public skipped)" if skipped else ""
        print(f"{ns}: {len(public)} public repos (enumerated){note}",
              file=sys.stderr)

    # Listed namespaces: fetch only the repositories the manifest names.
    listed = []
    for filename, (rows, _) in tiers.items():
        if TIER_FILES[filename]:
            continue
        listed += [r for r in rows if r["upstream"].split("/")[0] in scope]
    for row in listed:
        repo = api_get(f"/repos/{row['upstream']}", allow_missing=True)
        if repo:
            live[row["upstream"]] = repo[0] if isinstance(repo, list) else repo
    if listed:
        print(f"{len(listed)} listed repos checked individually", file=sys.stderr)

    known = {r["upstream"] for rows, _ in tiers.values() for r in rows}
    new_upstream = sorted(set(live) - known)

    in_scope = [r for rows, _ in tiers.values() for r in rows
                if r["upstream"].split("/")[0] in scope]
    # A repository is only a tombstone candidate if its namespace was actually
    # listed. Without this guard, one unreachable namespace would report every
    # repository in it as having disappeared upstream.
    gone = sorted(r["upstream"] for r in in_scope
                  if r["upstream"] not in live
                  and r["upstream"].split("/")[0] not in unreachable)

    by_upstream = {r["upstream"]: r for rows, _ in tiers.values() for r in rows}
    changed = []
    for full_name, repo in sorted(live.items()):
        row = by_upstream.get(full_name)
        pushed = repo.get("pushed_at") or ""
        if row is None:
            changed.append((full_name, mirror_name(*full_name.split("/", 1)),
                            repo.get("default_branch") or "", "core"))
        elif (args.force_all or not row.get("last_synced")
              or pushed > (row.get("upstream_pushed_at") or "")):
            changed.append((full_name, row["mirror_name"],
                            repo.get("default_branch") or row.get("default_branch") or "",
                            row.get("tier") or "core"))

    if args.report:
        print(f"namespaces in scope: {len(scope)}")
        print(f"live upstream repos: {len(live)}")
        print(f"manifest rows in scope: {len(in_scope)}")
        print(f"needing sync: {len(changed)}")
        print(f"new upstream (review before mirroring): {len(new_upstream)}")
        for n in new_upstream:
            print(f"  + {n}")
        print(f"disappeared upstream (tombstone candidates): {len(gone)}")
        for g in gone:
            print(f"  - {g}")
        if unreachable:
            print(f"NAMESPACES UNREACHABLE: {len(unreachable)}")
            for ns in unreachable:
                print(f"  ! {ns} - could not be listed; its repos were not "
                      f"checked this run")

    if args.emit_changed:
        for upstream, mirror, branch, tier in changed:
            print(f"https://github.com/{upstream}.git\t{mirror}\t{branch}\t{tier}")

    if args.update_manifest:
        today = date.today().isoformat()
        core_rows, core_fields = tiers["core.csv"]
        for filename, (rows, fields) in tiers.items():
            for row in rows:
                repo = live.get(row["upstream"])
                if not repo:
                    continue
                row["last_seen"] = today
                row["upstream_pushed_at"] = repo.get("pushed_at") or ""
                row["upstream_archived"] = str(bool(repo.get("archived"))).lower()
                row["default_branch"] = repo.get("default_branch") or row.get("default_branch", "")
                row["size_kb"] = repo.get("size") or row.get("size_kb", 0)
            write_tier(filename, rows, fields)

        # Newly discovered repos in discovery namespaces are accepted
        # automatically, with the same ownership_confidence and status as the
        # seeded rows. The verified thing is the namespace: if CSOIreland is
        # the Central Statistics Office's account, a new repository in it is
        # CSO code by the same evidence that covers the other 35. No human
        # gate, so a repo published upstream on Monday is mirrored by the
        # following sync.
        #
        # The safety property this relies on is that DISCOVERY_NAMESPACES is
        # the only list that grants automatic trust, and it is only ever
        # changed by a human editing this file.
        added = 0
        for full_name in new_upstream:
            repo = live[full_name]
            ns = full_name.split("/")[0]
            row = {f: "" for f in core_fields}
            row.update({
                "upstream": full_name,
                "mirror_name": mirror_name(*full_name.split("/", 1)),
                "tier": "core",
                "public_body": body_for_namespace(core_rows, ns),
                "ownership_confidence": "high",
                "clone_url": f"https://github.com/{full_name}.git",
                "web_url": f"https://github.com/{full_name}",
                "default_branch": repo.get("default_branch") or "",
                "upstream_archived": str(bool(repo.get("archived"))).lower(),
                "size_kb": repo.get("size") or 0,
                "first_seen": today,
                "last_seen": today,
                "status": "pending",
                "lfs": "unknown",
                "evidence_url": f"https://github.com/{ns}",
                "fidelity_notes": f"auto-accepted from verified namespace {ns} on {today}",
            })
            core_rows.append(row)
            added += 1
            print(f"auto-accepted {full_name}", file=sys.stderr)
        if added:
            write_tier("core.csv", core_rows, core_fields)
        print(f"manifest updated ({added} new rows)", file=sys.stderr)

    # Unreachable namespaces are the serious case: repositories in them were
    # not checked at all, so their absence from `live` must not be mistaken for
    # upstream deletion.
    if unreachable:
        print(f"warning: {len(unreachable)} namespace(s) unreachable: "
              f"{unreachable}", file=sys.stderr)
    return 1 if (new_upstream or gone or unreachable) else 0


if __name__ == "__main__":
    sys.exit(main())
