"""Compare five RAG configurations using disposable indexes; never reset live data."""

import argparse
import asyncio
import json
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


async def run(args):
    import mlflow

    mlflow.set_tracking_uri(args.tracking_uri)
    mlflow.set_experiment("rag-ishms-configurations")
    cases = load_cases(args.dataset)
    args.reports.mkdir(parents=True, exist_ok=True)
    summaries = []
    for config in CONFIGS:
        with mlflow.start_run(run_name=config["name"]):
            mlflow.log_params(
                {
                    key: value if value is not None else "article"
                    for key, value in config.items()
                }
            )
            report = await run_live(cases, 0.75, args.corpus, config=config)
            path = args.reports / f"{config['name']}.json"
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
    (args.reports / "comparison.json").write_text(
        json.dumps(summaries, indent=2) + "\n"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path("eval/golden_set.json"))
    parser.add_argument(
        "--corpus", type=Path, default=Path("eval/corpus/articles.json")
    )
    parser.add_argument("--reports", type=Path, default=Path("reports/experiments"))
    parser.add_argument("--tracking-uri", default="sqlite:///reports/mlflow.db")
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
