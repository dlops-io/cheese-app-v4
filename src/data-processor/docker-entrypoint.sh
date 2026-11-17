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
    python cli.py --bucket \$ML_BUCKET
        Clean gs://\$ML_BUCKET/raw.zip into gs://\$ML_BUCKET/clean.zip
\033[0m
"

exec /bin/bash
