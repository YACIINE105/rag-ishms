"""Score frozen captured RAG answers without indexing or invoking the generator."""

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
from time import monotonic

from evaluate_rag import JUDGE_RUBRIC_VERSION, evaluate, load_cases, make_judge
from run_experiments import CONFIGS, is_transient_provider_error


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

        async def captured_answer(case):
            raise RuntimeError("Scoring requires saved answers, never new generation")

        for attempt in range(4):
            client, judge = make_judge()
            try:
                report = await evaluate(cases, captured_answer, judge, 0.75, checkpoint)
                break
            except Exception as error:
                if attempt == 3 or not is_transient_provider_error(error):
                    raise
                print(
                    f"{name}: judge unavailable ({type(error).__name__}); retained checkpoint",
                    flush=True,
                )
                await asyncio.sleep(60 * (attempt + 1))
            finally:
                await client.close()
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
    parser.add_argument("--wait-seconds", type=int, default=7200)
    args = parser.parse_args()
    from dotenv import load_dotenv

    load_dotenv(args.env_file, override=True)
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
