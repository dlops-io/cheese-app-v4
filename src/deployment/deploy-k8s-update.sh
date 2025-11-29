#!/bin/bash
export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python

cd deploy_images
uv run pulumi stack select dev
uv run pulumi up --stack dev -y

cd ..
cd deploy_k8s
uv run pulumi stack select dev
uv run pulumi up --stack dev -y