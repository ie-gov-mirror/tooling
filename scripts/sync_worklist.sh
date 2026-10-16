#!/usr/bin/env bash
# Mirror every repository in a worklist, retrying transient failures.
#
# Usage: sync_worklist.sh WORKLIST SYNCED_OUT
#   WORKLIST    tab-separated rows from `enumerate.py --emit-changed`:
#               clone_url  mirror_name  default_branch  tier  pushed_at
#   SYNCED_OUT  appended with "mirror_name<TAB>pushed_at" for each success,
#               the format `enumerate.py --mark-synced` reads
#
# sync_repo.sh exit codes and how each is handled:
#   0  synced                    recorded in SYNCED_OUT
#   4  repo creation throttled   deferred to the next run, not retried here:
#                                sync_repo.sh has already backed off, and
#                                trying again at once only extends the limit
#   3  clone failed              retried. The repository was listed by the API
#                                moments ago, so this is almost always
#                                transient; real deletions are left to the
#                                daily enumerate, whose tombstone check asks
#                                the API rather than inferring from a clone
#   *  any other failure         retried, then counted as failed
#
# Exits 1 if any repository still failed after its retries, so the job shows
# red; everything that did sync is in SYNCED_OUT regardless.
#
# Environment: WORKDIR (required), SYNC_ATTEMPTS (default 3),
# SYNC_BACKOFF_SECONDS (default 30), PACE_SECONDS between repositories
# (default 0), SYNC_REPO (default: sync_repo.sh beside this script).

set -uo pipefail

WORKLIST="${1:?worklist required}"
SYNCED_OUT="${2:?synced output file required}"
WORKDIR="${WORKDIR:?WORKDIR required}"
ATTEMPTS="${SYNC_ATTEMPTS:-3}"
BACKOFF="${SYNC_BACKOFF_SECONDS:-30}"
PACE="${PACE_SECONDS:-0}"
SYNC_REPO="${SYNC_REPO:-$(dirname "$0")/sync_repo.sh}"

mkdir -p "$WORKDIR"
touch "$SYNCED_OUT"
synced=0 failed=0 throttled=0 retried=0

while IFS=$'\t' read -r clone_url mirror_name default_branch tier pushed_at; do
  [ -z "${clone_url:-}" ] && continue

  for attempt in $(seq 1 "$ATTEMPTS"); do
    # sync_repo.sh leaves its clone behind when it fails part-way, and a
    # leftover directory makes the next `git clone --mirror` fail - which
    # would look like the upstream had vanished. Start every attempt clean.
    rm -rf "${WORKDIR:?}"/*
    # stdin from /dev/null: nothing inside may consume the worklist.
    "$SYNC_REPO" "$clone_url" "$mirror_name" "$default_branch" "$tier" < /dev/null
    rc=$?
    case "$rc" in
      0|4) break ;;
    esac
    if [ "$attempt" -lt "$ATTEMPTS" ]; then
      wait=$(( attempt * BACKOFF ))
      echo "::warning::$mirror_name failed (exit $rc), retry $((attempt + 1))/$ATTEMPTS in ${wait}s"
      retried=$((retried + 1))
      sleep "$wait"
    fi
  done

  case "$rc" in
    0) printf '%s\t%s\n' "$mirror_name" "$pushed_at" >> "$SYNCED_OUT"
       synced=$((synced + 1)) ;;
    4) echo "::warning::$mirror_name deferred - repo creation throttled, next run will retry"
       throttled=$((throttled + 1)) ;;
    *) echo "::error::$mirror_name failed after $ATTEMPTS attempts (last exit $rc)"
       failed=$((failed + 1)) ;;
  esac

  # Reclaim runner disk: ~14 GB available, largest repo is 4.4 GB.
  rm -rf "${WORKDIR:?}"/*
  [ "$PACE" -gt 0 ] && sleep "$PACE"
done < "$WORKLIST"

summary="synced=$synced failed=$failed throttled=$throttled retries=$retried"
echo "$summary"
[ -n "${GITHUB_STEP_SUMMARY:-}" ] && echo "$summary" >> "$GITHUB_STEP_SUMMARY"
[ "$failed" -eq 0 ]
