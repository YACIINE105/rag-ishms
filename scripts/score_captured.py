"""Score frozen captured RAG answers without indexing or invoking the generator."""

import argparse
import asyncio
import hashlib
import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path
from time import monotonic

from evaluate_rag import JUDGE_RUBRIC_VERSION, evaluate, load_cases, make_judge
from run_experiments import CONFIGS, is_transient_provider_error


def cached_stage_count():
    database = Path(os.environ.get("RAG_EVAL_CACHE_DIR", ".cache/ragas")) / "cache.db"
    if not database.exists():
        return 0
    try:
        with closing(
            sqlite3.connect(
                database.resolve().as_uri() + "?mode=ro", uri=True, timeout=1
            )
        ) as cache:
            return cache.execute("SELECT COUNT(*) FROM Cache").fetchone()[0]
    except sqlite3.Error:
        return 0


async def score_with_recovery(cases, checkpoint, deadline, name):
    async def captured_answer(case):
        raise RuntimeError("Scoring requires saved answers, never new generation")

    completed = len(json.loads(checkpoint.read_text())["cases"])
    cached = cached_stage_count()
    consecutive_failures = 0
    while True:
        client, judge = make_judge()
        try:
            return await evaluate(cases, captured_answer, judge, 0.75, checkpoint)
        except Exception as error:
            current = len(json.loads(checkpoint.read_text())["cases"])
            current_cached = max(cached, cached_stage_count())
            new_stages = current_cached - cached
            if current > completed or new_stages:
                consecutive_failures = 0
            completed = max(completed, current)
            cached = current_cached
            consecutive_failures += 1
            if (
                consecutive_failures >= 4
                or monotonic() >= deadline
                or not is_transient_provider_error(error)
            ):
                raise
            print(
                f"{name}: judge unavailable ({type(error).__name__}); retained {completed} grades; cached {new_stages} additional grading stages",
                flush=True,
            )
            await asyncio.sleep(min(60 * consecutive_failures, deadline - monotonic()))
        finally:
            await client.close()


async def run(args):
    cases = load_cases(args.dataset)
    fingerprint = hashlib.sha256(
        json.dumps(cases, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    args.reports.mkdir(parents=True, exist_ok=True)
    profile = {
        "rubric_version": JUDGE_RUBRIC_VERSION,
        "model": os.environ["RAG_EVAL_JUDGE_MODEL"],
        "base_url": os.environ.get("RAG_EVAL_JUDGE_BASE_URL"),
        "extra_body": json.loads(os.environ.get("RAG_EVAL_JUDGE_EXTRA_BODY", "{}")),
        "temperature": 0,
        "full_metrics": os.environ.get("RAG_EVAL_FULL_METRICS") == "1",
        "embedding_model": os.environ.get("RAG_EVAL_EMBEDDING_MODEL"),
    }
    profile_path = args.reports / "judge-profile.json"
    if profile_path.exists():
        if json.loads(profile_path.read_text()) != profile:
            raise ValueError(
                "Use a separate report directory for a different judge rubric/profile"
            )
    elif any(
        json.loads(path.read_text()).get("cases")
        for path in args.reports.glob("*.checkpoint.json")
    ) or any((args.reports / f"{config['name']}.json").exists() for config in CONFIGS):
        raise ValueError(
            "Legacy scores require a separate report directory for the revised rubric"
        )
    else:
        profile_path.write_text(json.dumps(profile, indent=2) + "\n")
    deadline = monotonic() + args.wait_seconds
    for config in CONFIGS:
        name = config["name"]
        output = args.reports / f"{name}.json"
        if output.exists():
            existing = json.loads(output.read_text())
            if existing.get("judge_model") != os.environ["RAG_EVAL_JUDGE_MODEL"]:
                raise ValueError(
                    "Use a separate report directory for a different judge"
                )
            continue
        source = args.captures / f"{name}.capture.json"
        scored_source = args.captures / f"{name}.json"
        while not source.exists() and not scored_source.exists():
            if monotonic() >= deadline:
                raise TimeoutError("Waiting for complete captured answers")
            await asyncio.sleep(10)
        if not source.exists():
            source = scored_source
        capture = json.loads(source.read_text())
        rows = {row["id"]: row for row in capture["cases"]}
        if set(rows) != {case["id"] for case in cases}:
            raise ValueError("Captured case IDs do not match the frozen dataset")
        checkpoint = args.reports / f"{name}.checkpoint.json"
        if not checkpoint.exists():
            raw = {
                case_id: {
                    key: row[key]
                    for key in ("id", "answer", "contexts", "latency_seconds")
                }
                for case_id, row in rows.items()
            }
            checkpoint.write_text(
                json.dumps(
                    {
                        "dataset_fingerprint": fingerprint,
                        "answers": raw,
                        "cases": [],
                        "pending": None,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

        report = await score_with_recovery(cases, checkpoint, deadline, name)
        for key in (
            "index_metadata",
            "collections",
            "generation_model",
            "generation_provider",
            "config",
            "prompt_version",
            "embedding_base_url",
            "corpus_sha256",
            "git_sha",
        ):
            report[key] = capture.get(key)
        report.update(
            judge_model=os.environ["RAG_EVAL_JUDGE_MODEL"],
            judge_temperature=0,
            judge_rubric_version=JUDGE_RUBRIC_VERSION,
            capture_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            generation_reused=True,
        )
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        print(f"{name}: scoring complete", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset", type=Path, default=Path("eval/civil_code_full.json")
    )
    parser.add_argument(
        "--captures",
        type=Path,
        default=Path("eval/reports/final-project/configurations"),
    )
    parser.add_argument("--reports", type=Path, required=True)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument(
        "--wait-seconds",
        type=int,
        default=7200,
        help="Total budget for waiting on captures and transient judge recovery",
    )
    args = parser.parse_args()
    from dotenv import load_dotenv

    load_dotenv(args.env_file, override=True)
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
