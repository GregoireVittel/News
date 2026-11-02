#!/usr/bin/env bash
# Keep the generated site on the `site` branch with at most two commits:
# the current version and the one before it. Nothing is committed to main.
#
#   site_branch.sh fetch DIR   Extract the currently published version into DIR
#                              (empty DIR if the branch does not exist yet).
#   site_branch.sh save DIR    Publish DIR as the new version: one commit whose
#                              only parent is a parentless copy of the previous
#                              version, force-pushed to `site`.
# Run inside a clone whose `origin` is the repository.
set -euo pipefail
BRANCH="${SITE_BRANCH:-site}"
cmd="${1:?usage: site_branch.sh fetch|save DIR}"
dir="${2:?usage: site_branch.sh fetch|save DIR}"

fetch_previous() {
  git fetch --quiet --depth=1 origin "refs/heads/$BRANCH:refs/remotes/origin/$BRANCH" 2>/dev/null
}

case "$cmd" in
  fetch)
    mkdir -p "$dir"
    if fetch_previous; then
      git archive "refs/remotes/origin/$BRANCH" | tar -x -C "$dir"
      echo "Previous version: $(git rev-parse --short "refs/remotes/origin/$BRANCH")"
    else
      echo "No $BRANCH branch yet; starting without a previous version."
    fi
    ;;
  save)
    export GIT_AUTHOR_NAME='github-actions[bot]' GIT_COMMITTER_NAME='github-actions[bot]'
    export GIT_AUTHOR_EMAIL='41898282+github-actions[bot]@users.noreply.github.com'
    export GIT_COMMITTER_EMAIL="$GIT_AUTHOR_EMAIL"
    index="$(mktemp)"
    rm -f "$index"
    tree="$(GIT_INDEX_FILE="$index" git --work-tree="$dir" add -A . && GIT_INDEX_FILE="$index" git write-tree)"
    rm -f "$index"
    stamp="$(date -u +%Y-%m-%dT%H:%MZ)"
    if fetch_previous; then
      previous_tree="$(git rev-parse "refs/remotes/origin/$BRANCH^{tree}")"
      base="$(git commit-tree "$previous_tree" -m 'Previous published version')"
      commit="$(git commit-tree "$tree" -p "$base" -m "Published version $stamp")"
    else
      commit="$(git commit-tree "$tree" -m "Published version $stamp")"
    fi
    git push --quiet --force origin "$commit:refs/heads/$BRANCH"
    echo "Saved $(git rev-parse --short "$commit") to $BRANCH (current + previous only)."
    ;;
  *)
    echo "unknown command: $cmd" >&2
    exit 2
    ;;
esac
