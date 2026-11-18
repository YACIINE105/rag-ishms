"""Register a retrieval recipe from five complete, existing MLflow runs."""

import csv
import hashlib
import json
import re
from pathlib import Path

from check_comparison_evidence import METRICS

MODEL = "rag-ishms-retrieval-config"
ALIAS = "candidate"
SELECTED = "article-rerank"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, value):
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def register(args, configs, cases):
    import mlflow.artifacts
    from mlflow import MlflowClient
    from mlflow.exceptions import MlflowException

    if not args.tracking_uri.startswith("sqlite:///"):
        raise ValueError("Registration requires a local SQLite tracking URI")
    if not args.run_inventory or not args.review_export or not args.registry_artifacts:
        raise ValueError(
            "Registration requires --run-inventory, --review-export and --registry-artifacts"
        )
    ids = {case["id"] for case in cases}
    if len(cases) != 62 or len(ids) != 62:
        raise ValueError("Registration requires all 62 frozen cases")
    manifest = read_json(args.reports / "manifest.json")
    judge = read_json(args.reports / "judge-profile.json")
    hashes = {
        "dataset_sha256": digest(args.dataset),
        "corpus_sha256": digest(args.corpus),
    }
    if any(manifest.get(key) != value for key, value in hashes.items()):
        raise ValueError("Report manifest hashes do not match input files")
    if manifest.get("configurations") != configs:
        raise ValueError(
            "The report manifest does not identify the five expected configurations"
        )
    if (
        not judge.get("full_metrics")
        or not judge.get("model")
        or not judge.get("rubric_version")
    ):
        raise ValueError("Registration requires a complete judge profile")
    judge_params = {
        "judge_model": judge["model"],
        "judge_rubric_version": judge["rubric_version"],
    }
    inventory = read_json(args.run_inventory)
    entries = inventory["current_runs"]
    if len(entries) != len(configs) or {
        entry["params"]["name"] for entry in entries
    } != {config["name"] for config in configs}:
        raise ValueError(
            "Expected one inventory entry for each of the five configurations"
        )
    if len({entry["id"] for entry in entries}) != len(configs):
        raise ValueError("Duplicate source run")
    by_name = {entry["params"]["name"]: entry["id"] for entry in entries}
    client = MlflowClient(
        tracking_uri=args.tracking_uri, registry_uri=args.tracking_uri
    )
    rows, report_hashes = [], {}
    for config in configs:
        name = config["name"]
        run_id = by_name[name]
        if not re.fullmatch(r"[0-9a-f]{32}", run_id):
            raise ValueError(f"{name}: invalid source run ID")
        run = client.get_run(run_id)
        path = args.reports / f"{name}.json"
        report = read_json(path)
        metrics = report["metrics"]
        config_params = {
            key: str(value) if value is not None else "article"
            for key, value in config.items()
        }
        lineage = {**hashes, **judge_params, **config_params, "capture_only": "False"}
        if run.info.status != "FINISHED" or any(
            run.data.params.get(key) != value for key, value in lineage.items()
        ):
            raise ValueError(
                f"{name}: MLflow run lineage does not match the comparison"
            )
        if (
            len(report["cases"]) != 62
            or {case["id"] for case in report["cases"]} != ids
        ):
            raise ValueError(f"{name}: expected the exact 62 completed case IDs")
        if (
            report["config"] != config
            or report["corpus_sha256"] != hashes["corpus_sha256"]
            or any(report.get(key) != value for key, value in judge_params.items())
        ):
            raise ValueError(f"{name}: report profile mismatch")
        if (
            type(report["passed"]) is not bool
            or run.data.metrics.get("completed_grades") != 62
            or any(
                run.data.metrics.get(key) != metrics.get(key)
                or type(metrics.get(key)) not in (int, float)
                for key in METRICS
            )
        ):
            raise ValueError(f"{name}: incomplete or mismatched MLflow scores")
        rows.append(
            {
                "config": name,
                "run_id": run_id,
                "gate": "PASS" if report["passed"] else "FAIL",
                "cases_scored": 62,
                "cases_total": 62,
                **{key: metrics[key] for key in METRICS},
            }
        )
        report_hashes[name] = digest(path)
        if name == SELECTED:
            if not report["passed"]:
                raise ValueError("The selected article-rerank recipe did not pass")
            recipe = {
                "config": config,
                "run_id": run_id,
                "generation_model": report["generation_model"],
                "embedding_model": report["index_metadata"]["embedding_model_id"],
                "prompt_version": report["prompt_version"],
                **judge_params,
                **hashes,
                "report_sha256": report_hashes[name],
            }

    exported = args.review_export
    exported.mkdir(parents=True, exist_ok=True)
    filename = "selected-retrieval-config.json"
    selected = exported / filename
    write_json(selected, recipe)
    sha = digest(selected)
    artifact = args.registry_artifacts.resolve() / sha / filename
    artifact.parent.mkdir(parents=True, exist_ok=True)
    if not artifact.exists():
        artifact.write_bytes(selected.read_bytes())
    if digest(artifact) != sha:
        raise ValueError("Registry recipe bytes do not match their content address")
    try:
        client.get_registered_model(MODEL)
    except MlflowException as error:
        if error.error_code != "RESOURCE_DOES_NOT_EXIST":
            raise
        client.create_registered_model(MODEL)
    versions = client.search_model_versions(
        f"name = '{MODEL}' and run_id = '{recipe['run_id']}'"
    )
    version = next(
        (item for item in versions if item.tags.get("recipe_sha256") == sha), None
    )
    if version is None:
        version = client.create_model_version(
            MODEL,
            artifact.as_uri(),
            run_id=recipe["run_id"],
            tags={"recipe_sha256": sha},
        )
    uri = client.get_model_version_download_uri(MODEL, version.version)
    if digest(Path(mlflow.artifacts.download_artifacts(uri))) != sha:
        raise ValueError("Registry version does not resolve to the selected recipe")
    client.set_registered_model_alias(MODEL, ALIAS, version.version)
    if client.get_model_version_by_alias(MODEL, ALIAS).version != version.version:
        raise ValueError("Candidate alias did not resolve to the verified version")
    with (exported / "mlflow-comparison.csv").open(
        "w", encoding="utf-8", newline=""
    ) as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    write_json(
        exported / "mlflow-provenance.json",
        {
            "release": inventory["release"],
            "registered_model": MODEL,
            "alias": ALIAS,
            "version": version.version,
            "run_id": recipe["run_id"],
            "recipe_sha256": sha,
            "report_sha256": report_hashes,
            **hashes,
            **judge_params,
        },
    )
    print(f"{MODEL}@{ALIAS} -> version {version.version} (run {recipe['run_id']})")
