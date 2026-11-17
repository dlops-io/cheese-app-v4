"""Model training: fine-tune MobileNetV2 on clean.zip, and save the model where the API finds it.

    python cli.py --bucket <bucket> --epochs 10

Writes gs://<bucket>/models/<run>/model.keras, data_details.json (the labels) and metrics.json, then
points gs://<bucket>/models/latest at <run>. The API loads models/latest when it starts, so restarting
the API's pods puts the new model in front of users.
"""

import argparse
import json
import tempfile
import time
import zipfile
from pathlib import Path

import tensorflow as tf
from google.cloud import storage

IMAGE_SIZE = 224  # the API resizes every photo to this too
SEED = 42


def load_dataset(folder: Path, labels: list[str], batch_size: int):
    """(train, validation, sizes): a fifth of the photos, picked at random, are kept for validation"""
    paths, indexes = [], []
    for index, label in enumerate(labels):
        for path in sorted((folder / label).glob("*.jpg")):
            paths.append(str(path))
            indexes.append(index)

    def load(path, index):
        image = tf.io.decode_jpeg(tf.io.read_file(path), channels=3)
        image = tf.image.resize(image, [IMAGE_SIZE, IMAGE_SIZE]) / 255  # 0 to 1, as the API sends
        return image, tf.one_hot(index, len(labels))

    photos = tf.data.Dataset.from_tensor_slices((paths, indexes))
    photos = photos.shuffle(len(paths), seed=SEED, reshuffle_each_iteration=False)
    validation_size = max(1, len(paths) // 5)
    validation = photos.take(validation_size).map(load).batch(batch_size)
    train = photos.skip(validation_size).map(load).shuffle(256, seed=SEED).batch(batch_size)
    return train, validation, (len(paths) - validation_size, validation_size)


def build_model(num_classes: int) -> tf.keras.Model:
    """MobileNetV2 trained on ImageNet, frozen, with a new last layer for our cheeses"""
    base = tf.keras.applications.MobileNetV2(
        input_shape=(IMAGE_SIZE, IMAGE_SIZE, 3), include_top=False, weights="imagenet", pooling="avg"
    )
    base.trainable = False
    inputs = tf.keras.Input((IMAGE_SIZE, IMAGE_SIZE, 3))
    x = tf.keras.layers.RandomFlip("horizontal")(inputs)  # only while training
    x = tf.keras.layers.Rescaling(2.0, offset=-1.0)(x)  # MobileNetV2 wants -1 to 1
    x = base(x, training=False)
    x = tf.keras.layers.Dropout(0.2)(x)
    outputs = tf.keras.layers.Dense(num_classes, activation="softmax")(x)
    return tf.keras.Model(inputs, outputs, name="cheese_mobilenetv2")


def main() -> None:
    parser = argparse.ArgumentParser(description="Model training")
    parser.add_argument("--bucket", required=True, help="the bucket with clean.zip; the model goes there")
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--learning-rate", type=float, default=0.001)
    parser.add_argument("--run", default=time.strftime("%Y%m%d-%H%M%S"), help="name of this model")
    args = parser.parse_args()
    tf.keras.utils.set_random_seed(SEED)
    bucket = storage.Client().bucket(args.bucket)

    with tempfile.TemporaryDirectory() as work:
        clean, out = Path(work) / "clean", Path(work) / "model"
        clean_zip = Path(work) / "clean.zip"
        bucket.blob("clean.zip").download_to_filename(clean_zip)
        with zipfile.ZipFile(clean_zip) as archive:
            archive.extractall(clean)

        # The folder names are the labels; sorted, so the same photos always give the same numbers
        labels = sorted(path.name for path in clean.iterdir() if path.is_dir())
        train, validation, (train_size, validation_size) = load_dataset(clean, labels, args.batch_size)
        print(f"Labels: {labels}; {train_size} photos to train on, {validation_size} to validate")

        model = build_model(len(labels))
        model.compile(
            optimizer=tf.keras.optimizers.Adam(args.learning_rate),
            loss="categorical_crossentropy",
            metrics=["accuracy"],
        )
        started = time.time()
        history = model.fit(
            train, validation_data=validation, epochs=args.epochs, shuffle=False, verbose=2
        )  # train shuffles itself, every epoch
        accuracy = float(history.history["val_accuracy"][-1])
        print(f"Validation accuracy {accuracy:.1%}, after {time.time() - started:.0f} s")

        # The same files and label format as the model the API downloads from GitHub
        out.mkdir()
        model.save(out / "model.keras")
        details = {
            "image_width": IMAGE_SIZE,
            "image_height": IMAGE_SIZE,
            "num_channels": 3,
            "num_classes": len(labels),
            "label2index": {label: index for index, label in enumerate(labels)},
            "index2label": {str(index): label for index, label in enumerate(labels)},
        }
        (out / "data_details.json").write_text(json.dumps(details, indent=2))
        metrics = {"val_accuracy": accuracy, "train_photos": train_size, "validation_photos": validation_size}
        (out / "metrics.json").write_text(json.dumps(metrics, indent=2))

        for path in out.iterdir():
            bucket.blob(f"models/{args.run}/{path.name}").upload_from_filename(path)
        # Last, so the API never sees a half-uploaded model
        bucket.blob("models/latest").upload_from_string(args.run)
        print(f"Saved gs://{args.bucket}/models/{args.run}/ and pointed models/latest at it")


if __name__ == "__main__":
    main()
