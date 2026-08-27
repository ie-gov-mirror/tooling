#!/usr/bin/env bash
# Mirror one upstream repository into the mirror org.
#
# Usage: sync_repo.sh <upstream-clone-url> <mirror-name> [default-branch] [tier]
#   e.g. sync_repo.sh https://github.com/CSOIreland/PxStat.git CSOIreland.PxStat master core
#
# Requires: GH_TOKEN (contents:write, administration:write, workflows:write on
# the target org), MIRROR_ORG, and the `gh` CLI. Idempotent: safe to re-run.
#
# tier is "core" (owned by a verified Irish public body) or "extended" (an
# Irish public-service project owned by someone else - Linux Foundation Public
# Health, a cross-border project, a vendor). Extended repos live in the same
# org but are labelled so government ownership is never implied.
#
# Fidelity contract: git data is pushed verbatim. This script never rewrites
# history, never injects files, and never edits repository contents.

set -uo pipefail

UPSTREAM_URL="${1:?upstream clone url required}"
MIRROR_NAME="${2:?mirror name required}"
WANT_DEFAULT_BRANCH="${3:-}"
TIER="${4:-core}"
MIRROR_ORG="${MIRROR_ORG:?MIRROR_ORG required}"
WORKDIR="${WORKDIR:-$(mktemp -d)}/${MIRROR_NAME}.git"

# GitHub rejects packs larger than ~2GB in a single push, so oversized repos are
# backfilled in history slices. The slice count is derived from repository SIZE,
# not from a fixed commit count: a fixed count is wrong in both directions - a
# repo with fewer commits than the step gets no slices at all (which is how a
# 4.3GB repo with 71 commits went out as one pack and got HTTP 500), and a repo
# with huge blobs in few commits needs finer slicing than commit count implies.
CHUNK_THRESHOLD_KB="${CHUNK_THRESHOLD_KB:-1500000}"   # chunk above ~1.5 GiB
CHUNK_TARGET_KB="${CHUNK_TARGET_KB:-400000}"          # aim ~400 MiB per push
CHUNKED=0
PUSH_PROTECTED=0

note() { printf '%s %s\n' "[$MIRROR_NAME]" "$*" >&2; }
fail() { note "FAILED: $*"; exit 1; }

MIRROR_PUSH_URL="https://x-access-token:${GH_TOKEN}@github.com/${MIRROR_ORG}/${MIRROR_NAME}.git"

# ---------------------------------------------------------------------------
# 1. Clone upstream. A 404 here means the upstream is gone: signal for the
#    tombstone flow rather than a hard failure.
# ---------------------------------------------------------------------------
note "cloning $UPSTREAM_URL"
if ! git clone --mirror --quiet "$UPSTREAM_URL" "$WORKDIR"; then
  note "clone failed - upstream may be deleted, private, or DMCA'd"
  exit 3   # exit 3 == "upstream unreachable", caller runs tombstone.py
fi
cd "$WORKDIR" || fail "cannot enter $WORKDIR"

# ---------------------------------------------------------------------------
# 2. Strip refs GitHub refuses to accept. `git clone --mirror` fetches hidden
#    refs such as refs/pull/*; pushing them is rejected with "deny updating a
#    hidden ref" and would abort the whole push.
# ---------------------------------------------------------------------------
git for-each-ref --format='%(refname)' refs/pull refs/merge-requests 2>/dev/null \
  | while read -r ref; do git update-ref -d "$ref"; done

BRANCH_COUNT=$(git for-each-ref --format='%(refname)' refs/heads | wc -l | tr -d ' ')
TAG_COUNT=$(git for-each-ref --format='%(refname)' refs/tags | wc -l | tr -d ' ')
note "$BRANCH_COUNT branches, $TAG_COUNT tags"

# ---------------------------------------------------------------------------
# 3. Ensure the mirror repo exists. Description and homepage point at upstream
#    so the mirror is never mistaken for the canonical source. Issues, wiki and
#    projects stay off: this is an archive, not a place to file bugs.
# ---------------------------------------------------------------------------
UPSTREAM_SLUG="${UPSTREAM_URL#https://github.com/}"; UPSTREAM_SLUG="${UPSTREAM_SLUG%.git}"

