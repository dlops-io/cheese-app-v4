#!/usr/bin/env bash
# Run the checks in .pre-commit-config.yaml inside the checks image. Needs only git and Docker.
#   src/checks/run.sh                 the files you staged: what the git hook runs before each commit
#   src/checks/run.sh --all-files     every file, as CI does
# Any other arguments go to `pre-commit run`.
set -euo pipefail
here="$(cd "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
root="$(git -C "${here}" rev-parse --show-toplevel)"
image="cheese-app-checks"

if ! docker info >/dev/null 2>&1; then
    echo "The checks run in Docker, and Docker is not running. Start Docker, then commit again." >&2
    echo "(git commit --no-verify skips them this once; CI on GitHub still runs them.)" >&2
    exit 1
fi

# About a second when nothing changed: every layer comes from Docker's cache
docker build --quiet --tag "${image}" --build-context frontend="${root}/src/frontend-react" "${here}" >/dev/null

# The repo at the same path as on this machine, so file names in messages match. A git worktree keeps
# its history in the main checkout's .git, so mount that too.
git_dir="$(git -C "${root}" rev-parse --path-format=absolute --git-common-dir)"
mounts=(-v "${root}:${root}")
if [[ "${git_dir}" != "${root}/.git" ]]; then
    mounts+=(-v "${git_dir}:${git_dir}")
fi

# pre-commit sets your unstaged changes aside while the checks run: keep that copy in .git, on this
# machine, not in the container, so it survives even if the container is killed
env=(-e HOME=/tmp -e PRE_COMMIT_HOME="${git_dir}/pre-commit")
# `git commit -a` and `git commit <file>` stage into a temporary index: check that one
if [[ -n "${GIT_INDEX_FILE:-}" ]]; then
    [[ "${GIT_INDEX_FILE}" == /* ]] || GIT_INDEX_FILE="${PWD}/${GIT_INDEX_FILE}"
    env+=(-e GIT_INDEX_FILE="${GIT_INDEX_FILE}")
fi

# Colours when someone is watching
tty=()
if [[ -t 1 ]]; then
    tty=(-t)
fi

# Your user ID, so files the formatters fix stay yours on Linux
# (${tty[@]+...}: macOS's bash 3.2 calls an empty array unset)
exec docker run --rm ${tty[@]+"${tty[@]}"} "${mounts[@]}" "${env[@]}" -w "${root}" --user "$(id -u):$(id -g)" \
    "${image}" pre-commit run "$@"
