#!/usr/bin/env python3
"""Generate the public deleted-repository report from the tombstone record.

This is the artefact that makes the archive's value legible: a mirror is only
interesting insofar as it holds things that no longer exist upstream. It is
generated from manifest/tombstones.csv, so it cannot drift from the data.

Usage:
  deleted_repo_report.py                  # write docs/DELETED.md
  deleted_repo_report.py --check          # exit 1 if the file is out of date
"""

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOMBSTONES = ROOT / "manifest" / "tombstones.csv"
OUTPUT = ROOT / "docs" / "DELETED.md"
MIRROR_ORG = "ie-gov-mirror"


def load_tombstones():
    if not TOMBSTONES.exists() or TOMBSTONES.stat().st_size == 0:
        return []
    with TOMBSTONES.open() as fh:
        return list(csv.DictReader(fh))


def render(rows):
    out = ["# Repositories no longer available upstream", ""]
    out.append(
        "Irish public-sector repositories that have been deleted, made "
        "private, or otherwise removed from GitHub since this archive began "
        "tracking them. Each one is still readable in "
        f"[{MIRROR_ORG}](https://github.com/{MIRROR_ORG})."
    )
    out.append("")
    out.append(
        "Generated from `manifest/tombstones.csv`. Do not edit by hand."
    )
    out.append("")

    if not rows:
        out += [
            "## Nothing recorded yet",
            "",
            "No tracked upstream repository has disappeared since the archive "
            "started. This page will populate itself as that changes.",
            "",
        ]
        return "\n".join(out)

    legal = [r for r in rows if str(r.get("http_status")) == "451"]
    normal = [r for r in rows if str(r.get("http_status")) != "451"]

    out.append(f"**{len(rows)} repositories** recorded across "
               f"{len({r['upstream'].split('/')[0] for r in rows})} namespaces.")
    out.append("")

    by_ns = defaultdict(list)
    for row in normal:
        by_ns[row["upstream"].split("/")[0]].append(row)

    for ns in sorted(by_ns, key=str.lower):
        entries = sorted(by_ns[ns], key=lambda r: r["upstream"].lower())
        out.append(f"## {ns} ({len(entries)})")
        out.append("")
        out.append("| Repository | Last seen | Detected gone | Mirror |")
        out.append("|---|---|---|---|")
        for r in entries:
            mirror = f"[{r['mirror_name']}](https://github.com/{MIRROR_ORG}/{r['mirror_name']})"
            out.append(f"| `{r['upstream']}` | {r.get('last_seen','')} | "
                       f"{r.get('detected_gone','')} | {mirror} |")
        out.append("")

    if legal:
        # Separated deliberately: a 451 may reflect a legal demand that could
        # also reach the mirror, which is a human decision under POLICY.md.
        out.append("## Removed for legal reasons (HTTP 451)")
        out.append("")
        out.append("These upstreams returned 451 rather than 404, which can "
                   "indicate a legal demand. Each is reviewed individually "
                   "under [POLICY.md](../POLICY.md).")
        out.append("")
        out.append("| Repository | Last seen | Detected | Note |")
        out.append("|---|---|---|---|")
        for r in sorted(legal, key=lambda r: r["upstream"].lower()):
            out.append(f"| `{r['upstream']}` | {r.get('last_seen','')} | "
                       f"{r.get('detected_gone','')} | {r.get('note','')} |")
        out.append("")

    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if the generated file is stale")
    args = ap.parse_args()

    content = render(load_tombstones())

    if args.check:
        current = OUTPUT.read_text() if OUTPUT.exists() else ""
        if current != content:
            print(f"{OUTPUT} is out of date; run deleted_repo_report.py",
                  file=sys.stderr)
            return 1
        print(f"{OUTPUT} is up to date")
        return 0

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(content)
    print(f"wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
