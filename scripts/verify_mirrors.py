#!/usr/bin/env python3
"""Compare every mirror's git refs against its upstream.

Exit codes and log lines are not evidence that a mirror is faithful: a push can
report rejections while the refs actually landed, and a wrapper can report
success for a script that failed. This compares the actual ref sets.

For each manifest row it fetches GET /repos/{repo}/git/refs from both sides and
compares the full {ref: sha} mapping, so a missing branch, a missing tag or a
stale head is caught rather than just a differing default branch.

refs/pull/* is excluded on both sides: GitHub does not return hidden refs here,
and the sync deliberately strips them because pushes to them are rejected.

Usage:
  verify_mirrors.py                    # verify every mirrored row
  verify_mirrors.py --tier extended
  verify_mirrors.py --check-lfs        # also flag upstreams that use Git LFS
  verify_mirrors.py --json report.json
"""

import argparse
import csv
import json
import os
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

MANIFEST_DIR = Path(__file__).resolve().parent.parent / "manifest"
TIERS = {"core": "core.csv", "extended": "extended.csv"}
MIRROR_ORG = os.environ.get("MIRROR_ORG", "ie-gov-mirror")
API = "https://api.github.com"


def get(path):
    req = urllib.request.Request(f"{API}{path}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    token = os.environ.get("GH_TOKEN", "")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp), resp.status
    except urllib.error.HTTPError as exc:
        return None, exc.code
    except Exception:
        return None, 0


def ref_map(full_name):
    """{refname: sha} for a repository, or (None, status) on failure."""
    data, status = get(f"/repos/{full_name}/git/refs?per_page=100")
    if data is None:
        # 409 means an empty repository: no refs, which is a valid state.
        return ({}, status) if status == 409 else (None, status)
    if isinstance(data, dict):
        data = [data]
    return ({r["ref"]: r["object"]["sha"] for r in data
             if not r["ref"].startswith("refs/pull/")}, status)


def uses_lfs(full_name):
    data, _ = get(f"/repos/{full_name}/contents/.gitattributes")
    if not data or "content" not in data:
        return False
    import base64
    try:
        return "filter=lfs" in base64.b64decode(data["content"]).decode("utf-8", "replace")
    except Exception:
        return False


def check(row, check_lfs=False):
    upstream, mirror = row["upstream"], f"{MIRROR_ORG}/{row['mirror_name']}"
    up, up_status = ref_map(upstream)
    mi, mi_status = ref_map(mirror)
    res = {"upstream": upstream, "mirror": mirror, "tier": row.get("tier", ""),
           "upstream_status": up_status, "mirror_status": mi_status}

    if up is None and up_status in (404, 451):
        # Upstream is gone: the mirror preserving it is the point, not a fault.
        res["verdict"] = "upstream-gone"
        res["detail"] = f"upstream HTTP {up_status}; mirror has {len(mi or {})} refs"
        return res
    if up is None:
        res["verdict"] = "upstream-unreadable"
        res["detail"] = f"HTTP {up_status}"
        return res
    if mi is None:
        res["verdict"] = "mirror-missing"
        res["detail"] = f"HTTP {mi_status}"
        return res

    missing = {k: v for k, v in up.items() if k not in mi}
    stale = {k: (v, mi[k]) for k, v in up.items() if k in mi and mi[k] != v}
    extra = {k: v for k, v in mi.items() if k not in up}

    if not missing and not stale:
        res["verdict"] = "ok"
        res["detail"] = f"{len(up)} refs match"
        if extra:
            # Refs deleted upstream since the sync, or a leftover scratch ref.
            res["verdict"] = "ok-with-extra"
            res["detail"] += f"; {len(extra)} extra: {sorted(extra)[:3]}"
    else:
        res["verdict"] = "MISMATCH"
        bits = []
        if missing:
            bits.append(f"{len(missing)} missing: {sorted(missing)[:3]}")
        if stale:
            bits.append(f"{len(stale)} stale: {sorted(stale)[:3]}")
        res["detail"] = "; ".join(bits)

    if check_lfs and uses_lfs(upstream):
        res["lfs"] = True
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", choices=sorted(TIERS))
    ap.add_argument("--check-lfs", action="store_true")
    ap.add_argument("--json", metavar="FILE")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    rows = []
    for tier, filename in TIERS.items():
        if args.tier and tier != args.tier:
            continue
        path = MANIFEST_DIR / filename
        if path.exists():
            rows += list(csv.DictReader(path.open()))

    print(f"verifying {len(rows)} mirrors against upstream…", file=sys.stderr)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(lambda r: check(r, args.check_lfs), rows))

    order = ["MISMATCH", "mirror-missing", "upstream-unreadable",
             "upstream-gone", "ok-with-extra", "ok"]
    counts = {v: 0 for v in order}
    for r in results:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1

    for verdict in order:
        hits = [r for r in results if r["verdict"] == verdict]
        if not hits:
            continue
        print(f"\n=== {verdict}: {len(hits)}")
        if verdict != "ok":
            for r in hits:
                print(f"  {r['upstream']:56s} {r['detail']}")

    lfs = [r for r in results if r.get("lfs")]
    if lfs:
        print(f"\n=== upstreams using Git LFS: {len(lfs)}")
        for r in lfs:
            print(f"  {r['upstream']}")

    print(f"\ntotal {len(results)}: " +
          ", ".join(f"{k}={v}" for k, v in counts.items() if v))

    if args.json:
        Path(args.json).write_text(json.dumps(results, indent=2))
        print(f"wrote {args.json}", file=sys.stderr)

    bad = counts.get("MISMATCH", 0) + counts.get("mirror-missing", 0)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