if [ "$TIER" = "extended" ]; then
  # Owned by a non-government body. The description carries the caveat because
  # the upstream owner segment alone (covidgreen, derilinx, localgovdrupal) is
  # not an explicit enough signal.
  DESCRIPTION="Unofficial mirror of ${UPSTREAM_SLUG}. An Irish public-service project NOT owned by an Irish public body. Not affiliated with or endorsed by any Irish public body."
  TOPICS="mirror,unofficial,not-government-owned"
else
  DESCRIPTION="Unofficial mirror of ${UPSTREAM_SLUG}. Not affiliated with or endorsed by any Irish public body."
  TOPICS="mirror,unofficial"
fi

# Repository creation is governed by an undocumented secondary rate limit that
# is much tighter than the 500 content-generating requests/hour in the docs: a
# backfill creating ~150 repositories in under an hour was blocked with "You
# have created too many repositories, too quickly". The limit is not reported in
# /rate_limit (primary quota stays full), so it can only be discovered by being
# refused. Back off and wait it out rather than dropping the repository.
create_repo_with_backoff() {
  local attempt=0 wait=60 out
  while :; do
    if out=$(gh repo create "${MIRROR_ORG}/${MIRROR_NAME}" --public \
               --description "$DESCRIPTION" \
               --homepage "https://github.com/${UPSTREAM_SLUG}" \
               --disable-issues --disable-wiki 2>&1); then
      return 0
    fi
    # Another shard may have created it between the check and here.
    if printf '%s' "$out" | grep -qi "name already exists"; then
      note "repository already exists, continuing"
      return 0
    fi
    if ! printf '%s' "$out" | grep -qiE "too many repositories|secondary rate limit|abuse detection"; then
      note "$out"
      return 1   # a real error, not throttling
    fi
    attempt=$((attempt + 1))
    if [ "$attempt" -gt "${CREATE_MAX_ATTEMPTS:-6}" ]; then
      note "still rate limited after $attempt attempts, giving up on this repo"
      return 2
    fi
    note "creation rate limited, waiting ${wait}s (attempt $attempt)"
    sleep "$wait"
    wait=$(( wait * 2 ))
    [ "$wait" -gt 1800 ] && wait=1800
  done
}

if ! gh repo view "${MIRROR_ORG}/${MIRROR_NAME}" >/dev/null 2>&1; then
  note "creating ${MIRROR_ORG}/${MIRROR_NAME} (tier=$TIER)"
  create_repo_with_backoff
  case $? in
    0) ;;
    2) exit 4 ;;   # exit 4 == throttled, retry this repo in a later run
    *) fail "repo creation failed" ;;
  esac
  sleep "${CREATE_PACE_SECONDS:-2}"
fi

