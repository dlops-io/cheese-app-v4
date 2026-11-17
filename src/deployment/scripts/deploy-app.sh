#!/usr/bin/env bash
# Ship the code in this repo to the GKE cluster: build and push the images whose files changed, then
# roll the workloads onto them, a pod at a time. This is what /deploy-app in a commit message runs.
#   ./scripts/deploy-app.sh          (STACK=dev by default)
set -euo pipefail
cd "$(dirname -- "${BASH_SOURCE[0]}")/.."
stack="${STACK:-dev}"

# Each image's tag is a hash of its files: unchanged code is not built again, and its pods stay
(cd deploy_images && pulumi up --stack "${stack}" --yes --non-interactive)
STACK="${stack}" ./scripts/deploy-k8s.sh
