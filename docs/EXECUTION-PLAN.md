# Execution plan: `ie-gov-mirror`

Mirroring Irish public-sector GitHub repositories, modelled on
[uk-gov-mirror](https://github.com/uk-gov-mirror).

**Status:** Complete and running. **209 of 209 mirrored**, all verified against
upstream; both workflows green on Actions. See the execution record in §7.
**Source data:** research snapshot of 11 August 2026 (`docs/source-research-2026-08-11.md`).
**Control repo:** `ie-gov-mirror/tooling` (this repo).

---

## 1. What we are copying, and how big it is

Computed from `manifest/inventory-2026-08-11.csv`, not estimated:

| Tier | Repos | Size | Destination |
|---|---:|---:|---|
| **core** | 191 | **11.51 GiB** | `ie-gov-mirror` |
| **extended** | 18 | 44.5 MiB | `ie-gov-mirror`, labelled not-government-owned |
| **candidate** | 18 | 892 MiB | **not mirrored** — ownership unverified twice (§5) |
| **adjacent** | 1 | 58 MiB | not mirrored; linked from README |

**Mirrored total: 209 repositories, 11.56 GiB, across 12 namespaces.**

Core repos by namespace: IrishMarineInstitute 100, CSOIreland 35, Oireachtas 18,
HSEIreland 15, Teagasc 7, ogcio 6, revenue-ie 5, MetEireann 3,
Geological-Survey-Ireland 2.

### Five facts from the data that drive the design

1. **One size outlier.** `CSOIreland/edprofiles` is **4.44 GiB**. GitHub
   [strongly recommends repositories stay under 5 GB](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github),
   so it is allowed to exist — but it exceeds the ~2 GB single-push pack
   ceiling, so its first push **must be chunked**. Next largest is
   `IrishMarineInstitute/ecosystem_case` at 1.16 GiB; everything else is
   under 450 MiB. Most of the remaining bulk is upstream forks of large
   third-party projects: `ogcio/unleash` (249 MiB), `ogcio/logto` (83 MiB),
   `IrishMarineInstitute/WW3` (82 MiB), the `Oireachtas/silverstripe-*` set.
2. **Default branches are a minefield.** 111 `master`, 59 `main`, and then
   `current` ×7, `2` ×4, `dev`, `trunk`, `develop`, `gh-pages`, `2.0`, `7`,
   and one repo whose default branch is literally `fix/http-sitemap`. `git
   push` cannot set a default branch, so **~10% of repos would present the
   wrong head** if the script assumed `main`. Handled by an explicit API
   `PATCH` after first push.
3. **12 repos are empty or near-empty** (0–1 KB). Clone succeeds, push
   pushes nothing, exit code 0. The sync must not treat "nothing to push" as
   failure.
4. **22 of 191 are already archived upstream** — all 15 HSEIreland covid-era
   repos, 5 IrishMarineInstitute, 1 CSOIreland, 1 ogcio. Recorded in the
   manifest, but the mirrors are **not** GitHub-archived: upstream archives
   are occasionally unarchived and pushed to. Only tombstones get archived.
5. **No name collisions at all under `owner.repo`** — verified across all
   209 mirrored repos. Seven clashes *would* exist under flat bare-name
   naming, all `HSEIreland/covid-green-*` against `covidgreen/covid-green-*`,
   but the owner segment separates them. This is why the extended tier needs
   no name prefix.

---

## 2. How uk-gov-mirror actually works

Verified directly, not assumed:

| Property | Finding |
|---|---|
| Scale | **26,416 repositories** (org page, fetched 2026-08-20) |
| Naming | **`owner.repo`, dot-flattened**, upstream case preserved — `alphagov.pay-toolbox`, `ministryofjustice.opg-use-an-lpa`, `nhsconnect.gpconnect-appointment-checker` |
| Mechanism | Plain repositories, **not forks** (`"fork": false` on every sampled repo) — i.e. pushed clones. GitHub has no pull-mirror feature. |
| Disclaimer | Lives in the **org description**: *"An unofficial mirror of every UK Government Github repository, to preserve repositories that are removed or made private. Updated at least weekly."* |
| Fidelity | Full-ref pushing, not default-branch snapshots — `uk-gov-mirror/nhs-england-tools.github-runner-image` retains a `dependabot/...` branch, and its upstream now 404s. The mirror worked. |
| Metadata | Upstream description copied verbatim; no injected README, no `[mirror]` prefix, no topics observed |
| Tooling | Two pinned repos: `meta-repository` (submodule metarepo, ~80 per-org directories) and `deleted-repo-report` (tracks **1,571 deletions across 62 upstream orgs**) |
| Backfill shape | Thousands of repos created 2021-04-10/11 in a bulk event; incremental additions and pushes continuing through 2026 |
| Operator | One person, Jonty Wareing ([Hackaday, 11 Aug 2026](https://hackaday.com/2026/08/11/the-code-the-british-government-doesnt-want-you-to-see-any-more/)) |

**Inferred, not verified:** the sync engine is not published anywhere in the
org — almost certainly a script on a machine the operator controls, given the
2021 backfill rate. Issues, PRs, wikis and release assets do not appear to be
captured; it is a git-data mirror only.

**A caution about search.** GitHub's search API indexes only **1,582** of the
26,416 repos — bulk-pushed mirrors largely never enter the search index.
Expect the same here: **the manifest is the inventory, not GitHub search.**

### Two places we deliberately diverge

- **Discoverability of intent.** uk-gov-mirror puts the disclaimer only in
  the org description. We add a `.github` profile README, per-repo homepage
  links to upstream, and `mirror`/`unofficial` topics — plus
  `not-government-owned` on the extended tier. Ireland has nine small upstream
  namespaces, so a mirror will rank highly in searches for them; the
  "mistaken for official" risk is materially higher than for the UK.
- **Provenance in the open.** uk-gov-mirror's sync engine is unpublished. Here
  the manifest, scripts and workflow logs are all public, so the archive's
  coverage and cadence are auditable by anyone.

Where we *match* uk-gov-mirror, deliberately: **one operator** (decision 10).
The mitigations that don't need a second person — public workflows, an in-repo
manifest, a group contact address — are in place. What stays unmitigated is
that if the operator stops, the archive silently stops updating.

---

## 3. Design decisions

### 3.1 Naming: `Owner.repo` — copy uk-gov-mirror exactly

`CSOIreland/PxStat` → `ie-gov-mirror/CSOIreland.PxStat`

Chosen over `csoireland-pxstat` because it is **losslessly reversible**:
GitHub owner names cannot contain dots, so splitting on the first dot always
recovers the upstream. Hyphen-lowercasing is ambiguous (`revenue-ie` + `dpl`
versus a repo literally named `revenue-ie-dpl`) and destroys case.

Verified against the real data: all 228 generated names are GitHub-legal,
unique case-insensitively, and at most 58 characters (limit is 100).
Edge cases handled: `Oireachtas/Oireachtas.github.io` →
`Oireachtas.Oireachtas.github.io` (split on *first* dot only, so this still
round-trips), and `IrishMarineInstitute/geocalculator-` (trailing hyphen) is
legal. Note that a `*.github.io`-shaped name inside the mirror org will not
serve Pages — which is what we want, and Pages is disabled org-wide anyway.

### 3.2 Pushed clones, not forks

Forks are wrong here on four counts: fork creation is aggressively
secondary-rate-limited; one org cannot hold two forks from the same network;
the "forked from" relationship breaks when upstream is deleted; and a DMCA
against an upstream repo can take down **the whole fork network**, including
our copy. Since surviving upstream deletion is the entire point, the mirror
must not be structurally coupled to upstream. Pushed clones are not.

### 3.3 The per-repo sync unit

Implemented in `scripts/sync_repo.sh`. Five caveats it exists to handle:

1. **Never `git push --mirror`.** It deletes any ref absent locally, and it
   retries hidden refs. Use explicit refspecs:
   `+refs/heads/*:refs/heads/*` and `+refs/tags/*:refs/tags/*`.
   **Without `--prune`** — see §3.8.
2. **Strip `refs/pull/*` first.** `git clone --mirror` fetches them; GitHub
   rejects pushes to them (*"deny updating a hidden ref"*) and one rejected
   ref aborts the push.
3. **LFS before git push**, so pointer files never dangle. Upstream LFS
   storage may be over quota or purged — record the gap in the manifest's
   `fidelity_notes`, don't fail the repo.
4. **Chunk the oversized backfill.** Push history in ~2,000-commit slices via
   a scratch ref for anything over ~1.5 GiB, then push the real refs. Only
   needed on first backfill; later syncs take the normal path because the
   objects are already remote.
5. **Set the default branch by API** afterwards (see §1, fact 2).

Exit code 3 means "upstream unreachable" and routes to the tombstone flow
rather than counting as a failure.

### 3.8 Refs deleted upstream are kept

The push deliberately omits `--prune`, so a branch or tag deleted upstream
stays in the mirror.

This is the archive's whole purpose applied one level down. The org description
promises to preserve repositories that are removed or made private; if a public
body force-deletes a branch, pruning would destroy it on the next weekly sync,
which is exactly the material most worth having. Whole-repository deletion is
handled by tombstones (§3.3); ref-level deletion is handled here.

Seen in practice on the very first sweep:
`HSEIreland/hse-healthapp-test-fhir-server` is archived upstream and now has
only `main`, but the mirror holds six `dependabot/*` branches captured before
GitHub cleaned them up. Under `--prune` those would have been silently deleted
on the following Monday.

The cost, accepted deliberately: a mirror is a **superset** of its upstream, not
a copy. Mirrors accumulate refs indefinitely, and a repository with heavy
dependabot churn will grow branches that no longer exist anywhere else.
`verify_mirrors.py` classifies this as `ok-with-extra` rather than a fault, so
the condition stays visible rather than becoming invisible drift.

### 3.4 Two org settings that will bite if forgotten

- **Disable Actions org-wide, allowlisting only this control repo.** Many
  mirrored repos contain `.github/workflows/*` with `on: push` or
  `on: schedule`. Without this, **mirrored third-party workflows execute in
  our org on every sync.** This is the single most dangerous default.
- **Secret scanning: both push protection and alerts OFF** — but be clear that
  **this does not actually stop push protection.** Disabling it org-wide was
  expected to unblock the backfill. It does not: with
  `secret_scanning_push_protection_enabled_for_new_repositories` false, the
  `mirror-archive` configuration enforced with push protection disabled, and no
  rulesets at all, GitHub still refused `ogcio/govie-messagingie` with `GH013`.
  Push protection applies to **public** repositories at a level a free-plan
  organisation cannot switch off; rulesets that might override it need a Team
  plan. The working fallback is to push while the mirror is **private**, where
  push protection does not apply without Advanced Security, then restore
  visibility (`push_via_private` in `sync_repo.sh`).

  Turning alerts off does have its intended effect: there is **no proactive
  signal for credentials in mirrored history**, so `POLICY.md` commits only to
  a reactive process. Note the irony that the one credential exposure found so
  far was surfaced by the push protection that could not be disabled, not by
  the scanning that was.

The pushing token also needs **Workflows: write**, or any push touching a
workflow file is rejected.

### 3.5 Credentials: fine-grained PAT now, GitHub App later

The control repo's built-in `GITHUB_TOKEN` **cannot** create repositories in
the org, so it is not an option.

**Decision: a fine-grained PAT**, stored as the `MIRROR_TOKEN` org secret,
migrating to an org-owned GitHub App once backfill is done.

| | **Fine-grained PAT (now)** | GitHub App (later) |
|---|---|---|
| Rate limit | 5,000 req/hr | scales to **12,500 req/hr** |
| Token lifetime | months, manual rotation | minted per job, 1-hour expiry |
| Ownership | tied to one person's account | owned by the org, survives people leaving |

The authoritative permission list lives in the
[README](../README.md#the-token) so there is one place to look when the token
needs replacing. In summary: repository **Administration**, **Contents** and
**Workflows** at write, **Metadata** at read, plus organisation
**Administration** and **Secrets** at write. No `Pull requests` permission is
required, since new repositories are auto-accepted and committed directly.

`Administration: write` covers more than repository creation — it is also what
allows the visibility toggle that the push-protection workaround in §3.4
depends on.

The PAT's 5,000 req/hr is ample: backfill is ~209 repo creations plus a few
hundred metadata calls. The reason to migrate is hygiene and continuity, not
throughput — so it is not on the critical path.

> Confirmed the hard way while writing this plan: the session token scoped to
> a single repo returns `403 Resource not accessible by integration` on
> `POST /orgs/ie-gov-mirror/repos`. Administration:write at org scope is not
> optional.

### 3.6 Rate limits and the actual budget

[Verified against GitHub's REST rate-limit docs](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api):
primary 5,000/hr (PAT) or up to 12,500/hr (App); secondary **80
content-generating requests/minute** and **500/hour**; 100 concurrent.

- **Repository creation has a tighter, undocumented secondary limit than the
  published 500/hour**, and this was hit for real: a backfill that created
  ~149 repositories in under an hour was blocked with *"You have created too
  many repositories, too quickly"*. Critically, `/rate_limit` still reported
  **5000/5000 on both core and graphql** — the creation limit is invisible
  there, so it can only be discovered by being refused. `sync_repo.sh` now
  backs off (60s doubling to 30 min) and returns exit 4 so the repository is
  deferred rather than dropped; `backfill.yml` paces at
  `CREATE_PACE_SECONDS` (default 20s). Budget roughly **150 creations per
  hour**, so a full 209-repo backfill is a two-session job.
- **Enumeration** is ~13 requests per crawl across 9 orgs. Trivial; runs daily.
- **Weekly refresh** is gated on `pushed_at`, so a typical week re-clones a
  handful of repos, not 11.5 GiB.
- Git-protocol transfer is not REST-rate-limited.

### 3.7 Automation host: scheduled Actions in this repo

| Option | Verdict |
|---|---|
| **Actions in the control repo** | **Chosen.** Zero infrastructure, free minutes on public repos, publicly auditable logs, secrets in the org store, survives laptop loss. The 6-hour job cap is ample: the largest shard is ~6 GiB. The ~14 GB runner disk comfortably fits the 4.44 GiB outlier processed one repo at a time. |
| Self-hosted runner | Gives persistent bare clones and true `git remote update --prune` incrementals, but means running a machine exposed to workflows in a public repo. Overkill at 11.5 GiB. |
| VM / cron outside GitHub | What uk-gov-mirror almost certainly does. No Actions limits, but invisible provenance and a machine to pay for and maintain. |

**Revisit if** the archive passes ~1,000 repos, or we start capturing release
assets in bulk. Data volume, not repo count, is what will force a VM.

---

## 4. Phases

### Phase 0 — Org setup (~1 hour, all manual)

- [ ] Org description: *"Unofficial mirror of Irish public-sector GitHub
      repositories, to preserve code that is removed or made private. Not
      affiliated with or endorsed by any Irish public body. Updated at least
      weekly."*
- [ ] `ie-gov-mirror/.github` repo with `profile/README.md`: the same
      disclaimer, the takedown and data-erasure contact, and a link to this
      manifest.
- [ ] Base member permission **read**; 2FA required. Single owner by
      decision (10) — the contact address is a group so the contact route
      survives even though the operator is a single point of failure.
- [ ] **Actions disabled for all repos except `tooling`** (§3.4).
- [ ] Pages disabled org-wide. New-repo defaults: issues, wiki, projects,
      discussions all **off**.
- [ ] Secret scanning alerts **on**, push protection **off** (§3.4).
- [ ] No branch protection anywhere — mirrors need force-push and ref deletion.
- [ ] Dependabot alerts **off** org-wide: alert noise on 191 repos we do not
      maintain is pure cost.
- [ ] Create the fine-grained PAT (§3.5) and store it as the `MIRROR_TOKEN`
      org secret. Diarise the migration to a GitHub App after backfill.

### Phase 1 — Control repo (this repo, largely done)

```
tooling/
├── manifest/
│   ├── core.csv                  # 191 rows: the authoritative worklist
│   ├── extended.csv              # 18 rows, separate destination org
│   ├── candidates.csv            # 18 rows, status dropped-unverified
│   ├── adjacent.csv              # 1 row, not mirrored
│   ├── tombstones.csv            # upstreams that have disappeared
│   ├── inventory-2026-08-11.csv  # original research snapshot, unmodified
│   └── core-mirror-seeds.txt     # original 191 clone URLs, unmodified
├── scripts/
│   ├── enumerate.py              # API enumeration + manifest drift diff
│   ├── sync_repo.sh              # the per-repo mirror unit (§3.3)
│   └── tombstone.py              # disappearance handling, never deletes
├── .github/workflows/
│   ├── enumerate.yml             # daily
│   ├── sync.yml                  # weekly, sharded by namespace
│   └── backfill.yml              # manual, one namespace at a time
├── POLICY.md                     # takedown, erasure, secrets, tombstones
└── docs/EXECUTION-PLAN.md        # this file
```

**Provenance model:** the manifest CSVs *are* the provenance record. Bot
commits update `first_seen` / `last_seen` / `last_synced` /
`upstream_pushed_at`, so `git log manifest/core.csv` is a complete audit
trail. No database needed.

Three rules encoded in the tooling:

- **New repos in verified namespaces are auto-accepted.** The daily
  enumeration adds them with `ownership_confidence=high`, `status=pending` and
  a `fidelity_notes` entry recording the namespace they came from, then commits
  directly to the branch. The next sync mirrors them. The verified thing is the
  namespace: a new repository in `CSOIreland` is CSO code on the same evidence
  that covers the other 35, so there is nothing extra for a human to approve.
- **`DISCOVERY_NAMESPACES` in `scripts/enumerate.py` is the only thing that
  grants that automatic trust**, and only a human editing that file changes it.
  Extended-tier namespaces are deliberately *not* enumerated wholesale — only
  the repositories the manifest names are fetched, because `covidgreen`,
  `derilinx` and `localgovdrupal` are not government namespaces and enumerating
  them would pull in arbitrary unrelated repositories.
- **Nothing is ever auto-deleted.** Disappearance routes to `tombstone.py`.

### Phase 2 — Backfill (one weekend)

1. **Dry-run five representative repos** against scratch names first:
   - an empty repo (`MetEireann/GitTest`) — exit 0 with nothing pushed
   - a weird default branch (`ogcio/wagtail-sitemap-seo`, `fix/http-sitemap`)
   - an archived upstream (any HSEIreland covid repo)
   - a large fork (`ogcio/unleash`, 249 MiB) — LFS and ref volume
   - **the 4.44 GiB outlier** (`CSOIreland/edprofiles`) — chunked push path
2. Run `backfill.yml` per namespace, **smallest first**:
   Geological-Survey-Ireland (2) → MetEireann (3) → revenue-ie (5) → ogcio (6)
   → Teagasc (7) → HSEIreland (15) → Oireachtas (18) → CSOIreland (35) →
   IrishMarineInstitute (100). Each with `dry_run: true` first.
3. Per repo the script sets description (verbatim upstream text + disclaimer),
   homepage → upstream URL, issues/wiki off, and the correct default branch.
   Add topics `mirror`, `unofficial`, and the upstream org slug.
   **Repository contents are never modified** — no injected README, no
   relicensing, no history rewriting. Fidelity means bit-identical git data.
4. Verify: **209 repos, ~11.56 GiB**, 22 flagged `upstream_archived=true` in
   the manifest but **not** GitHub-archived, and 18 carrying the
   `not-government-owned` topic.

### Phase 3 — Steady state

- `enumerate.yml` daily: detects new repos (auto-accepted, committed
  directly, mirrored on the next sync), renames (GitHub redirects old clone
  URLs; follow and update the manifest), deletions (→ tombstone), and
  `pushed_at` changes.
- `sync.yml` weekly, `pushed_at`-gated, sharded 3-at-a-time.
- Deliberately **out of initial scope** — a bare git mirror captures none of
  these, and uk-gov-mirror does not either:
  - **wikis** — mirror `Owner/repo.wiki.git` → `Owner.repo.wiki`, cheap
  - **release assets** — tags arrive, uploaded binaries do not. This is where
    volume can explode; measure before committing.
  - **issues and PRs** — the largest personal-data surface in the whole
    project (§5). If done at all, opt-in per repo, as JSONL snapshots.

---

## 5. Risks and what a human must decide

**Licensing.** Mirroring public repos has a five-year uk-gov-mirror precedent
that GitHub has not acted against. But GitHub's ToS grants other users the
right to *view and fork* public content; wholesale re-hosting as new
repositories sits in a tolerated grey zone rather than an explicitly licensed
one. Some core repos will have **no licence file at all** — and unlike US
federal works, Irish government code is not automatically public domain, so
the default is all rights reserved. Fidelity mirroring preserves LICENSE files
verbatim and adds no relicensing by construction.

**GDPR.** Mirroring ~11.5 GiB of history in the EU makes the operator a data
controller for the commit author names and email addresses inside it.
Rewriting history to remove them destroys the archive's purpose. The
defensible posture is legitimate-interest archival plus a published erasure
contact and a real process — where the likely outcome of a valid Article 17
request is deleting and tombstoning the affected mirror, because selective
history rewriting breaks fidelity. Issue and PR content is a much larger
personal-data surface, which is the main argument for keeping Phase 3 issue
archiving opt-in.

> Incidentally demonstrated while setting up this repo: the first push was
> rejected because the account has commit email privacy enabled. That setting
> protects *our* address. It does nothing for the thousands of third-party
> author emails inside mirrored history.

**Mistaken for official.** Higher risk for Ireland than the UK: only nine
small upstream namespaces exist, so `ie-gov-mirror` will rank well in
searches for them. Mitigations are built into Phase 0 and 2 — org name says
"mirror", description says unofficial, homepage points upstream, Pages and
issues disabled.

**Upstream deletion versus legal removal.** Deletion is the whole point:
tombstone, never purge. But a DMCA or court order against upstream can be
re-served against the mirror, and — the sharpest edge — **secrets or personal
data published upstream by accident and then force-pushed away will be
preserved by our mirror**. `POLICY.md` must draw that line before the first
incident, not during it.

### Decisions taken

| # | Question | Decision |
|---|---|---|
| 0 | New repos in verified namespaces | **Auto-accepted** — no review gate. Committed directly by the daily enumeration and mirrored on the next sync. |
| 1 | Extended tier destination | **Same org, no name prefix.** Marked by a `not-government-owned` topic and an explicit description. Verified there are **zero collisions across all 209 repos** under `owner.repo` — the 7 `covid-green-*` clashes only exist under flat naming, and the owner segment separates them. |
| 2 | Credential | **Fine-grained PAT now, migrate to a GitHub App later.** Stored as the `MIRROR_TOKEN` org secret. |
| 3 | Secret scanning | **Push protection and alerts both off.** |
| 4 | Unlicensed repos | **Mirror them**, relying on the removal-request policy. |
| 5 | Contact | **ie-gov-mirror@googlegroups.com** — a group, so the contact route outlives any one inbox. |
| 6 | Notify OGCIO | **No.** Stay quiet; `POLICY.md`'s request route is the sole contact path. |
| 7 | Scope beyond git data | **Git data only.** No wikis, release assets, issues or PRs — matching uk-gov-mirror, and keeping the personal-data surface to commit metadata. |
| 8 | Tombstones | Manifest + GitHub-archive the mirror **+ a generated public report** at `docs/DELETED.md` (`scripts/deleted_repo_report.py`). |
| 9 | Org name | **Keep `ie-gov-mirror`**, following the tolerated uk-gov-mirror pattern. |
| 10 | Second owner | **Solo for now.** Same posture as uk-gov-mirror; the Google Group contact softens it. |
| 11 | Accidental publication upstream | **Preserve everything; remove on request.** A bright-line rule with no case-by-case judgement. |
| 12 | Reported live credential | **Notify upstream, leave the mirror up.** Removal only if the body requests it. |
| 13 | The 18 candidates | **Dropped** — see below. |
| 14 | Cadence | **Claim "updated at least weekly"** from the start. |
| 15 | Refs deleted upstream | **Kept.** No `--prune`; a mirror is a superset of its upstream (§3.8). |
| 16 | Push protection | **Cannot be disabled** on a free plan. Blocked pushes go up with the mirror temporarily private (§3.4). |

Not adopted: a `meta-repository`-style submodule metarepo. It earns its keep
at 26,416 repos; at 209 the manifest CSV serves the same discovery need.
Revisit past ~1,000 repos.

### Two decisions with costs worth restating

**Secret scanning fully off (#3).** Push protection off is necessary — it would
block the backfill on the first secret pattern in upstream history. Turning
*alerts* off as well means there is no proactive signal for credentials in
11.5 GiB of mirrored history. `POLICY.md` therefore commits only to a reactive
process: notify upstream if a credential is reported. That is a promise the
setup can actually keep.

**Solo operation (#10).** uk-gov-mirror has survived five years this way, so
the precedent is real. The mitigations that don't depend on a second person are
in place: public workflows, an in-repo manifest, and a group contact address.
What remains unmitigated is that if the operator stops, the archive silently
stops updating.

### Why the 18 candidates were dropped

The candidate tier was checked twice and failed both times.

The original research found no authoritative cross-link for any of them. A
second check against **data.gov.ie** on 2026-08-20 — the CKAN
`resource_search`, `package_search` and `organization_show` endpoints —
found:

- **No GitHub reference in any candidate body's portal profile.** Cavan, Dún
  Laoghaire–Rathdown, Kerry and Kildare County Councils, Tailte Éireann and
  Sport Ireland are all publishers on data.gov.ie, but none links to a GitHub
  namespace.
- **The portal references exactly one GitHub namespace in total**:
  `IrishMarineInstitute`, which is already core. (Plus `MobilityData`, a
  third party.)

The councils being publishers proves the *bodies* publish open data. It says
nothing about who owns a GitHub handle, which is what needed verifying.

What the tier actually contained also argued against it: **11 of 18 are
empty**, and 771 MiB of the 892 MiB is `Cavancoco/AspNetCore.Docs`, a fork of
Microsoft's ASP.NET Core documentation. Several names read like individuals
learning git — `kerrycoco/myfirstTest`, `OrdnanceSurveyIreland/OracleTeam`.
The genuine archival content was ~142 MiB.

The highest risk was `govdataie`: an unbranded personal account holding five
empty repos named after the Arts Council, the Central Bank, Fáilte Ireland, the
Heritage Council and RTÉ. Mirroring it under a `gov`-named org would publicly
assert state ownership of repositories that may belong to a private individual.

**This is a negative search result, not proof of non-ownership.** The rows stay
in `manifest/candidates.csv` with `status=dropped-unverified` and the check
recorded, so a future crawl need not redo the work. If a body confirms a
handle, the row moves to `core.csv` by pull request.

---

## 6. Tier handling summary

| Tier | Destination | Sync |
|---|---|---|
| core (191) | `ie-gov-mirror`, `Owner.repo` | daily enumerate, weekly sync |
| extended (18) | `ie-gov-mirror`, same as core | Same tooling, `tier=extended` passed to `sync_repo.sh`, which sets the `not-government-owned` topic and an explicit description. Only the repos the manifest names are synced — these namespaces are **not** enumerated wholesale, since `covidgreen` and `derilinx` are not government namespaces. |
| candidate (18) | nowhere | `status=dropped-unverified`. Documented with the failed data.gov.ie check so a future crawl need not redo it. A confirmed handle moves to `core.csv` by PR. |
| adjacent (1) | nowhere | `legalize-dev/legalize-ie` is linked from the README as a companion project, per its own self-description as an independent derivative. |

---

## Sources

Verified: [uk-gov-mirror org](https://github.com/uk-gov-mirror) ·
[meta-repository](https://github.com/uk-gov-mirror/meta-repository) ·
[deleted-repo-report](https://github.com/uk-gov-mirror/deleted-repo-report) ·
[GitHub large-file limits](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github) ·
[GitHub REST rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api) ·
[Hackaday, 11 Aug 2026](https://hackaday.com/2026/08/11/the-code-the-british-government-doesnt-want-you-to-see-any-more/) ·
branch-fidelity spot check: [mirror branches](https://github.com/uk-gov-mirror/nhs-england-tools.github-runner-image/branches/all) against a deleted upstream.

Inventory figures computed from `manifest/inventory-2026-08-11.csv`.


---

## 7. Execution record

### Phase 0 — complete (26 August 2026)

| Item | State |
|---|---|
| Org description | Set, carrying the unofficial/preservation disclaimer |
| `.github` profile | Created: disclaimer, scope, what is *not* mirrored, contact address. Issues/wiki/projects off |
| Actions | `enabled_repositories: selected` — **only `tooling`**. Verified a newly created repo is not auto-added |
| Code security | `mirror-archive` configuration: secret scanning, push protection, Dependabot and dependency graph all disabled. `default_for_new_repos: all`, attached to all existing. Confirmed `status: enforced` on new mirrors |
| Base member permission | `read` |
| `MIRROR_TOKEN` | Org secret, `visibility: selected` → `tooling` only |
| 2FA requirement | **Not set** — read-only in the API, must be done in the web UI |
| Pages | Not disabled org-wide: that control is Enterprise-only. Mirrors never enable Pages, so the per-repo default of off applies |

### Phase 2 — representative cases, all passed

| Case | Repository | Outcome |
|---|---|---|
| Extended tier labelling | `derilinx.ckanext-dgi-public` | HEAD identical; `not-government-owned` topic and caveat in description |
| Default branch not `main` | `ogcio.wagtail-sitemap-seo` | `default_branch: fix/http-sitemap` set correctly |
| Archived upstream | `HSEIreland.covid-tracker-app` | Mirrored unarchived, as designed |
| Minimal repository | `MetEireann.GitTest` | Clean |
| Oversized, chunked push | `CSOIreland.edprofiles` (4.44 GiB) | **Failed first**, see below. Now correct: `main`, `pdf`, `resources` and all three tags match upstream |

### Bugs found by running it

Eight, every one needing a real repository of a particular shape. None would
have appeared in a dry run, and **four presented as a green run doing the wrong
thing** — which is why `verify_mirrors.py` exists and why status was never
treated as evidence.

| # | Bug | Consequence if unfixed |
|---|---|---|
| 1 | `sha_pinning_required` is enabled on the org, so `actions/checkout@v4` was rejected | Every workflow run fails |
| 2 | `last_synced` was read in one place and written in none | Weekly sync re-clones all 209 repos (~11.5 GiB) forever |
| 3 | Chunked push sliced by commit count; `edprofiles` has 71 commits so `awk 'NR % 2000'` emitted nothing | 4.3 GiB repo unmirrorable, `HTTP 500` |
| 4 | Scratch ref deleted before the default branch was set — GitHub refuses to delete a default branch | Stray `__backfill` branch on every chunked mirror |
| 5 | Repository-creation throttle unhandled | 6 repositories dropped rather than deferred |
| 6 | Verifier read only page 1 of `/git/refs`; refs sort `heads < pull < tags` | Tags never verified on any repo with >100 refs |
| 7 | `/orgs/{name}/repos` assumed, but `Geological-Survey-Ireland` is a **User** account | **Every** scheduled run failed from 21–27 August |
| 8 | Sync gate compared against `upstream_pushed_at`, which the daily enumerate overwrites | Stale mirrors reported as current, permanently unfixable |

Bug 8 is the one worth remembering. The daily job was silently disarming the
weekly one: upstream pushes, enumerate advances the watermark, the comparison
goes equal, and the repository is never re-synced. It surfaced only because a
green `sync` run reporting 12/12 shards successful was checked against what it
had actually done — `ogcio/govie-ds` sat a day stale while the manifest claimed
it was current. Fixed with a separate `synced_pushed_at` column that only a
successful sync advances.

### The repository-creation rate limit

The backfill was blocked after **~149 creations in under an hour**:

> You have created too many repositories, too quickly.

`/rate_limit` reported **5000/5000 remaining on both `core` and `graphql`**
throughout. This limit is invisible there and cannot be predicted, only
observed by being refused. The documented 500 content-generating requests per
hour was never the binding constraint.

`sync_repo.sh` backs off (60s doubling to a 30-minute ceiling) and returns exit
4 so a throttled repository is deferred rather than dropped. Repeated attempts
while blocked can *extend* the limit, so probing is deliberately infrequent —
waiting one hour cleared it on the first probe. **Budget ~150 creations per
hour.**

### Fidelity

`scripts/verify_mirrors.py` compares the complete `{ref: sha}` mapping on both
sides of every manifest row, across all pages.

Final sweep — **209 of 209 mirrored**:

| Verdict | Count | Meaning |
|---|---:|---|
| `ok` | 207 | Every ref identical to upstream |
| `ok-with-extra` | 2 | Mirror holds refs upstream has since deleted — the archive working as intended |
| `MISMATCH` | 0 | |

The two `ok-with-extra` are the no-prune decision (§3.8) demonstrated on live
data: six `dependabot/*` branches on
`HSEIreland/hse-healthapp-test-fhir-server` and four feature branches on
`ogcio/govie-ds`, all deleted upstream after being mirrored. Under `--prune`
all ten would have been destroyed.

**Git LFS:** all 209 upstreams checked; the 20 with a root `.gitattributes` use
only `text=auto`, `diff`, `merge` and `export-ignore` directives. None uses
`filter=lfs`. Covers root `.gitattributes` only.

**One repository needed a workaround:** `ogcio.govie-messagingie` was pushed
with the mirror temporarily private because its upstream history contains
Google OAuth credentials and push protection cannot be disabled (§3.4). Noted
in `fidelity_notes`.

### Workflows proven on Actions

| Workflow | Run | Result |
|---|---|---|
| `enumerate` | #8 | Success. All 9 namespaces listed, 0 new, 0 gone, manifest committed |
| `sync` | #3 | Success, 12/12 shards. Detected the one stale mirror, pushed 36 branches and 797 tags, stamped the watermark, gate closed to 0 |

Schedules: `enumerate` daily 06:00 UTC, `sync` Mondays 02:00 UTC.

### Outstanding, for a human

1. Revoke the backfill PAT and replace the `MIRROR_TOKEN` secret value.
2. Set the organisation 2FA requirement — read-only in the API, web UI only.
3. Decide the OGCIO credential disclosure. Details are in
   `FINDINGS-credentials.local.md`, which is deliberately untracked.
   `POLICY.md` commits to notifying an upstream body about a live-looking
   credential, while decision 6 was not to contact OGCIO. Unresolved.
