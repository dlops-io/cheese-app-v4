"""The ML pipeline on Vertex AI: collect photos of each cheese, clean them, train the model.

Each step runs one of our images (from deploy_images), and the steps hand their work to each other
through the ML bucket: raw.zip, then clean.zip, then models/<run>/ and models/latest.

    python ml/pipeline.py --steps collect process train --bucket <ML bucket> --service-account <email> \\
        --collector <image> --processor <image> --trainer <image>

scripts/run-ml-pipeline.sh fills all of this in from the Pulumi stacks; run that instead.
"""

import argparse
import os
from pathlib import Path

from google.cloud import aiplatform
from kfp import compiler, dsl

STEPS = ["collect", "process", "train"]


def build_pipeline(args: argparse.Namespace):
    """The pipeline, with only the steps asked for, each after the one before"""

    @dsl.container_component
    def collect():
        return dsl.ContainerSpec(
            image=args.collector,
            command=["python", "cli.py"],
            args=["--bucket", args.bucket, "--per-label", str(args.per_label)],
        )

    @dsl.container_component
    def process():
        return dsl.ContainerSpec(
            image=args.processor, command=["python", "cli.py"], args=["--bucket", args.bucket]
        )

    @dsl.container_component
    def train():
        return dsl.ContainerSpec(
            image=args.trainer,
            command=["python", "cli.py"],
            args=["--bucket", args.bucket, "--epochs", str(args.epochs)],
        )

    # name, function, CPUs and memory: training is the step that needs a bigger machine
    components = {
        "collect": ("Data Collector", collect, "1", "2G"),
        "process": ("Data Processor", process, "1", "4G"),
        "train": ("Model Training", train, "4", "16G"),
    }

    @dsl.pipeline(name="cheese-app-ml", description="Collect photos, clean them, train the model")
    def pipeline():
        previous = None
        for step in args.steps:
            name, component, cpus, memory = components[step]
            task = component().set_display_name(name).set_cpu_limit(cpus).set_memory_limit(memory)
            task.set_caching_options(False)  # every run collects and trains again
            if previous is not None:
                task.after(previous)
            previous = task

    return pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the ML pipeline on Vertex AI")
    parser.add_argument("--steps", nargs="+", choices=STEPS, default=STEPS)
    parser.add_argument("--bucket", required=True, help="the ML bucket, from deploy_base")
    parser.add_argument("--service-account", required=True, help="the steps run as this account")
    parser.add_argument("--collector", required=True, help="the data-collector image")
    parser.add_argument("--processor", required=True, help="the data-processor image")
    parser.add_argument("--trainer", required=True, help="the model-training image")
    parser.add_argument("--per-label", type=int, default=50, help="photos to collect for each cheese")
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--compile-only", action="store_true", help="write the pipeline file, run nothing")
    args = parser.parse_args()
    args.steps = [step for step in STEPS if step in args.steps]  # always in this order

    # The pipeline as a file Vertex AI runs; keep it to read what was submitted
    template = Path(".local/ml-pipeline.yaml")
    template.parent.mkdir(exist_ok=True)
    compiler.Compiler().compile(build_pipeline(args), package_path=str(template))
    print(f"Pipeline with steps {', '.join(args.steps)} written to {template}")
    if args.compile_only:
        return

    aiplatform.init(project=os.environ["GCP_PROJECT"], location=os.environ["GCP_REGION"])
    job = aiplatform.PipelineJob(
        display_name=f"cheese-app-{'-'.join(args.steps)}",
        template_path=str(template),
        pipeline_root=f"gs://{args.bucket}/pipeline-root",
        enable_caching=False,
    )
    job.submit(service_account=args.service_account)
    print("Watch it in the console: Vertex AI > Pipelines")
    job.wait()  # raises if a step fails, so the script (and a GitHub Action) fails too


if __name__ == "__main__":
    main()
