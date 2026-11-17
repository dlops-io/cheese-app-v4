FROM python:3.13-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/home/app/.venv \
    UV_LINK_MODE=copy \
    PATH="/home/app/.venv/bin:$PATH"

RUN pip install --no-cache-dir uv==0.13.6 && \
    useradd -ms /bin/bash app -d /home/app -u 1000 && \
    mkdir -p /app && \
    chown app:app /app

USER app
WORKDIR /app

# Dependencies first: they only reinstall when pyproject.toml or uv.lock change
COPY --chown=app:app pyproject.toml uv.lock ./
RUN uv sync --frozen

# The ImageNet weights MobileNetV2 starts from, downloaded once here instead of in every training run
RUN python -c "import tensorflow as tf; tf.keras.applications.MobileNetV2(input_shape=(224, 224, 3), include_top=False, weights='imagenet')"

COPY --chown=app:app . ./

ENTRYPOINT ["/bin/bash", "docker-entrypoint.sh"]
