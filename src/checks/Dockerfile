# The checks image: every linter and formatter in .pre-commit-config.yaml, so the git hook and CI need
# nothing on the machine but git and Docker. run.sh builds it and runs pre-commit in it.
# Each tool is copied from its own official image, at a pinned version.
FROM koalaman/shellcheck:v0.11.0 AS shellcheck
FROM rhysd/actionlint:1.7.12 AS actionlint
FROM zricethezav/gitleaks:v8.30.1 AS gitleaks
FROM ghcr.io/astral-sh/ruff:0.17.3 AS ruff
FROM ghcr.io/astral-sh/uv:0.13.6 AS uv

# Node for eslint and prettier, at the frontend's version
FROM node:24.22.1-bookworm-slim
ENV UV_PYTHON_INSTALL_DIR=/opt/python \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1 \
    PATH=/opt/venv/bin:/node_modules/.bin:${PATH}

# git: pre-commit asks it which files are staged
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates git \
    && rm -rf /var/lib/apt/lists/* \
    && git config --system --add safe.directory '*'

# pre-commit, and pre-commit-hooks for the file checks (trailing whitespace, YAML, private keys, ...)
COPY --from=uv /uv /usr/local/bin/uv
RUN uv venv /opt/venv --python 3.13 \
    && uv pip install --python /opt/venv pre-commit==4.7.0 pre-commit-hooks==6.0.0

COPY --from=shellcheck /bin/shellcheck /usr/local/bin/
COPY --from=actionlint /usr/local/bin/actionlint /usr/local/bin/
COPY --from=gitleaks /usr/bin/gitleaks /usr/local/bin/
COPY --from=ruff /ruff /usr/local/bin/

# eslint, prettier and eslint's plugins, the versions in the frontend's package-lock.json (run.sh
# passes the frontend folder as the `frontend` build context). They go in /node_modules: Node looks
# there last when src/frontend-react/eslint.config.js, in the mounted repo, imports its plugins.
WORKDIR /
COPY --from=frontend package.json package-lock.json ./
RUN npm ci --ignore-scripts --no-audit --no-fund

COPY hooks /checks
