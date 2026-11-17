"""Where the CNN model comes from: the ML pipeline's bucket when there is one, otherwise GitHub"""

import os
from pathlib import Path

import pytest
from google.api_core.exceptions import NotFound

from api import settings
from api.utils import llm_cnn_utils


class FakeBlob:
    def __init__(self, objects, name):
        self.objects = objects
        self.name = name

    def download_as_text(self):
        if self.name not in self.objects:
            raise NotFound("no such object")
        return self.objects[self.name].decode()

    def download_to_filename(self, filename):
        with open(filename, "wb") as f:
            f.write(self.objects[self.name])


class FakeClient:
    def __init__(self, objects):
        self.objects = objects
        self.buckets = []

    def bucket(self, name):
        self.buckets.append(name)
        return self

    def blob(self, name):
        return FakeBlob(self.objects, name)


@pytest.fixture
def bucket(monkeypatch, tmp_path):
    objects = {}
    client = FakeClient(objects)
    monkeypatch.setattr("google.cloud.storage.Client", lambda: client)
    monkeypatch.setattr(settings, "CNN_MODEL_DIR", "gs://ml-bucket/models")
    monkeypatch.setattr(llm_cnn_utils, "local_experiments_path", str(tmp_path))
    return client


def test_downloads_the_run_latest_names(bucket, tmp_path):
    bucket.objects.update(
        {
            "models/latest": b"20261116-120000\n",
            "models/20261116-120000/model.keras": b"weights",
            "models/20261116-120000/data_details.json": b"{}",
        }
    )
    run, model_path = llm_cnn_utils.fetch_from_bucket()
    assert bucket.buckets == ["ml-bucket"]
    assert run == "20261116-120000"
    assert model_path == str(tmp_path / run / "model.keras")
    assert Path(model_path).read_bytes() == b"weights"
    assert os.path.exists(tmp_path / run / "data_details.json")
    assert not os.path.exists(model_path + ".part")


def test_downloads_once(bucket):
    bucket.objects.update(
        {
            "models/latest": b"run-1",
            "models/run-1/model.keras": b"weights",
            "models/run-1/data_details.json": b"{}",
        }
    )
    llm_cnn_utils.fetch_from_bucket()
    del bucket.objects["models/run-1/model.keras"]  # a second download would now fail
    assert llm_cnn_utils.fetch_from_bucket()[0] == "run-1"


def test_nothing_trained_yet(bucket):
    assert llm_cnn_utils.fetch_from_bucket() is None


def test_a_bucket_without_a_folder(bucket, monkeypatch):
    monkeypatch.setattr(settings, "CNN_MODEL_DIR", "gs://ml-bucket")
    bucket.objects.update({"latest": b"run-2", "run-2/model.keras": b"w", "run-2/data_details.json": b"{}"})
    assert llm_cnn_utils.fetch_from_bucket()[0] == "run-2"
