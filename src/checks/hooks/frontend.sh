#!/usr/bin/env bash
# prettier or eslint on the frontend files pre-commit passes, run from the frontend's folder, so its
# .prettierrc.json, .prettierignore and eslint.config.js apply as they do for `npm run check`.
#   frontend.sh prettier <files>    format them
#   frontend.sh eslint <files>      lint them
set -euo pipefail
tool="$1"
shift
cd src/frontend-react
files=("${@#src/frontend-react/}")
case "${tool}" in
    prettier) exec prettier --write --ignore-unknown "${files[@]}" ;;
    eslint) exec eslint --max-warnings 0 --no-warn-ignored "${files[@]}" ;;
    *) echo "frontend.sh: unknown tool ${tool}" >&2 && exit 2 ;;
esac
