#!/usr/bin/env bash
# Check the deployment tooling, in the deployment container (CI runs it there too):
#   ./docker-shell.sh ./scripts/check.sh
# Lints the shell scripts and the Python (Pulumi programs, the ML pipeline), renders the Kubernetes
# YAML for both clusters, and compiles the ML pipeline without running it.
set -euo pipefail
cd "$(dirname -- "${BASH_SOURCE[0]}")/.."
mapfile -t scripts < <(find . \( -path ./.local -o -path ./.venv -o -path ./pulumi-plugins -o -path ./docker-config \) -prune -o -name '*.sh' -print | sort)
for script in "${scripts[@]}"; do
    bash -n "${script}"
done
shellcheck -x --source-path=SCRIPTDIR "${scripts[@]}"
ruff check .
ruff format --check .
for target in k8s/gke k8s/kind k8s/load-vector-db k8s/kind/load-vector-db; do
    kubectl kustomize "${target}" >/dev/null
    echo "${target}: renders"
done
python ml/pipeline.py --compile-only --bucket check --service-account check \
    --collector check/collector --processor check/processor --trainer check/trainer
echo "check.sh: all checks passed"
