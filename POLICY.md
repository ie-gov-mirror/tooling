# Policy

Operating policy for the `ie-gov-mirror` archive. These are decisions taken in
advance, so incidents are handled by policy rather than improvised.

**Contact for all matters below: ie-gov-mirror@googlegroups.com**

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

Known and accepted gaps, recorded per repository in `manifest/*.csv`
(`fidelity_notes`):

- `refs/pull/*` and other hidden refs — GitHub rejects pushes to them.
- Issues, pull requests, wikis, discussions, projects and uploaded release
  assets are **out of scope**. Tags are mirrored; binaries attached to them are
  not. This matches uk-gov-mirror, and keeps the archive's personal-data
  surface limited to commit metadata.
- Git LFS objects are mirrored where upstream LFS storage is still readable.
  Where it is not, the repository is marked `lfs-fetch-incomplete`.

## Preservation posture

**Everything mirrored is preserved. Removal happens on request, not on our own
initiative.** This is uk-gov-mirror's posture and it is a bright-line rule with
no case-by-case judgement: content is not removed because it is embarrassing,
obsolete, politically inconvenient, or because upstream force-pushed it away.

The single exception is a removal request (below).

This is a deliberate choice with a known cost: where a public body publishes
something in error and retracts it, our copy persists until someone asks us to
remove it. The mitigation is that the request route is published, monitored,
and honoured without requiring legal compulsion.

## Removal requests

We act on requests from the upstream repository owner, the public body that
published the code, or any person whose personal data is involved — **whether
or not the request is legally compelled**.

Process:

1. Request arrives at ie-gov-mirror@googlegroups.com.
2. The affected mirror repository is deleted.
3. A row is recorded in `manifest/tombstones.csv` noting removal by request.

We do not silently delete. The tombstone stays, because an archive that can be
quietly emptied is not an archive. The tombstone records that a repository
existed and was removed — not the content that was removed.

## Personal data (GDPR)

Mirrored history contains commit author names and email addresses. The lawful
basis relied on is legitimate interest in archiving material that was published
publicly by public bodies.

Selective history rewriting is incompatible with the fidelity contract, so a
valid Article 17 erasure request is satisfied by **deleting and tombstoning the
affected mirror repository**, not by rewriting it. Requests go to the contact
address above.

Issues and PRs — the largest personal-data surface, containing free-text
comments from members of the public — are deliberately out of scope. That is
partly a privacy decision, not only a scope decision.

## Secrets in mirrored history

Secret scanning is **disabled** for this org, both push protection and alerts.
Push protection would block the backfill on the first secret pattern in
upstream history, and fidelity requires pushing history verbatim.

The consequence is accepted and stated plainly: **we have no proactive signal
for credentials in mirrored history.** We will not discover them ourselves.

If a credential is reported to us:

1. Notify the upstream body privately and promptly.
2. The mirror stays up — the same commits are public upstream, and rotation is
   the only real remedy.
3. If the upstream body asks for the mirror to be removed, that is a removal
   request and is honoured as above.

## Legal removal (HTTP 451) upstream

An upstream returning 451 rather than 404 may indicate a DMCA notice or court
order that could also be served against the mirror. `tombstone.py` records
these separately, and `docs/DELETED.md` lists them in their own section, so
they are visible rather than buried among ordinary deletions. A human reviews
before the mirror copy continues to be served.

## Refs deleted upstream

Branches and tags removed upstream are **kept**. The sync does not use
`git push --prune`, so a mirror is a superset of its upstream rather than a
copy. Preserving what upstream removes is the point of the archive, and that
applies to a deleted branch as much as to a deleted repository.

## Tombstones

Upstream disappearance never causes deletion. The mirror repository is
GitHub-archived — visibly frozen and push-proof — and a row is appended to
`manifest/tombstones.csv` with last-seen date, detection date, HTTP status and
a Wayback URL. `docs/DELETED.md` is generated from that file.

## What we do not mirror

- **Namespaces whose public-body ownership is not established.** The 18
  repositories in `manifest/candidates.csv` were checked twice — once in the
  original research, once against data.gov.ie on 2026-08-20 via the CKAN
  `resource_search`, `package_search` and `organization_show` endpoints. No
  cross-link between any candidate namespace and a public body was found. The
  portal references exactly one GitHub namespace in total
  (`IrishMarineInstitute`, already core). They are documented, not mirrored.

  This is a negative search result, not proof of non-ownership. If a body
  confirms one of these handles, the row moves to `core.csv` by pull request.

- Repositories in individuals' personal accounts, even where the person works
  for a public body.
- Anything a public body asks us not to mirror, in advance.
- `legalize-dev/legalize-ie`, which self-describes as an independent
  derivative rather than government code. Linked from the README instead.

## Non-government projects that are mirrored

The 18 repositories in `manifest/extended.csv` (`covidgreen`, `derilinx`,
`localgovdrupal`) are Irish public-service projects **not owned by an Irish
public body**. They are mirrored in the same org, and marked so ownership is
never implied:

- topic `not-government-owned`
- a repository description stating it explicitly
- `tier=extended` in the manifest

## Governance

Currently operated by one person, as uk-gov-mirror has been for five years.
The contact address is a Google Group rather than a personal inbox, so the
contact route survives a change of operator even though the operator does not.
This is a known single point of failure.
