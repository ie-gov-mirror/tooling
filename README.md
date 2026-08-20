# ie-gov-mirror / tooling

Tooling, manifest and provenance record for **`ie-gov-mirror`** — an unofficial
mirror of Irish public-sector GitHub repositories, kept so that code removed or
made private upstream stays available.

**Not affiliated with or endorsed by any Irish public body.** The canonical
source for every mirrored repository is its upstream, linked from each mirror's
homepage field.

> **Status: nothing has been mirrored yet.** This repo currently holds the
> plan, the tooling and the inventory. See
> [`docs/EXECUTION-PLAN.md`](docs/EXECUTION-PLAN.md), which has ten open
> questions to settle before backfill.

## Scope

| Tier | Repos | Size | Mirrored |
|---|---:|---:|---|
| core | 191 | 11.51 GiB | yes, to `ie-gov-mirror` |
| extended | 18 | 44.5 MiB | yes, to a separate org so ownership is never implied |
| candidate | 18 | 892 MiB | **no** — ownership unverified |
| adjacent | 1 | 58 MiB | no — independent derivative, linked only |

Core namespaces: [IrishMarineInstitute](https://github.com/IrishMarineInstitute)
(100), [CSOIreland](https://github.com/CSOIreland) (35),
[Oireachtas](https://github.com/Oireachtas) (18),
[HSEIreland](https://github.com/HSEIreland) (15),
[Teagasc](https://github.com/Teagasc) (7), [ogcio](https://github.com/ogcio) (6),
[revenue-ie](https://github.com/revenue-ie) (5),
[MetEireann](https://github.com/MetEireann) (3),
[Geological-Survey-Ireland](https://github.com/Geological-Survey-Ireland) (2).

## Naming

Upstream `owner/repo` is flattened to `owner.repo`, matching
[uk-gov-mirror](https://github.com/uk-gov-mirror):

```
CSOIreland/PxStat  →  ie-gov-mirror/CSOIreland.PxStat
```

GitHub owner names cannot contain dots, so splitting on the first dot always
recovers the upstream exactly.

## Layout

```
manifest/    the authoritative inventory and provenance record
scripts/     enumerate.py, sync_repo.sh, tombstone.py
.github/     enumerate (daily), sync (weekly), backfill (manual)
POLICY.md    takedown, GDPR erasure, secrets, tombstones
docs/        execution plan and the source research snapshot
```

`manifest/*.csv` **is** the provenance record — `git log manifest/core.csv` is
the full audit trail of `first_seen`, `last_seen` and `last_synced`. Note that
GitHub search indexes only a fraction of a bulk-pushed mirror org (1,582 of
uk-gov-mirror's 26,416 repos), so the manifest is the inventory, not search.

## Running it

Requires a GitHub App installed on the org with **Administration: write**,
**Contents: write**, **Workflows: write**, **Metadata: read** — stored as the
`MIRROR_APP_ID` org variable and `MIRROR_APP_PRIVATE_KEY` org secret.

```bash
# What has drifted from the manifest?
GH_TOKEN=... python scripts/enumerate.py --report

# Mirror one repository
GH_TOKEN=... MIRROR_ORG=ie-gov-mirror \
  scripts/sync_repo.sh https://github.com/CSOIreland/PxStat.git CSOIreland.PxStat master

# Check for upstreams that have disappeared (never deletes anything)
GH_TOKEN=... python scripts/tombstone.py --check-all --dry-run
```

Backfill runs from the Actions tab, one namespace at a time, `dry_run: true`
first.

## Two things not to get wrong

- **Actions must be disabled org-wide**, allowlisting only this repo. Mirrored
  repositories contain their own `.github/workflows/*` with `on: push`
  triggers, which would otherwise execute in the mirror org on every sync.
- **Secret scanning push protection must be off** for the mirror org, or the
  backfill will be blocked the first time upstream history contains something
  matching a secret pattern. Keep *alerts* on. See [`POLICY.md`](POLICY.md).

## Related

- [uk-gov-mirror](https://github.com/uk-gov-mirror) — the model for this
  archive, 26,416 UK public-sector repositories.
- [legalize-dev/legalize-ie](https://github.com/legalize-dev/legalize-ie) — a
  git-native mirror of official Irish legislation. Independent derivative, not
  government code, not mirrored here.
