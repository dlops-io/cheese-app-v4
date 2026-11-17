"""CNN mode: the trained classifier names the cheese in an image; Gemini takes the questions after.

Importing TensorFlow takes seconds, so it happens inside the functions: the API starts at once and
loads the model in the background (see service.py).
"""

import json
import os
import urllib.request
import zipfile

import numpy as np
from fastapi import HTTPException

from api import settings
from api.utils import llm_utils
from api.utils.chat_utils import ChatHistoryManager, decode_image

IMAGE_SIZE = [224, 224]

local_experiments_path = os.path.join(settings.PERSISTENT_DIR, "experiments")
cnn_model = None
data_details = None
model_version = None  # which model answers: a training run's name, or the GitHub experiment's


def fetch_from_bucket() -> tuple[str, str] | None:
    """(run, model path) for the model models/latest names, downloaded once. None before any training."""
    from google.api_core.exceptions import NotFound
    from google.cloud import storage

    bucket_name, _, prefix = settings.CNN_MODEL_DIR.removeprefix("gs://").partition("/")
    bucket = storage.Client().bucket(bucket_name)
    prefix = prefix.strip("/") + "/" if prefix.strip("/") else ""
    try:
        run = bucket.blob(f"{prefix}latest").download_as_text().strip()
    except NotFound:
        print(f"No {settings.CNN_MODEL_DIR}/latest yet: using the model on GitHub")
        return None

    folder = os.path.join(local_experiments_path, run)
    model_path = os.path.join(folder, "model.keras")
    if not os.path.exists(model_path):
        os.makedirs(folder, exist_ok=True)
        bucket.blob(f"{prefix}{run}/data_details.json").download_to_filename(
            os.path.join(folder, "data_details.json")
        )
        # Under another name first, so a download cut short is never mistaken for a model
        bucket.blob(f"{prefix}{run}/model.keras").download_to_filename(model_path + ".part")
        os.replace(model_path + ".part", model_path)
    return run, model_path


def fetch_from_github() -> tuple[str, str]:
    """(experiment, model path) for the model we trained for you, downloaded once"""
    experiment_path = os.path.join(local_experiments_path, settings.CNN_EXPERIMENT)
    model_path = os.path.join(experiment_path, settings.CNN_MODEL_FILE)
    if not os.path.exists(model_path):
        os.makedirs(local_experiments_path, exist_ok=True)
        packet_path = os.path.join(local_experiments_path, os.path.basename(settings.CNN_PACKET_URL))
        urllib.request.urlretrieve(settings.CNN_PACKET_URL, packet_path)
        with zipfile.ZipFile(packet_path) as packet:
            packet.extractall(local_experiments_path)
    return settings.CNN_EXPERIMENT, model_path


def load_cnn_model() -> None:
    import tensorflow as tf

    global cnn_model, data_details, model_version

    found = fetch_from_bucket() if settings.CNN_MODEL_DIR else None
    version, model_path = found or fetch_from_github()
    with open(os.path.join(os.path.dirname(model_path), "data_details.json")) as f:
        data_details = json.load(f)
    model_version = version
    cnn_model = tf.keras.models.load_model(model_path)  # last: /readyz waits for this
    print(f"CNN model {version} loaded")


def make_prediction(image_bytes: bytes) -> dict:
    import tensorflow as tf

    try:
        image = tf.io.decode_image(image_bytes, channels=3, expand_animations=False)
    except tf.errors.InvalidArgumentError:
        raise HTTPException(status_code=400, detail="Image processing failed: not an image")
    image = tf.image.resize(image, IMAGE_SIZE) / 255

    prediction = cnn_model.predict(tf.expand_dims(image, 0), verbose=0)
    if cnn_model.layers[-1].activation.__name__ != "softmax":
        prediction = tf.nn.softmax(prediction).numpy()

    return {
        "prediction_label": data_details["index2label"][str(int(prediction.argmax()))],
        "accuracy": round(float(np.max(prediction)) * 100, 2),
    }


def respond(chat_manager: ChatHistoryManager, past_messages: list[dict], message: dict) -> dict:
    if not message.get("image"):
        return llm_utils.respond(chat_manager, past_messages, message)
    if cnn_model is None:
        raise HTTPException(status_code=503, detail="The CNN model is still loading")
    return {"role": "cnn", "results": make_prediction(decode_image(message["image"]))}
