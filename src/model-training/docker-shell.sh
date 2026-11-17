#!/bin/bash
# A shell in the model-training container on your laptop, against your ML bucket, with the deployment key
# The ML pipeline runs the same image on Vertex AI.
set -e

export SECRETS_DIR=$(pwd)/../../../secrets/
export GCP_PROJECT="ac215-project" # CHANGE TO YOUR PROJECT ID
export ML_BUCKET="$GCP_PROJECT-cheese-app-ml"
export IMAGE_NAME="cheese-app-model-training"

docker build -t "$IMAGE_NAME" -f Dockerfile .

docker run --rm -ti --name "$IMAGE_NAME" \
    -v "$SECRETS_DIR":/secrets:ro \
    -e GOOGLE_APPLICATION_CREDENTIALS=/secrets/deployment.json \
    -e GOOGLE_CLOUD_PROJECT="$GCP_PROJECT" \
    -e ML_BUCKET="$ML_BUCKET" \
    "$IMAGE_NAME" "$@"
