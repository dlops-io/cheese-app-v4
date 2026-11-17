#!/bin/bash

echo "Container is running!!!"
echo "Architecture: $(uname -m)"
echo "Python version: $(python --version)"

# With arguments, run them as a command and stop. The ML pipeline's step works this way.
if [[ $# -gt 0 ]]; then
    exec python "$@"
fi

echo -en "\033[92m
The following command is available:
    python cli.py --bucket \$ML_BUCKET --epochs 10
        Train on gs://\$ML_BUCKET/clean.zip and save gs://\$ML_BUCKET/models/<run>/
\033[0m
"

exec /bin/bash
