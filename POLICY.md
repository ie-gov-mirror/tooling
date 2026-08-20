# Policy

Operating policy for the `ie-gov-mirror` archive. These are decisions taken in
advance, so that incidents are handled by a policy rather than improvised.

**Draft.** Items marked **[DECIDE]** are open and need a named human's answer
before backfill begins.

## What this archive is

An unofficial mirror of publicly published Irish public-sector GitHub
repositories, kept so that code removed or made private upstream remains
available. It is **not affiliated with or endorsed by any Irish public body**.
The canonical source is always the upstream repository, linked from each
mirror's homepage field.

## Fidelity

Mirrored git data is byte-identical to upstream. We do not rewrite history,
inject files, add or change licence terms, or modify repository contents. All
mirror-specific information lives in repository *metadata* (description,
homepage, topics) and in this repo's manifest.

Known fidelity gaps, recorded per repository in `manifest/*.csv`
(`fidelity_notes`):

- `refs/pull/*` and other hidden refs are not mirrored — GitHub rejects pushes
  to them.
- Issues, pull requests, wikis, discussions, projects and uploaded release
  assets are not currently captured. Tags are; the binaries attached to them
  are not.
- Git LFS objects are mirrored where upstream LFS storage is still readable.
  Where it is not, the repository is marked `lfs-fetch-incomplete`.

## Takedown requests

We will act on a request from the upstream repository owner or a public body
that published the code, whether or not it is legally compelled. Requests go
to the contact address on the org profile.

Default response: the affected mirror is deleted and a tombstone row is
recorded in `manifest/tombstones.csv` noting that removal was by request. We
do not silently delete — the tombstone stays, because an archive that can be
quietly emptied is not an archive.

**[DECIDE]** Named contact and address for takedown requests.

## Personal data and erasure (GDPR)

Mirrored history contains commit author names and email addresses. The lawful
basis relied on is legitimate interest in archiving material that was
published publicly.

Selective history rewriting is incompatible with fidelity, so a valid Article
17 erasure request is normally satisfied by **deleting and tombstoning the
affected mirror repository**, not by rewriting it.

**[DECIDE]** Named data controller and erasure contact.

## Secrets found in mirrored history

Secret scanning **alerts** are enabled so we know what we are re-hosting.
Push protection is disabled, because pushing history verbatim is the point and
these commits are already public upstream.

When scanning flags a credential that appears to be live:

1. Notify the upstream body promptly and privately.
2. Do not publicise the finding.
3. **[DECIDE]** Do we proactively remove the mirror copy while upstream
   rotates the credential, or preserve it? These conflict. Preservation is the
   archive's purpose; removal reduces harm from a credential that is live
   right now. Recommendation: temporarily make the mirror private, restore it
   once the credential is rotated, and record the gap in `fidelity_notes`.

## Material removed upstream after accidental publication

The hardest case: something published upstream in error — personal data, an
internal document, a credential — and then force-pushed away. Our mirror will
have preserved it.

Position: **accidental publication of personal data is not archival material.**
Where we can establish that upstream removed content because it should never
have been published, and the content is personal data or a live secret rather
than merely embarrassing code, we remove it and record the gap. Code removed
because it is unflattering, obsolete or politically inconvenient stays — that
is exactly what the archive exists for.

**[DECIDE]** Confirm or amend this position, and name who adjudicates.

## Legal removal (HTTP 451) upstream

An upstream returning 451 may indicate a DMCA notice or court order that could
also be served against the mirror. `tombstone.py` flags these separately
rather than treating them as ordinary deletions. A human reviews before the
mirror copy continues to be served.

## Tombstones

Upstream disappearance never causes deletion. The mirror repository is
GitHub-archived — visibly frozen and push-proof — and a row is appended to
`manifest/tombstones.csv` with the last-seen date, detection date, HTTP status
and a Wayback URL.

## Repositories we will not mirror

- Namespaces whose public-body ownership is not established. These sit in
  `manifest/candidates.csv` and are never cloned. A plausible-looking handle
  is not evidence of ownership.
- Repositories in individuals' personal accounts, even where the person works
  for a public body.
- Anything a public body asks us not to mirror, in advance.

## Notification

**[DECIDE]** Whether and when to notify OGCIO and the Irish public-service
open-source Community of Practice. Current recommendation in
`docs/EXECUTION-PLAN.md` is to inform them shortly after backfill, and to use
the same contact to ask about the 18 unverified candidate namespaces and any
self-hosted forges.