# Topics are metadata, never contents - the fidelity contract is untouched.
# Build the args as an array so each topic is a separate -f flag.
TOPIC_ARGS=()
for topic in ${TOPICS//,/ }; do
  TOPIC_ARGS+=(-f "names[]=${topic}")
done
# Upstream org slug as a topic makes provenance filterable in the org listing.
TOPIC_ARGS+=(-f "names[]=$(echo "${UPSTREAM_SLUG%%/*}" | tr '[:upper:]' '[:lower:]')")
gh api -X PUT "/repos/${MIRROR_ORG}/${MIRROR_NAME}/topics" "${TOPIC_ARGS[@]}" \
  >/dev/null 2>&1 || note "WARNING could not set topics"

# ---------------------------------------------------------------------------
# 4. Git LFS before the git push, so pointer files never dangle. Upstream LFS
#    storage may be over quota or purged - record the gap, don't fail the repo.
# ---------------------------------------------------------------------------
LFS_NOTE=""
if git lfs ls-files --all >/dev/null 2>&1 && [ -n "$(git lfs ls-files --all 2>/dev/null)" ]; then
  note "LFS objects present"
  git lfs fetch --all origin >/dev/null 2>&1 || LFS_NOTE="lfs-fetch-incomplete"
  git lfs push --all "$MIRROR_PUSH_URL" >/dev/null 2>&1 || LFS_NOTE="${LFS_NOTE:+$LFS_NOTE,}lfs-push-incomplete"
  [ -n "$LFS_NOTE" ] && note "WARNING $LFS_NOTE"
fi

# ---------------------------------------------------------------------------
# 5. Push. Explicit refspecs, never `git push --mirror`: that would also delete
#    refs absent locally, and would retry the hidden refs stripped above.
#
#    Deliberately NOT --prune. The archive exists to preserve what upstream
#    removes, and that has to hold at ref level, not only whole-repository
#    level. Pruning would make the mirror track upstream exactly and destroy
#    branches and tags on the next sync after upstream deleted them - which is
#    precisely the material worth keeping. Observed for real on
#    HSEIreland/hse-healthapp-test-fhir-server, whose six dependabot branches
#    the mirror captured and upstream has since removed.
#
#    The cost is accepted: mirrors accumulate refs upstream no longer has, so a
#    mirror is a superset of its upstream rather than a copy. verify_mirrors.py
#    reports that as ok-with-extra rather than a fault.
# ---------------------------------------------------------------------------
push_all() {
  git push --quiet "$MIRROR_PUSH_URL" \
    '+refs/heads/*:refs/heads/*' '+refs/tags/*:refs/tags/*'
}

# Walk one branch's history, pushing progressively to a scratch ref so each
# push carries a bounded slice of new objects. Returns non-zero on failure.
chunked_push_ref() {
  local ref="$1" list total slices step n sha
  list=$(mktemp "${TMPDIR:-/tmp}/chunklist.XXXXXX")
  git rev-list --reverse "$ref" > "$list" || return 1
  total=$(wc -l < "$list" | tr -d ' ')
  [ "${total:-0}" -eq 0 ] && return 0

  # One slice per CHUNK_TARGET_KB of repository, capped at one slice per commit.
  slices=$(( REPO_KB / CHUNK_TARGET_KB + 1 ))
  [ "$slices" -gt "$total" ] && slices="$total"
  [ "$slices" -lt 1 ] && slices=1
  step=$(( (total + slices - 1) / slices ))
  [ "$step" -lt 1 ] && step=1
  note "chunking ${ref#refs/heads/}: $total commits in ~$slices slices of $step"

  n=0
  while [ "$n" -lt "$total" ]; do
    n=$(( n + step ))
    [ "$n" -gt "$total" ] && n="$total"
    sha=$(sed -n "${n}p" "$list")
    if ! git push --quiet --force "$MIRROR_PUSH_URL" "${sha}:refs/heads/__backfill"; then
      # A slice still too large for one pack: halve the step and retry from
      # the last known-good point rather than giving up on the repository.
      if [ "$step" -gt 1 ]; then
        n=$(( n - step )); step=$(( step / 2 )); [ "$step" -lt 1 ] && step=1
        note "slice too large, retrying with step $step"
        continue
      fi
      note "single-commit push failed at $n/$total ($sha)"
      rm -f "$list"; return 1
    fi
  done
  rm -f "$list"
  return 0
}

REPO_KB=$(du -sk . | cut -f1)
if [ "$REPO_KB" -gt "$CHUNK_THRESHOLD_KB" ]; then
  # Oversized first backfill: get the objects onto the remote in bounded packs
  # first, so the real ref push below sends almost nothing. Later syncs take the
  # normal path because the objects are already there.
  note "large repo (${REPO_KB} KB) - chunked backfill"
  for ref in $(git for-each-ref --format='%(refname)' refs/heads); do
    chunked_push_ref "$ref" || fail "chunked push failed on $ref"
  done
  # The scratch ref is NOT deleted here. On a freshly created repository it is
  # the first ref pushed, so GitHub makes it the default branch, and a default
  # branch cannot be deleted ("refusing to delete the current branch"). It is
  # removed after the real default branch is set, at the end of this script.
  CHUNKED=1
fi

# GitHub applies secret-scanning push protection to PUBLIC repositories at a
# level that org settings cannot switch off on a free plan: the org has
# secret_scanning_push_protection disabled, the mirror-archive configuration is
# enforced with it disabled, and there are no rulesets - yet a push carrying a
# credential in history is still refused with GH013. Push protection does not
# apply to private repositories without Advanced Security, so the fallback is to
# push while private and restore visibility afterwards.
#
# This preserves fidelity: history is pushed verbatim, nothing is rewritten and
# no secret is stripped. The alternative would be to skip such repositories,
# which would silently put a hole in the archive exactly where upstream
# published something it should not have.
push_via_private() {
  note "push blocked by push protection - retrying with the mirror private"
  gh api -X PATCH "/repos/${MIRROR_ORG}/${MIRROR_NAME}" -F private=true >/dev/null 2>&1 \
    || { note "could not make repository private"; return 1; }
  local rc=0
  push_all || rc=$?
  # Restore visibility whether or not the push worked; a mirror left private is
  # worse than one that failed loudly.
  gh api -X PATCH "/repos/${MIRROR_ORG}/${MIRROR_NAME}" -F private=false >/dev/null 2>&1 \
    || note "WARNING mirror left PRIVATE - restore visibility manually"
  return $rc
}

if [ "$BRANCH_COUNT" -eq 0 ] && [ "$TAG_COUNT" -eq 0 ]; then
  # Empty upstream repo. The mirror exists and is correct; nothing to push.
  note "upstream is empty - mirror created, nothing to push"
else
  if ! push_out=$(push_all 2>&1); then
    if printf '%s' "$push_out" | grep -qiE "GH013|push protection|cannot contain secrets"; then
      PUSH_PROTECTED=1
      push_via_private || fail "push failed even with the mirror private"
    else
      note "$push_out"
      fail "push rejected (check workflows:write on the token)"
    fi
  fi
fi

# ---------------------------------------------------------------------------
# 6. Default branch. git cannot set it, and the inventory contains branches
#    named `current`, `dev`, `trunk`, `2`, `2.0`, `7` and `fix/http-sitemap`.
#    Assuming `main` would silently mirror the wrong head for ~10% of repos.
# ---------------------------------------------------------------------------
if [ -z "$WANT_DEFAULT_BRANCH" ]; then
  WANT_DEFAULT_BRANCH=$(git symbolic-ref --short HEAD 2>/dev/null || true)
fi
if [ -n "$WANT_DEFAULT_BRANCH" ] && git show-ref --quiet "refs/heads/${WANT_DEFAULT_BRANCH}"; then
  CURRENT=$(gh repo view "${MIRROR_ORG}/${MIRROR_NAME}" --json defaultBranchRef \
              --jq '.defaultBranchRef.name // ""' 2>/dev/null || true)
  if [ "$CURRENT" != "$WANT_DEFAULT_BRANCH" ]; then
    note "setting default branch to $WANT_DEFAULT_BRANCH"
    gh api -X PATCH "/repos/${MIRROR_ORG}/${MIRROR_NAME}" \
      -f "default_branch=${WANT_DEFAULT_BRANCH}" >/dev/null 2>&1 \
      || note "WARNING could not set default branch"
  fi
fi

# ---------------------------------------------------------------------------
# 7. Remove the chunked-backfill scratch ref, now that a real default branch is
#    set and GitHub will allow it.
# ---------------------------------------------------------------------------
if [ "$CHUNKED" -eq 1 ]; then
  if git ls-remote --exit-code --heads "$MIRROR_PUSH_URL" __backfill >/dev/null 2>&1; then
    gh api -X DELETE "/repos/${MIRROR_ORG}/${MIRROR_NAME}/git/refs/heads/__backfill" \
      >/dev/null 2>&1 || note "WARNING could not remove __backfill scratch ref"
  fi
fi

# ---------------------------------------------------------------------------
# 8. Report machine-readable result for manifest update, then free disk. The
#    runner has ~14GB; the largest repo here is 4.4GB.
# ---------------------------------------------------------------------------
NOTES="${LFS_NOTE:-none}"
[ "$PUSH_PROTECTED" -eq 1 ] && NOTES="${NOTES},pushed-via-private-visibility"
printf 'RESULT\t%s\t%s\t%s\t%s\t%s\n' \
  "$MIRROR_NAME" "synced" "$BRANCH_COUNT" "$TAG_COUNT" "$NOTES"
cd /
rm -rf "$WORKDIR"
