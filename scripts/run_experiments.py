"""Compare five RAG configurations using disposable indexes; never reset live data."""

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path

from evaluate_rag import load_cases, run_live

CONFIGS = [
    {
        "name": "article-rerank",
        "chunk_size": None,
        "overlap": 0,
        "reranker": True,
        "limit": 5,
    },
    {
        "name": "article-no-rerank",
        "chunk_size": None,
        "overlap": 0,
        "reranker": False,
        "limit": 5,
    },
    {
        "name": "250-rerank",
        "chunk_size": 250,
        "overlap": 30,
        "reranker": True,
        "limit": 5,
    },
    {
        "name": "500-rerank",
        "chunk_size": 500,
        "overlap": 50,
        "reranker": True,
        "limit": 5,
    },
    {
        "name": "article-k3",
        "chunk_size": None,
        "overlap": 0,
        "reranker": True,
        "limit": 3,
    },
]


def is_transient_provider_error(error):
    pending = [error]
    seen = set()
    while pending:
        current = pending.pop()
        if current is None or id(current) in seen:
            continue
        seen.add(id(current))
        if getattr(current, "status_code", None) in {429, 500, 502, 503, 504}:
            return True
        if type(current).__name__ in {
            "APITimeoutError",
            "APIConnectionError",
            "JudgeResponseError",
        }:
            return True
        pending.extend([current.__cause__, current.__context__])
        pending.extend(
            attempt.exception
            for attempt in getattr(current, "failed_attempts", None) or []
        )
    return False


async def run(args):
    import mlflow

    mlflow.set_tracking_uri(args.tracking_uri)
    mlflow.set_experiment("rag-ishms-configurations")
    cases = load_cases(args.dataset)
    args.reports.mkdir(parents=True, exist_ok=True)
    manifest = {
        "dataset_sha256": hashlib.sha256(args.dataset.read_bytes()).hexdigest(),
        "corpus_sha256": hashlib.sha256(args.corpus.read_bytes()).hexdigest(),
        "configurations": CONFIGS,
        "profile": {
            key: os.environ.get(key)
            for key in (
                "EMBEDDING_MODEL_ID",
                "OPENAI_BASE_URL",
                "GENERATION_MODEL_ID",
                "GENERATION_BASE_URL",
                "RAG_EVAL_JUDGE_MODEL",
                "RAG_EVAL_JUDGE_BASE_URL",
                "MAX_OUTPUT_TOKENS",
                "RAG_EVAL_FULL_METRICS",
            )
        },
    }
    manifest_path = args.reports / "manifest.json"
    if manifest_path.exists() and json.loads(manifest_path.read_text()) != manifest:
        raise ValueError("Use a new report directory for changed evaluation inputs")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    summaries = []
    for config in CONFIGS:
        with mlflow.start_run(
            run_name=config["name"] + ("-capture" if args.capture_only else "")
        ):
            mlflow.log_params(
                {
                    key: value if value is not None else "article"
                    for key, value in config.items()
                }
            )
            path = (
                args.reports
                / f"{config['name']}{'.capture' if args.capture_only else ''}.json"
            )
            scored = args.reports / f"{config['name']}.json"
            checkpoint = args.reports / f"{config['name']}.checkpoint.json"
            if scored.exists() and args.resume:
                report = json.loads(scored.read_text())
            elif path.exists() and args.resume:
                report = json.loads(path.read_text())
            else:
                for attempt in range(4):
                    try:
                        report = await run_live(
                            cases,
                            0.75,
                            args.corpus,
                            config=config,
                            checkpoint=checkpoint,
                            capture_only=args.capture_only,
                        )
                        break
                    except Exception as error:
                        if attempt == 3 or not is_transient_provider_error(error):
                            raise
                        print(
                            f"Provider temporarily unavailable ({type(error).__name__}); resuming saved scores after cooldown",
                            flush=True,
                        )
                        await asyncio.sleep(60 * (attempt + 1))
            path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
            mlflow.log_params(
                {
                    "embedding_model": report["index_metadata"]["embedding_model_id"],
                    "generation_model": report["generation_model"],
                    "prompt_version": report["prompt_version"],
                }
            )
            mlflow.log_metrics(
                {
                    key: value
                    for key, value in report["metrics"].items()
                    if type(value) in (int, float)
                }
            )
            mlflow.log_artifact(str(path))
            summaries.append(
                {
                    "config": config,
                    "passed": report["passed"],
                    "metrics": report["metrics"],
                }
            )
    (
        args.reports
        / ("capture-comparison.json" if args.capture_only else "comparison.json")
    ).write_text(json.dumps(summaries, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path("eval/golden_set.json"))
    parser.add_argument(
        "--corpus", type=Path, default=Path("eval/corpus/articles.json")
    )
    parser.add_argument("--reports", type=Path, default=Path("reports/experiments"))
    parser.add_argument("--tracking-uri", default="sqlite:///reports/mlflow.db")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--full-metrics", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--capture-only",
        action="store_true",
        help="Save real RAG answers/contexts without waiting for an external judge",
    )
    args = parser.parse_args()
    if args.env_file:
        from dotenv import load_dotenv

        load_dotenv(args.env_file, override=True)
    if args.full_metrics:
        os.environ["RAG_EVAL_FULL_METRICS"] = "1"
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
