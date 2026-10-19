"""Serve the existing pinned models; keep downloaded weights outside the image."""

import argparse
import json
import os
import shutil
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("role", choices=("generator", "reranker"))
    args = parser.parse_args()
    if not os.environ.get("VLLM_API_KEY"):
        parser.error("Set VLLM_API_KEY before starting a model server")

    models = json.loads(Path(__file__).with_name("models.json").read_text())
    model = models[args.role]
    model_path = os.environ.get("MODEL_PATH")
    command = [
        shutil.which("vllm"),
        "serve",
        model_path or model["repo_id"],
        "--served-model-name",
        model["served_name"],
        "--host",
        "0.0.0.0",
        "--dtype",
        "half",
        "--enforce-eager",
    ]
    if not model_path:
        command.extend(["--revision", model["revision"]])

    if args.role == "generator":
        command.extend(
            [
                "--port",
                "8001",
                "--quantization",
                "bitsandbytes",
                "--max-model-len",
                os.environ.get("MAX_MODEL_LEN", "2048"),
                "--max-num-seqs",
                "1",
                "--max-num-batched-tokens",
                "512",
                "--gpu-memory-utilization",
                os.environ.get("GPU_MEMORY_UTILIZATION", "0.70"),
                "--generation-config",
                "vllm",
            ]
        )
    else:
        command.extend(
            [
                "--port",
                "8002",
                "--runner",
                "pooling",
                "--max-model-len",
                os.environ.get("MAX_MODEL_LEN", "512"),
                "--max-num-seqs",
                "16",
                "--gpu-memory-utilization",
                os.environ.get("GPU_MEMORY_UTILIZATION", "0.45"),
            ]
        )
    print(f"Starting {args.role}: {model['url']}", flush=True)
    os.execv(command[0], command)


if __name__ == "__main__":
    main()
