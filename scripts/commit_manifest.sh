#!/usr/bin/env bash
# Regenerate the manifest on the latest branch tip, commit it, and push it,
# retrying when another writer got there first.
#
# Usage: commit_manifest.sh MESSAGE COMMAND [ARGS...]
#   e.g. commit_manifest.sh "Update manifest" scripts/refresh_manifest.sh
#
# Manifest edits are derived data, so a rejected push is never resolved by
# merging text. The old approach - `git pull --rebase || true` then
# `git push || true` - conflicted whenever two writers touched neighbouring
# CSV rows, and swallowed the conflict: on 12 Oct 2026 six of twelve sync
# shards lost their records that way while the run reported success. Here each
# attempt resets to the newest tip and re-runs COMMAND on top of it, so there
# is nothing to conflict with.
#
# COMMAND exit status decides what happens:
#   0  commit and push
#   3  partial success: commit and push what was produced, then exit 3 so
#      the job still fails visibly (e.g. a namespace could not be listed).
#      Not 2, which bash and argparse use for misuse: a broken COMMAND must
#      abort, never be mistaken for partial success.
#   *  abort without committing, and exit with that status
#
# Environment: COMMIT_ATTEMPTS (default 5), COMMIT_BACKOFF_SECONDS (default
# 10), BRANCH (default $GITHUB_REF_NAME, else main).

set -uo pipefail

# Everything lives in main(): `git reset --hard` below can replace this very
# file on disk, and bash reads scripts incrementally. A function is parsed in
# full before it runs, so a mid-run rewrite cannot change what executes.
main() {
  local message="${1:?commit message required}"; shift
  if [ "$#" -eq 0 ]; then
    echo "usage: commit_manifest.sh MESSAGE COMMAND [ARGS...]" >&2
    return 64
  fi
  local branch="${BRANCH:-${GITHUB_REF_NAME:-main}}"
  local attempts="${COMMIT_ATTEMPTS:-5}"
  local base="${COMMIT_BACKOFF_SECONDS:-10}"
  local attempt rc wait

  git config user.name "ie-gov-mirror bot"
  git config user.email "noreply@github.com"

  for attempt in $(seq 1 "$attempts"); do
    # Explicit refspec: actions/checkout makes a shallow clone whose remote
    # may not track the branch, so a bare `git fetch origin` is not enough.
    if git fetch --quiet origin "+refs/heads/${branch}:refs/remotes/origin/${branch}"; then
      git reset --quiet --hard "origin/${branch}"

      rc=0
      "$@" || rc=$?
      case "$rc" in
        0|3) ;;
        *) echo "::error::manifest regeneration failed (exit $rc); nothing committed" >&2
           return "$rc" ;;
      esac

      git add -A -- manifest docs/DELETED.md
      if git diff --cached --quiet; then
        echo "no manifest changes to commit"
        return "$rc"
      fi
      git commit --quiet -m "$message"
      if git push --quiet origin "HEAD:${branch}"; then
        echo "manifest committed on attempt ${attempt}/${attempts}"
        return "$rc"
      fi
      echo "push rejected - another writer moved ${branch}" >&2
    else
      echo "fetch of ${branch} failed" >&2
    fi

    [ "$attempt" -lt "$attempts" ] || break
    # Linear backoff plus jitter, so two writers that collided do not
    # collide again on the next attempt.
    wait=$(( attempt * base + (base > 0 ? RANDOM % base : 0) ))
    echo "retrying in ${wait}s (attempt $((attempt + 1))/${attempts}), regenerating on the latest ${branch}" >&2
    sleep "$wait"
  done

  echo "::error::could not push the manifest after ${attempts} attempts" >&2
  return 1
}

main "$@"
exit
