# ie-gov-mirror / tooling

Tooling, manifest and provenance record for **`ie-gov-mirror`** — an unofficial
mirror of Irish public-sector GitHub repositories, kept so that code removed or
made private upstream stays available.

**Not affiliated with or endorsed by any Irish public body.** The canonical
source for every mirrored repository is its upstream, linked from each mirror's
homepage field.

> **Status: 149 of 209 mirrored**, all verified byte-identical to upstream
> across every branch and tag. 60 pending, waiting on GitHub's
> repository-creation rate limit. Org setup is complete. See the execution
> record in [`docs/EXECUTION-PLAN.md`](docs/EXECUTION-PLAN.md#7-execution-record).

## Scope

| Tier | Repos | Size | Mirrored |
|---|---:|---:|---|
| core | 191 | 11.51 GiB | yes |
| extended | 18 | 44.5 MiB | yes, labelled `not-government-owned` |
| candidate | 18 | 892 MiB | **no** — ownership unverified twice |
| adjacent | 1 | 58 MiB | no — independent derivative, linked only |

**209 repositories, 11.56 GiB, 12 namespaces.**

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
scripts/     enumerate.py, sync_repo.sh, tombstone.py, deleted_repo_report.py
.github/     enumerate (daily), sync (weekly), backfill (manual)
POLICY.md    removal requests, GDPR erasure, secrets, tombstones
docs/        execution plan, DELETED.md, and the source research snapshot
```

Contact for removal and data-erasure requests: **ie-gov-mirror@googlegroups.com**
(see [`POLICY.md`](POLICY.md)).

`manifest/*.csv` **is** the provenance record — `git log manifest/core.csv` is
the full audit trail of `first_seen`, `last_seen` and `last_synced`. Note that
GitHub search indexes only a fraction of a bulk-pushed mirror org (1,582 of
uk-gov-mirror's 26,416 repos), so the manifest is the inventory, not search.

## Running it

### The token

Everything runs on one credential, stored as the **`MIRROR_TOKEN`** organisation
secret (visibility: selected → `tooling` only).

Create a **fine-grained personal access token** with:

| Setting | Value |
|---|---|
| **Resource owner** | **`ie-gov-mirror`** — not your personal account |
| **Repository access** | All repositories |

**Repository permissions**

| Permission | Level | Why |
|---|---|---|
| Administration | **Read and write** | Create repositories; set default branch, topics and homepage; archive tombstoned mirrors; **toggle visibility** for the push-protection workaround below |
| Contents | **Read and write** | Push git objects, branches and tags |
| Workflows | **Read and write** | Mandatory — any push touching `.github/workflows/*` is rejected without it, and many mirrored repositories contain workflow files |
| Metadata | Read | Mandatory, auto-enabled |
| Actions | **Read and write** | Only if you want runs triggered via the API (`workflow_dispatch`, re-run). **Read alone is not enough** — dispatch returns `403 Resource not accessible by personal access token`. Not needed for the mirroring itself |

**Organisation permissions**

| Permission | Level | Why |
|---|---|---|
| Administration | **Read and write** | Organisation profile, `default_repository_permission`, and the Actions policy |
| Secrets | **Read and write** | Managing `MIRROR_TOKEN` itself |

Not needed: **`Pull requests`** — new repositories in verified namespaces are
auto-accepted and committed directly, so there is no review PR.

Three things worth knowing before you create it:

- **The organisation may need to approve the token.** If `ie-gov-mirror` has
  personal-access-token restrictions enabled, a fine-grained token sits pending
  until an owner approves it, and until then it returns 403 in a way
  indistinguishable from a missing permission.
- **`Administration: write` is load-bearing for more than repo creation.**
  GitHub enforces secret-scanning push protection on public repositories at a
  level a free-plan organisation cannot disable, so `sync_repo.sh` pushes such
  repositories while private and restores visibility afterwards. That needs
  visibility control.
- **Actions' built-in `GITHUB_TOKEN` cannot substitute.** It is repository
  scoped with no organisation administration, so it cannot create repositories.

Migrating to an org-owned GitHub App is planned; see
[`docs/EXECUTION-PLAN.md`](docs/EXECUTION-PLAN.md) §3.5 for the trade-off.

```bash
# What has drifted from the manifest?
GH_TOKEN=... python scripts/enumerate.py --report

# Mirror one repository (tier controls labelling: core | extended)
GH_TOKEN=... MIRROR_ORG=ie-gov-mirror \
  scripts/sync_repo.sh https://github.com/CSOIreland/PxStat.git CSOIreland.PxStat master core

# Check for upstreams that have disappeared (never deletes anything)
GH_TOKEN=... python scripts/tombstone.py --check-all --dry-run
```

Backfill runs from the Actions tab, one namespace at a time, `dry_run: true`
first.

## Two things not to get wrong

- **Actions must be disabled org-wide**, allowlisting only this repo. Mirrored
  repositories contain their own `.github/workflows/*` with `on: push`
  triggers, which would otherwise execute in the mirror org on every sync.
- **Secret scanning must be off** for the mirror org — push protection would
  block the backfill on the first secret pattern in upstream history. Alerts
  are off too, so there is no proactive signal for credentials in mirrored
  history; [`POLICY.md`](POLICY.md) commits only to a reactive process.

## Repositories that vanished upstream

[`docs/DELETED.md`](docs/DELETED.md) lists tracked repositories that no longer
exist upstream but are still readable here. It is generated from
`manifest/tombstones.csv`, so it cannot drift from the data.

## Related

- [uk-gov-mirror](https://github.com/uk-gov-mirror) — the model for this
  archive, 26,416 UK public-sector repositories.
- [legalize-dev/legalize-ie](https://github.com/legalize-dev/legalize-ie) — a
  git-native mirror of official Irish legislation. Independent derivative, not
  government code, not mirrored here.
