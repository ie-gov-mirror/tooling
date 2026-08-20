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
# backfilled in history slices. Commits per slice on the chunked path.
CHUNK_COMMITS="${CHUNK_COMMITS:-2000}"
CHUNK_THRESHOLD_KB="${CHUNK_THRESHOLD_KB:-1500000}"

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

if ! gh repo view "${MIRROR_ORG}/${MIRROR_NAME}" >/dev/null 2>&1; then
  note "creating ${MIRROR_ORG}/${MIRROR_NAME} (tier=$TIER)"
  gh repo create "${MIRROR_ORG}/${MIRROR_NAME}" --public \
    --description "$DESCRIPTION" \
    --homepage "https://github.com/${UPSTREAM_SLUG}" \
    --disable-issues --disable-wiki >/dev/null || fail "repo creation failed"
  # Pace repo creation: the secondary rate limit is 80 content-generating
  # requests/minute and 500/hour.
  sleep 2
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
#    --prune still removes branches and tags deleted upstream, which is correct
#    for a live mirror; deletion of the whole upstream is handled by tombstones.
# ---------------------------------------------------------------------------
push_all() {
  git push --quiet --prune "$MIRROR_PUSH_URL" \
    '+refs/heads/*:refs/heads/*' '+refs/tags/*:refs/tags/*'
}

REPO_KB=$(du -sk . | cut -f1)
if [ "$REPO_KB" -gt "$CHUNK_THRESHOLD_KB" ]; then
  # Oversized first backfill: walk each branch's history in slices so no single
  # pack approaches the ~2GB ceiling. Subsequent syncs take the normal path
  # because the objects are already on the remote.
  note "large repo (${REPO_KB} KB) - chunked backfill"
  for ref in $(git for-each-ref --format='%(refname)' refs/heads); do
    git rev-list --reverse "$ref" | awk -v n="$CHUNK_COMMITS" 'NR % n == 0' \
      | while read -r sha; do
          git push --quiet --force "$MIRROR_PUSH_URL" "${sha}:refs/heads/__backfill" \
            || fail "chunked push failed at $sha on $ref"
        done
  done
  git push --quiet --delete "$MIRROR_PUSH_URL" refs/heads/__backfill 2>/dev/null || true
fi

if [ "$BRANCH_COUNT" -eq 0 ] && [ "$TAG_COUNT" -eq 0 ]; then
  # Empty upstream repo. The mirror exists and is correct; nothing to push.
  note "upstream is empty - mirror created, nothing to push"
else
  push_all || fail "push rejected (check secret-scanning push protection and workflows:write)"
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
# 7. Report machine-readable result for manifest update, then free disk. The
#    runner has ~14GB; the largest repo here is 4.4GB.
# ---------------------------------------------------------------------------
printf 'RESULT\t%s\t%s\t%s\t%s\t%s\n' \
  "$MIRROR_NAME" "synced" "$BRANCH_COUNT" "$TAG_COUNT" "${LFS_NOTE:-none}"
cd /
rm -rf "$WORKDIR"
