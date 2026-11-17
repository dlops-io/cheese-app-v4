#!/usr/bin/env bash
# Run the ML pipeline on Vertex AI with the code in this repo: build and push the images that changed,
# then collect photos, clean them and train the model. When training ran and the cluster is up, restart
# the API's pods, one at a time, so they load the new model.
#   ./scripts/run-ml-pipeline.sh                       all three steps
#   ./scripts/run-ml-pipeline.sh collect               some steps: collect, process, train
#   PER_LABEL=50 EPOCHS=10 ./scripts/run-ml-pipeline.sh
set -euo pipefail
cd "$(dirname -- "${BASH_SOURCE[0]}")/.."
stack="${STACK:-dev}"
output() { (cd "$1" && pulumi stack output --stack "${stack}" "$2"); }
steps=("$@")
if [[ ${#steps[@]} -eq 0 ]]; then
    steps=(collect process train)
fi

# The same stack the app's deploy uses: only the images whose files changed are built again
(cd deploy_images && pulumi up --stack "${stack}" --yes --non-interactive)

python ml/pipeline.py --steps "${steps[@]}" \
    --bucket "$(output deploy_base ml_bucket)" \
    --service-account "$(output deploy_base app_service_account)" \
    --collector "$(output deploy_images data_collector_ref)" \
    --processor "$(output deploy_images data_processor_ref)" \
    --trainer "$(output deploy_images model_training_ref)" \
    --per-label "${PER_LABEL:-50}" \
    --epochs "${EPOCHS:-10}"

if [[ " ${steps[*]} " != *" train "* ]]; then
    exit 0
fi
# A destroyed or never-made deploy_k8s stack has no outputs
if ! cluster="$(output deploy_k8s cluster_name 2>/dev/null)"; then
    echo "No cluster: the new model is in the bucket, and the API loads it when it next starts."
    exit 0
fi
zone="$(output deploy_k8s cluster_location)"
gcloud container clusters get-credentials "${cluster}" --zone "${zone}" --project "${GCP_PROJECT}"
context="gke_${GCP_PROJECT}_${zone}_${cluster}"
kubectl --context "${context}" -n cheese-app rollout restart deployment/api-service
kubectl --context "${context}" -n cheese-app rollout status deployment/api-service --timeout=600s
echo "The API now answers Identify with the new model: see Model in the app's footer."
