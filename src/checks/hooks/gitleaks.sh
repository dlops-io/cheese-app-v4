#!/usr/bin/env bash
# Look for keys and passwords in the files pre-commit passes: the staged versions before a commit, or
# every file with --all-files. gitleaks scans a folder, so copy them into an empty one first.
set -euo pipefail
scan="$(mktemp -d)"
trap 'rm -rf "${scan}"' EXIT
for file in "$@"; do
    mkdir -p "${scan}/$(dirname -- "${file}")"
    cp -- "${file}" "${scan}/${file}"
done
cd "${scan}"
gitleaks dir . --no-banner --redact --verbose
