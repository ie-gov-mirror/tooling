# Irish government open-source repository inventory

Research snapshot: **11 August 2026**

## Result

This sweep found **191 high-confidence repositories across 9 verified Irish public-sector GitHub namespaces**. It also found **18 project-related repositories** in partner or vendor namespaces, **18 quarantined candidates** that need ownership confirmation, and **1 useful independent companion repository**.

The core seed file contains only high-confidence repositories. The CSV contains every tier and the evidence used for classification.

## Core mirror: verified namespaces

| Public body | GitHub namespace | Public repos | Archived | Primary evidence |
|---|---:|---:|---:|---|
| Marine Institute | [IrishMarineInstitute](https://github.com/IrishMarineInstitute) | 100 | 5 | [evidence](https://github.com/IrishMarineInstitute/digital-stockbook) |
| Central Statistics Office | [CSOIreland](https://github.com/CSOIreland) | 35 | 1 | [evidence](https://github.com/CSOIreland) |
| Houses of the Oireachtas | [Oireachtas](https://github.com/Oireachtas) | 18 | 0 | [evidence](https://github.com/Oireachtas) |
| Health Service Executive | [HSEIreland](https://github.com/HSEIreland) | 15 | 15 | [evidence](https://government.github.com/community/) |
| Teagasc | [Teagasc](https://github.com/Teagasc) | 7 | 0 | [evidence](https://github.com/Teagasc) |
| Office of the Government Chief Information Officer | [ogcio](https://github.com/ogcio) | 6 | 1 | [evidence](https://government.github.com/community/) |
| Office of the Revenue Commissioners | [revenue-ie](https://github.com/revenue-ie) | 5 | 0 | [evidence](https://github.com/revenue-ie) |
| Met Éireann | [MetEireann](https://github.com/MetEireann) | 3 | 0 | [evidence](https://github.com/MetEireann) |
| Geological Survey Ireland | [Geological-Survey-Ireland](https://github.com/Geological-Survey-Ireland) | 2 | 0 | [evidence](https://github.com/Geological-Survey-Ireland) |
| **Total** | **9 namespaces** | **191** | **22** | |

“Core” means the namespace could be tied to the named body using an official-domain profile, GitHub’s government directory, explicit repository documentation, or an authoritative public-sector catalogue. It deliberately includes forks, documentation repositories, data repositories, empty repositories and archived repositories: an archive should preserve the namespace as published, not make a quality judgement.

GitHub’s own [government community directory](https://government.github.com/community/) lists only HSE Ireland and OGCIO for Ireland, so it is useful as evidence but not as a complete inventory. Direct enumeration found the additional official namespaces above.

## Extended archive: official projects outside government-owned namespaces

| Project group | Repositories | Why it belongs in the extended set |
|---|---:|---|
| [Covid Green](https://github.com/covidgreen) | 14 | The project README names an HSE lead maintainer, acknowledges HSE, and the official HSE namespace contains forks of several of these repositories. Hosted by Linux Foundation Public Health, not by government. |
| [LocalGov Drupal Irish modules](https://github.com/localgovdrupal) | 3 | The modules were funded or originated by Carlow and Tipperary county councils, but live in the cross-border LocalGov Drupal organisation. |
| [data.gov.ie CKAN extension](https://github.com/derilinx/ckanext-dgi-public) | 1 | The repository says it is the source of the data.gov.ie extension; it is vendor-owned. |
| **Total** | **18** | |

The [EU OSS Country Intelligence Report for Ireland](https://interoperable-europe.ec.europa.eu/sites/default/files/inline-files/OSS%20Country%20Intelligence%20Report%20Ireland%202024_0.pdf) independently identifies Covid Green, LocalGov Drupal and data.gov.ie as major Irish public-sector open-source initiatives. The [Government of Ireland Design System entry](https://interoperable-europe.ec.europa.eu/eu-oss-catalogue/solutions/government-ireland-design-system) also confirms OGCIO ownership of `ogcio/govie-ds`.

## Quarantined candidates

The CSV’s `candidate` tier contains 18 repositories. Do **not** automatically present these as government-owned until the relevant body confirms them.

| Candidate namespace/project | Repos | Reason for caution |
|---|---:|---|
| `OrdnanceSurveyIreland` | 1 | Exact-style name, but no official cross-link found. |
| `DLRCOCO` | 1 | Plausible council handle and tree-related repo, but no official cross-link found. |
| `Cavancoco` | 3 | Plausible council handle, but no official cross-link found. |
| `kildarecoco` | 1 | Plausible council handle, but no official cross-link found. |
| `kerrycoco` | 2 | Plausible council handle, but no official cross-link found. |
| `govdataie` | 5 | Unbranded user account with “old-*” public-body data repos; not proven official. |
| `data-gov-ie` | 3 | Obsolete 2011-era linked-data project; it predates the modern data.gov.ie initiative. |
| Derilinx Sport Ireland repos | 2 | Project names fit, but direct commissioning/ownership evidence was not found; one is empty. |

Search results also surfaced stale/deleted paths (for example a historical `govdataie/enterprise-ireland` result). They are not cloneable and therefore are not in the seed files; the web research record should be retained as a tombstone lead.

## Other forges

Targeted searches covered GitLab.com, Bitbucket, Codeberg, SourceForge, official `.gov.ie` pages, likely self-hosted Git/GitLab/Gitea hostnames, old department domains, 31 local authorities, and a broad set of statutory/state bodies. **No official Irish-government public namespace outside GitHub could be confirmed in this pass.**

That is a negative search result, not proof that none exists. Search indexing is incomplete; public repos can be unlinked, renamed, deleted, or hosted on an unindexed self-managed server.

## Important exclusions

- [legalize-dev/legalize-ie](https://github.com/legalize-dev/legalize-ie) is a useful Git-native mirror of official Irish legislation, but it explicitly identifies itself as an independent derivative. It is in the CSV as `adjacent`, not government code.
- [OpenIrelandNetwork/NOSIS](https://github.com/OpenIrelandNetwork/NOSIS) is community/event material, not a government repository.
- `api-evangelist/data-gov-ie` explicitly disclaims affiliation.
- Planning-alert, council-data scraper and civic-tech repositories were excluded unless a public body’s ownership or funding could be established.
- University/research organisations and publicly funded bodies were not treated as government merely because they receive state funding.

## Recommended archive design

1. Start with the 191 core clone URLs in the seed file.
2. Mirror with `git clone --mirror` / `git remote update --prune`, but retain tombstones when an upstream disappears.
3. Preserve release assets, Git LFS objects, issues, pull requests and wiki repositories separately; a bare Git mirror alone does not capture them.
4. Keep the CSV as a provenance manifest and record first-seen, last-seen and verification dates on each crawl.
5. Add the 18 extended repositories in a separate namespace so ownership is never implied.
6. Ask OGCIO and the [Irish public-service open-source Community of Practice](https://interoperable-europe.ec.europa.eu/collection/open-source-observatory-osor/news/open-ireland-network-and-irish-public-sector) to verify the candidate accounts and disclose any self-hosted forges.
7. Re-enumerate each verified organisation through the GitHub API on every crawl rather than relying on this static snapshot.

## Files

- `irish-government-open-source-inventory.csv`: every repository, tier, clone URL, archive metadata and evidence.
- `irish-government-core-mirror-seeds.txt`: one clone URL per line for the 191 high-confidence core repositories.
- This report: scope, evidence, exclusions and operational guidance.
